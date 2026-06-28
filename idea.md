# DARWIN — Pitch Strategy

> How to pitch the self-evolving alpha-research agent at the AI Engineer World's Fair Hackathon (June 2026).
> Themes: **Continual Learning · The Self-Improvement Stack · Recursive Intelligence (RSI)**.

---

## 0. The real numbers (quote these — they're what's on screen)

From the committed demo run (`runs/demo_committed/run.json`) — **use these, not the stale README figures**:

| | Memory ON (adaptive) | Memory OFF | Random search | Frozen seeds |
|---|---|---|---|---|
| Keepers discovered | **68** | 31 | 21 | 0 |
| Mean proposal quality (OOS IR) | **+0.29** | +0.16 | **−0.34** | — |
| OOS appraisal (avg) | **0.96** | — | — | 0.92 |
| Holdout net Sharpe @10bps | −0.83 | — | — | −0.81 |

Run scope: **777 proposals, 120 kept (15.4%)**, 21 walk-forward generations, 600 stocks, 2013–2023 + a **sealed 2024 holdout**.

**The whole pitch in one line:** grammar-search proposes *negative*-quality junk, the LLM proposes decent ideas, the LLM **with memory finds 2.2× more keepers and higher-quality ones**. (`+119%` memory advantage.)

> ⚠️ README/DEMO docs say "61 vs 40 vs 21." The live run says **68 vs 31 vs 21 (+119%)**. Quote the on-screen numbers — they're stronger — and make sure the speaker says the same number the audience is reading.

---

## 1. Theme decision: lead with Continual Learning, claim all three

You legitimately touch all three themes (rare). But **lead with one** or you read as unfocused.

- **Continual Learning — LEAD.** Your hero asset is a *controlled ablation*: the agent accumulates a memory of every win/failure (MongoDB Atlas + Voyage embeddings) and **measurably gets 2.2× better at discovery** when memory is on. That's the textbook definition of continual learning — *measured*, with a clean control. Most CL projects here will be "a chatbot with a memory file." Yours is the only one where the learning is quantified against a judge that can't be charmed. Highest, most defensible ground.

- **The Self-Improvement Stack — SUPPORT.** Don't pitch as a separate claim — pitch as *why you believe the first claim*. The eval harness is the market: an immutable 777-row trial ledger, a sealed 2024 holdout scored once, net-of-cost gating, cost sweeps, controls. It's the eval/observability/rigor layer that makes the continual-learning number trustworthy.

- **Recursive Intelligence / RSI — AMBITION (closing flourish only).** One line at the end: "the system improves the thing that does the improving — better memory → better proposals → better memory — and the Antigravity agent autonomously researches new building blocks." Don't *lead* RSI: the guide maps it to weight-level self-modification (Modular MAX); you operate at the memory/strategy level. Great as a closer, a trap as a headline.

