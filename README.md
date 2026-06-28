# 🧪 Quant Research Lab

**An AI that learns *how to search* for trading strategies — and proves the learning generalizes.**

> *The LLM proposes; the backtester disposes; the routing policy learns which **kinds** of edges survive.*

Built for the **AI Engineer World's Fair Hackathon** (SF — June 27–28, 2026).

---

## The one sentence

We did **not** build an AI that finds the best trading strategy. We built an AI that learns how to *search* for them — which *kinds* of edges survive on this market — and we can prove the learning generalizes to data the search never saw. **The strategy is the receipt; the improving research competence is the product.**

The chart that wins is **not** the equity curve. It's the one that shows the agent getting smarter: fewer experiments to find a robust edge, and a higher-quality edge when it does.

---

## Why trading? Because the scoreboard is incorruptible

Most "self-improving agent" demos can't *prove* the agent got better — the reward is subjective. **Trading has an objective, immediate, ground-truth grade: out-of-sample P&L.** That makes it the perfect testbed for *provable* continual learning. The LLM is the **researcher/explainer**, never the price oracle — the deterministic backtester is the source of truth.

---

## The honest scoring: appraisal ratio, not raw Sharpe

This basket is **survivor-biased and upward-drifting** (AAPL→1980, SPY→1993, XOM/KO/DIS→1962). On that universe, **absolute Sharpe just books market beta as skill** — and empirically **no** simple long/flat technical strategy beats buy-and-hold risk-adjusted after costs (buy&hold Sharpe ≈ 0.7; the best "ROBUST"-looking strategies only reach 0.46–0.62).

So the verdict gate runs on the **appraisal ratio** — *Jensen alpha ÷ residual vol* vs buy-and-hold, i.e. **timing alpha after stripping market beta** — and we show the **Information Ratio (excess vs buy-and-hold) FIRST** as the sanity check that passive indexing wins. The verdict label is **"beta-adjusted ROBUST," never "beats buy-and-hold."**

| Metric | Question it answers | Role |
|---|---|---|
| **Excess / Information Ratio** | "Does it beat buy&hold as a portfolio substitute?" | shown first — the answer is *no* (honest) |
| **Appraisal ratio** (verdict gate) | "Does it carry timing alpha *after* beta?" | the ROBUST/FRAGILE/OVERFIT gate |
| Absolute Sharpe | (display only) | the beta we strip out |

---

## The hero moment 🎯

The agent gets greedy: it stacks trend + RSI + momentum filters and tunes four knobs hard on a 1-year window. **In-sample its beta-adjusted alpha looks spectacular (+1.02).** Then the walk-forward guardrail scores it on the next, unseen windows — and it **craters to −0.36**. The system stamps it `OVERFIT`, **bans the family**, and — because both trend templates have now overfit — **routes to a different *kind* of edge (mean-reversion)**, which survives. *That's* "the AI caught itself cheating, understood why, and changed research direction" — computed live on real data, not scripted.

---

## How the loop works (a *caused* chain)

1. **Propose** — a creative proposer (stub *or* Gemini) picks a strategy family + grid + windows.
2. **Route** — `routing.py` turns past verdicts into **binding constraints**: ban OVERFIT families, tighten FRAGILE ones, abandon a kind that's exhausted and diversify. *The route is a provable function of verdicts — delete an early verdict and a later proposal changes.*
3. **Judge** — `walkforward.py` optimizes IS, scores OOS, rolls; the IS→OOS **appraisal** decay is the overfitting signal → `ROBUST / FRAGILE / OVERFIT`.
4. **Diagnose** — a **metric-grounded** lesson (param count, IS→OOS gap, the *dated* worst fold, per-name dispersion) is carried into the next proposal. Never a confabulated mechanism the backtester can't see.
5. **Prove** — a controlled ablation (the policy works) and a sealed holdout (the edge generalizes).

---

## The proofs

