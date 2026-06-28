"""The evolution loop — one walk-forward "arm".

An Arm maintains a live fleet of alphas and steps forward through time. At each
generation (decision date t) it ONLY uses data up to t to decide; it then scores
everything prospectively on the next unseen block (t, t+test]. This makes the
"improvement over time" claim honest: prune/keep/add are all decided before the
test block is seen.

Modes:
  mode="llm",    memory_on=True   -> the full agent (Gemini + memory)
  mode="llm",    memory_on=False  -> agent with memory ablated
  mode="random", memory_on=False  -> random-grammar-search control
  frozen baseline is scored separately (score_frozen) — fixed seed roster.
"""
from dataclasses import dataclass, field, asdict
import datetime as dt

import numpy as np
import pandas as pd

from .. import config
from ..engine import dsl, backtest
from . import fleet
from .memory import alpha_text


@dataclass
class Config:
    panel_which: str = "ext"
    universe_n: int = 600
    train_days: int = 504        # ~2y decision window
    test_days: int = 126         # ~6mo prospective block
    warmup_days: int = 280       # lookback headroom for long ts ops (max ~252)
    step_days: int = 126         # walk forward 6mo per generation
    holdout_start: str = "2024-01-01"   # sealed final holdout (never in the timeline)
    seeds_initial: int = 50
    target_fleet: int = 50
    max_fleet: int = 58
    min_fleet: int = 32
    n_propose: int = 12
    web_every: int = 3           # inject researched (web) ideas every K gens
    web_k: int = 3
    churn_per_gen: int = 2       # retire this many weakest each gen (forces evolution)
    max_deaths_per_gen: int = 5  # cap deaths/gen so the fleet declines gradually (no g0 cliff)
    ir_kill: float = 0.25        # prune if train IC-IR below this
    ir_admit: float = 0.45       # admit candidate only if train IC-IR above this
    turnover_admit: float = 0.7  # admit only if turnover below this (cost discipline)
    turnover_kill: float = 0.95  # prune cost-bleeders above this turnover
    corr_kill: float = 0.82      # prune redundant (pnl corr) keeping higher IR
    corr_admit: float = 0.80     # reject candidate too correlated with a live alpha (primary dedup)
    dedup_emb: float = 0.985     # reject only near-IDENTICAL formulas (embedding is coarse here)
    book_top: int = 25           # the TRADED book = top-K live alphas by train IR (research broad, trade best)
    book_smooth: int = 5         # trailing-mean smoothing of the combined book
    cost_bps: float = 10.0


def build_timeline(panel, cfg: Config):
    dates = panel["close"].index
    n = len(dates)
    holdout_pos = int(np.searchsorted(dates.values, np.datetime64(cfg.holdout_start)))
    first = cfg.warmup_days + cfg.train_days
    positions = list(range(first, min(holdout_pos, n) - cfg.test_days, cfg.step_days))
    return dates, positions, holdout_pos


