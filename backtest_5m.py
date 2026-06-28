"""No-lookahead 5-minute cross-sectional portfolio backtester."""
from __future__ import annotations

import numpy as np
import pandas as pd

from market_data_5m import BARS_PER_DAY_5M, BarPanel5m

ANN_5M = BARS_PER_DAY_5M * 252


def run_portfolio_backtest_5m(
    panel: BarPanel5m,
    target_weights: pd.DataFrame,
    commission_bps: float = 2.0,
    slippage_bps: float = 3.0,
) -> dict:
    returns = panel.returns.reindex_like(panel.close).fillna(0.0)
    target = target_weights.reindex_like(returns).fillna(0.0)
    target = target.where(panel.tradable.reindex_like(target).fillna(False), 0.0)
    held = target.shift(1).fillna(0.0)
    turnover = held.diff().abs().sum(axis=1).fillna(held.abs().sum(axis=1))
    gross_returns_by_symbol = held * returns
    gross_returns = gross_returns_by_symbol.sum(axis=1)
    costs = turnover * ((commission_bps + slippage_bps) / 1e4)
    net_returns = gross_returns - costs
    equity = (1.0 + net_returns).cumprod()
    return {
        "target_weights": target,
        "held_weights": held,
        "asset_returns": returns,
        "contribution": gross_returns_by_symbol,
        "gross_returns": gross_returns,
        "turnover": turnover,
        "costs": costs,
        "net_returns": net_returns,
        "equity": equity,
        "gross_exposure": held.abs().sum(axis=1),
        "net_exposure": held.sum(axis=1),
    }


def compute_portfolio_metrics_5m(bt: dict, ann: int = ANN_5M) -> dict:
    r = bt["net_returns"].fillna(0.0)
    eq = bt["equity"]
    sd = r.std()
    downside = r[r < 0].std()
    dd = (eq / eq.cummax() - 1.0).min() if len(eq) else np.nan
    return {
        "total_return": float(eq.iloc[-1] - 1.0) if len(eq) else np.nan,
        "sharpe": float(r.mean() / sd * np.sqrt(ann)) if sd and np.isfinite(sd) else 0.0,
        "sortino": float(r.mean() / downside * np.sqrt(ann)) if downside and np.isfinite(downside) else 0.0,
        "volatility": float(sd * np.sqrt(ann)) if np.isfinite(sd) else np.nan,
        "max_drawdown": float(dd) if np.isfinite(dd) else np.nan,
        "avg_turnover": float(bt["turnover"].mean()),
        "avg_gross_exposure": float(bt["gross_exposure"].mean()),
        "avg_net_exposure": float(bt["net_exposure"].mean()),
    }


def information_coefficient(scores: pd.DataFrame, returns: pd.DataFrame, method: str = "spearman") -> pd.Series:
    future = returns.shift(-1)
    vals = {}
    for ts in scores.index.intersection(future.index):
        x = scores.loc[ts]
        y = future.loc[ts]
        ok = x.notna() & y.notna()
        if ok.sum() < 2:
            vals[ts] = np.nan
            continue
        x_ok = x[ok]
        y_ok = y[ok]
        if method == "spearman":
            x_ok = x_ok.rank(method="average")
            y_ok = y_ok.rank(method="average")
            vals[ts] = x_ok.corr(y_ok, method="pearson")
        elif method == "pearson":
            vals[ts] = x_ok.corr(y_ok, method="pearson")
        else:
            raise ValueError(f"unsupported IC method: {method}")
    return pd.Series(vals, dtype=float)


def quantile_returns(scores: pd.DataFrame, returns: pd.DataFrame, n_quantiles: int = 5) -> pd.DataFrame:
    future = returns.shift(-1)
    out = pd.DataFrame(index=scores.index, columns=list(range(1, n_quantiles + 1)), dtype=float)
    ranks = scores.rank(axis=1, pct=True, ascending=True)
    for q in range(1, n_quantiles + 1):
        lo = (q - 1) / n_quantiles
        hi = q / n_quantiles
        mask = ranks.gt(lo) & ranks.le(hi)
        out[q] = future.where(mask).mean(axis=1)
    return out

