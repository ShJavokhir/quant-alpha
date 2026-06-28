"""Cross-sectional portfolio construction for 5-minute factor scores."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PortfolioConfig5m:
    mode: str = "long_short"          # long_only | short_only | long_short
    top_quantile: float = 0.2
    bottom_quantile: float = 0.2
    weighting: str = "equal"          # equal | score
    gross_exposure: float = 1.0
    rebalance_every: int = 1


def _normalize_side(raw: pd.DataFrame, exposure: float) -> pd.DataFrame:
    denom = raw.abs().sum(axis=1).replace(0, pd.NA)
    out = raw.div(denom, axis=0).fillna(0.0) * exposure
    return out.astype(float)


def _selection_mask(scores: pd.DataFrame, mask: pd.DataFrame, side: str, q: float) -> pd.DataFrame:
    selected = pd.DataFrame(False, index=scores.index, columns=scores.columns)
    for ts in scores.index:
        row = scores.loc[ts].where(mask.loc[ts]).dropna()
        if row.empty:
            continue
        n = max(1, int(np.ceil(len(row) * q)))
        picks = row.nlargest(n).index if side == "long" else row.nsmallest(n).index
        selected.loc[ts, picks] = True
    return selected


def _side_weights(scores: pd.DataFrame, mask: pd.DataFrame, side: str, q: float, weighting: str, exposure: float) -> pd.DataFrame:
    if side not in {"long", "short"}:
        raise ValueError(f"unknown side: {side}")
    selected = _selection_mask(scores, mask, side, q)
    raw = scores.where(selected & mask, 0.0).abs() if weighting == "score" else selected.astype(float)
    weights = _normalize_side(raw, exposure)
    return weights if side == "long" else -weights


def weights_from_scores(scores: pd.DataFrame, tradable: pd.DataFrame, config: PortfolioConfig5m | None = None) -> pd.DataFrame:
    cfg = config or PortfolioConfig5m()
    if cfg.mode not in {"long_only", "short_only", "long_short"}:
        raise ValueError(f"unsupported portfolio mode: {cfg.mode}")
    if cfg.weighting not in {"equal", "score"}:
        raise ValueError(f"unsupported weighting: {cfg.weighting}")
    if not 0 < cfg.top_quantile <= 1 or not 0 < cfg.bottom_quantile <= 1:
        raise ValueError("quantiles must be in (0, 1]")

    s = scores.astype(float)
    mask = tradable.reindex_like(s).fillna(False) & s.notna()
    if cfg.mode == "long_only":
        weights = _side_weights(s, mask, "long", cfg.top_quantile, cfg.weighting, cfg.gross_exposure)
    elif cfg.mode == "short_only":
        weights = _side_weights(s, mask, "short", cfg.bottom_quantile, cfg.weighting, cfg.gross_exposure)
    else:
        half = cfg.gross_exposure / 2.0
        weights = (_side_weights(s, mask, "long", cfg.top_quantile, cfg.weighting, half) +
                   _side_weights(s, mask, "short", cfg.bottom_quantile, cfg.weighting, half))
    weights = weights.where(mask, 0.0).fillna(0.0)
    return apply_rebalance_schedule(weights, cfg.rebalance_every)


def apply_rebalance_schedule(weights: pd.DataFrame, every_n_bars: int = 1) -> pd.DataFrame:
    n = max(1, int(every_n_bars))
    if n == 1 or weights.empty:
        return weights
    out = weights.copy()
    rebalance_rows = list(range(0, len(out), n))
    held = out.iloc[rebalance_rows].reindex(out.index).ffill().fillna(0.0)
    return held