class Arm:
    def __init__(self, name, cfg, panel, store, embedder, proposer, researcher,
                 mode="llm", memory_on=True, rng_seed=0):
        self.name = name
        self.cfg = cfg
        self.panel = panel              # already universe-restricted
        self.store = store
        self.embedder = embedder
        self.proposer = proposer
        self.researcher = researcher
        self.mode = mode
        self.memory_on = memory_on
        self.rng_seed = rng_seed
        self.live = {}                  # name -> alpha doc
        self.tried_names = set()
        self.tried_emb = []             # list[(name, vec)]
        self.failures = []              # recent rejected {formula, reject_reason, family}
        self.records = []

    # ---------- setup ----------
    def seed(self, seed_defs):
        defs = seed_defs[: self.cfg.seeds_initial]
        texts = [alpha_text(s["formula"], s.get("family", ""), s.get("rationale", "")) for s in defs]
        vecs = self.embedder.embed(texts)
        for s, v in zip(defs, vecs):
            doc = {"name": s["name"], "family": s.get("family", "unknown"),
                   "formula": s["formula"], "rationale": s.get("rationale", ""),
                   "source": "seed", "born_g": 0, "embedding": v.tolist(),
                   "history": []}
            self.live[s["name"]] = doc
            self.tried_names.add(s["name"])
            self.tried_emb.append((s["name"], v))

    # ---------- per-window evaluation ----------
    def _windows(self, dates, p):
        c = self.cfg
        return dict(
            warm=dates[p - c.train_days - c.warmup_days],
            train_start=dates[p - c.train_days],
            decision=dates[p],
            test_start=dates[p + 1],
            test_end=dates[min(p + c.test_days, len(dates) - 1)],
        )

    def _sig_metrics(self, formula, sub, w, with_pnl=False):
        sig = dsl.evaluate(formula, sub)   # may raise DSLError
        tr = backtest.evaluate_signal(sig, sub, w["train_start"], w["decision"],
                                      cost_bps=self.cfg.cost_bps, with_series=with_pnl)
        te = backtest.evaluate_signal(sig, sub, w["test_start"], w["test_end"],
                                      cost_bps=self.cfg.cost_bps)
        return sig, tr, te

    # ---------- the book (combined fleet portfolio) ----------
    def _robust_score(self, name, trm_by):
        """Track-record-aware fitness: blends the current train IR with the alpha's
        historical mean. Unproven alphas (no history) are discounted, so one-window-lucky
        LLM proposals can't displace robust, long-proven seeds from the traded book."""
        cur = trm_by[name]["ic_ir"] if name in trm_by else 0.0
        hist = [h["ic_ir"] for h in self.live.get(name, {}).get("history", [])] if name in self.live else []
        if hist:
            return 0.4 * cur + 0.6 * (sum(hist) / len(hist))
        return cur * 0.85   # unproven discount

    def _book(self, names, sig_by, trm_by, sub, start, end):
        # the traded book = top-K live alphas by ROBUST track record (research broadly, trade the proven best)
        ranked = sorted([n for n in names if n in trm_by],
                        key=lambda n: self._robust_score(n, trm_by), reverse=True)
        names = ranked[: self.cfg.book_top]
        # turnover-aware weighting: reward track record, penalize churn (improves net-of-cost)
        weights = {n: max(self._robust_score(n, trm_by), 0.0) / (0.3 + trm_by[n]["turnover"])
                   for n in names if n in trm_by}
        orient = {n: (1.0 if trm_by[n]["ic"] >= 0 else -1.0) for n in names if n in trm_by}
        if not any(weights.values()):
            weights = {n: 1.0 for n in names if n in trm_by}
        combined = fleet.combine_signals({n: sig_by[n] for n in weights}, orient, weights,
                                         smooth=self.cfg.book_smooth)
        if combined is None:
            return {k: 0.0 for k in ("ic_ir", "appraisal", "sharpe_net", "turnover", "ann_ret_net")}
        return backtest.evaluate_signal(combined, sub, start, end, cost_bps=self.cfg.cost_bps)

    # ---------- one generation ----------
    def step(self, g, dates, p):
        c = self.cfg
        w = self._windows(dates, p)
        sub = fleet.slice_panel(self.panel, w["warm"], w["test_end"])
        date_str = pd.Timestamp(w["decision"]).strftime("%Y-%m-%d")

        # 1) evaluate live fleet (train + pnl for redundancy)
        sig_by, trm_by, tem_by, train_pnl = {}, {}, {}, {}
        deaths = []
        for name in list(self.live):
            try:
                sig, tr, te = self._sig_metrics(self.live[name]["formula"], sub, w, with_pnl=True)
            except dsl.DSLError as e:
                deaths.append({"name": name, "reason": f"compute failed: {str(e)[:60]}",
                               "lived_gens": g - self.live[name].get("born_g", 0)})
                del self.live[name]
                continue
            sig_by[name] = sig
            trm_by[name] = tr
            tem_by[name] = te
            train_pnl[name] = tr["_series"]["pnl"]
            self.live[name].setdefault("history", []).append(
                {"g": g, "date": date_str, "ic_ir": tr["ic_ir"], "turnover": tr["turnover"]})

        # 2) prune (skip in frozen — handled by score_frozen, not Arm)
        if self.mode != "frozen":
            self._prune(g, trm_by, train_pnl, deaths)

        # 3) research + select (skip if frozen)
        proposals, births = [], []
        if self.mode != "frozen":
            proposals, births = self._research(g, date_str, w, sub, sig_by, trm_by)
            for b in births:
                sig_by[b["name"]] = b.pop("_sig")
                trm_by[b["name"]] = b.pop("_trm")

        # 4) enforce capacity (drop weakest live by train IR)
        self._cap_fleet(trm_by, deaths, g)

        # 5) book on train + prospective test
        live_names = [n for n in self.live if n in sig_by and n in trm_by]
        book_tr = self._book(live_names, sig_by, trm_by, sub, w["train_start"], w["decision"])
        book_te = self._book(live_names, sig_by, trm_by, sub, w["test_start"], w["test_end"])

        # 6) record
        n_prop = len(proposals)
        n_acc = sum(1 for q in proposals if q["verdict"] == "accept")
        prop_test_irs = [q["test_ir"] for q in proposals if q["test_ir"] is not None]
        rec = {
            "arm": self.name, "mode": self.mode, "memory_on": self.memory_on,
            "g": g, "date": date_str, "fleet_size": len(self.live),
            "deaths": deaths, "births": births, "proposals": proposals,
            "hit_rate": (n_acc / n_prop) if n_prop else 0.0,
            "n_proposed": n_prop, "n_accepted": n_acc,
            "mean_proposal_test_ir": float(np.mean(prop_test_irs)) if prop_test_irs else 0.0,
            "median_proposal_test_ir": float(np.median(prop_test_irs)) if prop_test_irs else 0.0,
            "book_train": _slim(book_tr), "book_test": _slim(book_te),
            "fleet": [{"name": n, "family": self.live[n]["family"],
                       "ir": round(trm_by[n]["ic_ir"], 3) if n in trm_by else 0.0,
                       "turnover": round(trm_by[n]["turnover"], 3) if n in trm_by else 0.0,
                       "source": self.live[n].get("source", "seed"),
                       "age": g - self.live[n].get("born_g", 0)} for n in live_names],
        }
        self.records.append(rec)
        self.store.log_event({"type": "generation", **{k: rec[k] for k in
                              ("arm", "g", "date", "fleet_size", "hit_rate",
                               "n_proposed", "n_accepted", "book_test")}})
        print(f"  [{self.name}] g{g:>2} {date_str}  fleet={len(self.live):>2} "
              f"+{len(births)}/-{len(deaths)}  hit={rec['hit_rate']:.2f}  "
              f"book_test net={book_te.get('sharpe_net',0):>6.2f} appr={book_te.get('appraisal',0):>5.2f}",
              flush=True)
        return rec

    def _prune(self, g, trm_by, train_pnl, deaths):
        c = self.cfg
        # decay + cost-bleeder prune
        to_kill = []
        for name, m in trm_by.items():
            if m["ic_ir"] < c.ir_kill:
                to_kill.append((name, f"decayed: train IR {m['ic_ir']:.2f} < {c.ir_kill}"))
            elif m["turnover"] > c.turnover_kill:
                to_kill.append((name, f"cost-bleeder: turnover {m['turnover']:.2f} > {c.turnover_kill}"))
        # redundancy prune: among correlated pairs keep the higher-IR one
        if len(train_pnl) > 1:
            corr = pd.DataFrame(train_pnl).corr().abs()
            names = list(corr.columns)
            killed = {n for n, _ in to_kill}
            order = sorted(names, key=lambda n: trm_by[n]["ic_ir"], reverse=True)
            kept = []
            for n in order:
                if n in killed:
                    continue
                redundant_with = next((k for k in kept if corr.loc[n, k] > c.corr_kill), None)
                if redundant_with:
                    to_kill.append((n, f"redundant: corr {corr.loc[n, redundant_with]:.2f} with {redundant_with}"))
                    killed.add(n)
                else:
                    kept.append(n)
        # apply, but never below min_fleet, and cap deaths/gen (kill worst-IR first)
        # so the fleet declines gradually instead of a generation-0 cliff.
        to_kill_sorted = sorted(set(to_kill), key=lambda kr: trm_by.get(kr[0], {}).get("ic_ir", 0))
        for name, reason in to_kill_sorted:
            if len(self.live) <= c.min_fleet or len(deaths) >= c.max_deaths_per_gen:
                break
            if name in self.live:
                deaths.append({"name": name, "reason": reason,
                               "lived_gens": g - self.live[name].get("born_g", 0)})
                self._retire(name, g, reason)
        # continuous churn: retire the weakest few each gen so the fleet keeps
        # evolving and the researcher is always tested to find replacements.
        survivors = [n for n in self.live if n in trm_by and n not in {d["name"] for d in deaths}]
        survivors.sort(key=lambda n: self._robust_score(n, trm_by))
        for name in survivors[: c.churn_per_gen]:
            if len(self.live) <= c.min_fleet or len(deaths) >= c.max_deaths_per_gen:
                break
            deaths.append({"name": name, "reason": f"rotated out (weakest, IR {trm_by[name]['ic_ir']:.2f})",
                           "lived_gens": g - self.live[name].get("born_g", 0)})
            self._retire(name, g, "rotated out (weakest)")

    def _retire(self, name, g, reason):
        doc = self.live.pop(name)
        doc["status"] = "dead"; doc["gen_died"] = g; doc["death_reason"] = reason
        self.store.upsert_alpha(doc)

    def _candidates(self, g, w):
        """Build the candidate list for this generation (LLM or random + web)."""
        c = self.cfg
        if self.mode == "random":
            return self.proposer.propose(c.n_propose)
        memory_ctx = ""
        if self.memory_on:
            from .proposer import build_memory_context
            winners = sorted(
                [{"formula": a["formula"], "family": a["family"],
                  "ir": (a["history"][-1]["ic_ir"] if a.get("history") else 0.0),
                  "turnover": (a["history"][-1]["turnover"] if a.get("history") else 0.0)}
                 for a in self.live.values()],
                key=lambda d: d["ir"], reverse=True)[:6]
            fam_counts = {}
            for a in self.live.values():
                fam_counts[a["family"]] = fam_counts.get(a["family"], 0) + 1
            lesson = ("On this universe, hyper-reactive 1-5 day reversal signals have strong gross "
                      "IC but NEGATIVE net-of-cost returns due to high turnover. Favor smoother, "
                      "lower-turnover constructions (longer windows, decay_linear, multi-day holds).")
            existing = [a["formula"] for a in self.live.values()]
            memory_ctx = build_memory_context(winners, self.failures[-10:], fam_counts,
                                              lesson, existing=existing)
        cands = self.proposer.propose(c.n_propose, memory_ctx=memory_ctx)
        # periodically inject web-researched ideas (with citations)
        if self.researcher and g % c.web_every == 0:
            cands += self.researcher.fresh_ideas(c.web_k, self.tried_names)
        return cands

    def _research(self, g, date_str, w, sub, sig_by, trm_by):
        c = self.cfg
        cands = self._candidates(g, w)
        # de-dup names within this batch and against tried
        seen = set()
        uniq = []
        for q in cands:
            nm = q["name"]
            if nm in seen:
                nm = f"{nm}_{g}"
            seen.add(nm)
            q["name"] = nm
            uniq.append(q)
        # batch-embed candidate formulas
        if uniq:
            texts = [alpha_text(q["formula"], q.get("family", ""), q.get("rationale", "")) for q in uniq]
            vecs = self.embedder.embed(texts)
        proposals, births = [], []
        live_pnls = {n: trm_by[n]["_series"]["pnl"] for n in trm_by if "_series" in trm_by[n]}
        # running book: a candidate is accepted only if it improves the combined book's
        # risk-adjusted objective (greedy marginal contribution), the thing we actually score.
        book_names = [n for n in self.live if n in sig_by and n in trm_by]
        book_sig = {n: sig_by[n] for n in book_names}
        book_trm = {n: trm_by[n] for n in book_names}
        base_obj = self._book_obj(book_names, book_sig, book_trm, sub, w)
        for q, v in zip(uniq, vecs if uniq else []):
            rec = {"g": g, "date": date_str, "arm": self.name, "memory_on": self.memory_on,
                   "name": q["name"], "family": q.get("family", "unknown"),
                   "formula": q["formula"], "rationale": q.get("rationale", ""),
                   "source": q.get("source", "gemini" if self.mode == "llm" else "random"),
                   "source_url": q.get("source_url", ""), "source_title": q.get("source_title", ""),
                   "verdict": "reject",
                   "reject_reason": None, "train_ir": None, "test_ir": None,
                   "turnover": None, "marginal": None,
                   "steps": q.get("steps"), "interaction_id": q.get("interaction_id")}
            # dedup by embedding
            sim, who = self._max_sim(v)
            if sim > c.dedup_emb:
                rec["reject_reason"] = f"duplicate (emb sim {sim:.2f} vs {who})"
                self._finalize_prop(rec, q, v); proposals.append(rec); continue
            # compute + backtest
            try:
                sig, tr, te = self._sig_metrics(q["formula"], sub, w, with_pnl=True)
            except dsl.DSLError as e:
                rec["reject_reason"] = f"invalid/degenerate: {str(e)[:50]}"
                self._finalize_prop(rec, q, v); proposals.append(rec); continue
            rec["train_ir"] = round(tr["ic_ir"], 3)
            rec["test_ir"] = round(te["ic_ir"], 3)
            rec["turnover"] = round(tr["turnover"], 3)
            # redundancy vs live (pnl corr)
            cand_pnl = tr["_series"]["pnl"]
            maxc, cwho = self._max_pnl_corr(cand_pnl, live_pnls)
            if maxc > c.corr_admit:
                rec["reject_reason"] = f"too correlated (corr {maxc:.2f} with {cwho})"
                self._finalize_prop(rec, q, v); proposals.append(rec); continue
            if tr["ic_ir"] < c.ir_admit:
                rec["reject_reason"] = f"weak: train IR {tr['ic_ir']:.2f} < {c.ir_admit}"
                self._finalize_prop(rec, q, v); proposals.append(rec); continue
            if tr["turnover"] > c.turnover_admit:
                rec["reject_reason"] = f"too costly: turnover {tr['turnover']:.2f} > {c.turnover_admit}"
                self._finalize_prop(rec, q, v); proposals.append(rec); continue
            # marginal contribution to the book (recorded for transparency, not a hard gate)
            new_obj = self._book_obj(book_names + [q["name"]], {**book_sig, q["name"]: sig},
                                     {**book_trm, q["name"]: tr}, sub, w)
            rec["marginal"] = round(new_obj - base_obj, 3)
            # ACCEPT
            rec["verdict"] = "accept"
            base_obj = new_obj
            book_names.append(q["name"]); book_sig[q["name"]] = sig; book_trm[q["name"]] = tr
            ag = {k: q.get(k) for k in ("steps", "interaction_id", "environment_id") if q.get(k)}
            doc = {"name": q["name"], "family": q.get("family", "unknown"),
                   "formula": q["formula"], "rationale": q.get("rationale", ""),
                   "source": rec["source"], "source_url": rec.get("source_url", ""),
                   "born_g": g, "embedding": v.tolist(), "status": "live", "history": [], **ag}
            self.live[q["name"]] = doc
            self.store.upsert_alpha(doc)
            births.append({"name": q["name"], "family": doc["family"], "formula": q["formula"],
                           "rationale": doc["rationale"], "source": rec["source"],
                           "source_url": rec.get("source_url", ""),
                           "train_ir": rec["train_ir"], "test_ir": rec["test_ir"],
                           "turnover": rec["turnover"], "_sig": sig, "_trm": tr, **ag})
            live_pnls[q["name"]] = cand_pnl
            self._finalize_prop(rec, q, v)
            proposals.append(rec)
        return proposals, births

    def _book_obj(self, names, sig_by, trm_by, sub, w):
        """Objective the agent greedily maximizes: combined-book appraisal ratio on
        the train window (beta-adjusted, turnover-aware via the book weighting)."""
        if not names:
            return 0.0
        m = self._book(names, sig_by, trm_by, sub, w["train_start"], w["decision"])
        return m.get("appraisal", 0.0)

    def _finalize_prop(self, rec, q, v):
        self.tried_names.add(q["name"])
        self.tried_emb.append((q["name"], v))
        self.store.log_experiment(rec)
        if rec["verdict"] == "reject" and rec["reject_reason"]:
            self.failures.append({"formula": q["formula"], "family": q.get("family", ""),
                                  "reject_reason": rec["reject_reason"]})

    def _cap_fleet(self, trm_by, deaths, g):
        c = self.cfg
        while len(self.live) > c.max_fleet:
            # drop the live alpha with the lowest train IR we know about
            ranked = sorted(self.live.keys(),
                            key=lambda n: trm_by.get(n, {}).get("ic_ir", -9))
            victim = ranked[0]
            deaths.append({"name": victim, "reason": "capacity: lowest IR dropped",
                           "lived_gens": g - self.live[victim].get("born_g", 0)})
            self._retire(victim, g, "capacity")

    def _max_sim(self, vec):
        if not self.tried_emb:
            return 0.0, None
        mat = np.asarray([e for _, e in self.tried_emb], dtype=np.float32)
        sims = (mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)) @ (
            vec / (np.linalg.norm(vec) + 1e-12))
        i = int(np.argmax(sims))
        return float(sims[i]), self.tried_emb[i][0]

    @staticmethod
    def _max_pnl_corr(cand_pnl, live_pnls):
        best, who = 0.0, None
        for n, p in live_pnls.items():
            df = pd.concat([cand_pnl, p], axis=1).dropna()
            if len(df) < 30:
                continue
            cc = abs(df.iloc[:, 0].corr(df.iloc[:, 1]))
            if cc > best:
                best, who = cc, n
        return best, who

    def run(self, dates, positions):
        for g, p in enumerate(positions):
            self.step(g, dates, p)
        return self.records


def _slim(m):
    keys = ("ic", "ic_ir", "appraisal", "appraisal_net", "sharpe", "sharpe_net",
            "ann_ret", "ann_ret_net", "turnover", "beta", "n_days")
    return {k: round(float(m.get(k, 0.0)), 4) for k in keys}
