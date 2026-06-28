"""Fleet utilities: liquid universe, portfolio combination, redundancy correlation."""
import numpy as np
import pandas as pd

from ..engine import backtest


def liquid_universe(panel: dict, n=600) -> list:
    """Top-n tickers by median daily dollar volume (tradeable names)."""
    dollar = (panel["close"] * panel["volume"]).median(axis=0)
    return list(dollar.sort_values(ascending=False).head(n).index)


def restrict(panel: dict, tickers) -> dict:
    return {k: (v[tickers] if isinstance(v, pd.DataFrame) and set(tickers).issubset(v.columns) else v)
            for k, v in panel.items()}


def slice_panel(panel: dict, start, end) -> dict:
    out = {}
    for k, v in panel.items():
        if isinstance(v, pd.DataFrame):
            idx = v.index
            mask = (idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))
            out[k] = v.loc[mask]
        else:
            out[k] = v
    return out


def combine_signals(signals: dict, orient: dict, weights: dict, smooth: int = 3) -> pd.DataFrame:
    """Weighted, oriented average of cross-sectional ranks -> one combined signal.

    Each alpha's raw signal is rank-normalized across stocks (0..1), demeaned, flipped
    so its training IC is positive (orient), scaled by weight, and summed. The combined
    signal is then lightly smoothed (trailing mean over `smooth` days) — a standard
    turnover-reduction step that materially lifts net-of-cost performance. Applied
    identically to every arm so comparisons stay fair.
    """
    combined = None
    for name, sig in signals.items():
        w = float(weights.get(name, 0.0))
        if w <= 0:
            continue
        r = sig.rank(axis=1, pct=True)
        r = r.sub(r.mean(axis=1), axis=0) * float(orient.get(name, 1.0)) * w
        combined = r if combined is None else combined.add(r, fill_value=0.0)
    if combined is not None and smooth and smooth > 1:
        combined = combined.rolling(int(smooth), min_periods=1).mean()
    return combined


def pnl_series(signals: dict, panel: dict, start=None, end=None) -> pd.DataFrame:
    """Per-alpha daily L/S pnl on a window (columns=alpha names) for correlation."""
    cols = {}
    for name, sig in signals.items():
        m = backtest.evaluate_signal(sig, panel, start=start, end=end, with_series=True)
        cols[name] = m["_series"]["pnl"]
    return pd.DataFrame(cols)


def redundancy(pnls: pd.DataFrame) -> pd.DataFrame:
    """Pairwise correlation of alpha PnL streams (redundancy matrix)."""
    return pnls.corr()