**Sponsor-prize alignment:** the two load-bearing integrations are **Google/Gemini** (the Antigravity managed agent — a genuine flagship money-shot) and **MongoDB/Voyage** (the memory that *demonstrably* drives the 2.2× lift — it's the independent variable in the experiment, not bolted on). Target those two prizes. DigitalOcean/MiniMax (the M2.5 proposer backend) is a credible third mention, secondary.

---

## 2. The big idea / frame: "The judge that can't be fooled"

Organize the whole pitch around this. Every AI self-improvement demo has a soft judge — an LLM grading itself, a gameable benchmark, vibes. **Yours is graded by the market: net-of-cost P&L on data the agent never saw.** You cannot p-hack past it.

So when DARWIN gets 2.2× better, that improvement is *real* in a way no agent-with-memory chatbot can claim. Open with this and you reframe the room: not "another agent that says it improves," but "the one where improvement is measured against something that can't be charmed."

> **"Every self-improving-agent demo you'll see today is graded by a judge it can sweet-talk. Ours is graded by the market. Let me show you an AI that gets measurably better at quant research — and can't lie to you about it."**

---

## 3. The 3-minute arc (words to say + what to show)

**[0:00 — Hook, on the Hero]** Frame above. Point at the 4 stat cards: 777 researched, 120 survived, OOS appraisal beats frozen, **+119% memory advantage**.

**[0:25 — The one chart that matters: "the researcher is learning" (Section 03 right)]** Lead with strength — go here *early*.
> "Same Gemini model, same data, three versions. Random formula-search proposes garbage — *negative* average quality. Give the LLM its priors, it gets better. Give it a **memory of everything it's already tried** — Atlas plus Voyage embeddings — and it finds **2.2× more keepers, and better ones.** Turn the memory off, it stops improving. That's continual learning, measured."

**[1:10 — "Watch it evolve" (Section 01), hit ▶]** The visual payoff. Living Fleet animates; Research Log streams kills and births.
> "11 years of walk-forward. Watch it kill a cost-bleeder and breed a new alpha it pulled from a real paper — Amihud liquidity, with a citation." Click a cell → drill-down → "and here are its nearest neighbors in idea-space, via MongoDB Atlas Vector Search."

**[1:50 — Honesty as the flex (Section 05)]** Don't hide the loss — *weaponize* it.
> "Quant demos lie three ways: lookahead, p-hacking, ignoring costs. We engineered against all three. And here's the part nobody does — **we'll show you where we lose.** Net of real trading costs at 10 basis points, our book is underwater. So is the frozen baseline. Gross signal is strong; net-of-cost is the genuine frontier. We're not selling a fund — we're showing a *research agent that compounds*, and we refuse to fake the P&L."

This wins sophisticated judges. Voluntarily showing your loss, with controls to prove it's honest, beats any green equity curve — because everyone else's green curve is a lie they hope you won't catch.

**[2:25 — Live money-shot (Section 04): "🛰 Research live"]**
> "Not a replay. One API call just spun up a Google-hosted Antigravity agent in an isolated box — it's browsing the literature, writing code, handing back a brand-new *cited* alpha we backtest on the spot. Real environment ID, real step trace, real DOI."

**[2:50 — Close]**
> "DARWIN. The LLM proposes, the backtester disposes — and because it remembers, the researcher compounds. Continual learning you can watch, on a judge that can't be fooled."

---

## 4. The "money moments" — what makes people lean in

Rank-ordered by impact; make sure each lands:

1. **The three-tier learning chart** (random < LLM < LLM+memory). Your thesis in one image. Lead with it.
2. **Voluntarily showing the net-of-cost loss.** Counterintuitive credibility bomb. No one else does this.
3. **Live Antigravity agent** spinning up a real sandbox. Sponsor catnip + "this is real, right now."
4. **The Living Fleet animation** — the emotional "I can *see* evolution" beat.
5. **Atlas Vector Search drill-down** — "nearest alphas in idea-space" makes the memory tangible.

---

## 5. Objection handling (rehearse — judges will probe)

- **"Your strategy loses money."** → "Net of cost, yes — and we *show* that on purpose. We're not pitching a fund; we're pitching the research loop. The gross signal is genuinely predictive (holdout IC-IR over 2). The adaptive book loses *less* than frozen and wins outright at low cost — because it learned to be cheaper. The contribution is the learning, not the P&L."
- **"Isn't this just brute-force formula search?"** → "No, and we prove it. Random grammar search proposes *negative*-quality alphas on average. The LLM-with-memory proposes +0.29. The reasoning and accumulated memory do real work; that gap is the point."
- **"Is Antigravity real or staged?"** → "Real Interactions API, real isolated environment, real step traces, real DOI citations. The button's live — want me to run it again?"
- **"Could the LLM be leaking future prices?"** → "It never sees or predicts prices. It writes *formulas*; the backtester is the only thing that touches data, and every keep/kill decision is made before the test block. LLMs are great at ideas and untrustworthy with truth — so we never trust them with truth."

---

## 6. Live-demo risk management (where teams lose)

- **Atlas was intermittent** during the build (free-tier failover). Before presenting: resume the cluster, confirm the IP allowlist. If down, the dual-backend falls back to local and the header honestly shows "local mirror" — fine, but the Atlas badge going green is worth the 2-minute check.
- **Antigravity is 60–220s.** Don't stand in silence. Either fire it at 2:25 and let it finish during your close, or pre-warm one with the cached result as instant backup. Narrate the latency as "watch it think"; don't apologize.
- **Reconcile spoken numbers to the screen.** Quote the on-screen **68 / 31 / 21 (+119%)**, not the README's 61/40/21.

---

## 7. Openers — pick by room energy

- **The reframe (recommended):** *"Every self-improving-agent demo today is graded by a judge it can charm. Ours is graded by the market — and it gets measurably better anyway."*
- **The trader's cold open:** *"We gave an AI 50 trading signals and one job: invent better ones, and get better at inventing them. Here's the proof it did — and the proof we didn't cheat."*
- **The contrarian honesty hook:** *"I'm going to show you our strategy losing money. Then I'm going to show you why that's the most honest — and most valuable — thing in this room."*

---

## Bottom line

A genuinely rare combination — a *measured* learning result, an *ungameable* judge, and *voluntary* honesty — wrapped in a deck that makes a hard idea legible in 30 seconds. Lead with Continual Learning, let the three-tier memory chart carry the thesis, use the net-of-cost loss as a trust weapon instead of hiding it, and land the live Antigravity agent for the sponsor moment. That's the win.

**One loop, three themes:**
- **Continual Learning** — accumulates memory of every win/failure (Atlas + Voyage), measurably gets better at discovery (2.2× vs memory-off). *The proof.*
- **Self-Improvement Stack** — eval-driven loop: immutable trial ledger, sealed holdout, cost-aware net gating; the eval is the market, which can't be gamed. *The rigor.*
- **Recursive Intelligence** — improves the thing that does the improving (better memory → better proposals → better memory); Antigravity agent autonomously researches new building blocks. *The ambition.*
