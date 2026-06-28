"""Walk-forward optimization + overfitting detection -- the rigor core / the guardrail.

This is what keeps the research lab honest. For a parameterized template:
  1. optimize()     picks the best params on an in-sample (IS) window -- i.e. MT
                    Strategy Tester optimization, automated.
  2. walk_forward() rolls it across history: optimize on IS, score on the NEXT
                    out-of-sample (OOS) window, step, repeat. The IS->OOS decay is
                    the overfitting signal.
  3. verdict()      turns the IS/OOS gap into ROBUST / FRAGILE / OVERFIT -- the gate
                    the LLM researcher must pass before a strategy is kept.

SCORING BASIS (the #1 credibility axis): on a survivor-biased, upward-drifting
large-cap basket, ABSOLUTE Sharpe just books market beta as skill. So:
  * the optimizer objective AND the verdict gate run on the APPRAISAL RATIO
    (Jensen alpha / residual vol vs buy&hold) -- genuine timing alpha after beta.
  * EXCESS Sharpe (Information Ratio vs buy&hold) is carried for DISPLAY and shown
    FIRST -- the honest "no technical family beats passive indexing here" sanity check.
  * absolute IS/OOS Sharpe + the benchmark's own Sharpe are carried DISPLAY-ONLY
    (edge-vs-beta side by side).
"""
from __future__ import annotations

from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import (ANN, appraisal_ratio, compute_metrics, excess_sharpe,
                      run_backtest)
from strategies import buy_and_hold

# --- overfitting verdict thresholds (on the APPRAISAL RATIO) ---
MIN_OOS_APPRAISAL = 0.2   # below this OOS alpha, the edge isn't worth trusting
MAX_APPRAISAL_GAP = 0.5   # (IS appraisal - OOS appraisal) above this = curve-fit


def _bench_ret(df: pd.DataFrame) -> pd.Series:
    """Investable buy&hold net return run through the SAME engine (symmetric costs)."""
    return run_backtest(df, buy_and_hold(df))["net_ret"]


def _appraisal(df: pd.DataFrame, signal: pd.Series, bench: pd.Series | None = None) -> float:
    if bench is None:
        bench = _bench_ret(df)
    return appraisal_ratio(run_backtest(df, signal)["net_ret"], bench)


def _metric_bundle(df: pd.DataFrame, signal: pd.Series, bench: pd.Series | None = None) -> dict:
    """All metrics for one (window, params): the appraisal gate + IR + absolute display."""
    if bench is None:
        bench = _bench_ret(df)
    net = run_backtest(df, signal)["net_ret"]
    return {
        "appraisal": appraisal_ratio(net, bench),
        "excess": excess_sharpe(net, bench),
        "sharpe": compute_metrics(run_backtest(df, signal))["Sharpe"],
        "bench_sharpe": compute_metrics(run_backtest(df, buy_and_hold(df)))["Sharpe"],
    }


def _combos(grid: dict, valid=None):
    keys = list(grid)
    for values in product(*(grid[k] for k in keys)):
        params = dict(zip(keys, values))
        if valid is None or valid(params):
            yield params


def optimize(df_is, fn, grid, valid=None, bench=None):
    """Return (best_params, best_IS_appraisal) maximizing appraisal on the IS window.
    The benchmark is the SAME for every combo on this window -> compute it once."""
    if bench is None:
        bench = _bench_ret(df_is)
    best, best_score = None, -np.inf
    for params in _combos(grid, valid):
        score = appraisal_ratio(run_backtest(df_is, fn(df_is, **params))["net_ret"], bench)
        if np.isfinite(score) and score > best_score:
            best, best_score = params, score
    return best, best_score


def walk_forward(df, fn, grid, valid=None, is_years=4, oos_years=2, step_years=2):
    """Roll optimize->test across history. Returns a list of per-fold dicts carrying
    the appraisal gate + IR + absolute metrics on both IS and OOS windows."""
    start, end = df.index[0], df.index[-1]
    is_off = pd.DateOffset(years=is_years)
    oos_off = pd.DateOffset(years=oos_years)
    step_off = pd.DateOffset(years=step_years)

    folds, t0 = [], start
    while t0 + is_off + oos_off <= end:
        is_df = df.loc[t0:t0 + is_off]
        oos_df = df.loc[t0 + is_off:t0 + is_off + oos_off]
        if len(is_df) > 50 and len(oos_df) > 20:
            is_bench = _bench_ret(is_df)
            params, _ = optimize(is_df, fn, grid, valid, bench=is_bench)
            if params is not None:
                sig = fn(is_df, **params)
                is_m = _metric_bundle(is_df, sig, bench=is_bench)
                oos_m = _metric_bundle(oos_df, fn(oos_df, **params))
                folds.append({
                    "is_start": t0.date(),
                    "oos_start": (t0 + is_off).date(),
                    "oos_end": (t0 + is_off + oos_off).date(),
                    "params": params,
                    "is_appraisal": is_m["appraisal"], "oos_appraisal": oos_m["appraisal"],
                    "is_excess": is_m["excess"], "oos_excess": oos_m["excess"],
                    "is_sharpe": is_m["sharpe"], "oos_sharpe": oos_m["sharpe"],
                    "benchmark_oos_sharpe": oos_m["bench_sharpe"],
                })
        t0 = t0 + step_off
    return folds


