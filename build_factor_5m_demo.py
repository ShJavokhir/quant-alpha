"""Build deterministic 5-minute cross-sectional replay artifacts.

This demo is synthetic by design: it validates the 5m research pipeline without
Polygon/Alpaca credentials or network access. Output: runs/factor_5m_demo/.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_data_5m import bars_to_panel
from portfolio_5m import PortfolioConfig5m
from walkforward_5m import WalkForwardConfig5m, walk_forward_factor_5m, write_walkforward_artifacts

ROOT = Path(__file__).parent
RUN_DIR = ROOT / "runs" / "factor_5m_demo"


def synthetic_bars(days: int = 8, bars_per_day: int = 78) -> pd.DataFrame:
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ"]
    rows = []
    for day_i, day in enumerate(pd.bdate_range("2024-01-02", periods=days)):
        start = pd.Timestamp(f"{day.date()} 14:30", tz="UTC")
        for bar_i, ts in enumerate(pd.date_range(start, periods=bars_per_day, freq="5min")):
            for sym_i, sym in enumerate(symbols):
                drift = (sym_i - 4.5) * 0.0006
                reversal = -0.0003 * ((bar_i % 12) - 6)
                close = 100 + sym_i * 3 + day_i * 0.2 + bar_i * (0.01 + drift + reversal)
                rows.append({
                    "timestamp": ts,
                    "symbol": sym,
                    "open": close - 0.03,
                    "high": close + 0.08,
                    "low": close - 0.08,
                    "close": close,
                    "volume": 5000 + 50 * sym_i + bar_i,
                    "vwap": close - 0.01,
                    "trades": 20 + bar_i,
                    "provider": "synthetic",
                    "adjusted": True,
                })
    return pd.DataFrame(rows)


def main() -> None:
    panel = bars_to_panel(synthetic_bars())
    result = walk_forward_factor_5m(
        panel,
        "intraday_momentum",
        param_grid=[{"lookback": 1}, {"lookback": 3}, {"lookback": 6}],
        portfolio_config=PortfolioConfig5m(top_quantile=0.2, bottom_quantile=0.2, rebalance_every=1),
        config=WalkForwardConfig5m(is_days=4, oos_days=2, step_days=2, min_is_bars=78, min_oos_bars=78),
    )
    result["metadata"] = {
        "data": "synthetic 5-minute bars",
        "session": "09:30-16:00 America/New_York",
        "survivorship_warning": "Provider-backed V1 runs use a static requested universe and are survivor-biased unless supplied historical membership metadata says otherwise.",
    }
    write_walkforward_artifacts(RUN_DIR, result)
    print(f"wrote {RUN_DIR / 'walkforward.json'}")


if __name__ == "__main__":
    main()
