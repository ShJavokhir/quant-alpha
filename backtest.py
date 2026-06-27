"""Rigorous, transparent vectorized backtester -- the 'judge' of the research lab.

Priorities, in order: (1) correctness / NO lookahead, (2) honest costs,
(3) metrics an algo trader actually trusts. Kept small enough to review line by line.

EXECUTION MODEL (no lookahead):
  pos[t]    target position decided at bar t's CLOSE (from data <= t)
  held[t]   = pos[t-1]  -> the position actually held DURING bar t
  ret[t]    = held[t] * (Close[t]/Close[t-1] - 1)        # earned from yesterday's decision
  trade[t]  = |held[t] - held[t-1]|                       # turnover executed at bar t
  cost[t]   = trade[t] * (commission + slippage) / 1e4
So a signal computed on bar t can only ever affect P&L from bar t+1 onward.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ANN = 252  # trading days per year (daily data)


def run_backtest(df: pd.DataFrame, signal: pd.Series,
                 commission_bps: float = 2.0, slippage_bps: float = 3.0) -> dict:
    """Run a target-position signal over OHLCV data. Returns per-bar series."""
    close = df["Close"].astype(float)
    asset_ret = close.pct_change().fillna(0.0)

    pos = signal.reindex(df.index).astype(float).fillna(0.0).clip(-1, 1)
    held = pos.shift(1).fillna(0.0)                 # position held each bar (t+1 execution)
    turnover = held.diff().abs().fillna(0.0)        # held starts at 0, so entry is captured

    cost_rate = (commission_bps + slippage_bps) / 1e4
    gross_ret = held * asset_ret
    costs = turnover * cost_rate
    net_ret = gross_ret - costs
    equity = (1.0 + net_ret).cumprod()

    return {"asset_ret": asset_ret, "held": held, "gross_ret": gross_ret,
            "costs": costs, "net_ret": net_ret, "equity": equity}


def _extract_trades(held: pd.Series, net_ret: pd.Series) -> pd.Series:
    """Per-trade net return, compounded over each holding period.

    A 'trade' = a run of consecutive bars with the same non-zero held position.
    NOTE: entry cost lands inside the trade; the exit cost lands on the first
    flat bar after it, so per-trade stats slightly understate round-trip cost.
    The equity curve / Sharpe / drawdown below are exact -- every cost counted once.
    """
    h = held.fillna(0.0).to_numpy()
    r = net_ret.fillna(0.0).to_numpy()
    trades, i, n = [], 0, len(h)
    while i < n:
        if h[i] == 0:
            i += 1
            continue
        comp, cur, j = 1.0, h[i], i
        while j < n and h[j] == cur:
            comp *= 1.0 + r[j]
            j += 1
        trades.append(comp - 1.0)
        i = j
    return pd.Series(trades, dtype=float)


def compute_metrics(bt: dict, ann: int = ANN) -> dict:
    net, equity, held = bt["net_ret"], bt["equity"], bt["held"]
    final = equity.iloc[-1]
    years = len(net) / ann

    sd = net.std()
    downside = net[net < 0].std()
    dd = (equity / equity.cummax() - 1.0).min()

    trades = _extract_trades(held, net)
    wins, losses = trades[trades > 0], trades[trades < 0]
    gross_loss = -losses.sum()

    return {
        "Total Return %": (final - 1.0) * 100,
        "CAGR %": (final ** (1 / years) - 1.0) * 100 if years > 0 else np.nan,
        "Sharpe": net.mean() / sd * np.sqrt(ann) if sd > 0 else np.nan,
        "Sortino": net.mean() / downside * np.sqrt(ann) if downside > 0 else np.nan,
        "Volatility %": sd * np.sqrt(ann) * 100,
        "Max Drawdown %": dd * 100,
        "Exposure %": (held != 0).mean() * 100,
        "Trades": len(trades),
        "Win Rate %": len(wins) / len(trades) * 100 if len(trades) else np.nan,
        "Profit Factor": wins.sum() / gross_loss if gross_loss > 0 else np.inf,
        "Expectancy %": trades.mean() * 100 if len(trades) else np.nan,
    }


def train_test_split(df: pd.DataFrame, train_frac: float = 0.7):
    cut = int(len(df) * train_frac)
    return df.iloc[:cut], df.iloc[cut:]


if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    import strategies as st

    df = pd.read_csv(Path(__file__).parent / "data" / "GOOGL_1d.csv",
                     index_col=0, parse_dates=True)
    train, test = train_test_split(df, 0.7)

    strats = {
        "Buy & Hold": st.buy_and_hold,
        "SMA 20/50": lambda d: st.sma_crossover(d, 20, 50),
        "SMA 50/200": lambda d: st.sma_crossover(d, 50, 200),
    }

    print(f"GOOGL  {df.index[0].date()} -> {df.index[-1].date()}  ({len(df)} bars)")
    print(f"Train -> {test.index[0].date()} | Test(OOS) {test.index[0].date()} -> "
          f"{test.index[-1].date()}  (train {len(train)} / test {len(test)})\n")

    records = {}
    for name, fn in strats.items():
        for seg_label, d in (("Train", train), ("Test(OOS)", test)):
            records[f"{name} [{seg_label}]"] = compute_metrics(run_backtest(d, fn(d)))
    print(pd.DataFrame(records).round(2).to_string())

    # Equity curves over the full history, with the train/test split marked.
    fig, ax = plt.subplots(figsize=(11, 5))
    for name, fn in strats.items():
        ax.plot(df.index, run_backtest(df, fn(df))["equity"], label=name, lw=1.3)
    ax.axvline(test.index[0], color="gray", ls="--", lw=1)
    ax.text(test.index[0], ax.get_ylim()[0], "  OOS ->", color="gray", va="bottom")
    ax.set_yscale("log")
    ax.set_ylabel("Equity (log scale, start = 1.0)")
    ax.set_title("GOOGL -- baseline strategy equity curves")
    ax.legend()
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(out / "baseline_equity.png", dpi=120)
    print(f"\nsaved plot -> {out / 'baseline_equity.png'}")
