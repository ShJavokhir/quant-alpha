"""Multi-seed robustness ablation for the memory claim.

The committed run is N=1: "memory found 68 keepers vs 31 vs 21" is a single
stochastic draw (proposer temperature 0.95). This harness repeats the three
research arms (adaptive / memory_off / random) across K INDEPENDENT seeds and
reports the memory advantage as mean +/- std with a paired sign test, so the
headline stops being one lucky run.

Design notes (kept honest):
  * Independence: the LLM stochasticity is pure Gemini temperature sampling
    (Arm.rng_seed is unused on the LLM path), so re-running an arm is an
    independent sample. Arm-runs are mutually independent -> run them in a
    thread pool (Gemini calls are network-bound).
  * Clean memory ablation: BOTH llm arms run with researcher=None, so the only
    difference between adaptive and memory_off is the memory-conditioned prompt
    (removes the web-researcher as a confound). Faster, and a tighter control.
  * Fast config: smaller universe + capped generations so it fits a ~10-min
    budget. This measures the SAME effect, not the same absolute numbers as the
    full demo run (which a slide should still cite for the headline).
"""
import argparse
import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from . import config, seeds as seedmod
from .agent import fleet
from .agent.evolve import Config, Arm
from .agent.memory import Embedder, alpha_text
from .agent.proposer import Proposer
from .agent.random_search import RandomProposer


# ---------------- resilient embedder (never crashes a long unattended run) ----------------
class ResilientEmbedder(Embedder):
    """Voyage with retry; deterministic hash-vector fallback on total failure.
    Per-thread instance, in-memory only (no shared-file write races)."""

    def flush(self):  # never write the shared cache file from worker threads
        pass

    def _hash_vec(self, text):
        h = hashlib.sha256(text.encode()).digest()
        rng = np.random.default_rng(int.from_bytes(h[:8], "little"))
        v = rng.standard_normal(config.EMBED_DIM).astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-12)

    def embed(self, texts, input_type="document"):
        if isinstance(texts, str):
            texts = [texts]
        out = [None] * len(texts)
        missing, miss_idx = [], []
        for i, t in enumerate(texts):
            k = self._key(t)
            if k in self._cache:
                out[i] = self._cache[k]
            else:
                missing.append(t); miss_idx.append(i)
        if missing:
            vecs = None
            for attempt in range(3):
                try:
                    vecs = self._voyage().embed(missing, model=self.model,
                                                input_type=input_type).embeddings
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(1.5 * (attempt + 1))
            for j, i in enumerate(miss_idx):
                v = vecs[j] if vecs is not None else self._hash_vec(texts[i])
                out[i] = v
                self._cache[self._key(texts[i])] = v
        return np.asarray(out, dtype=np.float32)


class NullStore:
    """No-op store: the Arm only uses it for logging; dedup uses Arm.tried_emb."""
    backend = "null"

    def upsert_alpha(self, doc): pass
    def get_alpha(self, name): return None
    def all_alphas(self, status=None): return []
    def search_similar(self, *a, **k): return []
    def log_experiment(self, doc): pass
    def log_event(self, doc): pass
    def flush(self): pass


def fast_cfg():
    c = Config()
    c.universe_n = 300
    c.train_days = 378
    c.test_days = 84
    c.step_days = 252
    c.warmup_days = 280
    c.seeds_initial = 20
    c.target_fleet = 20
    c.max_fleet = 26
    c.min_fleet = 14
    c.n_propose = 8
    c.web_every = 999          # no web researcher in this controlled ablation
    c.churn_per_gen = 2
    c.book_top = 12
    return c


def build_positions(panel, cfg, ngen):
    dates = panel["close"].index
    n = len(dates)
    holdout_pos = int(np.searchsorted(dates.values, np.datetime64(cfg.holdout_start)))
    first = cfg.warmup_days + cfg.train_days
    positions = list(range(first, min(holdout_pos, n) - cfg.test_days, cfg.step_days))
    return dates, positions[:ngen]


