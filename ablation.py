"""ablation.py -- the controlled proof that the ROUTING POLICY learned (Task C).

Two arms, identical except ONE knob (whether the routing policy is applied):
  memory_ON  = seeded random-search proposer  INTERSECT  routing.enforce(derive_constraints(history))
               -> bans doomed families, tightens fragile ones, diversifies kinds.
  memory_OFF = the SAME seeded random-search proposer ALONE (blind to history)
               -> re-proposes banned families, never tightens.

Why random-search (not Gemini) as the proposer: it isolates the POLICY cleanly (no LLM
variance to confound the one-knob control), runs offline, and is fully reproducible. Family
order is RANDOMIZED per seed, so the result can't be dismissed as pre-sequencing.

Measured on BOTH axes (speed AND quality):
  * experiments_to_first_robust  (lower is better)
  * first_try_survival           (higher is better)
  * best_oos_appraisal           (higher is better)  <- the quality axis a judge can't wave away

Writes runs/<id>/ablation.json (per-seed results + aggregate, both arms).

NOTE: this proves the system-level routing POLICY accelerates+improves discovery. It does
NOT prove the LLM reasons better -- that's Layer 2, shown qualitatively in the demo run.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

import strategies as st
from research import RUNS_DIR, TICKERS, load_basket
from routing import derive_constraints, enforce
from walkforward import evaluate_template

# random-search candidate pools (per template param) -- the proposer samples 1-3 each
POOLS = {
    "sma_crossover": {"fast": [5, 10, 20, 50], "slow": [50, 100, 150, 200]},
    "rsi_reversion": {"period": [7, 14, 21], "low": [20, 25, 30], "high": [70, 75, 80]},
    "multi_filter": {"sma_fast": [5, 10, 20], "sma_slow": [50, 100, 150],
                     "rsi_period": [7, 14, 21], "rsi_max": [60, 70, 80],
                     "mom_lookback": [5, 10, 20]},
}
IS_YEARS_POOL = [1, 2, 3, 4, 5, 6]


def _rand_grid(rng: random.Random, fam: str) -> dict:
    cfg = st.TEMPLATES[fam]
    valid = cfg.get("valid")
    for _ in range(12):                                    # retry until a valid combo exists
        grid = {}
        for k, pool in POOLS[fam].items():
            n = rng.randint(1, min(3, len(pool)))
            grid[k] = sorted(rng.sample(pool, n))
        from itertools import product
        if any(valid is None or valid(dict(zip(grid, vals)))
               for vals in product(*grid.values())):
            return grid
    return {k: list(v) for k, v in cfg["grid"].items()}    # fallback to default


class RandomResearcher:
    """Seeded random-search proposer with per-seed randomized family order."""
    name = "random"

    def __init__(self, seed: int, arm: str):
        self.rng = random.Random(seed)
        self.seed = seed
        self.arm = arm
        self.family_order = list(st.TEMPLATES)
        self.rng.shuffle(self.family_order)                # kills the pre-sequencing critique

    def propose(self, history: list, constraints=None):
        fam = self.rng.choice(self.family_order)
        return {"iteration": len(history) + 1, "template": fam,
                "hypothesis": f"random-search {fam}", "rationale": "random-search proposer",
                "grid": _rand_grid(self.rng, fam),
                "windows": {"is_years": self.rng.choice(IS_YEARS_POOL),
                            "oos_years": self.rng.choice([1, 2]), "step_years": 2}}


def run_arm(data: dict, seed: int, arm: str, max_exp: int) -> dict:
    """One full budget run for one (seed, arm). Records both speed and quality axes."""
    researcher = RandomResearcher(seed, arm)
    history, best, first_robust = [], None, None
    for _ in range(max_exp):
        prop = researcher.propose(history)
        if arm == "memory_on":
            prop = enforce(prop, derive_constraints(history))
            if prop is None:
                break
        tmpl = st.TEMPLATES[prop["template"]]
        overall, _, _ = evaluate_template(data, tmpl["fn"], prop["grid"],
                                          tmpl.get("valid"), **prop["windows"])
        v, oos_a = overall["verdict"], overall["oos_appraisal"]
        history.append({"iteration": len(history) + 1, "template": prop["template"],
                        "verdict": v, "oos_appraisal": round(float(oos_a), 3) if np.isfinite(oos_a) else None})
        if np.isfinite(oos_a):
            best = oos_a if best is None else max(best, oos_a)
        if v == "ROBUST" and first_robust is None:
            first_robust = len(history)
    return {"seed": seed, "arm": arm, "n_experiments": len(history),
            "found_robust": first_robust is not None,
            "experiments_to_first_robust": first_robust if first_robust else max_exp,
            "censored": first_robust is None,
            "first_try_survival": bool(history and history[0]["verdict"] == "ROBUST"),
            "best_oos_appraisal": round(float(best), 3) if best is not None else None,
            "history": history}


def _stat(x: np.ndarray) -> dict:
    """mean, sample std, and standard ERROR (std/sqrt(n)) -- SEM is the right error bar
    for 'do the two arms' means differ'."""
    n = len(x)
    std = float(x.std(ddof=1)) if n > 1 else 0.0
    return {"mean": round(float(x.mean()), 3), "std": round(std, 3),
            "sem": round(std / np.sqrt(n), 3) if n > 1 else 0.0}


