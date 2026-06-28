"""5-minute market data normalization, cache, and panel helpers.

This module is intentionally provider-light: Polygon/Alpaca clients can fetch raw
payloads elsewhere, then normalize through these functions. Unit tests can use
synthetic payloads without live credentials.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
import json
import os
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
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


class ProviderError(RuntimeError):
    """Raised when a market data provider request cannot be completed."""


Transport = Callable[[str, dict[str, str] | None, int], dict]


def _json_get(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> dict:
    req = Request(url, headers=headers or {})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"provider HTTP {exc.code}: {body[:300]}") from exc
    except URLError as exc:
        raise ProviderError(f"provider request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("provider returned invalid JSON") from exc


def _credential(value: str | None, env_name: str) -> str | None:
    return value or os.getenv(env_name)


class MarketDataProvider:
    """Interface for provider adapters."""

    name = "provider"

    def fetch_5m_bars(self, symbols: list[str], start: str, end: str, adjusted: bool = True) -> pd.DataFrame:
        raise NotImplementedError


class PolygonProvider(MarketDataProvider):
    """Polygon/Massive 5-minute aggregate adapter."""

    name = "polygon"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.polygon.io",
        timeout: int = 30,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = _credential(api_key, "POLYGON_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport or _json_get

    def fetch_5m_bars(self, symbols: list[str], start: str, end: str, adjusted: bool = True) -> pd.DataFrame:
        if not self.api_key:
            raise ProviderError("POLYGON_API_KEY is required for Polygon ingestion")
        frames = []
        for symbol in symbols:
            ticker = symbol.upper()
            params = urlencode({
                "adjusted": str(bool(adjusted)).lower(),
                "sort": "asc",
                "limit": 50000,
                "apiKey": self.api_key,
            })
            url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/5/minute/{start}/{end}?{params}"
            payload = self.transport(url, None, self.timeout)
            rows = payload.get("results") or []
            if rows:
                frames.append(normalize_polygon_aggs(ticker, rows, adjusted))
        if not frames:
            return validate_bars(pd.DataFrame(columns=BAR_COLUMNS))
        return validate_bars(pd.concat(frames, ignore_index=True))


class AlpacaProvider(MarketDataProvider):
    """Alpaca market data 5-minute bar adapter."""

    name = "alpaca"

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        base_url: str = "https://data.alpaca.markets",
        feed: str | None = None,
        timeout: int = 30,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = _credential(api_key, "ALPACA_API_KEY") or _credential(None, "APCA_API_KEY_ID")
        self.secret_key = _credential(secret_key, "ALPACA_SECRET_KEY") or _credential(None, "APCA_API_SECRET_KEY")
        self.base_url = base_url.rstrip("/")
        self.feed = feed or os.getenv("ALPACA_DATA_FEED")
        self.timeout = timeout
        self.transport = transport or _json_get

    def fetch_5m_bars(self, symbols: list[str], start: str, end: str, adjusted: bool = True) -> pd.DataFrame:
        if not self.api_key or not self.secret_key:
            raise ProviderError("ALPACA_API_KEY and ALPACA_SECRET_KEY are required for Alpaca ingestion")
        headers = {"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.secret_key}
        params = {
            "symbols": ",".join(s.upper() for s in symbols),
            "timeframe": "5Min",
            "start": start,
            "end": end,
            "adjustment": "all" if adjusted else "raw",
            "limit": 10000,
        }
        if self.feed:
            params["feed"] = self.feed
        frames = []
        page_token = None
        while True:
            q = dict(params)
            if page_token:
                q["page_token"] = page_token
            url = f"{self.base_url}/v2/stocks/bars?{urlencode(q)}"
            payload = self.transport(url, headers, self.timeout)
            bars_by_symbol = payload.get("bars") or {}
            for symbol, rows in bars_by_symbol.items():
                if rows:
                    frames.append(normalize_alpaca_bars(symbol, rows, adjusted))
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        if not frames:
            return validate_bars(pd.DataFrame(columns=BAR_COLUMNS))
        return validate_bars(pd.concat(frames, ignore_index=True))


def get_provider(name: str, **kwargs) -> MarketDataProvider:
    provider = name.lower()
    if provider == "polygon":
        return PolygonProvider(**kwargs)
    if provider == "alpaca":
        return AlpacaProvider(**kwargs)
    raise ValueError(f"unsupported 5m provider: {name}")


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


def ingest_5m_bars(
    provider: MarketDataProvider,
    symbols: list[str],
    start: str,
    end: str,
    cache_root: Path | str,
    adjusted: bool = True,
    universe: str = "custom",
    regular_session_only: bool = True,
) -> dict:
    requested = [s.upper() for s in symbols]
    bars = provider.fetch_5m_bars(requested, start, end, adjusted=adjusted)
    bars = filter_regular_session(bars) if regular_session_only else validate_bars(bars)
    written = write_bar_cache(bars, cache_root, provider.name)
    found = sorted(bars["symbol"].unique()) if not bars.empty else []
    missing = sorted(set(requested) - set(found))
    manifest = {
        "provider": provider.name,
        "universe": universe,
        "symbols_requested": requested,
        "symbols_found": found,
        "missing_symbols": missing,
        "start": start,
        "end": end,
        "bar_interval": "5m",
        "regular_session_only": regular_session_only,
        "session": "09:30-16:00 America/New_York" if regular_session_only else "provider_raw",
        "adjusted": bool(adjusted),
        "rows": int(len(bars)),
        "cache_files": [str(p) for p in written],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "survivorship_warning": "V1 uses the requested static universe; current S&P 500 constituent runs are survivor-biased.",
    }
    manifest_path = write_manifest(cache_root, provider.name, manifest)
    return {**manifest, "manifest_path": str(manifest_path)}




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