def run_one(kind, seed, cfg, panel, dates, positions):
    """One independent arm-run. Returns summary metrics."""
    t0 = time.time()
    embedder = ResilientEmbedder()
    store = NullStore()
    if kind == "random":
        proposer = RandomProposer(seed=1000 + seed)
        mode, mem = "random", False
    else:
        proposer = Proposer()
        mode, mem = "llm", (kind == "adaptive")
    arm = Arm(kind, cfg, panel, store, embedder, proposer, researcher=None,
              mode=mode, memory_on=mem, rng_seed=seed)
    arm.seed(seedmod.SEEDS)
    for g, p in enumerate(positions):
        arm.step(g, dates, p)
    recs = arm.records
    n_prop = sum(r["n_proposed"] for r in recs)
    n_acc = sum(r["n_accepted"] for r in recs)
    cum, c = [], 0
    for r in recs:
        c += r["n_accepted"]; cum.append(c)
    appr = float(np.mean([r["book_test"]["appraisal"] for r in recs])) if recs else 0.0
    return {"kind": kind, "seed": seed, "keepers": n_acc, "proposed": n_prop,
            "hit_rate": (n_acc / n_prop) if n_prop else 0.0,
            "cum_curve": cum, "book_appraisal": round(appr, 4),
            "final_fleet": len(arm.live), "secs": round(time.time() - t0, 1)}


def sign_test_one_sided(wins, n):
    """P(>= wins successes | p=0.5), the chance memory beats control >= wins/n by luck."""
    return sum(math.comb(n, i) for i in range(wins, n + 1)) / (2 ** n)


def paired_t(deltas):
    n = len(deltas)
    if n < 2:
        return None
    m = sum(deltas) / n
    sd = (sum((d - m) ** 2 for d in deltas) / (n - 1)) ** 0.5
    t = m / (sd / math.sqrt(n)) if sd > 0 else float("inf")
    return {"mean_delta": round(m, 2), "sd": round(sd, 2), "t": round(t, 2), "df": n - 1}