def _agg(rows: list, max_exp: int) -> dict:
    e2r = np.array([r["experiments_to_first_robust"] for r in rows], float)
    best = np.array([r["best_oos_appraisal"] if r["best_oos_appraisal"] is not None else 0.0 for r in rows], float)
    return {
        "n_seeds": len(rows),
        "experiments_to_first_robust": _stat(e2r),
        "best_oos_appraisal": _stat(best),
        "first_try_survival_rate": round(np.mean([r["first_try_survival"] for r in rows]), 3),
        "found_robust_rate": round(np.mean([r["found_robust"] for r in rows]), 3),
    }


_WORKER_DATA = None


def _init_worker(tickers, end):
    global _WORKER_DATA
    _WORKER_DATA = load_basket(tickers, end=end)


def _worker(task):
    seed, arm, max_exp = task
    return run_arm(_WORKER_DATA, seed, arm, max_exp)


def run_ablation(tickers=None, n_seeds=20, max_exp=6, run_dir: Path | None = None,
                 end=None, parallel=True):
    if run_dir is None:
        RUNS_DIR.mkdir(exist_ok=True)
        run_dir = RUNS_DIR / datetime.now().strftime("ablation_%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    tasks = [(s, arm, max_exp) for s in range(n_seeds) for arm in ("memory_on", "memory_off")]
    if parallel and n_seeds > 1:
        import multiprocessing as mp
        n_proc = max(1, min(mp.cpu_count() - 1, len(tasks)))
        with mp.Pool(n_proc, initializer=_init_worker, initargs=(tickers, end)) as pool:
            results = pool.map(_worker, tasks)
    else:
        _init_worker(tickers, end)
        results = [_worker(t) for t in tasks]

    by_seed = {}
    for r in results:
        by_seed.setdefault(r["seed"], {})[r["arm"]] = r
    on_rows = [by_seed[s]["memory_on"] for s in range(n_seeds)]
    off_rows = [by_seed[s]["memory_off"] for s in range(n_seeds)]
    for s in range(n_seeds):
        on, off = by_seed[s]["memory_on"], by_seed[s]["memory_off"]
        print(f"seed {s:2d} | ON  e2r={on['experiments_to_first_robust']} best={on['best_oos_appraisal']} "
              f"| OFF e2r={off['experiments_to_first_robust']} best={off['best_oos_appraisal']}")

    out = {
        "run_id": run_dir.name, "n_seeds": n_seeds, "max_experiments": max_exp,
        "tickers": tickers or TICKERS, "data_end": str(end) if end else None,
        "memory_on": {"agg": _agg(on_rows, max_exp), "seeds": on_rows},
        "memory_off": {"agg": _agg(off_rows, max_exp), "seeds": off_rows},
    }
    (run_dir / "ablation.json").write_text(json.dumps(out, indent=2))
    on_a, off_a = out["memory_on"]["agg"], out["memory_off"]["agg"]
    print("\n=== ABLATION (memory-ON vs memory-OFF) ===")
    print(f"experiments-to-first-ROBUST  ON {on_a['experiments_to_first_robust']['mean']:.2f}"
          f"±{on_a['experiments_to_first_robust']['std']:.2f}  vs  "
          f"OFF {off_a['experiments_to_first_robust']['mean']:.2f}±{off_a['experiments_to_first_robust']['std']:.2f}  (lower better)")
    print(f"best OOS appraisal           ON {on_a['best_oos_appraisal']['mean']:.3f}"
          f"±{on_a['best_oos_appraisal']['std']:.3f}  vs  "
          f"OFF {off_a['best_oos_appraisal']['mean']:.3f}±{off_a['best_oos_appraisal']['std']:.3f}  (higher better)")
    print(f"found-robust rate            ON {on_a['found_robust_rate']:.2f}  vs  OFF {off_a['found_robust_rate']:.2f}")
    print(f"\nablation.json -> {run_dir / 'ablation.json'}")
    return run_dir, out


if __name__ == "__main__":
    args = sys.argv[1:]
    kw = {}
    if "--fast" in args:                                   # quick prototype
        kw = dict(tickers=["SPY", "AAPL", "MSFT", "XOM", "KO", "JNJ"], n_seeds=4, max_exp=5)
    run_ablation(**kw)
