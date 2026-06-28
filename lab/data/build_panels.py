"""Pivot per-ticker daily CSVs into date x stock panels.

Usage:
  python build_panels.py raw      -> panels.pkl   (box 2010-2014, files TICKER_1d.csv)
  python build_panels.py raw_ext  -> panels_ext.pkl (2010-2024, files TICKER.csv)

Output dict of wide DataFrames (rows=trading days, cols=tickers):
  open, high, low, close, volume, returns, vwap(approx=(H+L+C)/3), fwd(next-day ret).
fwd clipped to +/-50% to neutralize adjusted-data glitches.
"""
import pickle, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent


def load(fp: Path):
    name = fp.name
    ticker = name[:-7] if name.endswith("_1d.csv") else name[:-4]
    df = pd.read_csv(fp, usecols=["Date", "Open", "High", "Low", "Close", "Volume"],
                     parse_dates=["Date"], index_col="Date")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return ticker, df


def build(src="raw"):
    DATA = HERE / src
    OUT = HERE / ("panels.pkl" if src == "raw" else "panels_ext.pkl")
    files = sorted(DATA.glob("*.csv"))
    print(f"reading {len(files)} csv from {DATA} (32 threads) ...", flush=True)
    t0 = time.time()
    data = {}
    with ThreadPoolExecutor(max_workers=32) as ex:
        for ticker, df in ex.map(load, files):
            if len(df) >= 250:
                data[ticker] = df
    keymap = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    panels = {key: pd.DataFrame({t: df[field] for t, df in data.items()}).sort_index()
              for field, key in keymap.items()}
    close = panels["close"]
    panels["returns"] = close.pct_change()
    panels["vwap"] = (panels["high"] + panels["low"] + panels["close"]) / 3.0
    panels["fwd"] = panels["returns"].shift(-1).clip(-0.5, 0.5)

    idx = close.index
    print(f"panel shape : {close.shape[0]} days x {close.shape[1]} stocks", flush=True)
    print(f"date range  : {idx.min().date()} -> {idx.max().date()}", flush=True)
    print(f"NaN density : {close.isna().mean().mean():.1%}", flush=True)
    with open(OUT, "wb") as fh:
        pickle.dump(panels, fh, protocol=4)
    print(f"saved {OUT.name} ({OUT.stat().st_size/1e6:.0f} MB) in {time.time()-t0:.1f}s", flush=True)
    return OUT


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "raw")
