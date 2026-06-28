"""Download the Alpha101 formula reference used by alpha_engine.py.

It is NOT vendored in this repo because the source project carries no license.
Run once:  python fetch_reference.py

Source: https://github.com/yli188/WorldQuant_alpha101_code  (101Alpha_code_1.py)
"""
import sys
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parent / "alpha101_ref.py"
URLS = [
    "https://raw.githubusercontent.com/yli188/WorldQuant_alpha101_code/master/101Alpha_code_1.py",
    "https://raw.githubusercontent.com/yli188/WorldQuant_alpha101_code/main/101Alpha_code_1.py",
]

for url in URLS:
    try:
        data = urllib.request.urlopen(url, timeout=30).read()
        DEST.write_bytes(data)
        print(f"saved {DEST.name} ({len(data):,} bytes) from {url}")
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        print(f"  failed {url} -> {e}")

print("ERROR: could not fetch the reference file.", file=sys.stderr)
sys.exit(1)
