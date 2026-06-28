from __future__ import annotations

import pandas as pd

from backtest_5m import information_coefficient, quantile_returns, run_portfolio_backtest_5m
from market_data_5m import BarPanel5m
from portfolio_5m import PortfolioConfig5m, weights_from_scores


def make_panel():
    idx = pd.date_range("2024-01-02 14:30", periods=4, freq="5min", tz="UTC")
    cols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    close = pd.DataFrame({c: [100 + i + j for i in range(4)] for j, c in enumerate(cols)}, index=idx)
    volume = pd.DataFrame(1000, index=idx, columns=cols)
    returns = close.pct_change().fillna(0.0)
    tradable = pd.DataFrame(True, index=idx, columns=cols)
    return BarPanel5m(close, close, close, close, volume, None, None, returns, tradable, {})


def test_long_short_weights_are_dollar_neutral_and_per_timestamp():
    panel = make_panel()
    scores = pd.DataFrame([range(5)] * 4, index=panel.close.index, columns=panel.symbols)
    weights = weights_from_scores(scores, panel.tradable, PortfolioConfig5m(top_quantile=0.2, bottom_quantile=0.2))
    assert weights.sum(axis=1).abs().max() < 1e-12
    assert weights.abs().sum(axis=1).eq(1.0).all()
    assert weights.loc[weights.index[0], "EEE"] > 0
    assert weights.loc[weights.index[0], "AAA"] < 0


def test_untradable_symbols_receive_zero_weight_and_rebalance_holds():
    panel = make_panel()
    scores = pd.DataFrame([range(5), range(5), [4, 3, 2, 1, 0], [4, 3, 2, 1, 0]], index=panel.close.index, columns=panel.symbols)
    tradable = panel.tradable.copy()
    tradable.loc[tradable.index[0], "EEE"] = False
    weights = weights_from_scores(scores, tradable, PortfolioConfig5m(top_quantile=0.2, bottom_quantile=0.2, rebalance_every=2))
    assert weights.loc[weights.index[0], "EEE"] == 0
    assert weights.iloc[1].equals(weights.iloc[0])
    assert not weights.iloc[2].equals(weights.iloc[1])


def test_backtester_shifts_targets_one_bar_before_returns_and_charges_turnover_costs():
    panel = make_panel()
    target = pd.DataFrame(0.0, index=panel.close.index, columns=panel.symbols)
    target.loc[:, "AAA"] = 1.0
    bt = run_portfolio_backtest_5m(panel, target, commission_bps=1.0, slippage_bps=1.0)
    assert bt["held_weights"].iloc[0].abs().sum() == 0
    assert bt["net_returns"].iloc[0] == 0
    assert bt["costs"].iloc[1] > 0
    assert bt["costs"].iloc[2] == 0


def test_perfect_factor_has_positive_quantile_spread_and_ic_uses_future_returns():
    idx = pd.date_range("2024-01-02 14:30", periods=3, freq="5min", tz="UTC")
    cols = ["A", "B", "C", "D", "E"]
    scores = pd.DataFrame([[-2, -1, 0, 1, 2]] * 3, index=idx, columns=cols)
    returns = pd.DataFrame(0.0, index=idx, columns=cols)
    returns.iloc[1] = [-0.02, -0.01, 0, 0.01, 0.02]
    ic = information_coefficient(scores, returns)
    q = quantile_returns(scores, returns, n_quantiles=5)
    assert ic.iloc[0] > 0.99
    assert q.loc[idx[0], 5] > q.loc[idx[0], 1]
