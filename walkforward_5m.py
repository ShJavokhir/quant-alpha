"""Walk-forward evaluation for 5-minute cross-sectional factor research."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest_5m import (
    compute_portfolio_metrics_5m,
    information_coefficient,
    quantile_returns,
    run_portfolio_backtest_5m,
)
from factors_5m import evaluate_factor
from market_data_5m import BarPanel5m, EASTERN
from portfolio_5m import PortfolioConfig5m, weights_from_scores


@dataclass(frozen=True)
class WalkForwardConfig5m:
    is_days: int = 20
    oos_days: int = 5
    step_days: int = 5
    min_is_bars: int = 78
    min_oos_bars: int = 20
    turnover_cap: float = 8.0
    drawdown_cap: float = -0.15
    min_oos_sharpe: float = 0.5
    max_sharpe_decay: float = 1.0


def _session_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    eastern = index.tz_convert(EASTERN)
    return sorted(pd.Timestamp(d) for d in pd.Series(eastern.date).unique())


def _date_mask(index: pd.DatetimeIndex, start_day: pd.Timestamp, end_day: pd.Timestamp) -> pd.Series:
    days = pd.Series(index.tz_convert(EASTERN).date, index=index)
    return (days >= start_day.date()) & (days <= end_day.date())


def slice_panel(panel: BarPanel5m, start_day: pd.Timestamp, end_day: pd.Timestamp) -> BarPanel5m:
    mask = _date_mask(panel.close.index, start_day, end_day)
    idx = panel.close.index[mask.to_numpy()]

    def take(df: pd.DataFrame | None) -> pd.DataFrame | None:
        return None if df is None else df.loc[idx]

    return BarPanel5m(
        open=panel.open.loc[idx],
        high=panel.high.loc[idx],
        low=panel.low.loc[idx],
        close=panel.close.loc[idx],
        volume=panel.volume.loc[idx],
        vwap=take(panel.vwap),
        trades=take(panel.trades),
        returns=panel.returns.loc[idx],
        tradable=panel.tradable.loc[idx],
        metadata={**panel.metadata, "slice_start": str(start_day.date()), "slice_end": str(end_day.date())},
    )


def _combos(param_grid: list[dict] | dict | None) -> list[dict]:
    if param_grid is None:
        return [{}]
    if isinstance(param_grid, list):
        return [dict(p) for p in param_grid] or [{}]
    keys = list(param_grid)
    return [dict(zip(keys, vals)) for vals in product(*(param_grid[k] for k in keys))]


def run_factor_backtest_5m(
    panel: BarPanel5m,
    factor_name: str,
    factor_params: dict | None = None,
    portfolio_config: PortfolioConfig5m | None = None,
    commission_bps: float = 2.0,
    slippage_bps: float = 3.0,
) -> dict:
    scores = evaluate_factor(panel, factor_name, factor_params)
    weights = weights_from_scores(scores, panel.tradable, portfolio_config or PortfolioConfig5m())
    bt = run_portfolio_backtest_5m(panel, weights, commission_bps, slippage_bps)
    ic = information_coefficient(scores, panel.returns)
    quants = quantile_returns(scores, panel.returns)
    return {
        "scores": scores,
        "weights": weights,
        "backtest": bt,
        "metrics": compute_portfolio_metrics_5m(bt),
        "ic": ic,
        "rank_ic": information_coefficient(scores, panel.returns, method="spearman"),
        "quantiles": quants,
    }


def optimize_factor_params_5m(
    panel: BarPanel5m,
    factor_name: str,
    param_grid: list[dict] | dict | None,
    portfolio_config: PortfolioConfig5m | None = None,
) -> tuple[dict, dict]:
    best_params: dict | None = None
    best_metrics: dict | None = None
    best_score = -np.inf
    for params in _combos(param_grid):
        result = run_factor_backtest_5m(panel, factor_name, params, portfolio_config)
        metrics = result["metrics"]
        ic = result["ic"].dropna()
        ic_ir = float(ic.mean() / ic.std() * np.sqrt(78 * 252)) if len(ic) > 1 and ic.std() > 0 else 0.0
        score = metrics["sharpe"] + 0.25 * ic_ir - 0.1 * max(0.0, metrics["avg_turnover"] - 8.0)
        score -= 2.0 * max(0.0, abs(metrics["max_drawdown"]) - 0.15)
        if np.isfinite(score) and score > best_score:
            best_params, best_metrics, best_score = params, metrics, score
    if best_params is None or best_metrics is None:
        return {}, {"objective": -np.inf, "sharpe": -np.inf}
    return best_params, {**best_metrics, "objective": float(best_score)}


def _mean(folds: list[dict], key: str) -> float:
    vals = [float(f[key]) for f in folds if np.isfinite(f.get(key, np.nan))]
    return float(np.mean(vals)) if vals else np.nan


def verdict_5m(folds: list[dict], cfg: WalkForwardConfig5m | None = None) -> dict:
    cfg = cfg or WalkForwardConfig5m()
    base = {
        "verdict": "NO DATA", "n_folds": 0, "is_sharpe": np.nan, "oos_sharpe": np.nan,
        "sharpe_decay": np.nan, "oos_ic_ir": np.nan, "oos_turnover": np.nan,
        "oos_max_drawdown": np.nan,
    }
    if not folds:
        return base
    is_sharpe = _mean(folds, "is_sharpe")
    oos_sharpe = _mean(folds, "oos_sharpe")
    oos_ic_ir = _mean(folds, "oos_ic_ir")
    turnover = _mean(folds, "oos_turnover")
    drawdown = _mean(folds, "oos_max_drawdown")
    decay = is_sharpe - oos_sharpe
    if oos_sharpe < 0 or oos_ic_ir < 0 or decay > cfg.max_sharpe_decay * 2:
        v = "OVERFIT"
    elif oos_sharpe < cfg.min_oos_sharpe or decay > cfg.max_sharpe_decay or turnover > cfg.turnover_cap or drawdown < cfg.drawdown_cap:
        v = "FRAGILE"
    else:
        v = "ROBUST"
    return {
        "verdict": v,
        "n_folds": len(folds),
        "is_sharpe": is_sharpe,
        "oos_sharpe": oos_sharpe,
        "sharpe_decay": decay,
        "oos_ic_ir": oos_ic_ir,
        "oos_turnover": turnover,
        "oos_max_drawdown": drawdown,
    }


def walk_forward_factor_5m(
    panel: BarPanel5m,
    factor_name: str,
    param_grid: list[dict] | dict | None = None,
    portfolio_config: PortfolioConfig5m | None = None,
    config: WalkForwardConfig5m | None = None,
) -> dict:
    cfg = config or WalkForwardConfig5m()
    days = _session_dates(panel.close.index)
    folds: list[dict] = []
    start_i = 0
    while start_i + cfg.is_days + cfg.oos_days <= len(days):
        is_start = days[start_i]
        is_end = days[start_i + cfg.is_days - 1]
        oos_start = days[start_i + cfg.is_days]
        oos_end = days[start_i + cfg.is_days + cfg.oos_days - 1]
        is_panel = slice_panel(panel, is_start, is_end)
        oos_panel = slice_panel(panel, oos_start, oos_end)
        if len(is_panel.close) >= cfg.min_is_bars and len(oos_panel.close) >= cfg.min_oos_bars:
            params, is_metrics = optimize_factor_params_5m(is_panel, factor_name, param_grid, portfolio_config)
            oos_result = run_factor_backtest_5m(oos_panel, factor_name, params, portfolio_config)
            ic = oos_result["ic"].dropna()
            ic_ir = float(ic.mean() / ic.std() * np.sqrt(78 * 252)) if len(ic) > 1 and ic.std() > 0 else 0.0
            oos_metrics = oos_result["metrics"]
            folds.append({
                "is_start": str(is_start.date()),
                "is_end": str(is_end.date()),
                "oos_start": str(oos_start.date()),
                "oos_end": str(oos_end.date()),
                "params": params,
                "is_sharpe": is_metrics["sharpe"],
                "oos_sharpe": oos_metrics["sharpe"],
                "oos_ic_ir": ic_ir,
                "oos_turnover": oos_metrics["avg_turnover"],
                "oos_max_drawdown": oos_metrics["max_drawdown"],
            })
        start_i += cfg.step_days
    return {"summary": verdict_5m(folds, cfg), "folds": folds}


def write_walkforward_artifacts(run_dir: Path | str, result: dict) -> None:
    out = Path(run_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "walkforward.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
