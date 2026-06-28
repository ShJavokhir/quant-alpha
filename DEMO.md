# DARWIN — 3-minute demo script

**Setup:** `./run_demo.sh` → open `http://localhost:5173` (fullscreen). Works offline off the
committed run; backend adds drill-downs + Atlas vector search + the live button.

## The arc (≈3 min)

**0:00 — The hook (Hero)**
> "This is Darwin. We gave an AI 50 known trading signals and asked: *can it research new ones —
> and get better at researching over time?* Over 11 years of market history it ran **N research
> generations**, proposed **~hundreds of alphas**, and kept only the ones that survive a brutal,
> cost-aware backtest."

Point at the 4 stat cards: alphas researched, survived selection, net Sharpe vs frozen, **memory hit-rate lift**.

**0:30 — Watch it evolve (Section 01)**
Hit ▶ on the timeline. The **Living Fleet** animates — cells (alphas) are born (green pulse),
thrive (bright), decay (dim), and get retired. The **Research Log** streams alongside:
> "Watch it kill `alpha053` — a cost-bleeder, 1.5× daily turnover — and breed
> `liquidity_momentum`, an idea it pulled from Amihud (2002), with a real citation."

Click any cell → drill-down: the **formula**, its IC/equity curves, and *nearest alphas in
idea-space via MongoDB Atlas Vector Search*.

**1:30 — Proof it's improving (Section 02)** — the two money charts:
- **Adaptive vs Frozen (out-of-sample):** the evolving, cost-disciplined book pulls ahead of the
  frozen seed fleet on net-of-cost Sharpe; regime bands (COVID, 2022) shaded.
- **The researcher is learning:** the agent (memory ON) discovers keepers far faster than its
  memory-ablated self and than random search.
> "*This* is the point. It's not that we found one good strategy — it's that the **researcher
> itself gets better**, because it remembers what it already tried. Turn the memory off, it
> stops improving. That's continual learning, measured."

**2:15 — Why you can trust it (Section 03)**
> "Quant demos lie in three ways — lookahead, p-hacking, ignoring costs. We engineered against
> all three: every decision is made *before* the test block; a **sealed 2024 holdout** scored
> once; every trial logged; a cost sweep and a 1-day execution delay; random + memory-off
> controls."

**2:30 — See it research, live (Section 03)** — the sponsor money-shot:
Hit **🛰 Research live**. One API call spins up a Google-hosted **Antigravity managed agent** in an
isolated environment; watch it browse the web, run code, and bring back a brand-new *cited* alpha,
which we backtest on the spot (~1 min). Also the instant **Propose live** (Gemini) button.
> "This isn't a replay. That alpha was just researched by a Gemini Antigravity agent in a sandbox it
> spun up seconds ago — it read a real paper, wrote code, and we backtested the result live. The
> alphas it discovers (you'll see the 🛰 badge in the fleet) carry real citations and the agent's step trace."

**Close:**
> "Darwin: the LLM proposes, the backtester disposes — and the researcher compounds.
> Built on Gemini, MongoDB Atlas + Voyage, and Firecrawl."

## One-liners to have ready
- *Why not just trust the LLM's price calls?* It never predicts prices — it writes signals; the
  backtester is the judge. LLMs leak and hallucinate on prices; they're great at *ideas*.
- *Is the edge real money?* Gross signal is strong; net-of-cost is the hard frontier (we show the
  full cost sweep). The contribution is the **autonomous, improving research loop**, not a fund.
- *Survivorship/caveats?* Current-index universe; formulas in-sample to their 2015 publication.
  Disclosed on the page.
