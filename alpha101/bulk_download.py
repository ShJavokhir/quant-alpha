#!/usr/bin/env python3
"""Bulk-download daily OHLCV (2010-2014) for a broad US-equity universe via Yahoo.

Why daily (not 5-minute): Yahoo only serves intraday bars for ~the last 60 days,
so 5m for 2010-2014 is impossible on this source. Daily history goes back to IPO.

Universe : S&P 1500 (500 + 400 MidCap + 600 SmallCap) + Nasdaq-100 + Dow 30,
           pulled live from Wikipedia, deduped, with a hardcoded fallback core.
Adjust   : auto_adjust=True -> split/dividend-adjusted (matches download_data.py).
Resumable: existing non-empty CSVs are skipped, so re-running fills only the gaps.
Output   : data/<TICKER>_1d.csv  +  logs/manifest.csv (per-ticker status summary).

Survivorship note: this is the *current* index membership, so names that delisted
or went bankrupt in/after 2010-2014 are absent. A point-in-time universe needs a
paid source (CRSP etc.). Fine for research/backtesting demos; know the bias.

Env knobs: LIMIT=<n> (cap universe, for smoke tests), WORKERS=<n> (default 8).
Extra tickers can be appended as CLI args:  python bulk_download.py TSLA SHOP
"""
import io
import logging
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

# yfinance is chatty about delisted/failed tickers; keep our log readable.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
LOG_DIR = HERE / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

START = "2010-01-01"
END = "2015-01-01"          # end is exclusive in yfinance -> through 2014-12-31
INTERVAL = "1d"
WORKERS = int(os.environ.get("WORKERS", "8"))
RETRIES = 4
UA = {"User-Agent": "Mozilla/5.0 (compatible; research-data-fetch/1.0)"}

WIKI_SOURCES = {
    "S&P 500":    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "S&P 400":    "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "S&P 600":    "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
    "Nasdaq-100": "https://en.wikipedia.org/wiki/Nasdaq-100",
    "Dow 30":     "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
}

# Safety net so we always have a liquid core even if every web source breaks.
FALLBACK = ["AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "NVDA", "JPM", "JNJ",
            "XOM", "BAC", "WMT", "PG", "KO", "PFE", "CSCO", "INTC", "CVX", "HD", "DIS"]


def norm(sym: str) -> str:
    """Yahoo uses '-' for share-class dots: BRK.B -> BRK-B."""
    return sym.strip().upper().replace(".", "-")


def valid(sym: str) -> bool:
    return bool(sym) and len(sym) <= 6 and all(c.isalnum() or c == "-" for c in sym)


def get_universe() -> list[str]:
    tickers: set[str] = set()
    for name, url in WIKI_SOURCES.items():
        try:
            html = requests.get(url, headers=UA, timeout=20).text
            tables = pd.read_html(io.StringIO(html))
            got: set[str] = set()
            for tbl in tables:
                for col in tbl.columns:
                    if str(col) in ("Symbol", "Ticker"):
                        got |= {norm(str(v)) for v in tbl[col].dropna()}
            got = {s for s in got if valid(s)}
            print(f"  {name:11s}: {len(got):4d} tickers", flush=True)
            tickers |= got
        except Exception as e:
            print(f"  {name:11s}: FAILED ({type(e).__name__}: {e})", flush=True)
    tickers |= set(FALLBACK)
    if len(tickers) <= len(FALLBACK):
        print("  (web sources thin -> relying on fallback core)", flush=True)
    return sorted(tickers)


def fetch_one(ticker: str) -> dict:
    out = DATA_DIR / f"{ticker}_{INTERVAL}.csv"
    if out.exists() and out.stat().st_size > 0:
        with open(out) as fh:
            rows = sum(1 for _ in fh) - 1
        return {"ticker": ticker, "status": "skip", "rows": rows, "start": "", "end": "", "error": ""}

    last_err = "empty"
    for attempt in range(RETRIES):
        try:
            df = yf.Ticker(ticker).history(
                start=START, end=END, interval=INTERVAL, auto_adjust=True
            )
            if df is not None and not df.empty:
                df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(
                    subset=["Open", "High", "Low", "Close"]
                )
                if not df.empty:
                    df.index = df.index.date
                    df.index.name = "Date"
                    df.to_csv(out)
                    return {"ticker": ticker, "status": "ok", "rows": len(df),
                            "start": str(df.index[0]), "end": str(df.index[-1]), "error": ""}
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:100]}"
        time.sleep(1.5 * (attempt + 1) + random.random())  # backoff for rate limits
    return {"ticker": ticker, "status": "fail", "rows": 0, "start": "", "end": "", "error": last_err}


def main() -> None:
    print("Building universe from Wikipedia indices...", flush=True)
    universe = get_universe()
    for extra in sys.argv[1:]:
        n = norm(extra)
        if valid(n) and n not in universe:
            universe.append(n)

    limit = os.environ.get("LIMIT")
    if limit:
        universe = universe[: int(limit)]

    print(f"\nUniverse  : {len(universe)} unique tickers", flush=True)
    print(f"Range     : {START} -> {END} (exclusive)   interval={INTERVAL}", flush=True)
    print(f"Workers   : {WORKERS}   retries={RETRIES}\n", flush=True)

    results: list[dict] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(fetch_one, t): t for t in universe}
        done = 0
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            if done % 25 == 0 or done == len(universe):
                good = sum(1 for r in results if r["status"] in ("ok", "skip"))
                print(f"  [{done:4d}/{len(universe)}]  good={good:4d}  "
                      f"elapsed={time.time() - t0:5.0f}s", flush=True)

    manifest = pd.DataFrame(results).sort_values("ticker")
    manifest.to_csv(LOG_DIR / "manifest.csv", index=False)

    ok = manifest[manifest.status == "ok"]
    skip = manifest[manifest.status == "skip"]
    fail = manifest[manifest.status == "fail"]
    total_rows = int(manifest["rows"].clip(lower=0).sum())

    print("\n===== SUMMARY =====")
    print(f"  downloaded : {len(ok)}")
    print(f"  skipped    : {len(skip)} (already on disk)")
    print(f"  failed     : {len(fail)}")
    print(f"  total rows : {total_rows:,}")
    print(f"  wall time  : {time.time() - t0:.0f}s")
    print(f"  data dir   : {DATA_DIR}")
    print(f"  manifest   : {LOG_DIR / 'manifest.csv'}")
    if len(fail):
        print(f"  failed syms: {', '.join(fail.ticker.tolist()[:50])}"
              + (" ..." if len(fail) > 50 else ""))


if __name__ == "__main__":
    main()
