"""Pivot per-ticker daily CSVs into date x stock panels for Alpha101.

Output: panels.pkl = dict of wide DataFrames (rows=trading days, cols=tickers):
  open, high, low, close, volume, returns, vwap(approx), fwd(next-day return).
vwap is approximated as the typical price (H+L+C)/3 — we have no intraday/turnover
to compute true VWAP. fwd is the t->t+1 return, clipped to +/-50% to neutralize
the occasional adjusted-data glitch.
"""
import pickle
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "panels.pkl"


def load(fp: Path):
    ticker = fp.name[:-7]  # strip "_1d.csv"
    df = pd.read_csv(fp, usecols=["Date", "Open", "High", "Low", "Close", "Volume"],
                     parse_dates=["Date"], index_col="Date")
    return ticker, df


def main() -> None:
    files = sorted(DATA.glob("*_1d.csv"))
    print(f"reading {len(files)} csv files (32 threads) ...", flush=True)
    t0 = time.time()
    data = {}
    with ThreadPoolExecutor(max_workers=32) as ex:   # I/O-bound -> threads
        for ticker, df in ex.map(load, files):
            data[ticker] = df

    keymap = {"Open": "open", "High": "high", "Low": "low",
              "Close": "close", "Volume": "volume"}
    panels = {}
    for field, key in keymap.items():
        panels[key] = pd.DataFrame({t: df[field] for t, df in data.items()}).sort_index()

    close = panels["close"]
    panels["returns"] = close.pct_change()
    panels["vwap"] = (panels["high"] + panels["low"] + panels["close"]) / 3.0
    panels["fwd"] = panels["returns"].shift(-1).clip(-0.5, 0.5)   # next-day return

    idx = close.index
    print(f"panel shape : {close.shape[0]} days x {close.shape[1]} stocks", flush=True)
    print(f"date range  : {idx.min().date()} -> {idx.max().date()}", flush=True)
    print(f"NaN density : {close.isna().mean().mean():.1%} (mostly pre-IPO gaps)", flush=True)
    print(f"<250d stocks: {(close.notna().sum() < 250).sum()}", flush=True)
    if "AAPL" in close.columns:
        print(f"sanity AAPL : last close {float(close['AAPL'].dropna().iloc[-1]):.3f}", flush=True)

    with open(OUT, "wb") as fh:
        pickle.dump(panels, fh, protocol=4)
    print(f"saved {OUT.name} ({OUT.stat().st_size/1e6:.0f} MB) in {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
