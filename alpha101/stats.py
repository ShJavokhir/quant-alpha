#!/usr/bin/env python3
"""Full dataset stats for the 2010-2014 daily OHLCV pull (scans data/ directly)."""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
LOG = HERE / "logs"


def human(n: float) -> str:
    for u in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


recs, total_bytes = [], 0
for f in sorted(DATA.glob("*_1d.csv")):
    b = f.stat().st_size
    total_bytes += b
    lines = f.read_text().splitlines()
    n = len(lines) - 1
    if n <= 0:
        continue
    recs.append({
        "ticker": f.name.replace("_1d.csv", ""),
        "rows": n,
        "start": lines[1].split(",")[0],
        "end": lines[-1].split(",")[0],
        "bytes": b,
    })

df = pd.DataFrame(recs)
df["start"] = pd.to_datetime(df["start"])
df["end"] = pd.to_datetime(df["end"])
n_tickers = len(df)
total_rows = int(df.rows.sum())

print("=" * 62)
print("   QUANT-ALPHA DATASET  —  DAILY OHLCV  (Yahoo, auto-adjusted)")
print("=" * 62)
print("  VOLUME")
print(f"    Stocks (CSV files)   : {n_tickers:,}")
print(f"    Total rows (bars)    : {total_rows:,}")
print(f"    Avg bars / stock     : {total_rows / n_tickers:.0f}")
print(f"    Disk size (data/)    : {human(total_bytes)}")
print(f"    Avg file size        : {human(total_bytes / n_tickers)}")
print(f"    Largest file         : {df.loc[df.bytes.idxmax()].ticker} "
      f"({human(df.bytes.max())})")
print()
print("  HISTORY")
print(f"    Requested window     : 2010-01-01 -> 2014-12-31")
print(f"    Actual coverage      : {df.start.min().date()}  ->  {df.end.max().date()}")
print(f"    Interval             : 1d (daily)")
FULL = 1250
print(f"    Full ~5y history     : {len(df[df.rows >= FULL]):,} stocks (>= {FULL} bars)")
print(f"    IPO'd mid-window     : {len(df[df.start > pd.Timestamp('2010-01-15')]):,} "
      f"stocks (first bar after 2010-01-15)")
print()
print("  HISTORY-DEPTH BUCKETS")
for lo, hi, lab in [(0, 252, "< 1 year"), (252, 756, "1-3 years"),
                    (756, 1250, "3-5 years"), (1250, 10**9, "full 5 years")]:
    print(f"    {lab:13s}: {len(df[(df.rows >= lo) & (df.rows < hi)]):4d} stocks")
print()
print("  STOCKS WITH DATA, BY YEAR")
for y in range(2010, 2015):
    ys, ye = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y}-12-31")
    print(f"    {y}: {len(df[(df.start <= ye) & (df.end >= ys)]):4d}")
print()
print("  SANITY SPOT-CHECKS")
lo = df.sort_values('rows', ascending=False).head(3)
sh = df.sort_values('rows').head(3)
print("    Deepest : " + ", ".join(f"{r.ticker}({r.rows})" for _, r in lo.iterrows()))
print("    Shallow : " + ", ".join(f"{r.ticker}({r.rows} from {r.start.date()})"
                                   for _, r in sh.iterrows()))
print()

man = LOG / "manifest.csv"
if man.exists():
    m = pd.read_csv(man)
    universe = len(m)
    fails = m[m.status == "fail"]
    print("  COVERAGE vs UNIVERSE")
    print(f"    Universe attempted   : {universe:,} (S&P 1500 + Nasdaq-100 + Dow, deduped)")
    print(f"    Got data             : {n_tickers:,}  ({100*n_tickers/universe:.0f}%)")
    print(f"    No 2010-2014 data    : {len(fails):,}  (post-window IPOs / spinoffs)")
    print(f"      e.g. {', '.join(fails.ticker.head(20).tolist())} ...")
print()
print(f"  Per-ticker manifest    : {man}")
print(f"  Data directory         : {DATA}")
print("=" * 62)
