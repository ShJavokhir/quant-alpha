"""Resumable extended OHLCV downloader: 2010-01-01 .. 2024-12-31, daily.

Reuses the box ticker universe (lab/data/box_tickers.txt). Downloads in batches
via yfinance, writes one CSV per ticker to lab/data/raw_ext/<TICKER>.csv with
columns Date,Open,High,Low,Close,Volume (split/div-adjusted Close via auto_adjust).
Skips tickers already on disk -> safe to re-run.
"""
import sys, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
OUT = HERE / "raw_ext"
OUT.mkdir(exist_ok=True)
START, END = "2010-01-01", "2025-01-01"
BATCH = 40

tickers = [t.strip() for t in (HERE / "box_tickers.txt").read_text().splitlines() if t.strip()]
todo = [t for t in tickers if not (OUT / f"{t}.csv").exists()]
print(f"universe={len(tickers)} todo={len(todo)} (already={len(tickers)-len(todo)})", flush=True)

def save_one(tk, df):
    if df is None or df.empty:
        return False
    df = df.rename(columns=str.title)
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    if len(keep) < 5:
        return False
    out = df[keep].copy()
    out.index.name = "Date"
    out = out.dropna(how="all")
    if len(out) < 200:   # need a meaningful history
        return False
    out.to_csv(OUT / f"{tk}.csv")
    return True

ok = fail = 0
for i in range(0, len(todo), BATCH):
    batch = todo[i:i+BATCH]
    for attempt in range(3):
        try:
            data = yf.download(batch, start=START, end=END, progress=False,
                               auto_adjust=True, threads=True, group_by="ticker")
            break
        except Exception as e:
            print(f"  batch {i} attempt {attempt} err {e}", flush=True)
            time.sleep(5 * (attempt + 1))
    else:
        continue
    for tk in batch:
        try:
            if len(batch) == 1:
                df = data
            else:
                df = data[tk] if tk in data.columns.get_level_values(0) else None
            if save_one(tk, df):
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1
    print(f"  {i+len(batch)}/{len(todo)} ok={ok} fail={fail} elapsed_batches", flush=True)
    time.sleep(1.0)

print(f"DONE ok={ok} fail={fail} files={len(list(OUT.glob('*.csv')))}", flush=True)
