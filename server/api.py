"""FastAPI backend for the Darwin alpha-evolution dashboard.

Serves the committed experiment run (runs/<id>/run.json) plus on-demand drill-down
(recompute an alpha's IC / equity curve from its formula) and an optional single
live generation. The frontend reads /api/run for everything on the dashboard.
"""
import json
import threading
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import config, seeds as seedmod          # noqa: E402
from lab.engine import dsl, backtest               # noqa: E402
from lab.agent import fleet                         # noqa: E402
from lab.agent.memory import Embedder, open_memory, alpha_text  # noqa: E402

_PANEL_CACHE: dict = {}
_AG_JOBS: dict = {}   # job_id -> live state for the streaming Antigravity 'machine screen'


def _panel_for(run):
    which = run["meta"]["panel"]; n = run["meta"]["universe_n"]
    key = (which, n)
    if key not in _PANEL_CACHE:
        full = config.load_panel(which)
        _PANEL_CACHE[key] = fleet.restrict(full, fleet.liquid_universe(full, n))
    return _PANEL_CACHE[key]

app = FastAPI(title="Darwin Alpha Evolution API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

RUNS = config.RUNS
_DEFAULT = "demo_committed"


def _run_path(run_id=None):
    if run_id:
        p = RUNS / run_id / "run.json"
        if p.exists():
            return p
    p = RUNS / _DEFAULT / "run.json"
    if p.exists():
        return p
    # else newest run with a run.json
    cands = sorted(RUNS.glob("*/run.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def _load_run(run_id=None):
    p = _run_path(run_id)
    if not p:
        raise HTTPException(404, "no run found")
    return json.loads(p.read_text()), p.parent.name


@app.get("/api/health")
def health():
    p = _run_path()
    return {"ok": True, "default_run": p.parent.name if p else None}


@app.get("/api/runs")
def list_runs():
    out = []
    for p in sorted(RUNS.glob("*/run.json")):
        try:
            m = json.loads(p.read_text()).get("meta", {})
            out.append({"run_id": p.parent.name, "created": m.get("created"),
                        "n_generations": m.get("n_generations")})
        except Exception:
            pass
    return out


@app.get("/api/run")
def get_run(run_id: str | None = None):
    data, rid = _load_run(run_id)
    return JSONResponse(data)


def _formula_lookup(run):
    lut = {s["name"]: {"formula": s["formula"], "family": s["family"],
                       "rationale": s.get("rationale", ""), "source": "seed"}
           for s in seedmod.SEEDS}
    for q in run.get("proposals", []):
        if q.get("formula"):
            lut[q["name"]] = {"formula": q["formula"], "family": q.get("family", ""),
                              "rationale": q.get("rationale", ""), "source": q.get("source", ""),
                              "source_url": q.get("source_url", ""), "source_title": q.get("source_title", ""),
                              "steps": q.get("steps"), "interaction_id": q.get("interaction_id")}
    return lut


@app.get("/api/alpha/{name}")
def alpha_detail(name: str, run_id: str | None = None):
    run, rid = _load_run(run_id)
    lut = _formula_lookup(run)
    if name not in lut:
        raise HTTPException(404, f"unknown alpha {name}")
    info = lut[name]
    panel = _panel_for(run)
    try:
        sig = dsl.evaluate(info["formula"], panel)
        m = backtest.evaluate_signal(sig, panel, with_series=True, cost_bps=run["meta"]["config"]["cost_bps"])
    except dsl.DSLError as e:
        raise HTTPException(400, str(e))
    s = m.pop("_series")
    cum = s["pnl"].cumsum()
    cum_ic = s["ic_rank"].fillna(0).cumsum()
    # monthly resample to keep payload small
    eq = cum.resample("W").last().dropna()
    icc = cum_ic.resample("W").last().dropna()
    return {"name": name, **info, "metrics": {k: m[k] for k in m if not k.startswith("_")},
            "equity": [{"date": str(d.date()), "v": float(v)} for d, v in eq.items()],
            "cum_ic": [{"date": str(d.date()), "v": float(v)} for d, v in icc.items()]}


_REPLAY_CACHE: dict = {}


def _episodes(pct_col, thr=0.9, mink=5):
    """Conviction holds: runs of >= mink consecutive days where the name sits in the
    top decile (dir +1, long) or bottom decile (dir -1, short) of the cross-section.
    Returns [(dir, start_idx, end_idx)] as integer positions into the date axis."""
    s = pct_col.to_numpy()
    state = np.where(s >= thr, 1, np.where(s <= 1 - thr, -1, 0))
    eps, cur, start = [], 0, None
    for i, v in enumerate(state):
        if v != cur:
            if cur != 0 and start is not None and (i - 1 - start) >= mink - 1:
                eps.append((int(cur), int(start), int(i - 1)))
            cur, start = int(v), (i if v != 0 else None)
    if cur != 0 and start is not None and (len(state) - 1 - start) >= mink - 1:
        eps.append((int(cur), int(start), len(state) - 1))
    return eps


def _replay_compute(run, name):
    """Heavy part (eval formula -> book pnl/turnover + per-name decile ranks), cached."""
    if name in _REPLAY_CACHE:
        return _REPLAY_CACHE[name]
    lut = _formula_lookup(run)
    if name not in lut:
        raise HTTPException(404, f"unknown alpha {name}")
    info = lut[name]
    panel = _panel_for(run)
    try:
        sig = dsl.evaluate(info["formula"], panel)
    except dsl.DSLError as e:
        raise HTTPException(400, str(e))
    m = backtest.evaluate_signal(sig, panel, with_series=True,
                                 cost_bps=run["meta"]["config"]["cost_bps"])
    s = m.pop("_series")
    w = s["weights"]
    pnl = s["pnl"].reindex(sig.index).fillna(0.0)
    turn = w.diff().abs().sum(axis=1).reindex(sig.index).fillna(0.0)
    fwd = panel["fwd"].reindex(index=sig.index, columns=sig.columns)
    contrib = (w * fwd).sum().fillna(0.0)
    pct = sig.rank(axis=1, pct=True)

    # representative names: clean conviction story (3..60 episodes) ranked by P&L impact
    cands = []
    for nm in contrib.abs().sort_values(ascending=False).index:
        if nm not in pct.columns:
            continue
        ne = len(_episodes(pct[nm]))
        if 3 <= ne <= 60:
            cands.append({"symbol": nm, "contrib": round(float(contrib[nm]), 4), "episodes": ne})
        if len(cands) >= 14:
            break
    cands.sort(key=lambda c: -c["contrib"])  # most profitable name first -> nice default

    cache = {
        "info": {k: info.get(k) for k in ("formula", "family", "rationale", "source",
                                          "source_url", "source_title")},
        "dates": [str(d.date()) for d in sig.index],
        "pnl": [round(float(x), 6) for x in pnl],
        "turn": [round(float(x), 6) for x in turn],
        "metrics": {k: m[k] for k in m if not k.startswith("_")},
        "candidates": cands,
        "_close": panel["close"], "_pct": pct, "_idx": sig.index,
    }
    if len(_REPLAY_CACHE) > 6:
        _REPLAY_CACHE.clear()
    _REPLAY_CACHE[name] = cache
    return cache


@app.get("/api/alpha_replay/{name}")
def alpha_replay(name: str, symbol: str | None = None, run_id: str | None = None):
    """Replay a single alpha as a tradeable strategy: the dollar-neutral book's daily
    gross P&L + turnover (so the client can apply any deposit/cost instantly), plus one
    representative name's price with the alpha's conviction long/short episodes -> ▲/▼
    buy/sell markers. Powers the Strategy Replay view."""
    run, _ = _load_run(run_id)
    c = _replay_compute(run, name)
    sym = symbol or (c["candidates"][0]["symbol"] if c["candidates"] else None)
    series = {"symbol": sym, "price": [], "episodes": []}
    if sym is not None and sym in c["_close"].columns:
        price = c["_close"][sym].reindex(c["_idx"])
        series["price"] = [None if pd.isna(x) else round(float(x), 2) for x in price]
        if sym in c["_pct"].columns:
            series["episodes"] = [{"dir": d, "start": a, "end": b}
                                  for (d, a, b) in _episodes(c["_pct"][sym])]
    return {"name": name, "info": c["info"], "dates": c["dates"],
            "pnl": c["pnl"], "turn": c["turn"], "metrics": c["metrics"],
            "candidates": c["candidates"], "series": series,
            "cost_bps_default": run["meta"]["config"]["cost_bps"]}


_BOOK_CACHE: dict = {}
_ALPHA_EVAL_CACHE: dict = {}   # name -> (sig, metrics, daily pnl, daily turnover); makes basket edits snappy


def _eval_one(lut, panel, cost, name):
    """Evaluate a single alpha -> (raw signal, scalar metrics, daily pnl, daily turnover).
    Cached per name so editing the basket only re-blends already-evaluated signals."""
    if name in _ALPHA_EVAL_CACHE:
        return _ALPHA_EVAL_CACHE[name]
    sig = dsl.evaluate(lut[name]["formula"], panel)
    m = backtest.evaluate_signal(sig, panel, cost_bps=cost, with_series=True)
    s = m.pop("_series")
    pnl = s["pnl"].reindex(sig.index).fillna(0.0)
    turn = s["weights"].diff().abs().sum(axis=1).reindex(sig.index).fillna(0.0)
    if len(_ALPHA_EVAL_CACHE) > 40:        # the final fleet is ~33 names; bound memory (signals are large)
        _ALPHA_EVAL_CACHE.clear()
    _ALPHA_EVAL_CACHE[name] = (sig, m, pnl, turn)
    return _ALPHA_EVAL_CACHE[name]


def _book_replay_compute(run, selected=None, weighting="book"):
    """Blend several alphas into ONE traded book the same way the evolve loop does
    (fleet.combine_signals: rank → orient by IC sign → weight by track-record ÷ turnover
    → sum → smooth), then backtest the combined signal. Returns the combined book's
    daily gross P&L + turnover (client applies any deposit/leverage/cost), each
    constituent's series + metrics (for the overlay + 'vs single' stats), and the
    pairwise P&L correlation matrix (the diversification source). Powers the
    Combined-book view — the 'quants trade books, not single alphas' story."""
    key = (frozenset(selected) if selected else "default", weighting)
    if key in _BOOK_CACHE:
        return _BOOK_CACHE[key]
    from lab.agent.evolve import Config as _Cfg
    cfg = _Cfg()
    lut = _formula_lookup(run)
    panel = _panel_for(run)
    cost = run["meta"]["config"]["cost_bps"]
    members = run["generations"][-1]["fleet"]          # the final live fleet
    fam = {m["name"]: m["family"] for m in members}
    avail = [m for m in members if m["name"] in lut]
    cand = [n for n in selected if n in lut] if selected else [m["name"] for m in avail]
    if not cand:
        raise HTTPException(400, "no valid alphas selected")

    sig_by, met, pnl_by, turn_by = {}, {}, {}, {}
    for nm in cand:
        try:
            sig, m, pnl, turn = _eval_one(lut, panel, cost, nm)
        except dsl.DSLError:
            continue
        sig_by[nm], met[nm], pnl_by[nm], turn_by[nm] = sig, m, pnl, turn
    if not sig_by:
        raise HTTPException(400, "no evaluable alphas in selection")

    # robust-score proxy (full-sample IC-IR; no per-gen history at serve time), then
    # rank → top-K (only when defaulting to the agent's book; an explicit basket is kept whole).
    score = {nm: met[nm]["ic_ir"] for nm in sig_by}
    book = ([n for n in cand if n in sig_by] if selected
            else sorted(sig_by, key=lambda n: score[n], reverse=True)[: cfg.book_top])
    if weighting == "equal":
        weights = {nm: 1.0 for nm in book}
    else:
        weights = {nm: max(score[nm], 0.0) / (0.3 + met[nm]["turnover"]) for nm in book}
        if not any(weights.values()):
            weights = {nm: 1.0 for nm in book}
    orient = {nm: (1.0 if met[nm]["ic"] >= 0 else -1.0) for nm in book}
    combined = fleet.combine_signals({nm: sig_by[nm] for nm in book}, orient, weights,
                                     smooth=cfg.book_smooth)
    if combined is None:
        raise HTTPException(400, "could not combine selection")
    cm = backtest.evaluate_signal(combined, panel, cost_bps=cost, with_series=True)
    cs = cm.pop("_series")
    idx = combined.index
    cpnl = cs["pnl"].reindex(idx).fillna(0.0)
    cturn = cs["weights"].diff().abs().sum(axis=1).reindex(idx).fillna(0.0)

    wsum = sum(weights.values()) or 1.0
    P = pd.DataFrame({nm: pnl_by[nm] for nm in book}).corr().fillna(0.0)
    cnames = list(P.columns)
    off = P.where(~np.eye(len(P), dtype=bool)).values if len(P) > 1 else np.array([0.0])
    keep = ("ic", "ic_ir", "appraisal", "sharpe", "sharpe_net", "ann_ret", "turnover", "beta")
    out = {
        "names": book,
        "default_book": (None if selected else book),
        "available": [{"name": m["name"], "family": m["family"],
                       "ir": m["ir"], "turnover": m["turnover"]} for m in avail],
        "weighting": weighting,
        "dates": [str(d.date()) for d in idx],
        "pnl": [round(float(x), 6) for x in cpnl],
        "turn": [round(float(x), 6) for x in cturn],
        "metrics": {k: cm[k] for k in (*keep, "appraisal_net", "ann_ret_net", "n_days")},
        "constituents": [{
            "name": nm, "family": fam.get(nm, "unknown"),
            "weight": round(weights[nm] / wsum, 4), "orient": int(orient[nm]),
            "metrics": {k: met[nm][k] for k in keep},
            "pnl": [round(float(x), 6) for x in pnl_by[nm].reindex(idx).fillna(0.0)],
            "turn": [round(float(x), 6) for x in turn_by[nm].reindex(idx).fillna(0.0)],
        } for nm in book],
        "corr": {"names": cnames, "matrix": [[round(float(P.loc[a, b]), 3) for b in cnames] for a in cnames]},
        "avg_pair_corr": round(float(np.nanmean(off)), 3),
        "book_top": cfg.book_top,
        "cost_bps_default": cost,
    }
    if len(_BOOK_CACHE) > 8:
        _BOOK_CACHE.clear()
    _BOOK_CACHE[key] = out
    return out


@app.get("/api/book_replay")
def book_replay(names: str | None = None, weighting: str = "book", run_id: str | None = None):
    """Replay a COMBINED book of alphas (default = the agent's final traded book,
    top-K by track record). Pass ?names=a,b,c to blend an arbitrary basket and
    ?weighting=equal for an equal-weight blend instead of the engine's recipe."""
    run, _ = _load_run(run_id)
    selected = [s.strip() for s in (names.split(",") if names else []) if s.strip()]
    w = "equal" if weighting == "equal" else "book"
    return _book_replay_compute(run, selected or None, w)


@app.get("/api/similar/{name}")
def similar(name: str, run_id: str | None = None):
    """Atlas Vector Search (Voyage embeddings) — alphas the agent has tried that are
    closest in 'idea space'. Falls back to local cosine if Atlas is unreachable."""
    run, rid = _load_run(run_id)
    lut = _formula_lookup(run)
    if name not in lut:
        raise HTTPException(404, f"unknown alpha {name}")
    info = lut[name]
    try:
        emb = Embedder().embed_one(alpha_text(info["formula"], info.get("family", ""),
                                              info.get("rationale", "")))
        # use the run's ORIGINAL id (where alphas were written to Atlas), not the dir name
        mongo_rid = run.get("meta", {}).get("run_id", rid)
        store, backend = open_memory(mongo_rid, prefer_mongo=True)
        res = store.search_similar(emb, k=6, exclude={name})
        return {"backend": backend, "neighbors": [
            {"name": d.get("name"), "family": d.get("family"), "formula": d.get("formula"),
             "source": d.get("source"), "similarity": round(float(s), 3)} for d, s in res]}
    except Exception as e:  # noqa: BLE001
        return {"backend": "unavailable", "neighbors": [], "error": str(e)[:120]}


@app.post("/api/live_propose")
def live_propose(run_id: str | None = None, n: int = 4, backend: str = "gemini"):
    """Run the agent live: propose new alphas, validate + backtest them now.
    Powers the on-stage 'watch it think' moment.

    backend = "gemini" (default, fast) | "do" -> MiniMax-M2.5 served on
    DigitalOcean's inference engine (a reasoning model; ~60s, same DSL gates)."""
    run, rid = _load_run(run_id)
    panel = _panel_for(run)
    cost = run["meta"]["config"]["cost_bps"]
    if backend == "do":
        from lab.agent.do_proposer import DOProposer
        proposer = DOProposer()
        model_label = f"{config.DO_MODEL} · DigitalOcean"
    else:
        from lab.agent.proposer import Proposer
        proposer = Proposer()
        model_label = f"{config.GEMINI_MODEL} · Gemini"
    props = proposer.propose(n=max(1, min(8, n)),
                             regime_hint="US equities, recent regime")
    out = []
    for p in props:
        row = {"name": p["name"], "family": p["family"], "formula": p["formula"],
               "rationale": p.get("rationale", "")}
        try:
            sig = dsl.evaluate(p["formula"], panel)
            m = backtest.evaluate_signal(sig, panel, cost_bps=cost)
            row.update(ok=True, ic_ir=round(m["ic_ir"], 2), appraisal=round(m["appraisal"], 2),
                       sharpe_net=round(m["sharpe_net"], 2), turnover=round(m["turnover"], 2),
                       verdict="promising" if m["ic_ir"] > 0.6 and m["turnover"] < 0.8 else "weak")
        except dsl.DSLError as e:
            row.update(ok=False, error=str(e)[:100], verdict="invalid")
        out.append(row)
    return {"proposals": out, "backend": backend, "model": model_label}


@app.post("/api/antigravity_research")
def antigravity_research(run_id: str | None = None):
    """LIVE: spin up the Antigravity managed agent (isolated Google-hosted env), have it
    browse the web for a novel alpha, then backtest what it brings back. The on-stage
    'watch the managed agent research in real time' moment."""
    from lab.agent.antigravity import AntigravityResearcher
    from lab import seeds as seedmod
    run, _ = _load_run(run_id)
    panel = _panel_for(run)
    cost = run["meta"]["config"]["cost_bps"]
    avoid = [s["formula"] for s in seedmod.SEEDS]
    try:
        ag = AntigravityResearcher(max_wait=220)
        res = ag.research_alphas(n=1, avoid=avoid)
        if not res:
            return {"ok": False, "error": "Antigravity returned no usable alpha (timeout or no result)."}
        a = res[0]
        try:
            m = backtest.evaluate_signal(dsl.evaluate(a["formula"], panel), panel, cost_bps=cost)
            a.update(ok=True, ic_ir=round(m["ic_ir"], 2), appraisal=round(m["appraisal"], 2),
                     sharpe_net=round(m["sharpe_net"], 2), turnover=round(m["turnover"], 2),
                     verdict="promising" if m["ic_ir"] > 0.6 and m["turnover"] < 0.8 else "weak")
        except dsl.DSLError as e:
            a.update(ok=False, error=str(e)[:120], verdict="invalid")
        return {"ok": True, "alpha": a, "agent": "antigravity-preview-05-2026"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}


# ---- Streaming Antigravity: start a background job, poll its live state -------
# Powers the on-stage 'machine screen' — the UI streams the managed agent's real
# steps (provision -> browse -> code -> backtest) instead of one rotating line.

def _infer_phase(status, steps, elapsed):
    """Coarse phase (0 provision, 1 browse, 2 code, 3 backtest) for the UI to fall
    back on. Derived from the real step kinds when present, else from elapsed time."""
    if status == "completed":
        return 3
    blob = " ".join((str(s.get("type", "")) + " " + str(s.get("detail", ""))).lower()
                    for s in steps)
    if any(k in blob for k in ("backtest", "dsl", "evaluate", "sharpe")):
        return 3
    if any(k in blob for k in ("code", "exec", "python", "shell", "script", "run")):
        return 2
    if any(k in blob for k in ("browse", "search", "web", "http", "url", "fetch", "read")):
        return 1
    if steps:
        return 1
    return 0 if elapsed < 8 else 1


def _ag_worker(job_id, run_id):
    job = _AG_JOBS[job_id]
    try:
        from lab.agent.antigravity import AntigravityResearcher
        from lab import seeds as seedmod
        run, _ = _load_run(run_id)
        panel = _panel_for(run)
        cost = run["meta"]["config"]["cost_bps"]
        avoid = [s["formula"] for s in seedmod.SEEDS]
        ag = AntigravityResearcher(poll_interval=4, max_wait=240)

        def on_progress(ev):
            steps = ev.get("steps") or []
            job["status"] = "running"
            job["steps"] = steps
            job["n_steps"] = len(steps)
            job["env_id"] = ev.get("environment_id") or job.get("env_id")
            job["interaction_id"] = ev.get("interaction_id") or job.get("interaction_id")
            job["elapsed"] = round(time.time() - job["started"], 1)
            job["phase"] = _infer_phase(ev.get("status"), steps, job["elapsed"])

        res = ag.research_alphas(n=1, avoid=avoid, on_progress=on_progress)
        if not res:
            job.update(status="failed",
                       error="Antigravity returned no usable alpha (timeout or no result).")
            return
        a = res[0]
        try:
            m = backtest.evaluate_signal(dsl.evaluate(a["formula"], panel), panel, cost_bps=cost)
            a.update(ok=True, ic_ir=round(m["ic_ir"], 2), appraisal=round(m["appraisal"], 2),
                     sharpe_net=round(m["sharpe_net"], 2), turnover=round(m["turnover"], 2),
                     verdict="promising" if m["ic_ir"] > 0.6 and m["turnover"] < 0.8 else "weak")
        except dsl.DSLError as e:
            a.update(ok=False, error=str(e)[:120], verdict="invalid")
        job.update(alpha=a, status="completed", phase=3,
                   env_id=a.get("environment_id") or job.get("env_id"),
                   elapsed=round(time.time() - job["started"], 1))
    except Exception as e:  # noqa: BLE001
        job.update(status="failed", error=f"{type(e).__name__}: {str(e)[:160]}")


@app.post("/api/antigravity_research/start")
def antigravity_start(run_id: str | None = None):
    """Kick off a live Antigravity research run in the background; returns a job_id to poll."""
    if len(_AG_JOBS) > 24:   # keep the dict from growing without bound across a long demo
        for k in sorted(_AG_JOBS, key=lambda j: _AG_JOBS[j]["started"])[:-12]:
            _AG_JOBS.pop(k, None)
    job_id = uuid.uuid4().hex[:12]
    _AG_JOBS[job_id] = {"status": "starting", "phase": 0, "started": time.time(),
                        "elapsed": 0.0, "env_id": None, "interaction_id": None,
                        "steps": [], "n_steps": 0, "alpha": None,
                        "agent": "antigravity-preview-05-2026", "error": None}
    threading.Thread(target=_ag_worker, args=(job_id, run_id), daemon=True).start()
    return {"ok": True, "job_id": job_id}


@app.get("/api/antigravity_research/status/{job_id}")
def antigravity_status(job_id: str):
    job = _AG_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    out = {k: v for k, v in job.items() if k != "started"}
    out["job_id"] = job_id
    return out


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
