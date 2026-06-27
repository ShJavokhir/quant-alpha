# 🧪 Quant Research Lab

**An autonomous AI that discovers trading strategies — and catches itself when it overfits.**

> *The LLM proposes, the backtester disposes.*

Built for the **AI Engineer World's Fair Hackathon** (Cerebral Valley, SF — June 27–28, 2026).

---

## The idea

Most "self-improving agent" demos can't actually *prove* the agent got better — the reward is subjective ("the summary reads nicer"). **Trading is the one domain with an objective, immediate, ground-truth grade on every decision: out-of-sample P&L.** That makes it the perfect testbed for *provable* continual learning.

So we built a lab where an **LLM acts as a quant researcher**: it proposes a parameterized strategy and a hypothesis, a **rigorous walk-forward backtester optimizes and judges it**, and a **guardrail catches overfitting** before anything is trusted. The agent reads the verdict, writes a lesson, and proposes its next idea — accumulating a research memory across experiments.

The LLM is the **researcher, orchestrator, and explainer** — *never* the price oracle. LLMs are bad price predictors and leak future knowledge about famous tickers; the deterministic backtester is the source of truth.

### The hero moment 🎯

The agent gets greedy, stacks five indicators, and tunes them hard on short windows. In-sample it looks *spectacular*. Then the walk-forward guardrail tests it on the next, unseen window — and it **craters**. The system stamps it `OVERFIT` and rejects it, live, on screen. *That's* the "AI caught itself cheating" moment — and it's computed on real data, not scripted.

---

## How it maps to the hackathon themes

| Theme | How we hit it |
|---|---|
| **Continual Learning** | A research **journal/memory** the agent builds and learns from across experiments. |
| **The Self-Improvement Stack** | A **walk-forward eval harness** that *measures* improvement and gates every strategy with an honest verdict. |
| **Recursive Intelligence / RSI** | A **recursive loop** — propose → test → diagnose → improve — that compounds robust ideas and discards curve-fit ones. |

---

## Architecture

```
        ┌──────────────────────────────────────────────┐
        │  Researcher  (Gemini brain  ·  or stub)       │
        │  proposes:  template + parameter grid + windows│
        └───────────────┬──────────────────────────────┘
                        │ proposal
                        ▼
        ┌──────────────────────────────────────────────┐
        │  Walk-forward guardrail   (walkforward.py)    │
        │  optimize on in-sample → score out-of-sample  │
        │  → verdict  ROBUST / FRAGILE / OVERFIT         │
        │  (the IS→OOS Sharpe gap is the overfit signal) │
        └───────────────┬──────────────────────────────┘
                        │ result + diagnosis + lesson
                        ▼
        ┌──────────────────────────────────────────────┐
        │  JOURNAL   runs/<id>/journal.jsonl            │
        │  = agent memory  AND  the UI's data source    │
        │  (stores params, not curves — recompute later)│
        └───────────────┬──────────────────────────────┘
                        │ served + recomputed on demand
                        ▼  FastAPI  (api.py, :8077)
        ┌──────────────────────────────────────────────┐
        │  Next.js dashboard   (frontend/, :3007)       │
        │  Feed · Overfit Reveal · Arc · Heatmap · Sim  │
        └──────────────────────────────────────────────┘
```

**Key design decision:** the **journal is the single source of truth** — it's simultaneously the agent's memory *and* the frontend's data feed. It stores *parameters, not curves*, so the backend can recompute any equity curve, candle series, or trade list on demand. This decouples the engine from the UI and makes the whole research run replayable.

---

## What's built ✅

### Engine (Python)
| File | What it does |
|---|---|
| `download_data.py` | Pulls clean OHLCV candles from Yahoo Finance → CSV (drops malformed rows, dedups). |
| `data/` | **15-stock basket**, deep history (several tickers back to **1962**). |
| `backtest.py` | Transparent, vectorized, **no-lookahead** backtester (1-bar execution shift), realistic costs, and trader-grade metrics (Sharpe, Sortino, max drawdown, profit factor, expectancy, win rate, exposure). |
| `strategies.py` | Template registry — `sma_crossover`, `rsi_reversion`, `multi_filter` (deliberately overfit-prone). Each = `{fn, param grid, validity}`. |
| `walkforward.py` | **The guardrail.** Rolling walk-forward optimization + overfitting detector → `ROBUST / FRAGILE / OVERFIT`. |
| `research.py` | The research loop (propose → evaluate → diagnose → remember) + `StubResearcher` (scripted, no API key). Writes the journal. |
| `gemini_researcher.py` | `GeminiResearcher` — the live LLM brain (google-genai, structured JSON output, validates/clamps every proposal). |
| `api.py` | FastAPI backend: serves the journal and **recomputes** equity/candles/trades from stored params. |

### Frontend (`frontend/`) — Next.js 16 · React 19 · Tailwind v4 · lightweight-charts v5 · Framer Motion
A dark quant-terminal dashboard with five panels:
1. **Research Feed** — experiment cards stream in with hypothesis, verdict badge, diagnosis & lesson.
2. **Overfitting Reveal** — in-sample equity *soaring* vs out-of-sample *cratering*, with the `OVERFIT` stamp.
3. **Continual-Learning Arc** — best out-of-sample Sharpe climbing across experiments.
4. **Basket Heatmap** — per-ticker robustness at a glance.
5. **Trading Simulator** — candlesticks with BUY/SELL markers, strategy/ticker selectors, and a ▶ replay.

