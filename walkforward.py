"""Walk-forward optimization + overfitting detection -- the rigor core / the guardrail.

This is what keeps the research lab honest. For a parameterized template:
  1. optimize()     picks the best params on an in-sample (IS) window  -- i.e. MT
                    Strategy Tester optimization, automated.
  2. walk_forward() rolls it across history: optimize on IS, score on the NEXT
                    out-of-sample (OOS) window, step, repeat. The IS->OOS Sharpe
                    decay is the overfitting signal.
  3. verdict()      turns the IS/OOS gap into ROBUST / FRAGILE / OVERFIT -- the
                    gate the LLM researcher must pass before a strategy is kept.
"""
from __future__ import annotations

from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import compute_metrics, run_backtest

# --- overfitting verdict thresholds (tune to taste -- your call) ---
MIN_OOS_SHARPE = 0.3   # below this OOS, the edge isn't real
MAX_GAP = 0.5          # (IS Sharpe - OOS Sharpe) above this = curve-fit


def _sharpe(df: pd.DataFrame, signal: pd.Series) -> float:
    return compute_metrics(run_backtest(df, signal))["Sharpe"]


def _combos(grid: dict, valid=None):
    keys = list(grid)
    for values in product(*(grid[k] for k in keys)):
        params = dict(zip(keys, values))
        if valid is None or valid(params):
            yield params


def optimize(df_is, fn, grid, valid=None, metric=_sharpe):
    """Return (best_params, best_IS_score) maximizing `metric` on the IS window."""
    best, best_score = None, -np.inf
    for params in _combos(grid, valid):
        score = metric(df_is, fn(df_is, **params))
        if np.isfinite(score) and score > best_score:
            best, best_score = params, score
    return best, best_score


def walk_forward(df, fn, grid, valid=None, is_years=4, oos_years=2, step_years=2):
    """Roll optimize->test across history. Returns a list of per-fold dicts."""
    start, end = df.index[0], df.index[-1]
    is_off = pd.DateOffset(years=is_years)
    oos_off = pd.DateOffset(years=oos_years)
    step_off = pd.DateOffset(years=step_years)

    folds, t0 = [], start
    while t0 + is_off + oos_off <= end:
        is_df = df.loc[t0:t0 + is_off]
        oos_df = df.loc[t0 + is_off:t0 + is_off + oos_off]
        if len(is_df) > 50 and len(oos_df) > 20:
            params, is_sharpe = optimize(is_df, fn, grid, valid)
            if params is not None:
                folds.append({
                    "is_start": t0.date(),
                    "oos_start": (t0 + is_off).date(),
                    "oos_end": (t0 + is_off + oos_off).date(),
                    "params": params, "is_sharpe": is_sharpe,
                    "oos_sharpe": _sharpe(oos_df, fn(oos_df, **params)),
                })
        t0 = t0 + step_off
    return folds


def verdict(folds: list) -> dict:
    """Aggregate folds into an overfitting verdict."""
    if not folds:
        return {"verdict": "NO DATA", "is_sharpe": np.nan,
                "oos_sharpe": np.nan, "gap": np.nan, "n_folds": 0}
    is_s = float(np.nanmean([f["is_sharpe"] for f in folds]))
    oos_s = float(np.nanmean([f["oos_sharpe"] for f in folds]))
    gap = is_s - oos_s
    if oos_s < 0:
        v = "OVERFIT"          # made money IS, loses it OOS
    elif oos_s < MIN_OOS_SHARPE or gap > MAX_GAP:
        v = "FRAGILE"
    else:
        v = "ROBUST"
    return {"verdict": v, "is_sharpe": is_s, "oos_sharpe": oos_s,
            "gap": gap, "n_folds": len(folds)}


def evaluate_template(data: dict, fn, grid, valid=None, **wf) -> tuple:
    """Walk-forward across a basket {ticker: df}; aggregate per-ticker + overall."""
    per_ticker, all_folds = {}, []
    for tk, df in data.items():
        folds = walk_forward(df, fn, grid, valid, **wf)
        per_ticker[tk] = verdict(folds)
        all_folds.extend(folds)
    return verdict(all_folds), per_ticker


if __name__ == "__main__":
    import strategies as st

    data_dir = Path(__file__).parent / "data"
    tickers = ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
               "JPM", "XOM", "JNJ", "WMT", "KO", "PG", "HD", "DIS"]
    data = {tk: pd.read_csv(data_dir / f"{tk}_1d.csv", index_col=0, parse_dates=True)
            for tk in tickers}

    # Detailed walk-forward for SMA crossover (optimize fast/slow each IS window).
    t = st.TEMPLATES["sma_crossover"]
    overall, per = evaluate_template(data, t["fn"], t["grid"], t.get("valid"),
                                     is_years=4, oos_years=2, step_years=2)
    print("Walk-forward: SMA crossover  (optimize fast/slow on each in-sample window)")
    print(f"{'Ticker':8}{'IS Sharpe':>11}{'OOS Sharpe':>12}{'Gap':>8}{'Folds':>7}  Verdict")
    for tk, v in per.items():
        print(f"{tk:8}{v['is_sharpe']:>11.2f}{v['oos_sharpe']:>12.2f}"
              f"{v['gap']:>8.2f}{v['n_folds']:>7}  {v['verdict']}")
    print("-" * 62)
    print(f"{'OVERALL':8}{overall['is_sharpe']:>11.2f}{overall['oos_sharpe']:>12.2f}"
          f"{overall['gap']:>8.2f}{overall['n_folds']:>7}  {overall['verdict']}")

    # Generality check: overall verdict per template in the registry.
    print("\nTemplate comparison (overall, whole basket):")
    for name, tm in st.TEMPLATES.items():
        ov, _ = evaluate_template(data, tm["fn"], tm["grid"], tm.get("valid"),
                                  is_years=4, oos_years=2, step_years=2)
        print(f"  {name:16} IS {ov['is_sharpe']:>5.2f} | OOS {ov['oos_sharpe']:>5.2f} "
              f"| gap {ov['gap']:>5.2f} -> {ov['verdict']}")
