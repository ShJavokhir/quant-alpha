"""Ingest provider 5-minute bars into the local Parquet cache.

Credentials are read from environment variables:
  Polygon: POLYGON_API_KEY
  Alpaca:  ALPACA_API_KEY/ALPACA_SECRET_KEY or APCA_API_KEY_ID/APCA_API_SECRET_KEY
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from market_data_5m import ProviderError, get_provider, ingest_5m_bars

ROOT = Path(__file__).parent


def _symbols(value: str | None, file_path: str | None) -> list[str]:
    items: list[str] = []
    if value:
        items.extend(part.strip() for part in value.split(","))
    if file_path:
        for line in Path(file_path).read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                items.append(stripped.split(",")[0].strip())
    symbols = sorted({item.upper() for item in items if item})
    if not symbols:
        raise SystemExit("provide --symbols or --symbols-file")
    return symbols


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest 5-minute provider bars into data/cache/5m")
    parser.add_argument("--provider", choices=["polygon", "alpaca"], required=True)
    parser.add_argument("--symbols", help="Comma-separated tickers, e.g. AAPL,MSFT,NVDA")
    parser.add_argument("--symbols-file", help="Newline or CSV-like file; first column is ticker")
    parser.add_argument("--start", required=True, help="Start date/time accepted by provider")
    parser.add_argument("--end", required=True, help="End date/time accepted by provider")
    parser.add_argument("--cache-root", default=str(ROOT / "data" / "cache"))
    parser.add_argument("--universe", default="custom")
    parser.add_argument("--raw", action="store_true", help="Request raw/unadjusted bars when supported")
    parser.add_argument("--include-extended", action="store_true", help="Cache provider bars outside 09:30-16:00 ET")
    parser.add_argument("--base-url", help="Override provider base URL, useful for tests/proxies")
    parser.add_argument("--feed", help="Alpaca feed, e.g. iex or sip")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    provider_kwargs = {"timeout": args.timeout}
    if args.base_url:
        provider_kwargs["base_url"] = args.base_url
    if args.provider == "alpaca" and args.feed:
        provider_kwargs["feed"] = args.feed

    try:
        provider = get_provider(args.provider, **provider_kwargs)
        manifest = ingest_5m_bars(
            provider,
            symbols=_symbols(args.symbols, args.symbols_file),
            start=args.start,
            end=args.end,
            cache_root=Path(args.cache_root),
            adjusted=not args.raw,
            universe=args.universe,
            regular_session_only=not args.include_extended,
        )
    except ProviderError as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
