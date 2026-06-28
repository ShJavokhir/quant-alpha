"""5-minute market data normalization, cache, and panel helpers.

This module is intentionally provider-light: Polygon/Alpaca clients can fetch raw
payloads elsewhere, then normalize through these functions. Unit tests can use
synthetic payloads without live credentials.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
import json
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd

EASTERN = ZoneInfo("America/New_York")
SESSION_START = time(9, 30)
SESSION_END = time(16, 0)
BARS_PER_DAY_5M = 78

BAR_COLUMNS = [
    "timestamp", "symbol", "open", "high", "low", "close", "volume",
    "vwap", "trades", "provider", "adjusted",
]


@dataclass(frozen=True)
class BarPanel5m:
    """Wide 5-minute OHLCV panel: each frame is timestamp x symbol."""

    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    volume: pd.DataFrame
    vwap: pd.DataFrame | None
    trades: pd.DataFrame | None
    returns: pd.DataFrame
    tradable: pd.DataFrame
    metadata: dict = field(default_factory=dict)

    @property
    def symbols(self) -> list[str]:
        return list(self.close.columns)


class MarketDataProvider:
    """Interface for provider adapters."""

    name = "provider"

    def fetch_5m_bars(self, symbols: list[str], start: str, end: str, adjusted: bool = True) -> pd.DataFrame:
        raise NotImplementedError


class PolygonProvider(MarketDataProvider):
    """Placeholder adapter boundary for Polygon/Massive.

    The backend can be tested without network credentials. A production adapter
    should fetch /v2/aggs/ticker/{ticker}/range/5/minute/{from}/{to}, then call
    normalize_polygon_aggs per symbol.
    """

    name = "polygon"


class AlpacaProvider(MarketDataProvider):
    """Placeholder adapter boundary for Alpaca market data."""

    name = "alpaca"


def _to_utc_timestamp(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(timezone.utc)
    return ts.tz_convert(timezone.utc)


def normalize_polygon_aggs(symbol: str, rows: Iterable[dict], adjusted: bool = True) -> pd.DataFrame:
    """Normalize Polygon/Massive aggregate rows into the canonical schema."""
    out = []
    for row in rows:
        out.append({
            "timestamp": _to_utc_timestamp(pd.to_datetime(row["t"], unit="ms", utc=True)),
            "symbol": symbol.upper(),
            "open": row.get("o"),
            "high": row.get("h"),
            "low": row.get("l"),
            "close": row.get("c"),
            "volume": row.get("v", 0),
            "vwap": row.get("vw"),
            "trades": row.get("n"),
            "provider": "polygon",
            "adjusted": bool(adjusted),
        })
    return validate_bars(pd.DataFrame(out, columns=BAR_COLUMNS))


def normalize_alpaca_bars(symbol: str, rows: Iterable[dict], adjusted: bool = True) -> pd.DataFrame:
    """Normalize Alpaca bar rows into the canonical schema.

    Accepts both compact Alpaca-style keys (t/o/h/l/c/v/vw/n) and verbose names.
    """
    out = []
    for row in rows:
        ts = row.get("t", row.get("timestamp"))
        out.append({
            "timestamp": _to_utc_timestamp(ts),
            "symbol": symbol.upper(),
            "open": row.get("o", row.get("open")),
            "high": row.get("h", row.get("high")),
            "low": row.get("l", row.get("low")),
            "close": row.get("c", row.get("close")),
            "volume": row.get("v", row.get("volume", 0)),
            "vwap": row.get("vw", row.get("vwap")),
            "trades": row.get("n", row.get("trades")),
            "provider": "alpaca",
            "adjusted": bool(adjusted),
        })
    return validate_bars(pd.DataFrame(out, columns=BAR_COLUMNS))


def validate_bars(bars: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in BAR_COLUMNS if c not in bars.columns]
    if missing:
        raise ValueError(f"missing canonical bar columns: {missing}")
    df = bars.loc[:, BAR_COLUMNS].copy()
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["symbol"] = df["symbol"].astype(str).str.upper()
    for col in ["open", "high", "low", "close", "volume", "vwap", "trades"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = df["volume"].fillna(0)
    df["provider"] = df["provider"].astype(str)
    df["adjusted"] = df["adjusted"].astype(bool)
    return df.sort_values(["timestamp", "symbol"]).reset_index(drop=True)


def filter_regular_session(bars: pd.DataFrame) -> pd.DataFrame:
    """Keep bars whose timestamp is in the regular US equity session.

    Bars are interpreted as start timestamps, so 15:55 is the final 5-minute
    regular-session bar. 16:00 is excluded to preserve 78 bars per full day.
    """
    df = validate_bars(bars)
    if df.empty:
        return df
    eastern = df["timestamp"].dt.tz_convert(EASTERN)
    t = eastern.dt.time
    return df[(t >= SESSION_START) & (t < SESSION_END)].reset_index(drop=True)


def _session_date(ts: pd.Series) -> pd.Series:
    return ts.dt.tz_convert(EASTERN).dt.strftime("%Y-%m-%d")


def write_bar_cache(bars: pd.DataFrame, cache_root: Path | str, provider: str) -> list[Path]:
    """Write bars to partitioned parquet files and return written paths."""
    df = validate_bars(bars)
    root = Path(cache_root) / "5m" / f"provider={provider}"
    if df.empty:
        root.mkdir(parents=True, exist_ok=True)
        return []
    written = []
    df = df.copy()
    df["_date"] = _session_date(df["timestamp"])
    for date, part in df.groupby("_date", sort=True):
        out_dir = root / f"date={date}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "bars.parquet"
        part.drop(columns=["_date"]).to_parquet(out, index=False)
        written.append(out)
    return written


def read_bar_cache(
    cache_root: Path | str,
    provider: str,
    start: str | None = None,
    end: str | None = None,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    root = Path(cache_root) / "5m" / f"provider={provider}"
    if not root.exists():
        raise FileNotFoundError(f"no 5m cache for provider {provider}: {root}")
    frames = []
    for path in sorted(root.glob("date=*/bars.parquet")):
        date = path.parent.name.split("=", 1)[1]
        if start and date < start:
            continue
        if end and date > end:
            continue
        frames.append(pd.read_parquet(path))
    if not frames:
        return validate_bars(pd.DataFrame(columns=BAR_COLUMNS))
    df = validate_bars(pd.concat(frames, ignore_index=True))
    if symbols is not None:
        wanted = {s.upper() for s in symbols}
        df = df[df["symbol"].isin(wanted)]
    return df.reset_index(drop=True)


def write_manifest(cache_root: Path | str, provider: str, manifest: dict) -> Path:
    root = Path(cache_root) / "5m" / f"provider={provider}"
    root.mkdir(parents=True, exist_ok=True)
    payload = dict(manifest)
    payload.setdefault("provider", provider)
    payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    out = root / "manifest.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return out


def read_manifest(cache_root: Path | str, provider: str) -> dict:
    p = Path(cache_root) / "5m" / f"provider={provider}" / "manifest.json"
    if not p.exists():
        raise FileNotFoundError(p)
    return json.loads(p.read_text())


def bars_to_panel(bars: pd.DataFrame, require_complete_session: bool = False) -> BarPanel5m:
    df = filter_regular_session(bars)
    if df.empty:
        empty = pd.DataFrame()
        return BarPanel5m(empty, empty, empty, empty, empty, None, None, empty, empty, {})

    symbols = sorted(df["symbol"].unique())

    def pivot(col: str) -> pd.DataFrame:
        return (df.pivot_table(index="timestamp", columns="symbol", values=col, aggfunc="last")
                  .sort_index()
                  .reindex(columns=symbols))

    open_ = pivot("open")
    high = pivot("high")
    low = pivot("low")
    close = pivot("close")
    volume = pivot("volume").fillna(0)
    vwap = pivot("vwap") if df["vwap"].notna().any() else None
    trades = pivot("trades") if df["trades"].notna().any() else None
    returns = close.pct_change().fillna(0.0)
    tradable = close.notna() & volume.gt(0)
    if require_complete_session:
        complete = tradable.sum(axis=1).eq(len(symbols))
        tradable = tradable.where(complete, False)

    meta = {
        "interval": "5m",
        "symbols": symbols,
        "start": str(close.index.min()),
        "end": str(close.index.max()),
        "survivorship_warning": "V1 uses a static current universe unless provider metadata says otherwise.",
    }
    return BarPanel5m(open_, high, low, close, volume, vwap, trades, returns, tradable, meta)

