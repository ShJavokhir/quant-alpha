"""Initial 5-minute cross-sectional factor registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from market_data_5m import BarPanel5m

FactorFn = Callable[[BarPanel5m, dict], pd.DataFrame]


@dataclass(frozen=True)
class FactorSpec5m:
    name: str
    kind: str
    required_fields: tuple[str, ...]
    default_params: dict
    description: str
    fn: FactorFn


_REGISTRY: dict[str, FactorSpec5m] = {}


def register_factor(spec: FactorSpec5m) -> FactorSpec5m:
    _REGISTRY[spec.name] = spec
    return spec


def get_factor(name: str) -> FactorSpec5m:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"unknown 5m factor: {name}") from exc


def list_factors() -> list[dict]:
    return [{
        "name": s.name,
        "kind": s.kind,
        "required_fields": list(s.required_fields),
        "default_params": dict(s.default_params),
        "description": s.description,
    } for s in sorted(_REGISTRY.values(), key=lambda x: x.name)]


def _require(panel: BarPanel5m, fields: tuple[str, ...]) -> None:
    for field in fields:
        if getattr(panel, field) is None:
            raise ValueError(f"factor requires missing field: {field}")


def _mask(scores: pd.DataFrame, panel: BarPanel5m) -> pd.DataFrame:
    return scores.reindex_like(panel.close).where(panel.tradable)


def evaluate_factor(panel: BarPanel5m, name: str, params: dict | None = None) -> pd.DataFrame:
    spec = get_factor(name)
    _require(panel, spec.required_fields)
    p = dict(spec.default_params)
    p.update(params or {})
    return _mask(spec.fn(panel, p), panel)


def cross_sectional_rank(df: pd.DataFrame, ascending: bool = True) -> pd.DataFrame:
    return df.rank(axis=1, pct=True, ascending=ascending)


def intraday_momentum(panel: BarPanel5m, params: dict) -> pd.DataFrame:
    lookback = int(params.get("lookback", 6))
    return panel.close / panel.close.shift(lookback) - 1.0


def opening_range_breakout(panel: BarPanel5m, params: dict) -> pd.DataFrame:
    bars = int(params.get("range_bars", 6))
    daily = pd.Series(panel.close.index.tz_convert("America/New_York").date, index=panel.close.index)
    opening_high = pd.DataFrame(index=panel.close.index, columns=panel.close.columns, dtype=float)
    opening_low = pd.DataFrame(index=panel.close.index, columns=panel.close.columns, dtype=float)
    for _, idx in daily.groupby(daily).groups.items():
        day_high = panel.high.loc[idx]
        day_low = panel.low.loc[idx]
        if len(day_high) < bars:
            continue
        high = day_high.iloc[:bars].max(axis=0)
        low = day_low.iloc[:bars].min(axis=0)
        target_idx = idx[bars - 1:]
        for col in panel.close.columns:
            opening_high.loc[target_idx, col] = high[col]
            opening_low.loc[target_idx, col] = low[col]
    width = (opening_high - opening_low).replace(0, np.nan)
    return (panel.close - opening_high) / width


def vwap_deviation(panel: BarPanel5m, params: dict) -> pd.DataFrame:
    if panel.vwap is None:
        raise ValueError("vwap_deviation requires missing field: vwap")
    return (panel.close - panel.vwap) / panel.vwap.replace(0, np.nan)


def volume_surge(panel: BarPanel5m, params: dict) -> pd.DataFrame:
    lookback = int(params.get("lookback", 12))
    avg = panel.volume.rolling(lookback, min_periods=lookback).mean()
    return panel.volume / avg.replace(0, np.nan) - 1.0


def intraday_mean_reversion(panel: BarPanel5m, params: dict) -> pd.DataFrame:
    lookback = int(params.get("lookback", 6))
    mom = panel.close / panel.close.shift(lookback) - 1.0
    return -mom


register_factor(FactorSpec5m(
    name="intraday_momentum",
    kind="momentum",
    required_fields=("close",),
    default_params={"lookback": 6},
    description="Trailing 5-minute close-to-close momentum over N bars.",
    fn=intraday_momentum,
))
register_factor(FactorSpec5m(
    name="opening_range_breakout",
    kind="breakout",
    required_fields=("high", "low", "close"),
    default_params={"range_bars": 6},
    description="Close breakout beyond the rolling opening range.",
    fn=opening_range_breakout,
))
register_factor(FactorSpec5m(
    name="vwap_deviation",
    kind="mean_reversion",
    required_fields=("close", "vwap"),
    default_params={},
    description="Distance from bar VWAP, positive when close is above VWAP.",
    fn=vwap_deviation,
))
register_factor(FactorSpec5m(
    name="volume_surge",
    kind="liquidity",
    required_fields=("volume",),
    default_params={"lookback": 12},
    description="Current volume relative to trailing N-bar average.",
    fn=volume_surge,
))
register_factor(FactorSpec5m(
    name="intraday_mean_reversion",
    kind="mean_reversion",
    required_fields=("close",),
    default_params={"lookback": 6},
    description="Negative trailing momentum over N bars.",
    fn=intraday_mean_reversion,
))

