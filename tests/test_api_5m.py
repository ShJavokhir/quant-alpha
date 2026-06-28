from __future__ import annotations

from fastapi.testclient import TestClient

import api
from market_data_5m import write_bar_cache, write_manifest
from tests.conftest import synthetic_bars


def test_5m_factor_and_backtest_api_writes_replay_artifacts(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    runs_dir = tmp_path / "runs"
    monkeypatch.setattr(api, "DATA_DIR", data_dir)
    monkeypatch.setattr(api, "RUNS_DIR", runs_dir)
    write_bar_cache(synthetic_bars(days=1, symbols=("AAA", "BBB", "CCC", "DDD", "EEE"), bars_per_day=8), data_dir / "cache", "polygon")
    write_manifest(data_dir / "cache", "polygon", {"universe": "synthetic", "adjusted": True})

    client = TestClient(api.app)
    factors = client.get("/api/factors/5m")
    assert factors.status_code == 200
    assert any(f["name"] == "intraday_momentum" for f in factors.json()["factors"])

    created = client.post("/api/backtests/5m", json={
        "provider": "polygon",
        "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE"],
        "start": "2024-01-02",
        "end": "2024-01-02",
        "factor_name": "intraday_momentum",
        "factor_params": {"lookback": 1},
        "portfolio": {"top_quantile": 0.2, "bottom_quantile": 0.2},
    })
    assert created.status_code == 200, created.text
    run_id = created.json()["id"]
    assert "survivor-biased" in created.json()["survivorship_warning"]

    assert client.get(f"/api/backtests/5m/{run_id}/summary").status_code == 200
    assert client.get(f"/api/backtests/5m/{run_id}/equity").json()["points"]
    assert client.get(f"/api/backtests/5m/{run_id}/ic").status_code == 200
    assert client.get(f"/api/backtests/5m/{run_id}/quantiles").status_code == 200


def test_existing_daily_api_regression_still_serves_committed_journal():
    client = TestClient(api.app)
    resp = client.get("/api/runs/latest/journal")
    assert resp.status_code == 200
    assert resp.json()["experiments"]
