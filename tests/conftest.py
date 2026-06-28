from __future__ import annotations

import pandas as pd

from market_data_5m import bars_to_panel


def synthetic_bars(days=2, symbols=("AAA", "BBB", "CCC", "DDD", "EEE"), bars_per_day=78):
    rows = []
    for day in pd.bdate_range("2024-01-02", periods=days):
        start = pd.Timestamp(f"{day.date()} 14:30", tz="UTC")
        times = pd.date_range(start, periods=bars_per_day, freq="5min")
        for i, ts in enumerate(times):
            for j, sym in enumerate(symbols):
                close = 100 + j * 10 + i * (0.01 + j * 0.001)
                rows.append({
                    "timestamp": ts,
                    "symbol": sym,
                    "open": close - 0.05,
                    "high": close + 0.1,
                    "low": close - 0.1,
                    "close": close,
                    "volume": 1000 + i + j,
                    "vwap": close - 0.02,
                    "trades": 10 + i,
                    "provider": "polygon",
                    "adjusted": True,
                })
    return pd.DataFrame(rows)


def synthetic_panel(days=2, symbols=("AAA", "BBB", "CCC", "DDD", "EEE"), bars_per_day=78):
    return bars_to_panel(synthetic_bars(days, symbols, bars_per_day))
