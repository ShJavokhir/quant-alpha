from __future__ import annotations

import pytest

from factors_5m import evaluate_factor, list_factors
from market_data_5m import bars_to_panel
from tests.conftest import synthetic_bars, synthetic_panel


def test_registered_factors_return_timestamp_by_symbol_scores():
    panel = synthetic_panel(days=1)
    for spec in list_factors():
        scores = evaluate_factor(panel, spec["name"], {"lookback": 2, "range_bars": 2})
        assert scores.shape == panel.close.shape
        assert list(scores.columns) == panel.symbols


def test_factor_does_not_change_past_scores_when_future_bar_changes():
    panel = synthetic_panel(days=1, bars_per_day=8)
    base = evaluate_factor(panel, "intraday_momentum", {"lookback": 2})
    changed_bars = synthetic_bars(days=1, bars_per_day=8)
    changed_bars.loc[changed_bars["timestamp"] == changed_bars["timestamp"].max(), "close"] *= 10
    changed = evaluate_factor(bars_to_panel(changed_bars), "intraday_momentum", {"lookback": 2})
    assert base.iloc[:-1].equals(changed.iloc[:-1])


def test_vwap_factor_fails_when_vwap_missing():
    bars = synthetic_bars(days=1, bars_per_day=4)
    bars["vwap"] = None
    with pytest.raises(ValueError, match="vwap"):
        evaluate_factor(bars_to_panel(bars), "vwap_deviation")


def test_scores_remain_aligned_after_missing_bar_filtering():
    bars = synthetic_bars(days=1, bars_per_day=5)
    bars = bars[~((bars["symbol"] == "CCC") & (bars["timestamp"] == bars["timestamp"].max()))]
    panel = bars_to_panel(bars)
    scores = evaluate_factor(panel, "volume_surge", {"lookback": 2})
    assert scores.index.equals(panel.close.index)
    assert scores.columns.equals(panel.close.columns)
    assert scores.loc[scores.index.max(), "CCC"] != scores.loc[scores.index.max(), "CCC"]
