# Quant Alpha — Build Spec (Hackathon Overnight)

> **Status:** reviewed — Codex (GPT-5.5) deltas folded into §9.1; second-pass review fixes applied (excess scoring restored; beta risk added; ablation pinned + quality axis; Layer 2 confabulation guard; Tasks D/B reworked; cut priority + port resolved).
> **Owner:** solo build — you direct, Claude implements.
> **Deadline:** Sun **June 28, 12:00 PM**. One overnight. Submission = public repo + 1-min demo video.

---

## 0. Decisions locked (from review)

| Decision | Choice | Consequence |
|---|---|---|
| **Team** | Solo — you direct, I build | Ruthless scope. One flawless path, not five half-features. |
| **Brain** | Gemini 2.5 Flash (already wired) | $5K Antigravity prize is **out** (plain Gemini = the "basic wrapper" it excludes). Accepted. |
| **The star** | **Both** — deterministic routing *spine* + one *live* Gemini iteration | Spine is demo-safe & replayable (no API, no wifi). Live iteration is the "real AI" wow. |
| **Scope** | Tight — core loop + the proof | **No** MongoDB/Voyage memory. **No** Antigravity. **No** new strategy families. |

---

## 1. The one-sentence product

> **We did not build an AI that finds the best trading strategy. We built an AI that learns how to *search* for them — which *kinds* of edges survive on this market — and we can prove the learning generalizes to data the search never saw.**

The strategy is the *receipt*. The **improving research competence** is the product. The chart that wins is **not** the equity curve — it's the one that shows the agent getting smarter (experiments-to-robust trending **down**; first-try survival trending **up**).

### Claims register — say this / never say that

