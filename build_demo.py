"""build_demo.py -- assemble the COMMITTED replay run so the demo survives venue wifi.

Produces runs/demo_committed/{journal.jsonl, summary.json, ablation.json, holdout.json}:
  * journal  -- the caused-routing demo arc (stub, TRAIN names, pre-cutoff)
  * ablation -- memory-ON vs memory-OFF, K seeds (the proof the policy learned)
  * holdout  -- the dual-axis sealed exam (out-of-time + out-of-asset)

All search artifacts read ONLY the TRAIN names strictly before HOLDOUT_CUTOFF, so the
holdout slices stay uncontaminated. Run once, commit the directory, demo offline.

    python build_demo.py            # full committed run (K=20)
    python build_demo.py --quick    # fast smoke build (K=6)
"""
from __future__ import annotations

import sys

from ablation import run_ablation
from holdout import run_holdout
from research import (HOLDOUT_CUTOFF, RUNS_DIR, TRAIN_TICKERS, StubResearcher,
                      load_basket, run_research)

RUN_ID = "demo_committed"


def build(n_seeds: int = 20, max_exp: int = 6):
    run_dir = RUNS_DIR / RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    data = load_basket(TRAIN_TICKERS, end=HOLDOUT_CUTOFF)

    print(f"[1/3] demo arc  (TRAIN={len(TRAIN_TICKERS)} names, < {HOLDOUT_CUTOFF}) ...")
    run_research(data, StubResearcher(), run_dir=run_dir)

    print(f"\n[2/3] ablation  (K={n_seeds} seeds, max_exp={max_exp}) ...")
    run_ablation(tickers=TRAIN_TICKERS, n_seeds=n_seeds, max_exp=max_exp,
                 run_dir=run_dir, end=HOLDOUT_CUTOFF)

    print("\n[3/3] holdout  (out-of-time + out-of-asset) ...")
    run_holdout(run_dir=run_dir)

    print(f"\nCOMMITTED RUN -> {run_dir}")
    print("Files:", sorted(p.name for p in run_dir.iterdir()))


if __name__ == "__main__":
    if "--quick" in sys.argv:
        build(n_seeds=6, max_exp=6)
    else:
        build()
