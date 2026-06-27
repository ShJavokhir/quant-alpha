"""Download historical daily stock candles from Yahoo Finance.

Usage:
    python download_data.py              # defaults to GOOGL, full history
    python download_data.py MSFT AAPL    # one or more tickers
"""
import sys
from pathlib import Path

import yfinance as yf

DATA_DIR = Path(__file__).parent / "data"


def download(ticker: str, period: str = "max", interval: str = "1d") -> Path:
    """Pull OHLCV candles for one ticker, save to CSV, and verify."""
    ticker = ticker.upper()
    DATA_DIR.mkdir(exist_ok=True)

    # auto_adjust=True -> prices are split/dividend adjusted (standard for backtesting)
    df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        raise SystemExit(f"No data returned for {ticker!r} — check the symbol.")

    df = df[["Open", "High", "Low", "Close", "Volume"]]

    # Drop malformed rows (yfinance sometimes returns a price-less last row).
    before = len(df)
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    dropped = before - len(df)

    # Daily data: collapse the tz-aware timestamp index to plain dates for clean CSVs.
    if interval.endswith(("d", "wk", "mo")):
        df.index = df.index.date
        df.index.name = "Date"

    out = DATA_DIR / f"{ticker}_{interval}.csv"
    df.to_csv(out)

    # --- verification ---
    nans = int(df.isna().sum().sum())
    print(f"\n{ticker}  ({interval})")
    print(f"  rows      : {len(df):,}")
    print(f"  range     : {df.index[0]} -> {df.index[-1]}")
    print(f"  dropped   : {dropped} malformed row(s)")
    print(f"  NaNs      : {nans}")
    print(f"  saved     : {out}")
    print(df.head(3).to_string())
    print("  ...")
    print(df.tail(3).to_string())
    return out


if __name__ == "__main__":
    tickers = sys.argv[1:] or ["GOOGL"]
    for t in tickers:
        download(t)
