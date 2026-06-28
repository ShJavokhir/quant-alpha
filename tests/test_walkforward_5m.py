from __future__ import annotations

import json

from market_data_5m import bars_to_panel
from portfolio_5m import PortfolioConfig5m
from tests.conftest import synthetic_bars
from walkforward_5m import (
    WalkForwardConfig5m,
    slice_panel,
    verdict_5m,
    walk_forward_factor_5m,
    write_walkforward_artifacts,
)


def test_walkforward_windows_do_not_overlap():
    panel = bars_to_panel(synthetic_bars(days=4, symbols=("AAA", "BBB", "CCC", "DDD", "EEE"), bars_per_day=10))
    result = walk_forward_factor_5m(
        panel,
        "intraday_momentum",
        param_grid=[{"lookback": 1}],
        portfolio_config=PortfolioConfig5m(top_quantile=0.2, bottom_quantile=0.2),
        config=WalkForwardConfig5m(is_days=2, oos_days=1, step_days=1, min_is_bars=5, min_oos_bars=5),
    )
    assert result["folds"]
    for fold in result["folds"]:
        assert fold["is_end"] < fold["oos_start"]


def test_slice_panel_limits_optimization_data_to_is_session_range():
    panel = bars_to_panel(synthetic_bars(days=3, bars_per_day=4))
    is_panel = slice_panel(panel, panel.close.index[0].tz_convert("America/New_York"), panel.close.index[0].tz_convert("America/New_York"))
    assert len(is_panel.close) == 4
    assert is_panel.close.index.max() == panel.close.index[3]


def test_verdict_marks_overfit_and_robust_synthetic_folds():
    cfg = WalkForwardConfig5m()
    overfit = verdict_5m([{"is_sharpe": 4, "oos_sharpe": -1, "oos_ic_ir": -0.5, "oos_turnover": 1, "oos_max_drawdown": -0.01}], cfg)
    robust = verdict_5m([{"is_sharpe": 1.2, "oos_sharpe": 1.0, "oos_ic_ir": 0.8, "oos_turnover": 1, "oos_max_drawdown": -0.02}], cfg)
    assert overfit["verdict"] == "OVERFIT"
    assert robust["verdict"] == "ROBUST"


def test_walkforward_artifacts_are_replayable_without_network(tmp_path):
    payload = {"summary": {"verdict": "ROBUST"}, "folds": [{"params": {"lookback": 1}}]}
    write_walkforward_artifacts(tmp_path / "factor_5m_demo", payload)
    assert json.loads((tmp_path / "factor_5m_demo" / "walkforward.json").read_text()) == payload
