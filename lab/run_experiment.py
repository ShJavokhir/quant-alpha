"""Orchestrate the full experiment and write runs/<id>/run.json (frontend contract).

Arms:
  adaptive   = LLM proposer + memory  (the agent)              [full detail]
  memory_off = LLM proposer, memory ablated                    [control]
  random     = random-grammar search, same budget             [control]
  frozen     = fixed seed roster, reweighted each gen          [baseline]

Then: sealed 2024 holdout (final fleets scored once), cost sweep, 1-day delay test.
"""
import argparse
import datetime as dt
import json
import time

import numpy as np
import pandas as pd

from . import config, seeds as seedmod
from .engine import dsl, backtest
from .agent import fleet
from .agent.evolve import Config, Arm, build_timeline, _slim
from .agent.memory import Embedder, open_memory
from .agent.proposer import Proposer
from .agent.random_search import RandomProposer
from .agent.researcher import Researcher


def _book_on(alpha_docs, panel, cfg, decision_date, eval_start, eval_end,
             cost_bps=None, delay=0):
    """Score a fleet's combined book: weights/orient from the trailing train window
    ending at decision_date (decision-time info only), evaluated on [eval_start, eval_end]."""
    cost_bps = cfg.cost_bps if cost_bps is None else cost_bps
    dates = panel["close"].index
    p = int(np.searchsorted(dates.values, np.datetime64(pd.Timestamp(decision_date))))
    warm = dates[max(0, p - cfg.train_days - cfg.warmup_days)]
    train_start = dates[max(0, p - cfg.train_days)]
    sub = fleet.slice_panel(panel, warm, pd.Timestamp(eval_end))
    sig_by, trm_by, score = {}, {}, {}
    for d in alpha_docs:
        try:
            sig = dsl.evaluate(d["formula"], sub)
            tr = backtest.evaluate_signal(sig, sub, train_start, dates[p], cost_bps=cost_bps)
        except dsl.DSLError:
            continue
        if delay:
            sig = sig.shift(delay)
        sig_by[d["name"]] = sig
        trm_by[d["name"]] = tr
        # robust track-record score (mirrors Arm._robust_score) using stored history
        hist = [h["ic_ir"] for h in d.get("history", [])]
        score[d["name"]] = (0.4 * tr["ic_ir"] + 0.6 * (sum(hist) / len(hist))) if hist else tr["ic_ir"] * 0.85
    names = sorted(sig_by, key=lambda n: score[n], reverse=True)[: cfg.book_top]
    if not names:
        return _slim({})
    weights = {n: max(score[n], 0.0) / (0.3 + trm_by[n]["turnover"]) for n in names}
    if not any(weights.values()):
        weights = {n: 1.0 for n in names}
    orient = {n: (1.0 if trm_by[n]["ic"] >= 0 else -1.0) for n in names}
    combined = fleet.combine_signals(sig_by, orient, weights, smooth=cfg.book_smooth)
    return _slim(backtest.evaluate_signal(combined, sub, eval_start, eval_end, cost_bps=cost_bps))


def arm_curve(records):
    out = []
    for r in records:
        out.append({"g": r["g"], "date": r["date"], "fleet_size": r["fleet_size"],
                    "hit_rate": round(r["hit_rate"], 3),
                    "n_proposed": r["n_proposed"], "n_accepted": r["n_accepted"],
                    "median_proposal_test_ir": round(r["median_proposal_test_ir"], 4),
                    "mean_proposal_test_ir": round(r["mean_proposal_test_ir"], 4),
                    "book_train": r["book_train"], "book_test": r["book_test"]})
    return out