def aggregate(results):
    by = {"adaptive": {}, "memory_off": {}, "random": {}}
    for r in results:
        by[r["kind"]][r["seed"]] = r
    out = {"per_arm": {}, "paired": {}}
    for kind, d in by.items():
        ks = [d[s]["keepers"] for s in sorted(d)]
        hr = [d[s]["hit_rate"] for s in sorted(d)]
        ap = [d[s]["book_appraisal"] for s in sorted(d)]
        out["per_arm"][kind] = {
            "keepers": ks, "keepers_mean": round(np.mean(ks), 2), "keepers_sd": round(np.std(ks, ddof=1), 2) if len(ks) > 1 else 0.0,
            "hit_rate_mean": round(float(np.mean(hr)), 3), "hit_rate_sd": round(float(np.std(hr, ddof=1)), 3) if len(hr) > 1 else 0.0,
            "appraisal_mean": round(float(np.mean(ap)), 3),
        }
    seeds = sorted(by["adaptive"])
    for ctrl in ("memory_off", "random"):
        deltas, wins = [], 0
        for s in seeds:
            if s in by["adaptive"] and s in by[ctrl]:
                dlt = by["adaptive"][s]["keepers"] - by[ctrl][s]["keepers"]
                deltas.append(dlt); wins += (dlt > 0)
        out["paired"][f"adaptive_vs_{ctrl}"] = {
            "n": len(deltas), "adaptive_wins": wins,
            "sign_test_p_one_sided": round(sign_test_one_sided(wins, len(deltas)), 4) if deltas else None,
            "paired_t": paired_t(deltas), "deltas": deltas,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--ngen", type=int, default=8)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--arms", default="adaptive,memory_off,random")
    ap.add_argument("--calibrate", action="store_true", help="run ONE adaptive arm, print timing, exit")
    ap.add_argument("--out", default="runs/robustness/result.json")
    args = ap.parse_args()

    cfg = fast_cfg()
    t0 = time.time()
    full = config.load_panel(cfg.panel_which)
    universe = fleet.liquid_universe(full, cfg.universe_n)
    panel = fleet.restrict(full, universe)
    dates, positions = build_positions(panel, cfg, args.ngen)
    print(f"[robust] panel {panel['close'].shape}; {len(positions)} gens "
          f"{positions[0]}..{positions[-1]}; load+restrict {time.time()-t0:.0f}s", flush=True)

    # warm the on-disk embed cache for the shared seed texts (one Voyage call, confirms key)
    seed_texts = [alpha_text(s["formula"], s.get("family", ""), s.get("rationale", ""))
                  for s in seedmod.SEEDS[: cfg.seeds_initial]]
    Embedder().embed(seed_texts)
    print(f"[robust] seed embeddings warmed ({len(seed_texts)})", flush=True)

    if args.calibrate:
        r = run_one("adaptive", 0, cfg, panel, dates, positions)
        print(f"[calibrate] one adaptive arm: {r['secs']}s  keepers={r['keepers']} "
              f"hit={r['hit_rate']:.2f} fleet={r['final_fleet']}", flush=True)
        est = r["secs"] * (args.seeds * 2) / args.workers + r["secs"]
        print(f"[calibrate] rough wall for {args.seeds} seeds x ~2 llm arms @ {args.workers} workers "
              f"~ {est:.0f}s (+ random arms). Decide go/no-go from this.", flush=True)
        return

    arms = set(args.arms.split(","))
    jobs = []
    for s in range(args.seeds):
        for kind in ("adaptive", "memory_off", "random"):
            if kind in arms:
                jobs.append((kind, s))
    print(f"[robust] {len(jobs)} arm-runs ({args.seeds} seeds) @ {args.workers} workers", flush=True)

    results, done = [], 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one, k, s, cfg, panel, dates, positions): (k, s) for k, s in jobs}
        for fut in as_completed(futs):
            k, s = futs[fut]
            try:
                r = fut.result()
                results.append(r)
                done += 1
                print(f"[robust] ({done}/{len(jobs)}) {k} seed{s}: keepers={r['keepers']} "
                      f"hit={r['hit_rate']:.2f} appr={r['book_appraisal']:.2f} ({r['secs']}s)", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[robust] FAILED {k} seed{s}: {type(e).__name__}: {e}", flush=True)

    agg = aggregate(results)
    out = {"config": {"universe_n": cfg.universe_n, "ngen": len(positions),
                      "n_propose": cfg.n_propose, "seeds": args.seeds,
                      "model": config.GEMINI_MODEL, "wall_seconds": round(time.time() - t0, 1)},
           "results": sorted(results, key=lambda r: (r["kind"], r["seed"])),
           "aggregate": agg}
    outp = config.ROOT / args.out if hasattr(config, "ROOT") else None
    from pathlib import Path
    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(out, indent=2, default=str))

    print("\n================ ROBUSTNESS SUMMARY ================", flush=True)
    for kind in ("adaptive", "memory_off", "random"):
        a = agg["per_arm"].get(kind)
        if a:
            print(f"  {kind:11s} keepers {a['keepers']}  mean {a['keepers_mean']} +/- {a['keepers_sd']:<4}"
                  f"  hit {a['hit_rate_mean']:.3f}+/-{a['hit_rate_sd']:.3f}  appr {a['appraisal_mean']}", flush=True)
    for k, v in agg["paired"].items():
        print(f"  {k}: adaptive wins {v['adaptive_wins']}/{v['n']}  "
              f"sign-test p(1-sided)={v['sign_test_p_one_sided']}  "
              f"paired-t={v['paired_t']}  deltas={v['deltas']}", flush=True)
    print(f"  wall {out['config']['wall_seconds']}s -> wrote {op}", flush=True)


if __name__ == "__main__":
    main()