| ✅ Say | 🚫 Never say |
|---|---|
| "It learns which kinds of edges survive here." | "It found the optimal strategy." |
| "It reasons about which edge to pursue." | "It explored thousands of strategies." (A judge will count 3 families.) |
| "We prove the learning generalizes on a held-out slice." | "Sharpe went up, so it's working." (That's a quant *tool*, a theme miss.) |
| **"It beats buy-and-hold out-of-sample (excess Sharpe)."** | **"It has a positive Sharpe."** (Mostly market beta on a survivor basket.) |
| **"Our learned routing policy provably speeds up *and* improves discovery (controlled ablation)."** | **"The ablation proves the LLM learned."** (Ablation tests the *policy*; the LLM is shown *qualitatively*, separately — see §4 Task C / §9.1.) |
| **"The model's own diagnosis steered its next move — here's the ledger."** (qualitative) | **"The model figured out it was a 2008 momentum regime."** (The backtester scores folds; it doesn't know *why*. Don't assert mechanisms the data can't show.) |
| "We brought the backtest engine; tonight we built the autonomous researcher that drives it." | *(silence on attribution)* → **instant DQ risk.** |

---

## 2. Theme mapping (verified against the event page)

Confirmed: AIE World's Fair 2026, hackathon Jun 27–28, **$10K+ prizes**, themes explicitly include *continual learning* and *recursive self-improvement / self-improving agents*. Our mapping:

- **Continual Learning — PRIMARY, lead with it.** Memory, self-reflection (diagnosis), prompt/constraint reshaping the next proposal, adapts from real-world signal (the market), minimal human intervention. Verbatim fit.
- **Self-Improvement Stack — DIFFERENTIATOR.** Most continual-learning demos can't *prove* the learning is real. Our backtester + overfitting guardrail + final holdout **are** the eval/observability infra that makes it provable.
- **Recursive Intelligence — gesture only, never lead.** We touch no weights/architecture/pretraining. Use only the soft phrase "an early form of self-directed intelligence." Overclaiming here gets nuked in Q&A.

---

## 3. Ground truth — what the code actually is today

I read every engine file. The bones are genuinely strong; the "learning" is genuinely fake. Both matter.

**Strong (declare honestly as pre-built infra):**
- `backtest.py` — **honestly no-lookahead** (`held = pos.shift(1)`: a signal at bar *t*'s close only touches P&L from *t+1*). Real costs (2bps + 3bps). Trader-grade metrics. Survives a line-by-line read.
- `walkforward.py` — optimize IS → score OOS → roll → `verdict()` ∈ {ROBUST, FRAGILE, OVERFIT}. **~300 folds per template** across the basket = a statistically meaningful sample *at the fold level*.
- Data — 15 names, **AAPL → 1980, SPY → 1993, NVDA → 1999.** "Decades of data" is true. (`PLAN.md`'s "last 10 years" is a stale note — ignore.)
- `api.py` + `frontend/` — journal-driven; recomputes curves from stored params. UI skeleton exists (`VerdictBadge`, `OverfitReveal`, `ImprovementArc`, `ResearchFeed`, `TradingSimulator`, `BasketHeatmap`).

**Fake (this is tonight's whole job):**
- **The researcher is scripted.** `StubResearcher.propose(history)` = `i = len(history); return SCRIPT[i]`. It **ignores history**. The baseline→overfit→corrected→diversified arc is a hardcoded movie. `diagnose()` is a rule lookup. **The route is preordained, not caused.** The lesson text is decorative.
- **The hero OVERFIT badge never fires.** Real journal proof: greedy `multi_filter` = **IS 1.12 → OOS +0.11, gap 1.01 → FRAGILE**. Per-name XOM/KO/DIS go negative, but the basket *mean* stays positive, so the overall verdict washes to FRAGILE. **Root cause: the strategy is long-biased, so market beta floors OOS at +0.11 — on an *absolute* basis it can't go negative without overfitting hard enough to lose money despite a 40-yr tailwind. On an *excess*-over-buy-and-hold basis (see §5 / Task D) it fires as OVERFIT honestly.** The 30-second "caught itself cheating" beat does not trigger today.

---

## 4. The build — five tasks, in priority order

> Design principle that resolves "both spine + live hero": split the loop into **(a) a creative proposer** (stub *or* Gemini) and **(b) a deterministic routing policy** that converts a verdict+diagnosis into *binding constraints* on the next proposal. Both proposers flow through the same policy. The policy is what makes routing **caused** and **replayable**; the LLM is what makes it **creative and live**.

### Task A — Caused routing (THE spine) · highest leverage · CRITICAL PATH
> Codex flagged this as the critical path **and** the highest slip risk — budget the most time here and **test it end-to-end before touching anything else.** A scripted-but-logged spine + real holdout + real survival number beats a half-wired causal router that crashes on stage.

New module `routing.py`, **two layers**:

**Layer 1 — deterministic policy (safety + replay).** `derive_constraints(history) -> Constraints`, a pure function of past verdicts:
  - Family that returned **OVERFIT** → **banned** (never propose again).
  - Family that returned **FRAGILE** once → next proposal in it must **tighten** (freeze ≥N knobs, lengthen IS, shrink grid). Second FRAGILE → **abandon** → route to a different *kind* of edge (trend ↔ mean-reversion).
  - All families banned/exhausted → stop, report best ROBUST.

  `enforce(proposal, constraints) -> proposal'` repairs/rejects any proposal violating active constraints. Both `StubResearcher` and `GeminiResearcher` call it. **This layer is what makes the demo offline & replayable — and it's the layer the ablation (Task C) measures.**

**Layer 2 — the LLM's own words are the binding signal (qualitative depth, not the quantitative proof).** Codex's sharpest point: *rule-based diagnosis + scripted router = a decision tree with extra steps; a judge asks "what did the AI learn that wasn't already in your rules?"* The answer: the **LLM writes the diagnosis and that text is fed into the next proposal's prompt as a constraint** — the model conditions its next move on its own prior reasoning, not a rule we wrote.
  - **⚠️ Confabulation guard (new):** the **binding signal must be the metric-grounded part of the diagnosis** — parameter count, IS→OOS gap magnitude, *which dated fold* went negative, per-name dispersion. The LLM's natural-language prose may *accompany* it, but the **showcased** lesson must be grounded in numbers the system actually computed. ✅ *"OOS turned negative in the fold covering 2008–09 → this edge is regime-fragile; require positive OOS across ≥80% of folds."* 🚫 *"…because momentum overwhelms mean-reversion"* — the backtester scores folds, it does not know **why** one failed; asserting the mechanism is confabulation, and for the rigor team that's a self-inflicted Q&A wound.
  - **Evidence level (new):** Layer 2 is demonstrated **qualitatively** (a ledger excerpt + the one live iteration), n≈1. Do **not** let it inherit the ablation's quantitative credibility — the ablation tests Layer 1 (see Task C). If time allows, a *small* supplementary check (3–5 seeds: LLM-with-its-own-lessons vs lessons-stripped) can gesture at Layer 2's value, acknowledged as low-n.

- **Rewrite `StubResearcher`** to branch on history (verdicts), not `len(history)`. Same dramatic arc, now genuinely caused.
- **Robustness wrapper** (live path): Gemini call gets 3 retries → logged fallback to a safe canned proposal → cache last-good response. **Lock seeds for the random-search proposer and the (deterministic) backtester.** Note: seed-locking does **not** make the LLM's prose reproducible across calls — the reproducibility guarantee covers the ablation + a committed replay run, not live LLM text. (A judge asking "what if I re-run it?" gets: the *policy and backtest* are deterministic; the *LLM iteration* is shown as a committed replay.)
- **Journal records the causal link**: `caused_by` (prior iter #), `action` ∈ {baseline, tighten, abandon, diversify}, `constraints`, `banned_families`, **plus the verbatim LLM lesson carried forward**.

**Done when:** (1) deleting/altering an early verdict provably changes a later proposal; (2) the journal shows a *specific, metric-grounded* LLM lesson causing the next proposal to avoid what failed; (3) the live path degrades gracefully (retry→fallback) without crashing.

### Task D — Make a real OVERFIT fire (early — it gates the hero beat) · HARD TIMEBOX ~1h
> Codex's warning: this can rabbit-hole. Don't spend two hours hand-tuning cutoffs into something arbitrary a judge attacks. Timebox it.
- **Score on EXCESS over buy-and-hold (see §5) — this is what makes the catch honest *and* removes the rabbit-hole.** The greedy `multi_filter` is long-biased, so on an *absolute* basis market beta floors OOS at +0.11 and you'll fight that floor all night. On an *excess* basis the floor is gone — an overfit strategy underperforms buy-and-hold, so OOS excess goes **negative naturally**, from window/grid alone, no threshold gymnastics.
- **First choice (honest):** keep thresholds as-is, find a genuinely overfit config — **short IS (~1yr) + a real fat grid over all 5 `multi_filter` knobs** — so basket-mean OOS **excess** Sharpe goes **negative**.
- **If still not reached in ~1h (unlikely once on excess):** surface the **per-name OVERFIT fraction** as a *supplementary* robustness signal in the reveal (XOM/KO/DIS already go negative) — but do **not** redefine the verdict to a per-name rule to force the badge (that invites "why is your overfitting criterion this oddly specific shape?"). The excess basis should make this fallback unnecessary.
- Make the config **reproducible and clean** (one legible OVERFIT story) — it's the hero beat, not a messy random failure.

**Done when:** one proposal reproducibly carries an **OVERFIT** verdict from a committed config — basket-mean OOS **excess** Sharpe < 0, by window/grid — never by silently moving (or oddly reshaping) a threshold.

### Task C — The ablation (THE proof the *routing policy* learned) · un-cuttable
> Codex independently reached the same verdict I did: *with 3 families and a handful of iterations, the bare survival curve is "largely theater."* It added two requirements I'm adopting: **enough experiments** (≈20–30, run automated overnight — not 5 live), and the curve must be **blind to ordering** (if families always run in the same sequence, the judge says it was *pre-sequenced*, not chosen). The controlled ablation answers all of it. Backtests are vectorized (seconds), so this is cheap.

- **Proposer = seeded RANDOM-SEARCH over the template/param space — NOT Gemini**, **randomized family order per seed** (kills the pre-sequencing critique). Why random-search not the LLM: K×2×~6 = **120–250 Gemini calls** would be slow, cost money, and LLM variance would *confound* the only-one-knob-differs control. (The *backtests* are seconds; *Gemini calls* are the bottleneck — that's why the ablation runs offline.) This isolates the **routing policy** cleanly.
- **Two arms, identical except one knob:**
  - **memory-ON** = proposer **∩** `derive_constraints(history)` (bans doomed families, tightens).
  - **memory-OFF** = proposer alone (blind to history; re-proposes banned families; no tightening).
- **K ≈ 15–25 seeds per arm**, ≥20 experiments visible in the ledger. Metrics — **both axes**:
  - **Speed:** experiments-to-first-ROBUST, first-try survival rate.
  - **Quality (new):** best OOS **excess** Sharpe reached. *(Speed alone is near-tautological — memory-OFF re-proposes banned families by construction, so "fewer experiments" is partly just "no amnesia." The quality axis turns the result into "better outcomes," which a judge can't wave away.)*
- **What it proves — claim precisely:** the **routing policy** accelerates *and* improves discovery (system-level). It does **not** prove the LLM reasons better; that's Layer 2, shown qualitatively (Task A).
- **Killer chart:** memory-ON reaches ROBUST in *fewer* experiments *and* at *higher* excess Sharpe, **error bars across seeds**, clearly separated.

**Done when:** committed `ablation.json` + chart shows memory-ON beats memory-OFF on **both** experiments-to-robust **and** best-excess-Sharpe, with separated error bars, and family order is provably randomized per seed.

### Task B — Final never-touched holdout (the uncontaminated proof)
- **⚠️ Decision point — I reversed your holdout axis; override if you have a reason.** Your draft used a cross-sectional (held-out tickers) exam set, reasoning "walk-forward already consumes each name's full time axis." **That rationale doesn't bind:** you simply truncate the loop's data at a cutoff date and walk-forward runs inside the remainder — the only cost is the strategies aren't tuned on the most recent regime (arguably a *feature*).
- **Recommended (primary): out-of-TIME holdout.** Reserve the last ~3 years; the entire search/ablation reads **only** pre-cutoff data; at the end, score the **winning** family and a **rejected** family on the held-out tail, **once**. For a *trading* claim this is the gold standard — it answers "will it work going forward," the only question markets ask.
- **Alternative (if you keep cross-sectional): label it honestly as out-of-ASSET, not out-of-time, and pair it with excess scoring.** Held-out names (DIS/KO/HD/PG) are same-period correlated large-caps — they share the very beta/regime you're controlling for; catches name-specific overfitting but misses regime/time overfitting (the more dangerous kind).
- **Sealed & declared in advance (Codex — keep this regardless of axis):** commit to the winning family on IS/OOS evidence *before* opening the holdout; open it exactly once; never choose *which* family to test after seeing results. *"If you cherry-pick, a quant judge will know."*
- **Proof:** the family the agent *learned to trust* stays ROBUST on data it never saw; a family it *learned to reject* stays FRAGILE/OVERFIT there too — on an **excess** basis.

**Done when:** a one-shot `holdout.json` shows winner=ROBUST, rejected=not-ROBUST on a slice the search never saw (excess basis), with a guard that the held-out slice is absent from every search/ablation code path.

### Task E — Emit the competence metrics + wire the UI
- Per-run: `experiments_to_first_robust`, `first_try_survival`, `banned_families` timeline.
- Cross-run: the ablation summary feeding `ImprovementArc`.
- **Experiment ledger** (Codex's high-leverage, low-cost add) — extend `ResearchFeed` into one inspectable table: per iteration → proposed family + params, IS Sharpe, OOS Sharpe, **OOS excess Sharpe**, verdict, **plain-English diagnosis**, **routing decision / `caused_by`**. Seeing the full causal chain for 15–20 experiments at a glance is *harder to dismiss as theater* than a single rising curve.
- Wire `OverfitReveal` to the Task-D experiment; **show `oos_excess_sharpe` vs `benchmark_oos_sharpe` side by side (edge-vs-beta).** Wire `ImprovementArc` to the ablation. **Replay a committed precomputed run** so the demo survives venue wifi; optionally trigger **one** live Gemini iteration on stage.

**Done when:** the frontend renders the ablation chart and the OVERFIT reveal (with excess-vs-beta) from committed journal data with the API + Next dev server only.

---

## 5. The frozen interface — journal schema v2

Extend the existing record (frontend `Experiment` keeps all current fields → backward compatible). **Note: absolute `is_sharpe`/`oos_sharpe`/`gap` are now DISPLAY-ONLY; the verdict and the optimizer run on EXCESS-over-buy-and-hold.** Add:

```jsonc
{
  // ...all existing fields (iteration, template, verdict, is_sharpe, oos_sharpe, gap,
  //    per_ticker, diagnosis, lesson, accepted)  ← is/oos/gap kept for DISPLAY ONLY...

  // EXCESS-over-buy-and-hold — what the verdict + optimizer actually use:
  "is_excess_sharpe": 0.91,        // in-sample Sharpe of (strategy − buy_and_hold) returns
  "oos_excess_sharpe": -0.20,      // out-of-sample, same basis — THE number the verdict reads
  "excess_gap": 1.11,              // is_excess − oos_excess (the overfitting signal)
  "benchmark_oos_sharpe": 0.48,    // absolute buy-and-hold Sharpe — show edge-vs-beta side by side
  "best_oos_excess_so_far": 0.31,  // replaces best_oos_so_far

  // caused-routing + ablation:
  "action": "baseline | tighten | abandon | diversify",
  "caused_by": 2,                     // iteration # whose lesson forced this move (null for baseline)
  "constraints": { "banned_families": ["multi_filter"], "min_is_years": 5, "max_combos": 12 },
  "llm_lesson": "OOS negative in the 2008-09 fold; 5 knobs over-fit — cut to <=2, lengthen IS.",
  "arm": "live | memory_on | memory_off",   // which experiment arm produced this
  "seed": 7                                  // for ablation reproducibility (proposer + backtester only)
}
```

Verdict thresholds now apply to **excess** (start `MIN_OOS_EXCESS_SHARPE` ≈ 0.2, `MAX_EXCESS_GAP` ≈ 0.5 — tune; expect fewer ROBUST, that's the point). Plus two new artifacts: `runs/<id>/ablation.json` (per-seed experiments-to-robust + best-excess, both arms) and `runs/<id>/holdout.json` (one-shot exam scores). **Lock these fields before building** — they're simultaneously the agent's memory, the demo's data, and the UI's input.

> **Port resolved:** standardize on **8000**; set `frontend/lib/api.ts` default to `8000` (was 8077).

---

## 6. The hero demo (≤ 90s, replayed for safety)

1. **Propose** — agent proposes the greedy `multi_filter` (looks spectacular in-sample). `[OVERFIT ✗]` badge fires (excess basis).
2. **Reveal** — `OverfitReveal`: IS curve soaring, OOS curve collapsing, **vs the buy-and-hold benchmark line** (edge-vs-beta). *"It looked great — until data it hadn't seen."*
3. **Diagnose → Route** — journal shows `caused_by: 2 → action: abandon → diversify`, with the *metric-grounded* lesson. *"It caught itself cheating, understood why, and changed research direction."*
4. **Survive** — next proposal (mean-reversion) comes back ROBUST OOS **on an excess basis** (verify `rsi_reversion` clears the excess bar — see §9).
5. **Prove** — `ImprovementArc`: memory-ON vs memory-OFF, error bars (speed *and* excess-Sharpe). Then the **sealed holdout, opened live exactly once**: *"and on data it never touched, the family it trusted still holds and the one it rejected still fails."*
6. (Optional, if wifi cooperates) one **live** Gemini iteration on stage — framed as the model's own reasoning, *qualitatively*.

---

## 7. Build order (solo, overnight)

```
A (caused routing spine)  ──►  D (real OVERFIT)  ──►  C (ablation proof)
        │                                                   │
        └────────────►  B (holdout)  ◄──────────────────────┘
                                │
                                ▼
                        E (metrics + UI wiring + commit a replay run)
```
Critical path = **A → D → C**. First cut if short on time = the **live-Gemini step** (optional garnish). **Protect both B and C** — C proves the learning is *efficient*, B proves it *generalizes*; they answer different Q&A attacks. If truly desperate, trim B to winning-family-only on the holdout (drop the rejected-family check), but **keep the holdout**. Do **not** cut C.

---

## 8. Out of scope (explicit — protect the night)

- MongoDB Atlas / Voyage memory substrate.
- Antigravity / Interactions API hosted-agent spike.
- New strategy families beyond the existing 3.
- Intraday / new data. Shorting redesign. Portfolio construction.
- Any feature whose headline is the dashboard (banned). UI is *evidence*, never the headline.

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Meta-overfitting** ("you tried N families, kept the winner on your test data") | The ablation (C) + final holdout (B). We claim *learning-to-search*, never *the optimum*. |
| **Booking beta as alpha** ("what's buy-and-hold's Sharpe on this same basket?") | **Verdict + optimizer scored on EXCESS over buy-and-hold (§5); absolute Sharpe display-only. Survivor-biased universe (AAPL/NVDA) makes absolute doubly flattering — excess neutralizes it.** The #1 quant-judge attack; answerable in one sentence. |
| **"n=6, where's your control?"** | Task C — controlled ablation, error bars across seeds, **both** speed and quality axes. |
| **Ablation implies the *LLM* learned** | Ablation isolates the **routing policy** (random-search proposer); the LLM is shown reasoning **qualitatively & separately**. Claims register enforces the wording. |
| **LLM confabulation** (impressive but unverifiable causal story, e.g. "2008 momentum regime") | Bind on the **metric-grounded** diagnosis; showcased lessons cite computed numbers / dated folds, never mechanisms the backtester can't show (Task A, Layer 2 guard). |
| **Excess scoring → few/no ROBUST strategies → no "survive" beat** | Expected (most "edges" are beta — that's the story). Verify `rsi_reversion` clears the excess bar for §6 step 4; if needed tune `MIN_OOS_EXCESS_SHARPE` (~0.2) **honestly** and say so. |
| **OVERFIT won't fire honestly** | Task D early, **on the excess basis** (the beta floor is *why* absolute washes to FRAGILE). Per-name OVERFIT fraction is a *supplementary* signal — **never** redefine the verdict to force the badge. |
| **Live Gemini flakiness / wifi** | Demo runs off a **committed replay**; live iteration is optional garnish. Retry×3 → logged fallback to canned proposal → cache last-good. Validated/clamped in `_sanitize`. |
| **Non-reproducibility** | Lock seeds for proposer + (deterministic) backtester; commit the demo run. **Note:** the LLM's prose is *not* seed-reproducible — that part is shown as a committed replay, not claimed deterministic. |
| **"Decision tree with extra steps"** | LLM's metric-grounded diagnosis is the binding signal (Task A, Layer 2), not just rule code — shown via the ledger. |
| **Ordering confound in the curve** | Randomized family order per seed in the ablation (Task C). |
| **Attribution DQ** | Same honest line in demo + video: engine pre-built, researcher built tonight. |

### 9.1 Independent review (Codex) — verdict & deltas

**Convergence:** Codex reached the same core conclusion unprompted — the bare survival curve is *"largely theater"* without more experiments and a control. Two independent reviewers → the ablation (Task C) is the **spine of credibility, not optional.**

**Adopted from Codex:**
- *Task A, Layer 2* — make the LLM's verbatim diagnosis the binding signal, so it's learning, not a lookup table. Biggest refinement — **but see the second-pass caveats:** (1) the binding signal must be **metric-grounded**, not a confabulated mechanism; (2) Layer 2's evidence is **qualitative (n≈1)** and must not borrow the ablation's quantitative weight (the ablation tests Layer 1).
- *Experiment ledger* (Task E); *≥20 experiments + ordering-blind* (Task C); *retry/fallback + seed-lock* (Task A); *sealed holdout* (Task B); *hard timebox on OVERFIT* (Task D).

**Overridden — keep `multi_filter` in the loop.** Codex suggested cutting the 5-knob `multi_filter` from the live proposal space (it always fails messily). Keeping it: **its failure *is* the hero beat** *and* it's load-bearing for the ablation (the doomed family memory-ON learns to avoid while memory-OFF keeps stumbling into). The fix to Codex's real concern is Task D — make its overfit *clean and reproducible* (now easier on the excess basis), not messy. **Flag for you:** if you'd rather follow Codex and pull it from the live loop, say so — it changes the hero demo.

**Second-pass review delta (this revision):** restored **excess-over-benchmark scoring** as the verdict basis (the missing #1 credibility axis — it answers the beta attack *and* de-risks Task D); pinned the **ablation proposer to random-search** + added a **quality axis**; added the **Layer 2 confabulation guard** + **evidence-level caveat**; defaulted the **holdout to out-of-time**; protected **B** from the first-cut list; resolved the **port**.

---

## 10. Definition of done

- [ ] **Excess scoring:** verdict + optimizer run on excess-over-buy-and-hold; absolute Sharpe display-only; sanity `excess_sharpe(buy_and_hold) == 0`.
- [ ] A: route is a provable function of verdicts; journal shows cause→effect with a *metric-grounded* LLM lesson; live path degrades gracefully.
- [ ] D: a genuine OVERFIT verdict fires from a committed config **on the excess basis** (no threshold fudging/reshaping).
- [ ] C: `ablation.json` + chart, memory-ON beats memory-OFF on **both experiments-to-robust and best-excess-Sharpe**, error bars, randomized family order. **Proposer = seeded random-search.**
- [ ] B: `holdout.json`, winner ROBUST / rejected not-ROBUST on a slice the search never saw (excess basis), sealed & declared in advance.
- [ ] E: frontend renders the OVERFIT reveal (+ excess-vs-beta) + ablation arc + experiment ledger from a committed replay run.
- [ ] 1-min video; repo public; attribution line stated.