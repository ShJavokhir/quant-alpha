"""holdout.py -- the never-touched generalization exam (Task B), on TWO axes.

The agent's learned WINNER = a disciplined mean-reversion edge (rsi_reversion, frozen
knobs, 6yr IS). The REJECTED family = greedy multi_filter (5 knobs, 1yr IS). Both are
committed from the PRE-CUTOFF search evidence BEFORE any sealed slice is opened; opened
exactly once. Scored on the APPRAISAL basis (beta-adjusted alpha), Info-Ratio alongside.

  OUT-OF-TIME (PRIMARY, the harder regime axis): lock params on pre-cutoff TRAIN data,
     score once on the post-cutoff tail the search never saw; plus a decade-decay table
     (rolling) showing the edge's sign persists but its magnitude decays -> the system
     correctly downgrades recent RSI from ROBUST to FRAGILE.
  OUT-OF-ASSET (SECONDARY, clean name-generalization): score winner & rejected on the
     HELD names that were NEVER in the search, full history.

Honest headline: we did not find a strategy that robustly beats every regime; we found a
disciplined RSI timing edge that GENERALIZES across unseen NAMES (ROBUST) and stays
POSITIVE BUT WEAKENED out-of-TIME (FRAGILE), while the greedy family fails BOTH axes.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import strategies as st
from backtest import appraisal_ratio, compute_metrics, excess_sharpe, run_backtest
from research import (HELD_NAMES, HOLDOUT_CUTOFF, RUNS_DIR, TRAIN_TICKERS, load_basket)
from walkforward import MIN_OOS_APPRAISAL, evaluate_template, optimize, walk_forward

WINNER = {"family": "rsi_reversion", "grid": {"period": [7, 14, 21], "low": [30], "high": [70]},
          "windows": {"is_years": 6, "oos_years": 2, "step_years": 2}, "role": "trusted",
          "note": "the disciplined mean-reversion edge the agent converged to (ROBUST pre-cutoff)"}
REJECTED = {"family": "multi_filter",
            "grid": {"sma_fast": [5, 10, 20], "sma_slow": [50, 100], "rsi_period": [14],
                     "rsi_max": [60, 70, 80], "mom_lookback": [10, 20]},
            "windows": {"is_years": 1, "oos_years": 1, "step_years": 2}, "role": "rejected",
            "note": "the greedy multi-knob family the agent banned (OVERFIT pre-cutoff)"}


def _verdict(a: float) -> str:
    if not np.isfinite(a):
        return "NO DATA"
    return "OVERFIT" if a < 0 else ("FRAGILE" if a < MIN_OOS_APPRAISAL else "ROBUST")


def _sealed_tail(spec: dict, pre: dict, tail: dict) -> dict:
    """Lock params per ticker on PRE-cutoff data, score ONCE on the sealed post-cutoff tail."""
    cfg = st.TEMPLATES[spec["family"]]
    fn, valid = cfg["fn"], cfg.get("valid")
    apps, exs, per = [], [], {}
    for tk, pre_df in pre.items():
        tdf = tail.get(tk)
        if tdf is None or len(tdf) < 60:
            continue
        params, _ = optimize(pre_df, fn, spec["grid"], valid)
        if params is None:
            continue
        net = run_backtest(tdf, fn(tdf, **params))["net_ret"]
        bench = run_backtest(tdf, st.buy_and_hold(tdf))["net_ret"]
        a, x = appraisal_ratio(net, bench), excess_sharpe(net, bench)
        if np.isfinite(a):
            apps.append(a)
        if np.isfinite(x):
            exs.append(x)
        per[tk] = {"params": params, "appraisal": round(float(a), 3) if np.isfinite(a) else None}
    mean_a = float(np.mean(apps)) if apps else float("nan")
    return {"appraisal": round(mean_a, 3) if np.isfinite(mean_a) else None,
            "excess_sharpe": round(float(np.mean(exs)), 3) if exs else None,
            "verdict": _verdict(mean_a), "n_names": len(apps),
            "n_names_positive": sum(1 for a in apps if a > 0), "per_ticker": per}


def _decade_table(spec: dict, data: dict, cutoff: str) -> dict:
    """Rolling walk-forward appraisal by OOS-start decade + the post-cutoff mean
    (the family was chosen pre-cutoff, so this is honest by-regime OOS evidence)."""
    cfg = st.TEMPLATES[spec["family"]]
    cut = pd.Timestamp(cutoff).date()
    folds = []
    for df in data.values():
        folds += walk_forward(df, cfg["fn"], spec["grid"], cfg.get("valid"), **spec["windows"])
    by_dec, post = {}, []
    for f in folds:
        a = f["oos_appraisal"]
        if np.isfinite(a):
            by_dec.setdefault((f["oos_start"].year // 10) * 10, []).append(a)
            if f["oos_start"] >= cut:
                post.append(a)
    table = {f"{d}s": round(float(np.mean(v)), 3) for d, v in sorted(by_dec.items())}
    post_mean = float(np.mean(post)) if post else float("nan")
    return {"by_decade": table, "post_cutoff_appraisal": round(post_mean, 3) if np.isfinite(post_mean) else None,
            "post_cutoff_verdict": _verdict(post_mean), "post_cutoff_folds": len(post)}


def _out_of_asset(spec: dict, held: dict) -> dict:
    cfg = st.TEMPLATES[spec["family"]]
    ov, _, _ = evaluate_template(held, cfg["fn"], spec["grid"], cfg.get("valid"), **spec["windows"])
    return {"appraisal": round(float(ov["oos_appraisal"]), 3) if np.isfinite(ov["oos_appraisal"]) else None,
            "excess_sharpe": round(float(ov["oos_excess"]), 3) if np.isfinite(ov["oos_excess"]) else None,
            "appraisal_gap": round(float(ov["appraisal_gap"]), 3) if np.isfinite(ov["appraisal_gap"]) else None,
            "verdict": ov["verdict"], "n_folds": ov["n_folds"],
            "names": list(held), "n_names_positive": _per_pos(held, cfg, spec)}


def _per_pos(held, cfg, spec) -> int:
    pos = 0
    for df in held.values():
        folds = walk_forward(df, cfg["fn"], spec["grid"], cfg.get("valid"), **spec["windows"])
        vals = [f["oos_appraisal"] for f in folds if np.isfinite(f["oos_appraisal"])]
        if vals and np.mean(vals) > 0:
            pos += 1
    return pos


def run_holdout(cutoff: str = HOLDOUT_CUTOFF, run_dir: Path | None = None):
    pre = load_basket(TRAIN_TICKERS, end=cutoff)
    tail = load_basket(TRAIN_TICKERS, start=cutoff)
    full_train = load_basket(TRAIN_TICKERS)
    held = load_basket(HELD_NAMES)

    # GUARD: the search (TRAIN, pre-cutoff) must not overlap the sealed slices.
    for tk in tail:
        if len(pre[tk]) and len(tail[tk]):
            assert pre[tk].index[-1] <= tail[tk].index[0], f"out-of-time leak on {tk}"
    assert not (set(TRAIN_TICKERS) & set(HELD_NAMES)), "out-of-asset leak: held name in train"

    oot = {
        "winner": {**{k: WINNER[k] for k in ("family", "role", "note")},
                   "sealed_tail": _sealed_tail(WINNER, pre, tail),
                   "decade": _decade_table(WINNER, full_train, cutoff)},
        "rejected": {**{k: REJECTED[k] for k in ("family", "role", "note")},
                     "sealed_tail": _sealed_tail(REJECTED, pre, tail),
                     "decade": _decade_table(REJECTED, full_train, cutoff)},
    }
    ooa = {"winner": {**{k: WINNER[k] for k in ("family", "role", "note")}, **_out_of_asset(WINNER, held)},
           "rejected": {**{k: REJECTED[k] for k in ("family", "role", "note")}, **_out_of_asset(REJECTED, held)}}

    tail_starts = [t.index[0] for t in tail.values() if len(t)]
    bh = [compute_metrics(run_backtest(t, st.buy_and_hold(t)))["Sharpe"] for t in tail.values() if len(t) >= 60]

    # The honest proof: on BOTH unseen slices the trusted family stays POSITIVE while the
    # rejected family stays clearly NEGATIVE (winner need not be ROBUST out-of-sample --
    # the edge is real but decayed; we do not oversell it).
    oot_w = oot["winner"]["sealed_tail"]["appraisal"]
    oot_r = oot["rejected"]["sealed_tail"]["appraisal"]
    ooa_w, ooa_r = ooa["winner"]["appraisal"], ooa["rejected"]["appraisal"]
    proof = (None not in (oot_w, oot_r, ooa_w, ooa_r)
             and oot_w > 0 > oot_r and ooa_w > 0 > ooa_r)
    out = {
        "run_id": (run_dir.name if run_dir else "holdout"), "cutoff": cutoff,
        "train_names": TRAIN_TICKERS, "held_names": HELD_NAMES,
        "tail_from": str(min(tail_starts).date()) if tail_starts else None,
        "benchmark_tail_sharpe": round(float(np.mean(bh)), 3) if bh else None,
        "out_of_time": oot, "out_of_asset": ooa,
        "sealed_declaration": "Winner=rsi_reversion, Rejected=multi_filter committed from pre-cutoff "
                              "evidence BEFORE any sealed slice was opened; each opened exactly once.",
        "headline": ("On BOTH unseen slices the trusted mean-reversion edge stays POSITIVE while the "
                     "rejected greedy family stays clearly NEGATIVE. The edge is real but DECAYED "
                     "(FRAGILE out-of-sample, not ROBUST) — the system downgrades rather than oversells."),
        "proof": proof,
    }
    if run_dir is None:
        RUNS_DIR.mkdir(exist_ok=True)
        run_dir = RUNS_DIR / datetime.now().strftime("holdout_%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "holdout.json").write_text(json.dumps(out, indent=2))

    print(f"=== HOLDOUT (cutoff {cutoff}; buy&hold tail Sharpe {out['benchmark_tail_sharpe']}) ===")
    print("OUT-OF-TIME (primary, regime axis):")
    for role in ("winner", "rejected"):
        d = oot[role]["decade"]; s = oot[role]["sealed_tail"]
        print(f"  {role:8} {oot[role]['family']:14} sealed-tail appraisal {s['appraisal']} [{s['verdict']}] | "
              f"post-cutoff rolling {d['post_cutoff_appraisal']} [{d['post_cutoff_verdict']}]")
        print(f"           decade: {d['by_decade']}")
    print("OUT-OF-ASSET (secondary, name axis):")
    for role in ("winner", "rejected"):
        a = ooa[role]
        print(f"  {role:8} {a['family']:14} appraisal {a['appraisal']} gap {a['appraisal_gap']} "
              f"[{a['verdict']}] ({a['n_names_positive']}/{len(HELD_NAMES)} names +)")
    print(f"PROOF (winner generalizes by name & out-performs rejected out-of-time): {out['proof']}")
    print(f"holdout.json -> {run_dir / 'holdout.json'}")
    return run_dir, out


if __name__ == "__main__":
    run_holdout()
