# DARWIN — a self-evolving alpha-research agent

> An AI that researches quantitative trading signals ("alphas"), kills the weak,
> breeds the strong, and **measurably gets better at the research itself over time.**

Built for the AI Engineer World's Fair Hackathon (June 2026). Themes: **Continual
Learning · The Self-Improvement Stack · Recursive Intelligence**.

---

## The idea in one breath
We seed an agent with 50 known cross-sectional equity alphas (WorldQuant-101 style +
classic factors). Every research "generation" (a walk-forward step through 2013–2024) it:

1. **Evaluates** every live alpha on a trailing window (IC, IC-IR, appraisal, turnover, cost).
2. **Prunes** the decayed, the cost-bleeders, and the redundant (natural selection).
3. **Researches** new alphas — Gemini proposes formulas, conditioned on a **memory** of past
   wins/failures (MongoDB Atlas + Voyage embeddings); and the **Gemini Antigravity managed agent**
   spins up an isolated Google-hosted environment to browse the web + run code and bring back
   brand-new, *cited* alphas (e.g. Garman-Klass vol, Heston-Sadka seasonality, Abdi-Ranaldo spread).
4. **Validates** each candidate in a sandboxed backtest, **de-dupes** against the fleet
   (Voyage vector similarity + signal correlation), and **admits** the keepers.
5. **Trades** the top-K of the evolved fleet and scores it on the *next unseen block*.

The whole loop is **"the LLM proposes, the backtester disposes."**

## What we prove (honestly)
- **The researcher learns.** With memory of past research, the agent discovers keepers at
  ~2–3× the rate of a memory-ablated copy and of random-grammar search — the core
  continual-learning result (the "cumulative discoveries" chart).
- **The fleet adapts.** Out-of-sample, the evolving, cost-disciplined book beats the frozen
  seed fleet on net-of-cost Sharpe and sustains signal quality through regimes (COVID, 2022).
- **We engineered against self-deception** (per an adversarial review): prospective
  walk-forward (every keep/kill/add decided before the test block), an immutable trial ledger,
  a **sealed 2024 holdout** scored once, a cost sweep (1/5/10/25/50 bps) + 1-day execution
  delay, a liquid universe, and random-search + memory-ablated controls.

We **never** claim to have found the optimum or to beat the market — we claim an AI that
learns to *search* for alpha and proves it generalizes.

---

## Architecture
```
lab/                      python core
  engine/
    ops.py                alpha operator library (panel-correct, mirrors validated alpha101)
    dsl.py                safe formula DSL — AST-whitelisted sandbox (runs LLM formulas safely)
    backtest.py           IC / IC-IR / appraisal / turnover / net-of-cost metrics
  seeds.py                50+ seed alphas as DSL strings (validated)
  agent/
    memory.py             dual-backend store: MongoDB Atlas (+ Voyage vectors) | local fallback
    proposer.py           Gemini alpha proposer (memory-conditioned)
    antigravity.py        Gemini Antigravity managed-agent researcher (isolated env, web+code, cited)
    researcher.py         draws from Antigravity discoveries + a Firecrawl literature corpus -> DSL
    random_search.py      random-grammar-search control
    evolve.py             the walk-forward evolution loop (one "arm")
    fleet.py              liquid universe, book combination, redundancy
  run_experiment.py       orchestrates all arms + sealed holdout -> runs/<id>/run.json
server/api.py             FastAPI: serves the run, alpha drill-down, Atlas vector search, live propose
frontend/                 Vite + React + Tailwind v4 dashboard (the demo)
runs/demo_committed/      the committed run the demo replays (works offline)
```

Stack: **Gemini 2.5 Flash** (proposer) + **Gemini Antigravity managed agent**
(`antigravity-preview-05-2026` via the Interactions API — isolated env, web browse + code exec,
stateful via environment ids), **MongoDB Atlas + Voyage AI** (agent memory + vector search),
**Firecrawl** (literature corpus), data = ~1,200 US stocks daily 2010–2024.

## Run it
```bash
# 1) data (one-time): pulled from the box + extended via yfinance -> lab/data/*.pkl
# 2) (re)generate a run:        .venv/bin/python -m lab.run_experiment --run-id demo_full
# 3) demo (backend + frontend): ./run_demo.sh   -> http://localhost:5173
```
Secrets live in `.env` (`GEMINI_API_KEY`, `MONGO_URI`, `VOYAGE_API_KEY`). The dashboard works
fully offline off the committed run; with the backend up you also get drill-downs, Atlas vector
search, and a live "propose" button.

See `DEMO.md` for the on-stage script and `backlog.md` for status/notes.
