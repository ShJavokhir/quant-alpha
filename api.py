"""FastAPI backend for the Research Lab UI.

Serves the journal and RECOMPUTES equity / candle / trade data from stored params
on demand (params -> curves), so the frontend stays thin and any strategy is
re-simulatable. Run:  uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import numbers
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

import strategies as st
from backtest import compute_metrics, run_backtest
from walkforward import optimize, walk_forward
from backtest_5m import (
    compute_portfolio_metrics_5m,
    information_coefficient,
    quantile_returns,
    run_portfolio_backtest_5m,
)
from factors_5m import evaluate_factor, list_factors as list_factors_5m
from market_data_5m import ProviderError, bars_to_panel, get_provider, ingest_5m_bars, read_bar_cache, read_manifest
from portfolio_5m import PortfolioConfig5m, weights_from_scores

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
    """Demo research runs = directories that contain a journal (excludes bare
    ablation_*/holdout_* prototype dirs)."""
    if not RUNS_DIR.exists():
        return []
    return sorted(d.name for d in RUNS_DIR.iterdir()
                  if d.is_dir() and (d / "journal.jsonl").exists())


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
    APPRAISAL gap), then return in-sample equity (soaring) vs out-of-sample (collapsing)
    vs the buy&hold benchmark -- edge-vs-beta. Numbers carry both the appraisal gate
    (beta-adjusted alpha) and the Information Ratio (passive sanity)."""
    run_id = _resolve(run_id)
    exp = _find_exp(run_id, iteration)
    df = load_ticker(ticker)
    tmpl = st.TEMPLATES[exp["template"]]
    folds = walk_forward(df, tmpl["fn"], exp["grid"], tmpl.get("valid"), **exp["windows"])
    if not folds:
        raise HTTPException(422, "not enough history for this ticker/window")

    # the most-overfit fold by appraisal collapse (IS alpha that evaporates OOS)
    def _key(f):
        g = f["is_appraisal"] - f["oos_appraisal"]
        return g if math.isfinite(g) else -math.inf
    fold = max(folds, key=_key)
    params = fold["params"]
    is_df = df.loc[str(fold["is_start"]):str(fold["oos_start"])]
    oos_df = df.loc[str(fold["oos_start"]):str(fold["oos_end"])]

    def sig(d):
        return tmpl["fn"](d, **params)

    return {
        "ticker": ticker, "template": exp["template"], "iteration": iteration,
        "params": params, "verdict": exp["verdict"],
        "is": {"appraisal": _num(fold["is_appraisal"]), "excess": _num(fold["is_excess"]),
               "sharpe": _num(fold["is_sharpe"]), "from": str(fold["is_start"]),
               "curve": _equity_curve(is_df, sig(is_df))},
        "oos": {"appraisal": _num(fold["oos_appraisal"]), "excess": _num(fold["oos_excess"]),
                "sharpe": _num(fold["oos_sharpe"]), "from": str(fold["oos_start"]),
                "curve": _equity_curve(oos_df, sig(oos_df))},
        "benchmark_oos": _equity_curve(oos_df, st.buy_and_hold(oos_df)),
        "benchmark_oos_sharpe": _num(fold["benchmark_oos_sharpe"]),
        "appraisal_gap": _num(fold["is_appraisal"] - fold["oos_appraisal"]),
        "gap": _num(fold["is_sharpe"] - fold["oos_sharpe"]),
    }


def _find_artifact(run_id: str, name: str) -> dict:
    p = RUNS_DIR / _resolve(run_id) / name
    if not p.exists():
        raise HTTPException(404, f"no {name} for this run")
    return json.loads(p.read_text())


@app.get("/api/runs/{run_id}/ablation")
def get_ablation(run_id: str):
    """memory-ON vs memory-OFF ablation summary (Task C) -> ImprovementArc."""
    return _find_artifact(run_id, "ablation.json")


@app.get("/api/runs/{run_id}/holdout")
def get_holdout(run_id: str):
    """The sealed never-touched exam (Task B): winner vs rejected on unseen data."""
    return _find_artifact(run_id, "holdout.json")


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


# --- 5-minute cross-sectional research API ----------------------------------

class Portfolio5mRequest(BaseModel):
    mode: str = "long_short"
    top_quantile: float = 0.2
    bottom_quantile: float = 0.2
    weighting: str = "equal"
    gross_exposure: float = 1.0
    rebalance_every: int = 1


class Backtest5mRequest(BaseModel):
    provider: str = "polygon"
    symbols: list[str]
    start: str | None = None
    end: str | None = None
    factor_name: str = "intraday_momentum"
    factor_params: dict = Field(default_factory=dict)
    portfolio: Portfolio5mRequest = Field(default_factory=Portfolio5mRequest)
    commission_bps: float = 2.0
    slippage_bps: float = 3.0


class Ingest5mRequest(BaseModel):
    provider: str = "polygon"
    symbols: list[str]
    start: str
    end: str
    adjusted: bool = True
    universe: str = "custom"
    regular_session_only: bool = True


