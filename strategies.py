"""Strategy templates + registry for the research lab.

A *template* is a parameterized callable:  template(df, **params) -> pd.Series

  input  : OHLCV DataFrame indexed by date (cols: Open, High, Low, Close, Volume)
  output : target position per bar in {-1, 0, +1}
           (-1 = short, 0 = flat, +1 = long), aligned to df.index.

CRITICAL RULE (the backtester enforces execution timing, but respect it here):
the position decided for bar t may use data up to and INCLUDING bar t's close,
then it is HELD over bar t+1. Never peek ahead. Rolling/expanding windows look
backward and are fine; `.shift(-k)` (future data) is forbidden.

TEMPLATES (bottom of file) is the palette the LLM 'researcher' picks from and the
walk-forward optimizer tunes. Each entry = {fn, grid, valid?}.
"""
import numpy as np
import pandas as pd


def buy_and_hold(df: pd.DataFrame) -> pd.Series:
    """Benchmark: always long. The bar every strategy must beat."""
    return pd.Series(1.0, index=df.index)


def sma_crossover(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.Series:
    """Trend-follow: long when fast SMA > slow SMA, else flat."""
    fast_ma = df["Close"].rolling(fast).mean()
    slow_ma = df["Close"].rolling(slow).mean()
    return (fast_ma > slow_ma).astype(float)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def rsi_reversion(df: pd.DataFrame, period: int = 14,
                  low: int = 30, high: int = 70) -> pd.Series:
    """Mean-reversion: long when RSI dips below `low` (oversold),
    hold until RSI rises above `high` (overbought), then flat."""
    rsi = _rsi(df["Close"], period)
    state = pd.Series(np.nan, index=df.index)
    state[rsi < low] = 1.0    # enter long when oversold
    state[rsi > high] = 0.0   # exit when overbought
    return state.ffill().fillna(0.0)  # carry state forward (past info only)


def multi_filter(df: pd.DataFrame, sma_fast: int = 20, sma_slow: int = 100,
                 rsi_period: int = 14, rsi_max: int = 70,
                 mom_lookback: int = 20) -> pd.Series:
    """Overfit-prone by design: long only when a trend filter, an RSI 'not
    overbought' filter, and a momentum filter all agree. Five knobs -> lots of
    room to curve-fit on short windows. This is the template the guardrail is
    meant to catch when the optimizer gets greedy."""
    close = df["Close"]
    trend = close.rolling(sma_fast).mean() > close.rolling(sma_slow).mean()
    not_overbought = _rsi(close, rsi_period) < rsi_max
    momentum = close.pct_change(mom_lookback) > 0
    return (trend & not_overbought & momentum).astype(float)


# --- the palette: name -> {fn, grid, valid?, kind} -------------------------
# `kind` groups templates by the KIND of edge so the routing policy can abandon a
# failed kind and route to a different one (trend <-> mean_reversion).
TEMPLATES = {
    "sma_crossover": {
        "fn": sma_crossover,
        "grid": {"fast": [10, 20, 50], "slow": [50, 100, 200]},
        "valid": lambda p: p["fast"] < p["slow"],
        "kind": "trend",
    },
    "rsi_reversion": {
        "fn": rsi_reversion,
        "grid": {"period": [7, 14, 21], "low": [20, 30], "high": [70, 80]},
        "valid": lambda p: p["low"] < p["high"],
        "kind": "mean_reversion",
    },
    "multi_filter": {
        "fn": multi_filter,
        "grid": {"sma_fast": [10, 20], "sma_slow": [50, 100], "rsi_period": [14],
                 "rsi_max": [70], "mom_lookback": [20]},
        "valid": lambda p: p["sma_fast"] < p["sma_slow"],
        "kind": "trend",
    },
}

KINDS = {name: cfg["kind"] for name, cfg in TEMPLATES.items()}


def families_of_kind(kind: str) -> list[str]:
    return [name for name, k in KINDS.items() if k == kind]
