from __future__ import annotations

import pandas as pd
import pytest

from market_data_5m import (
    BARS_PER_DAY_5M,
    bars_to_panel,
    filter_regular_session,
    normalize_alpaca_bars,
    normalize_polygon_aggs,
    read_bar_cache,
    validate_bars,
    write_bar_cache,
)
from tests.conftest import synthetic_bars


def test_provider_normalizers_emit_canonical_schema():
    polygon = normalize_polygon_aggs("aapl", [{"t": 1704205800000, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100, "vw": 1.4, "n": 7}])
    alpaca = normalize_alpaca_bars("msft", [{"t": "2024-01-02T14:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100, "vw": 1.4, "n": 7}])
    assert list(polygon.columns) == list(alpaca.columns)
    assert polygon.loc[0, "symbol"] == "AAPL"
    assert alpaca.loc[0, "provider"] == "alpaca"


def test_session_filter_keeps_regular_5m_bars_only():
    rows = synthetic_bars(days=1, symbols=("AAA",), bars_per_day=BARS_PER_DAY_5M + 1)
    filtered = filter_regular_session(rows)
    assert len(filtered) == BARS_PER_DAY_5M
    assert filtered["timestamp"].max() == pd.Timestamp("2024-01-02 20:55", tz="UTC")


def test_cache_round_trip_preserves_bar_metadata(tmp_path):
    pytest.importorskip("pyarrow")
    bars = synthetic_bars(days=1, symbols=("AAA", "BBB"), bars_per_day=3)
    written = write_bar_cache(bars, tmp_path, "polygon")
    loaded = read_bar_cache(tmp_path, "polygon", "2024-01-02", "2024-01-02", ["AAA", "BBB"])
    assert written
    assert len(loaded) == len(validate_bars(bars))
    assert set(loaded["provider"]) == {"polygon"}
    assert loaded["adjusted"].all()


def test_zero_volume_and_missing_bars_are_not_tradable():
    bars = synthetic_bars(days=1, symbols=("AAA", "BBB"), bars_per_day=3)
    bars.loc[(bars["symbol"] == "AAA") & (bars["timestamp"] == bars["timestamp"].min()), "volume"] = 0
    bars = bars[~((bars["symbol"] == "BBB") & (bars["timestamp"] == bars["timestamp"].max()))]
    panel = bars_to_panel(bars)
    assert not bool(panel.tradable.loc[panel.tradable.index.min(), "AAA"])
    assert not bool(panel.tradable.loc[panel.tradable.index.max(), "BBB"])
