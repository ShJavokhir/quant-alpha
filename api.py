"""FastAPI backend for the Research Lab UI.

Serves the journal and RECOMPUTES equity / candle / trade data from stored params
on demand (params -> curves), so the frontend stays thin and any strategy is
re-simulatable. Run:  uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import strategies as st
from backtest import compute_metrics, run_backtest
from walkforward import optimize, walk_forward

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
RUNS_DIR = ROOT / "runs"

app = FastAPI(title="Quant Research Lab API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

_cache: dict[str, pd.DataFrame] = {}


def load_ticker(tk: str) -> pd.DataFrame:
    tk = tk.upper()
    if tk not in _cache:
        p = DATA_DIR / f"{tk}_1d.csv"
        if not p.exists():
            raise HTTPException(404, f"no data for {tk}")
        _cache[tk] = pd.read_csv(p, index_col=0, parse_dates=True)
    return _cache[tk]


def _runs() -> list[str]:
    return sorted(d.name for d in RUNS_DIR.iterdir() if d.is_dir()) if RUNS_DIR.exists() else []


def _resolve(run_id: str) -> str:
    if run_id == "latest":
        runs = _runs()
        if not runs:
            raise HTTPException(404, "no runs yet")
        return runs[-1]
    return run_id


def _journal(run_id: str) -> list[dict]:
    p = RUNS_DIR / run_id / "journal.jsonl"
    if not p.exists():
        raise HTTPException(404, f"no run {run_id}")
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _num(v):
    return round(float(v), 3) if isinstance(v, (int, float)) and math.isfinite(v) else None


def _equity_curve(df: pd.DataFrame, signal: pd.Series) -> list[dict]:
    eq = run_backtest(df, signal)["equity"]
    return [{"time": str(d.date()), "value": round(float(v), 4)} for d, v in eq.items()]


@app.get("/api/health")
def health():
    return {"ok": True, "runs": _runs(), "tickers": sorted(p.stem.replace("_1d", "")
            for p in DATA_DIR.glob("*_1d.csv"))}


@app.get("/api/runs")
def list_runs():
    runs = _runs()
    return {"runs": runs, "latest": runs[-1] if runs else None}


@app.get("/api/runs/{run_id}/journal")
def get_journal(run_id: str):
    run_id = _resolve(run_id)
    return {"run_id": run_id, "experiments": _journal(run_id)}


@app.get("/api/runs/{run_id}/summary")
def get_summary(run_id: str):
    run_id = _resolve(run_id)
    p = RUNS_DIR / run_id / "summary.json"
    if not p.exists():
        raise HTTPException(404, "no summary")
    return json.loads(p.read_text())


def _find_exp(run_id: str, iteration: int) -> dict:
    for e in _journal(run_id):
        if e["iteration"] == iteration:
            return e
    raise HTTPException(404, f"no experiment {iteration}")


@app.get("/api/runs/{run_id}/experiments/{iteration}/overfit")
def overfit_reveal(run_id: str, iteration: int, ticker: str = "SPY"):
    """The hero panel: pick this experiment's MOST overfit fold (biggest IS->OOS
    gap), then return the in-sample equity (soaring) vs out-of-sample (collapsing)."""
    run_id = _resolve(run_id)
    exp = _find_exp(run_id, iteration)
    df = load_ticker(ticker)
    tmpl = st.TEMPLATES[exp["template"]]
    folds = walk_forward(df, tmpl["fn"], exp["grid"], tmpl.get("valid"), **exp["windows"])
    if not folds:
        raise HTTPException(422, "not enough history for this ticker/window")

    fold = max(folds, key=lambda f: f["is_sharpe"] - f["oos_sharpe"])
    params = fold["params"]
    is_df = df.loc[str(fold["is_start"]):str(fold["oos_start"])]
    oos_df = df.loc[str(fold["oos_start"]):str(fold["oos_end"])]

    def sig(d):
        return tmpl["fn"](d, **params)

    return {
        "ticker": ticker, "template": exp["template"], "iteration": iteration,
        "params": params, "verdict": exp["verdict"],
        "is": {"sharpe": _num(fold["is_sharpe"]), "from": str(fold["is_start"]),
               "curve": _equity_curve(is_df, sig(is_df))},
        "oos": {"sharpe": _num(fold["oos_sharpe"]), "from": str(fold["oos_start"]),
                "curve": _equity_curve(oos_df, sig(oos_df))},
        "benchmark_oos": _equity_curve(oos_df, st.buy_and_hold(oos_df)),
        "gap": _num(fold["is_sharpe"] - fold["oos_sharpe"]),
    }


@app.get("/api/simulate")
def simulate(ticker: str = "SPY", template: str = "rsi_reversion", years: int = 5):
    """Bar-by-bar replay data for the trading simulator: candles + equity + trade
    markers for the template's best params (optimized on history, illustrative)."""
    df = load_ticker(ticker)
    if template not in st.TEMPLATES:
        raise HTTPException(404, f"unknown template {template}")
    tmpl = st.TEMPLATES[template]
    params, _ = optimize(df, tmpl["fn"], tmpl["grid"], tmpl.get("valid"))
    if params is None:
        raise HTTPException(422, "no valid params")

    d = df.loc[df.index[-1] - pd.DateOffset(years=years):]
    bt = run_backtest(d, tmpl["fn"](d, **params))
    held = bt["held"]

    trades, prev = [], 0.0
    for date, h in held.items():
        if h != prev:
            trades.append({"time": str(date.date()),
                           "type": "entry" if h > prev else "exit",
                           "price": round(float(d.loc[date, "Close"]), 2)})
            prev = h

    candles = [{"time": str(dt.date()), "open": round(float(r.Open), 2),
                "high": round(float(r.High), 2), "low": round(float(r.Low), 2),
                "close": round(float(r.Close), 2)} for dt, r in d.iterrows()]
    equity = [{"time": str(dt.date()), "value": round(float(v), 4)}
              for dt, v in bt["equity"].items()]

    return {"ticker": ticker, "template": template, "params": params,
            "metrics": {k: _num(v) for k, v in compute_metrics(bt).items()},
            "candles": candles, "equity": equity, "trades": trades}
