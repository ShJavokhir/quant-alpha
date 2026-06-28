"""Shared config: paths, env loading, panel loader, model names."""
import os
import pickle
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "lab"
DATA = LAB / "data"
RUNS = ROOT / "runs"
RUNS.mkdir(exist_ok=True)

# model / api config
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
VOYAGE_MODEL = os.environ.get("VOYAGE_MODEL", "voyage-3.5")
EMBED_DIM = 1024

_ENV_LOADED = False


def load_env():
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    envfile = ROOT / ".env"
    if envfile.exists():
        for line in envfile.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    _ENV_LOADED = True


@lru_cache(maxsize=2)
def load_panel(which: str = "ext") -> dict:
    """Load a panel dict. which='ext' (2010-2024) falls back to base (2010-2014)."""
    ext = DATA / "panels_ext.pkl"
    base = DATA / "panels.pkl"
    fp = ext if (which == "ext" and ext.exists()) else base
    with open(fp, "rb") as f:
        return pickle.load(f)