def _mean(folds, key):
    vals = [f[key] for f in folds if np.isfinite(f.get(key, np.nan))]
    return float(np.mean(vals)) if vals else np.nan


def verdict(folds: list) -> dict:
    """Aggregate folds into an overfitting verdict on the APPRAISAL RATIO."""
    base = {"verdict": "NO DATA", "n_folds": 0,
            "is_appraisal": np.nan, "oos_appraisal": np.nan, "appraisal_gap": np.nan,
            "is_excess": np.nan, "oos_excess": np.nan, "excess_gap": np.nan,
            "is_sharpe": np.nan, "oos_sharpe": np.nan, "gap": np.nan,
            "benchmark_oos_sharpe": np.nan}
    if not folds:
        return base

    is_a, oos_a = _mean(folds, "is_appraisal"), _mean(folds, "oos_appraisal")
    is_x, oos_x = _mean(folds, "is_excess"), _mean(folds, "oos_excess")
    is_s, oos_s = _mean(folds, "is_sharpe"), _mean(folds, "oos_sharpe")
    bench_s = _mean(folds, "benchmark_oos_sharpe")
    a_gap = is_a - oos_a

    if oos_a < 0:
        v = "OVERFIT"                                   # IS alpha evaporates / inverts OOS
    elif oos_a < MIN_OOS_APPRAISAL or a_gap > MAX_APPRAISAL_GAP:
        v = "FRAGILE"
    else:
        v = "ROBUST"                                    # "beta-adjusted ROBUST"

    return {"verdict": v, "n_folds": len(folds),
            "is_appraisal": is_a, "oos_appraisal": oos_a, "appraisal_gap": a_gap,
            "is_excess": is_x, "oos_excess": oos_x, "excess_gap": is_x - oos_x,
            "is_sharpe": is_s, "oos_sharpe": oos_s, "gap": is_s - oos_s,
            "benchmark_oos_sharpe": bench_s}


def evaluate_template(data: dict, fn, grid, valid=None, **wf) -> tuple:
    """Walk-forward across a basket {ticker: df}; aggregate per-ticker + overall.
    Returns (overall_verdict, per_ticker, all_folds_with_ticker)."""
    per_ticker, all_folds = {}, []
    for tk, df in data.items():
        folds = walk_forward(df, fn, grid, valid, **wf)
        per_ticker[tk] = verdict(folds)
        for f in folds:
            all_folds.append({**f, "ticker": tk})
    return verdict(all_folds), per_ticker, all_folds


if __name__ == "__main__":
    import strategies as st

    data_dir = Path(__file__).parent / "data"
    tickers = ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
               "JPM", "XOM", "JNJ", "WMT", "KO", "PG", "HD", "DIS"]
    data = {tk: pd.read_csv(data_dir / f"{tk}_1d.csv", index_col=0, parse_dates=True)
            for tk in tickers}

    t = st.TEMPLATES["sma_crossover"]
    overall, per, _ = evaluate_template(data, t["fn"], t["grid"], t.get("valid"),
                                        is_years=4, oos_years=2, step_years=2)
    print("Walk-forward: SMA crossover  (verdict gate = appraisal ratio vs buy&hold)")
    print(f"{'Ticker':8}{'IS apr':>9}{'OOS apr':>9}{'OOS IR':>9}{'absSh':>8}{'Folds':>7}  Verdict")
    for tk, v in per.items():
        print(f"{tk:8}{v['is_appraisal']:>9.2f}{v['oos_appraisal']:>9.2f}"
              f"{v['oos_excess']:>9.2f}{v['oos_sharpe']:>8.2f}{v['n_folds']:>7}  {v['verdict']}")
    print("-" * 64)
    print(f"{'OVERALL':8}{overall['is_appraisal']:>9.2f}{overall['oos_appraisal']:>9.2f}"
          f"{overall['oos_excess']:>9.2f}{overall['oos_sharpe']:>8.2f}{overall['n_folds']:>7}  {overall['verdict']}")

    print("\nTemplate comparison (overall basket). IR shown FIRST (passive sanity), then appraisal gate:")
    for name, tm in st.TEMPLATES.items():
        ov, _, _ = evaluate_template(data, tm["fn"], tm["grid"], tm.get("valid"),
                                     is_years=4, oos_years=2, step_years=2)
        print(f"  {name:16} OOS IR {ov['oos_excess']:>5.2f} (bench beats it) | "
              f"OOS appraisal {ov['oos_appraisal']:>5.2f} | gap {ov['appraisal_gap']:>5.2f} -> {ov['verdict']}")