---

## Results (real, from the engine)

**Walk-forward of a standard SMA crossover across the 15-stock basket (303 folds):**
optimizing fast/slow inflates **in-sample Sharpe to 0.80**, but it **holds at 0.46 out-of-sample** (gap 0.33) → `ROBUST`. The one short-history name (META) is flagged `FRAGILE` — exactly the small-sample caution a human quant would apply.

**The stub research run — an honest arc:**

| # | Strategy | In-sample | Out-of-sample | Gap | Verdict |
|--:|----------|:---------:|:-------------:|:---:|---------|
| 1 | SMA baseline | 0.80 | **0.46** | 0.33 | ✅ ROBUST |
| 2 | multi_filter *(greedy, 1y windows)* | **1.12** | **0.11** | **1.01** | ❌ caught |
| 3 | multi_filter *(corrected)* | 0.33 | 0.17 | 0.16 | ❌ still weak |
| 4 | rsi_reversion | 0.97 | **0.62** | 0.35 | ✅ ROBUST |

Best robust out-of-sample Sharpe climbs **0.46 → 0.62**. Note #3: removing the overfit didn't *rescue* the idea — it **revealed the idea was only ever curve-fit**, so the agent pivoted to a genuinely different, robust edge. Honest by construction.

**The overfitting reveal, on SPY** (experiment #2's most-overfit fold): in-sample Sharpe **+1.49** → out-of-sample **−1.03** (gap **2.52**). It looked like the best strategy of all in-sample, and *lost money* live.

---

## Run it

```bash
# 0. From the project root, set up the Python env
python3 -m venv .venv && source .venv/bin/activate
pip install yfinance pandas numpy matplotlib fastapi "uvicorn[standard]" google-genai

# 1. (Optional) refresh the data — the 15-ticker basket is already in data/
python download_data.py SPY AAPL MSFT GOOGL AMZN NVDA META JPM XOM JNJ WMT KO PG HD DIS

# 2. Run the research loop → writes runs/<timestamp>/journal.jsonl
python research.py            # stub researcher (scripted demo arc, no API key)
python research.py gemini     # live Gemini brain  (needs GEMINI_API_KEY in .env)

# 3. Start the backend API  (http://localhost:8077)
uvicorn api:app --port 8077

# 4. Start the dashboard  (http://localhost:3007)
cd frontend && npm install && npm run dev -- --port 3007
```

To use the live LLM brain, create a `.env` in the project root:

```
GEMINI_API_KEY=AIza...        # free key from https://aistudio.google.com/apikey
# GEMINI_MODEL=gemini-2.5-flash   # optional override (default)
```

---

## Project structure

```
quant-alpha/
├── download_data.py      # Yahoo Finance → clean CSV
├── data/                 # 15-ticker basket (daily OHLCV)
├── backtest.py           # no-lookahead vectorized backtester + metrics
├── strategies.py         # strategy template registry
├── walkforward.py        # walk-forward optimizer + overfitting guardrail
├── research.py           # the research loop + StubResearcher + journal
├── gemini_researcher.py  # live Gemini brain (structured output)
├── api.py                # FastAPI backend (serves + recomputes)
├── runs/                 # generated research journals
├── .env                  # GEMINI_API_KEY (gitignored)
└── frontend/             # Next.js dashboard
    ├── app/              # layout, page, dark theme
    ├── components/       # Feed, OverfitReveal, Arc, Heatmap, Simulator
    └── lib/api.ts        # typed API client
```

---

## Engineering notes (why the results are trustworthy)

- **No lookahead.** Positions decided at bar *t*'s close are *held* over bar *t+1* (a strict 1-bar execution shift). A signal can never trade on data it hasn't seen.
- **Walk-forward, not a single split.** Parameters are optimized on a rolling in-sample window and scored on the *next* out-of-sample window — the same discipline a real quant uses, automated.
- **Honest costs.** Commission + slippage charged on turnover (configurable bps).
- **Small-sample & regime caveats are surfaced, not hidden** (e.g., META flagged on thin history).
- **The LLM is sandboxed to proposing.** Every model output is validated and clamped (known templates, bounded parameters, capped grid size) before it touches the backtester.

---

## Status & roadmap

**Done:** data pipeline · backtester · walk-forward guardrail · research loop + journal · FastAPI backend · full 5-panel dashboard · Gemini integration (code complete & validated to the auth boundary).

**In progress / next:**
- 🔌 **Live Gemini brain** — code is ready; currently blocked by a project-level `403` on the provided key (a Workspace/account restriction). Needs a personal-account key *or* a MiniMax pivot (sponsor credits, OpenAI-compatible — drop-in).
- 🎬 Animated bar-by-bar replay in the simulator.
- 📊 Memory-on vs memory-off **ablation** chart (the cleanest proof of continual learning).
- ▶️ A "run live" button to spawn one real research iteration on stage.

---

## Tech stack

**Engine:** Python · pandas · NumPy · yfinance
**Backend:** FastAPI · uvicorn · google-genai
**Frontend:** Next.js 16 · React 19 · TypeScript · Tailwind v4 · TradingView lightweight-charts v5 · Framer Motion

---

*Built at the AI Engineer World's Fair 2026. The market grades every decision — so this agent can actually prove it's learning.*