### Ablation — *the policy learned* (`ablation.py`)
Two arms, identical except one knob: a seeded random-search proposer **with** vs **without** the routing policy (`memory-ON` = proposer ∩ `derive_constraints`; `memory-OFF` = proposer alone). Family order is **randomized per seed** (kills the "pre-sequenced" critique). Random-search, not the LLM, so the policy is isolated cleanly.

> memory-ON reaches a ROBUST edge in **fewer experiments** *and* at **higher OOS alpha**, with separated error bars across seeds — and finds a robust edge far more often within budget. Speed **and** quality.

### Holdout — *the learning generalizes* (`holdout.py`)
The search reads only the **TRAIN** names strictly **before a cutoff**. Two sealed slices, opened once, scored on the appraisal basis:

- **Out-of-time** (primary, the harder regime axis): the trusted edge stays **positive but decayed → FRAGILE**; the rejected family stays clearly negative. A decade table shows **persistent sign, decaying magnitude** (+0.40 in the '90s → +0.15 now) — the system honestly **downgrades** recent RSI rather than overselling.
- **Out-of-asset** (clean name-generalization): scored on names *never searched* — trusted edge positive, rejected family negative on every name.

**Honest headline:** the agent didn't find a strategy that beats every regime; it found a disciplined mean-reversion edge that **generalizes across unseen names and stays positive (if weakened) out-of-time**, while the greedy multi-knob family **fails both axes**.

---

## How it maps to the hackathon themes

| Theme | How we hit it |
|---|---|
| **Continual Learning** (primary) | a research **memory** the agent learns from; diagnosis reshapes the next proposal; adapts from real-world signal (the market) with minimal intervention. |
| **The Self-Improvement Stack** (differentiator) | the walk-forward eval harness + overfitting guardrail + sealed holdout **are** the eval/observability infra that makes the learning *provable*. |
| **Recursive Intelligence** | gestured only — "an early form of self-directed intelligence." We touch no weights/architecture. |

---

## Architecture

```
        ┌──────────────────────────────────────────────┐
        │  Proposer  (Gemini 2.5 Flash  ·  or stub)     │
        │  proposes: template + parameter grid + windows │
        └───────────────┬──────────────────────────────┘
                        │ proposal
                        ▼
        ┌──────────────────────────────────────────────┐
        │  Routing policy  (routing.py)                 │
        │  past verdicts → binding constraints           │
        │  ban OVERFIT · tighten FRAGILE · diversify kind│
        └───────────────┬──────────────────────────────┘
                        │ enforced proposal
                        ▼
        ┌──────────────────────────────────────────────┐
        │  Walk-forward guardrail  (walkforward.py)     │
        │  optimize IS → score OOS on the APPRAISAL ratio│
        │  → ROBUST / FRAGILE / OVERFIT                   │
        └───────────────┬──────────────────────────────┘
                        │ verdict + metric-grounded lesson
                        ▼
        ┌──────────────────────────────────────────────┐
        │  JOURNAL  runs/<id>/journal.jsonl             │
        │  = agent memory  AND  the UI's data source     │
        │  + ablation.json + holdout.json                │
        └───────────────┬──────────────────────────────┘
                        │  served + recomputed on demand
                        ▼  FastAPI  (api.py, :8000)
        ┌──────────────────────────────────────────────┐
        │  Next.js dashboard   (frontend/, :3000)       │
        │  Ledger · Overfit Reveal · Ablation · Holdout  │
        └──────────────────────────────────────────────┘
```

The **journal is the single source of truth** — simultaneously the agent's memory and the frontend's feed. It stores *parameters, not curves*, so the backend recomputes any equity/candle/trade series on demand, and the whole run is replayable.

---

## What's built

### Engine (Python)
| File | What it does |
|---|---|
| `backtest.py` | no-lookahead vectorized backtester + costs; **appraisal ratio & Information Ratio** vs buy&hold. |
| `strategies.py` | template registry (`sma_crossover`, `rsi_reversion`, `multi_filter`) tagged by **kind** (trend / mean_reversion). |
| `walkforward.py` | **the guardrail** — walk-forward optimization + overfitting verdict on the **appraisal** basis. |
| `routing.py` | **the caused-routing spine** — `derive_constraints` (policy) + `enforce` (repair/reject). |
| `research.py` | the loop + verdict-driven `StubResearcher` + metric-grounded `diagnose` + journal v2. |
| `gemini_researcher.py` | the live LLM brain (Gemini 2.5 Flash) with retry → fallback → cache. |
| `ablation.py` | memory-ON vs memory-OFF controlled ablation (seeded random-search, parallel). |
| `holdout.py` | the dual-axis sealed exam (out-of-time + out-of-asset). |
| `build_demo.py` | assembles the committed replay run. |
| `api.py` | FastAPI backend — serves the journal/ablation/holdout, recomputes curves. |

### Frontend (`frontend/`) — Next.js · React · Tailwind v4 · lightweight-charts v5 · Framer Motion
A dark quant-terminal dashboard: **Research Feed / experiment ledger** (appraisal + IR + routing decisions) · **Overfitting Reveal** (edge-vs-beta) · **Ablation** (memory-ON vs OFF, error bars) · **Sealed Holdout** (dual-axis + decade decay) · **Basket Heatmap** · **Trading Simulator**.

---

## Run it

```bash
# 0. Python env
uv sync --dev

# 1. (optional) refresh data — the 15-ticker basket is already in data/
uv run python download_data.py SPY AAPL MSFT GOOGL AMZN NVDA META JPM XOM JNJ WMT KO PG HD DIS

# 2. Build the committed replay run  → runs/demo_committed/{journal,ablation,holdout}
uv run python build_demo.py     # or --quick for a fast smoke build
#    or run pieces individually:
uv run python research.py       # the caused demo arc (stub, no API key)
uv run python research.py gemini # live Gemini brain (needs GEMINI_API_KEY in .env)
uv run python ablation.py       # the ablation proof
uv run python holdout.py        # the sealed holdout

# 3. Backend API  →  http://localhost:8000
uv run uvicorn api:app --port 8000

# 4. Dashboard    →  http://localhost:3000
cd frontend && npm install && npm run dev
```

Live LLM brain — create a `.env` in the project root:

```
GEMINI_API_KEY=AIza...            # free key from https://aistudio.google.com/apikey
# GEMINI_MODEL=gemini-2.5-flash   # optional override (default)
```

---

## Claims register — say this / never that

| ✅ Say | 🚫 Never say |
|---|---|
| "It learns which *kinds* of edges survive here." | "It found the optimal strategy." |
| "It beats buy&hold out-of-sample in **beta-adjusted alpha**." | "It has a positive Sharpe." (mostly market beta) |
| "Our routing policy provably speeds up *and* improves discovery (controlled ablation)." | "The ablation proves the LLM learned." (it tests the *policy*) |
| "The model's metric-grounded diagnosis steered its next move." | "The model figured out it was a 2008 momentum regime." (the backtester scores folds; it doesn't know *why*) |
| "We brought the backtest engine; this weekend we built the autonomous researcher that drives it." | *(silence on attribution)* |

---

## Engineering notes (why the results are trustworthy)

- **No lookahead.** A signal at bar *t*'s close only touches P&L from *t+1* (`held = pos.shift(1)`).
- **Appraisal-basis verdict.** Market beta is regressed out before judging — the survivor-biased universe can't flatter the result.
- **Walk-forward, not a single split** — optimize on a rolling IS window, score the *next* OOS window.
- **Honest costs** — commission + slippage on turnover.
- **The LLM is sandboxed to proposing** — every output is validated, clamped, and bound by the routing policy before it touches the backtester; the live path degrades gracefully (retry → fallback → cache).

---

*Built at the AI Engineer World's Fair 2026. The market grades every decision — so this agent can actually prove it's learning.*
