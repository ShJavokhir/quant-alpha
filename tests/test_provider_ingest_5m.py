from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pandas as pd
from fastapi.testclient import TestClient

import api
from market_data_5m import (
    AlpacaProvider,
    MarketDataProvider,
    PolygonProvider,
    ingest_5m_bars,
    read_bar_cache,
    read_manifest,
    validate_bars,
)


def polygon_payload():
    return {
        "results": [
            {"t": 1704205800000, "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 1000, "vw": 100.2, "n": 12},
            {"t": 1704206100000, "o": 101, "h": 102, "l": 100, "c": 101.5, "v": 1100, "vw": 101.2, "n": 13},
        ]
    }


def test_polygon_provider_fetches_and_normalizes_with_api_key():
    seen = {}

    def transport(url, headers, timeout):
        seen["url"] = url
        seen["headers"] = headers
        seen["timeout"] = timeout
        return polygon_payload()

    provider = PolygonProvider(api_key="test-key", base_url="https://example.test", timeout=7, transport=transport)
    bars = provider.fetch_5m_bars(["aapl"], "2024-01-02", "2024-01-02")

    parsed = urlparse(seen["url"])
    query = parse_qs(parsed.query)
    assert parsed.path == "/v2/aggs/ticker/AAPL/range/5/minute/2024-01-02/2024-01-02"
    assert query["apiKey"] == ["test-key"]
    assert query["adjusted"] == ["true"]
    assert seen["headers"] is None
    assert seen["timeout"] == 7
    assert list(bars["symbol"].unique()) == ["AAPL"]
    assert list(bars["provider"].unique()) == ["polygon"]


def test_alpaca_provider_fetches_paginated_symbol_bars_with_headers():
    calls = []

    def transport(url, headers, timeout):
        calls.append((url, headers, timeout))
        qs = parse_qs(urlparse(url).query)
        if "page_token" not in qs:
            return {
                "bars": {"MSFT": [{"t": "2024-01-02T14:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100, "vw": 1.2, "n": 5}]},
                "next_page_token": "next",
            }
        return {
            "bars": {"AAPL": [{"t": "2024-01-02T14:30:00Z", "o": 3, "h": 4, "l": 2.5, "c": 3.5, "v": 200, "vw": 3.2, "n": 6}]},
            "next_page_token": None,
        }

    provider = AlpacaProvider(api_key="ak", secret_key="sk", feed="iex", base_url="https://alpaca.test", transport=transport)
    bars = provider.fetch_5m_bars(["msft", "aapl"], "2024-01-02T14:30:00Z", "2024-01-02T21:00:00Z", adjusted=False)

    first_qs = parse_qs(urlparse(calls[0][0]).query)
    assert first_qs["symbols"] == ["MSFT,AAPL"]
    assert first_qs["timeframe"] == ["5Min"]
    assert first_qs["adjustment"] == ["raw"]
    assert first_qs["feed"] == ["iex"]
    assert calls[0][1] == {"APCA-API-KEY-ID": "ak", "APCA-API-SECRET-KEY": "sk"}
    assert set(bars["symbol"]) == {"AAPL", "MSFT"}
    assert set(bars["provider"]) == {"alpaca"}


class FakeProvider(MarketDataProvider):
    name = "fake"

    def fetch_5m_bars(self, symbols, start, end, adjusted=True):
        rows = []
        for symbol in symbols[:1]:
            rows.append({
                "timestamp": pd.Timestamp("2024-01-02 14:30", tz="UTC"),
                "symbol": symbol,
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 1.5,
                "volume": 100,
                "vwap": 1.2,
                "trades": 5,
                "provider": "fake",
                "adjusted": adjusted,
            })
        return validate_bars(pd.DataFrame(rows))


def test_ingest_helper_writes_cache_and_manifest(tmp_path):
    manifest = ingest_5m_bars(FakeProvider(), ["AAA", "BBB"], "2024-01-02", "2024-01-02", tmp_path, universe="unit")
    loaded = read_bar_cache(tmp_path, "fake", "2024-01-02", "2024-01-02")
    stored_manifest = read_manifest(tmp_path, "fake")

    assert len(loaded) == 1
    assert manifest["rows"] == 1
    assert manifest["missing_symbols"] == ["BBB"]
    assert stored_manifest["universe"] == "unit"
    assert stored_manifest["regular_session_only"] is True


def test_api_ingest_endpoint_uses_provider_and_writes_cache(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(api, "DATA_DIR", data_dir)
    monkeypatch.setattr(api, "get_provider", lambda name: FakeProvider())

    client = TestClient(api.app)
    resp = client.post("/api/market-data/5m/ingest", json={
        "provider": "fake",
        "symbols": ["AAA", "BBB"],
        "start": "2024-01-02",
        "end": "2024-01-02",
        "universe": "unit",
    })

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["rows"] == 1
    assert payload["missing_symbols"] == ["BBB"]
    assert read_bar_cache(data_dir / "cache", "fake", symbols=["AAA"]).iloc[0]["symbol"] == "AAA"
