# DARWIN — an AI that researches trading alphas and measurably gets better at it

> **The LLM proposes, the backtester disposes.** A research agent that invents
> quant trading signals, kills the weak, breeds the strong, and **accumulates
> memory that compounds into sharper research over time** — proven against a judge
> it cannot fool.

#### Built on the sponsor stack — every integration is load-bearing
[![Gemini 3.5 Flash](https://img.shields.io/badge/Gemini%203.5%20Flash-4285F4?style=flat-square&logo=googlegemini&logoColor=white)](https://ai.google.dev/gemini-api/docs)
[![Antigravity Agent](https://img.shields.io/badge/Antigravity%20Agent-6645E6?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/gemini-api/docs/antigravity-agent)
[![MongoDB Atlas](https://img.shields.io/badge/MongoDB%20Atlas-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/)
[![Voyage AI](https://img.shields.io/badge/Voyage%20AI-C2459A?style=flat-square)](https://www.mongodb.com/docs/voyageai/)
[![DigitalOcean Gradient](https://img.shields.io/badge/DigitalOcean%20Gradient-0080FF?style=flat-square&logo=digitalocean&logoColor=white)](https://docs.digitalocean.com/products/gradient-ai-platform/)
[![MiniMax M2.5](https://img.shields.io/badge/MiniMax%20M2.5-EE4D2D?style=flat-square)](https://platform.minimax.io/docs/api-reference/api-overview)

<sub>Gemini authors the alphas · **Antigravity** researches new ones live in an isolated cloud box · **Atlas + Voyage** are the memory that *drives* the learning lift · **MiniMax-M2.5 on DigitalOcean** is the swappable reasoning proposer. Full breakdown ↓</sub>

---

## Why this is different — read this first

Most "self-improving agent" demos are graded by a soft judge: an LLM scoring
itself, a benchmark that can be gamed, or vibes. **Ours is graded by the market.**

Every signal DARWIN invents is run through a **deterministic backtest** — rank
correlation against *forward* returns, dollar-neutral, net of real trading costs,
on data the agent never saw. You cannot p-hack, charm, or hallucinate your way past
it. So when we show the agent getting better, that improvement is **measured, not
asserted.**

That is the whole thesis: **a self-improvement loop with an evaluator that can't be
fooled.**

---

## What it does, in one breath

We seed the agent with 50 known cross-sectional equity alphas. Each research
"generation" — one walk-forward step through 2013–2024 — it:

1. **Evaluates** every live alpha on a trailing window (IC, IC-IR, appraisal, turnover, cost).
2. **Prunes** the decayed, the cost-bleeders, and the redundant — natural selection.
3. **Researches** new alphas — Gemini proposes formulas conditioned on a **memory**
   of every past win and failure (MongoDB Atlas + Voyage embeddings); a Gemini
   **Antigravity** managed agent spins up an isolated cloud box to browse the
   literature, write code, and return brand-new, *cited* alphas.
4. **Validates** each candidate in a sandboxed backtest, de-dupes against the fleet,
   and admits only the keepers.
5. **Trades** the evolved fleet and scores it on the *next unseen block*.

Every keep / kill / add decision is made **before** the test data is seen.

---

## What we measured — the proof

Full run: **600 US stocks, 2013–2024, 21 walk-forward generations, 777 alphas researched.**

### 1 · The researcher learns (the core result)

Same Gemini model, same data, three setups — only the memory differs:

| Proposer | Keeper alphas discovered | Avg proposal quality (out-of-sample IR) |
|---|:---:|:---:|
| **LLM + memory** | **68** | **+0.29** |
| LLM, memory ablated | 31 | +0.16 |
| Random formula search | 21 | −0.34 |

Memory makes the agent discover **+119% more** keepers — and propose *better* ones.
Random formula search proposes *negative*-quality junk. Turn memory off and the
agent stops improving. **This is continual learning, isolated by a controlled
ablation** — not a claim, a measurement.

### 2 · The fleet adapts

Across 21 unseen blocks, the evolving book beats the frozen seed fleet on
out-of-sample **appraisal (0.96 vs 0.92)** and **IC-IR (1.48 vs 1.37)**, while
turning over far less.

### 3 · We show where we lose (honestly)

Gross signal is strong (holdout IC-IR > 2). But **net of realistic 10 bps costs the
book is underwater — and so is the frozen baseline.** On the single sealed 2024
holdout, the elite frozen seeds even had a better year. We **display** this; hiding
it would be the exact self-deception the system is built to prevent. The
contribution is the *improving research loop*, not a profitable fund.

---

## Why you can trust the numbers

A deterministic judge only matters if you can't cheat it. We engineered against the
three ways quant results lie:

- **Lookahead** → prospective walk-forward; every decision made before the test
  block; a **sealed 2024 holdout** scored exactly once.
- **P-hacking** → an immutable ledger of all **777 trials**; random-search and
  memory-ablated **controls**; a safe DSL sandbox (whitelisted AST — LLM-written
  formulas run without trust; injection attempts blocked in tests).
- **Ignoring costs** → net-of-cost gate at 10 bps, a full **cost sweep (1→50 bps)**,
  a 1-day execution-delay test, and a liquid top-600 universe.

---

## Built on the sponsor stack

Every sponsor product below is **load-bearing** — pull it out and the result changes.

| Sponsor product | What it powers in DARWIN | Read more |
|---|---|---|
| **Google Gemini 3.5 Flash** | the memory-conditioned alpha proposer | [docs ↗](https://ai.google.dev/gemini-api/docs) |
| **Gemini Antigravity** managed agent (`antigravity-preview-05-2026`) | spins up an isolated Google-hosted box to browse the web + run code and return *cited* alphas (real DOIs, step traces, env IDs) — **live on stage** | [docs ↗](https://ai.google.dev/gemini-api/docs/antigravity-agent) |
| **MongoDB Atlas Vector Search** | the agent's memory + idea-space "nearest alphas" — the substrate that *drives* the +119% learning lift | [docs ↗](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/) |
| **Voyage AI** (`voyage-3.5`, 1024-d) | embeddings for memory, de-duplication, and similarity search | [docs ↗](https://www.mongodb.com/docs/voyageai/) |
| **DigitalOcean Gradient Inference** (`inference.do-ai.run`) | serves the swappable reasoning proposer through one OpenAI-compatible key | [docs ↗](https://docs.digitalocean.com/products/gradient-ai-platform/) |
| **MiniMax M2.5** | the reasoning ("interleaved thinking") proposer model, served on DigitalOcean | [docs ↗](https://platform.minimax.io/docs/api-reference/api-overview) |

<sub>Also uses Firecrawl to gather the grounded literature corpus. Data: ~1,200 US stocks, daily OHLCV, 2010–2024 (run on a liquid top-600 universe).</sub>

---

## Run it / what to look at

```bash
./run_demo.sh     # FastAPI :8090 + Vite :5173  →  open http://localhost:5173
```

The dashboard replays a committed run **fully offline**. With the backend up you also
get per-alpha drill-downs, Atlas vector search ("nearest alphas in idea-space"), a
live **⚡ Propose** button (Gemini authors + backtests a new alpha on the spot), and
**🛰 Research live** (the Antigravity agent researches a brand-new alpha in real time).

**In the demo, look for:**
- **Section 03 — "the researcher is learning"**: the three-tier chart above. This is the thesis.
- **Section 01 — the Living Fleet**: watch alphas get born, thrive, decay, and culled across 11 years.
- **Section 05 — the honesty panel**: the sealed holdout, cost sweep, and controls.

---

## Honest caveats

Current-index universe (survivorship bias); seed formulas are in-sample to their
~2015 publication; the 2024 holdout is a single year. Net-of-cost profitability is the
genuine frontier and we do **not** claim it. This is a research demo, not investment
advice. We never claim to beat the market — we claim an AI that **learns to search for
alpha**, and we prove it.