def _clean(v):
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if isinstance(v, numbers.Real):
        return float(v) if math.isfinite(float(v)) else None
    return v


def _model_dict(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _series_points(s: pd.Series) -> list[dict]:
    return [{"time": _clean(idx), "value": _clean(val)} for idx, val in s.items()]


def _frame_points(df: pd.DataFrame) -> list[dict]:
    out = []
    for idx, row in df.iterrows():
        rec = {"time": _clean(idx)}
        for key, value in row.items():
            rec[str(key)] = _clean(value)
        out.append(rec)
    return out


def _backtest_5m_dir(run_id: str) -> Path:
    if "/" in run_id or ".." in run_id:
        raise HTTPException(400, "invalid backtest id")
    return RUNS_DIR / "backtests_5m" / run_id


def _read_backtest_5m_artifact(run_id: str, name: str):
    p = _backtest_5m_dir(run_id) / name
    if not p.exists():
        raise HTTPException(404, f"no {name} for 5m backtest {run_id}")
    return json.loads(p.read_text())


@app.post("/api/market-data/5m/ingest")
def ingest_market_data_5m(req: Ingest5mRequest):
    if not req.symbols:
        raise HTTPException(422, "symbols are required")
    try:
        provider = get_provider(req.provider)
        return ingest_5m_bars(
            provider=provider,
            symbols=req.symbols,
            start=req.start,
            end=req.end,
            cache_root=DATA_DIR / "cache",
            adjusted=req.adjusted,
            universe=req.universe,
            regular_session_only=req.regular_session_only,
        )
    except ProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/factors/5m")
def get_factors_5m():
    return {"factors": list_factors_5m()}


@app.post("/api/backtests/5m")
def create_backtest_5m(req: Backtest5mRequest):
    if not req.symbols:
        raise HTTPException(422, "symbols are required")
    cache_root = DATA_DIR / "cache"
    try:
        bars = read_bar_cache(cache_root, req.provider, req.start, req.end, req.symbols)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    if bars.empty:
        raise HTTPException(404, "no cached 5m bars matched the request")

    panel = bars_to_panel(bars)
    if panel.close.empty:
        raise HTTPException(422, "cached bars contain no regular-session 5m data")
    cfg = PortfolioConfig5m(**_model_dict(req.portfolio))
    try:
        scores = evaluate_factor(panel, req.factor_name, req.factor_params)
        weights = weights_from_scores(scores, panel.tradable, cfg)
        bt = run_portfolio_backtest_5m(panel, weights, req.commission_bps, req.slippage_bps)
        metrics = compute_portfolio_metrics_5m(bt)
        ic = information_coefficient(scores, panel.returns)
        qret = quantile_returns(scores, panel.returns)
    except (KeyError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc

    run_id = datetime.now(timezone.utc).strftime("bt5m_%Y%m%d_%H%M%S_%f")
    out = _backtest_5m_dir(run_id)
    out.mkdir(parents=True, exist_ok=True)
    try:
        manifest = read_manifest(cache_root, req.provider)
    except FileNotFoundError:
        manifest = None

    summary = {
        "id": run_id,
        "provider": req.provider,
        "symbols": panel.symbols,
        "start": _clean(panel.close.index.min()),
        "end": _clean(panel.close.index.max()),
        "factor": {"name": req.factor_name, "params": req.factor_params},
        "portfolio": _model_dict(req.portfolio),
        "metrics": {k: _clean(v) for k, v in metrics.items()},
        "ic_mean": _clean(ic.mean()),
        "rank_ic_mean": _clean(ic.mean()),
        "survivorship_warning": "V1 5m research uses the requested static universe; S&P 500 current-constituent runs are survivor-biased.",
        "manifest": manifest,
        "artifacts": ["summary.json", "equity.json", "ic.json", "quantiles.json"],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    (out / "equity.json").write_text(json.dumps({"points": _series_points(bt["equity"])}, indent=2))
    (out / "ic.json").write_text(json.dumps({"points": _series_points(ic)}, indent=2))
    (out / "quantiles.json").write_text(json.dumps({"points": _frame_points(qret)}, indent=2))
    return summary


@app.get("/api/backtests/5m/{run_id}/summary")
def get_backtest_5m_summary(run_id: str):
    return _read_backtest_5m_artifact(run_id, "summary.json")


@app.get("/api/backtests/5m/{run_id}/equity")
def get_backtest_5m_equity(run_id: str):
    return _read_backtest_5m_artifact(run_id, "equity.json")


@app.get("/api/backtests/5m/{run_id}/ic")
def get_backtest_5m_ic(run_id: str):
    return _read_backtest_5m_artifact(run_id, "ic.json")


@app.get("/api/backtests/5m/{run_id}/quantiles")
def get_backtest_5m_quantiles(run_id: str):
    return _read_backtest_5m_artifact(run_id, "quantiles.json")