def flat_proposals(*arm_records):
    rows = []
    for records in arm_records:
        for r in records:
            for q in r["proposals"]:
                rows.append({k: q.get(k) for k in
                             ("g", "date", "arm", "memory_on", "name", "family", "formula",
                              "verdict", "reject_reason", "train_ir", "test_ir", "turnover",
                              "source", "source_url", "source_title", "steps", "interaction_id")})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="tiny smoke config")
    ap.add_argument("--arms", default="adaptive,memory_off,random,frozen")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--universe", type=int, default=None)
    ap.add_argument("--no-mongo", action="store_true")
    args = ap.parse_args()

    cfg = Config()
    if args.quick:
        cfg.universe_n = 250; cfg.train_days = 378; cfg.test_days = 84
        cfg.step_days = 168; cfg.seeds_initial = 20; cfg.n_propose = 5
        cfg.target_fleet = 20; cfg.max_fleet = 26; cfg.min_fleet = 14; cfg.web_k = 2
        cfg.book_top = 12
    if args.universe:
        cfg.universe_n = args.universe

    run_id = args.run_id or f"run_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    t0 = time.time()
    print(f"[run] {run_id} cfg.universe={cfg.universe_n} arms={args.arms}", flush=True)

    full = config.load_panel(cfg.panel_which)
    universe = fleet.liquid_universe(full, cfg.universe_n)
    panel = fleet.restrict(full, universe)
    dates, positions, holdout_pos = build_timeline(panel, cfg)
    print(f"[run] panel {panel['close'].shape}; {len(positions)} generations; "
          f"first={pd.Timestamp(dates[positions[0]]).date()} "
          f"last={pd.Timestamp(dates[positions[-1]]).date()}; "
          f"holdout from {cfg.holdout_start}", flush=True)

    store, backend = open_memory(run_id, prefer_mongo=not args.no_mongo)
    print(f"[run] memory backend = {backend}", flush=True)
    embedder = Embedder()
    researcher = Researcher()

    want = set(args.arms.split(","))
    arm_records = {}

    def run_arm(name, mode, memory_on, proposer, researcher_obj, seed=0):
        print(f"[arm] {name} starting ({mode}, memory={memory_on}) ...", flush=True)
        ta = time.time()
        arm = Arm(name, cfg, panel, store, embedder, proposer, researcher_obj,
                  mode=mode, memory_on=memory_on, rng_seed=seed)
        arm.seed(seedmod.SEEDS)
        arm.run(dates, positions)
        print(f"[arm] {name} done in {time.time()-ta:.0f}s "
              f"(final fleet {len(arm.live)})", flush=True)
        return arm

    arms = {}
    if "adaptive" in want:
        arms["adaptive"] = run_arm("adaptive", "llm", True, Proposer(), researcher)
    if "memory_off" in want:
        arms["memory_off"] = run_arm("memory_off", "llm", False, Proposer(), None)
    if "random" in want:
        arms["random"] = run_arm("random", "random", False, RandomProposer(seed=7), None)
    if "frozen" in want:
        arms["frozen"] = run_arm("frozen", "frozen", False, Proposer(), None)

    for name, arm in arms.items():
        arm_records[name] = arm.records

    # ---- sealed holdout (evaluate final fleets ONCE on 2024) ----
    holdout = {}
    if holdout_pos < len(dates) - cfg.test_days:
        h_decision = dates[holdout_pos]
        h_start = dates[holdout_pos + 1]
        h_end = dates[-1]
        holdout["window"] = {"start": pd.Timestamp(h_start).strftime("%Y-%m-%d"),
                             "end": pd.Timestamp(h_end).strftime("%Y-%m-%d")}
        seed_docs = [{"name": s["name"], "formula": s["formula"], "family": s["family"]}
                     for s in seedmod.SEEDS[:cfg.seeds_initial]]
        if "adaptive" in arms:
            adf = list(arms["adaptive"].live.values())
            holdout["adaptive"] = _book_on(adf, panel, cfg, h_decision, h_start, h_end)
            holdout["adaptive_delay1"] = _book_on(adf, panel, cfg, h_decision, h_start, h_end, delay=1)
            holdout["cost_sweep"] = []
            for bps in (1, 5, 10, 25, 50):
                a = _book_on(adf, panel, cfg, h_decision, h_start, h_end, cost_bps=bps)
                f = _book_on(seed_docs, panel, cfg, h_decision, h_start, h_end, cost_bps=bps)
                holdout["cost_sweep"].append({"bps": bps, "adaptive": a["sharpe_net"],
                                              "frozen": f["sharpe_net"]})
        holdout["frozen"] = _book_on(seed_docs, panel, cfg, h_decision, h_start, h_end)
        print(f"[holdout] window {holdout['window']} done", flush=True)

    # ---- assemble run.json ----
    all_props = flat_proposals(*[arm_records[a] for a in
                                 ("adaptive", "memory_off", "random") if a in arm_records])
    n_trials = len(all_props)
    n_accepted = sum(1 for q in all_props if q["verdict"] == "accept")
    out = {
        "meta": {
            "run_id": run_id, "created": dt.datetime.now().isoformat(timespec="seconds"),
            "panel": cfg.panel_which, "universe_n": cfg.universe_n,
            "n_stocks": panel["close"].shape[1], "n_generations": len(positions),
            "timeline": {"first": pd.Timestamp(dates[positions[0]]).strftime("%Y-%m-%d"),
                         "last": pd.Timestamp(dates[positions[-1]]).strftime("%Y-%m-%d"),
                         "holdout_start": cfg.holdout_start},
            "config": {k: getattr(cfg, k) for k in
                       ("train_days", "test_days", "step_days", "seeds_initial",
                        "target_fleet", "n_propose", "ir_kill", "ir_admit",
                        "corr_kill", "dedup_emb", "cost_bps")},
            "memory_backend": backend, "wall_seconds": round(time.time() - t0, 1),
        },
        "generations": arm_records.get("adaptive", []),
        "arms": {name: arm_curve(recs) for name, recs in arm_records.items()},
        "proposals": all_props,
        "holdout": holdout,
        "summary": {
            "n_trials": n_trials, "n_accepted": n_accepted,
            "accept_rate": round(n_accepted / n_trials, 3) if n_trials else 0,
            "final_fleet_size": len(arms["adaptive"].live) if "adaptive" in arms else 0,
        },
    }
    store.flush()
    embedder.flush()
    rundir = config.RUNS / run_id
    rundir.mkdir(parents=True, exist_ok=True)
    (rundir / "run.json").write_text(json.dumps(out, default=str))
    print(f"[run] wrote {rundir/'run.json'} ({(rundir/'run.json').stat().st_size/1e3:.0f} KB) "
          f"| trials={n_trials} accepted={n_accepted} | wall={time.time()-t0:.0f}s", flush=True)
    return out


if __name__ == "__main__":
    main()
