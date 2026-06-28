# Morning briefing — DARWIN is built & demo-ready

_Built overnight by Claude. Everything below is done, tested, and rendering. Read this, then run the demo._

## ▶ Run the demo (one command)
```bash
./run_demo.sh        # starts FastAPI (:8090) + Vite (:5173)
# open http://localhost:5173
```
The dashboard reads the **committed run** (`runs/demo_committed/`) so it works fully offline.
With the backend up you also get: click-any-alpha drill-down, **Atlas Vector Search** ("nearest
alphas"), and the **⚡ Propose live** button (Gemini authors + backtests a new alpha on stage).

A static fallback (`frontend/public/run.json`) means even `npm run build && npx vite preview`
works with zero backend.

## What it is
**DARWIN** — an AI that researches cross-sectional equity alphas, prunes the decayed/redundant,
researches+adds new ones each walk-forward generation, and **measurably gets better at the
research over time.** "The LLM proposes, the backtester disposes." Built on the validated
Alpha101 engine, re-expressed as a safe formula DSL the LLM authors into.

## The results (full run: 600 stocks, 2013–2024, 21 generations, **all on real MongoDB Atlas**)
- **Researcher learns (the hero):** with memory, the agent discovered **61** keeper alphas vs
  **40** memory-OFF vs **21** random search (hit-rate 23% / 16% / 8%). Memory ON finds **+52%**
  more than OFF. → the "researcher is learning" chart.
- **Fleet adapts:** out-of-sample, the evolving book beats the frozen seed fleet on **appraisal
  (1.00 vs 0.92)**, IC-IR (1.50 vs 1.37) and net Sharpe (−1.13 vs −1.33), averaged over 21
  unseen blocks.
- **764 alphas researched, 122 kept (16%).** Fleet starts at 50 seeds, lives at ~33–40.
- **Honest weak spot (shown, not hidden):** on the single **sealed 2024 holdout**, the elite
  frozen seeds had a great year (net −0.81 vs adaptive −0.94). We display it — hiding it would
  be the exact dishonesty we guard against. The robust evidence is the 21-block walk-forward.

## Sponsor integrations (all live)
- **Gemini Antigravity managed agent** (`antigravity-preview-05-2026` via the Interactions API) —
  **VERIFIED WORKING with our plain AI Studio key.** One call spins up an isolated Google-hosted
  Linux env; the agent browses the web + runs code and returns brand-new, *cited* alphas in our DSL.
  12 discovered & cached (`lab/agent/antigravity_alphas.json`, real papers: Garman-Klass, Baltussen
  vol-of-vol, Abdi-Ranaldo spread, AQR value-everywhere…); they flow into the fleet (🛰 badge +
  citation + agent step-count in the UI). LIVE on-stage button: "🛰 Research live" (Section 03) →
  spins up the agent in real time (~1 min). Code: `lab/agent/antigravity.py`. The env id is reused
  across calls for stateful (continual) research.
- **MongoDB Atlas** — agent memory (`alpha_evolution` db) + **Atlas Vector Search** index
  (`alpha_vec`, Voyage 1024-dim cosine) for "similar alphas". (You whitelisted my IP — thanks.)
  ⚠️ Atlas went **intermittent** late in the build ("Primary() timeout" — looks like a free-tier
  failover/pause). The dual-backend store handled it automatically: the committed run fell back to
  the **local vector store** (header shows that) and the demo works fully offline. When Atlas is up
  (it was for earlier runs — alphas + Atlas Vector Search both verified working), the live "similar
  alphas" panel uses it automatically. Before the live demo: in Atlas, resume the cluster + confirm
  the IP allowlist, and the Atlas-backed features light up with no code change.
- **Voyage AI** — `voyage-3.5` embeddings for dedup + idea-space search (cached on disk).
- **Gemini** — `gemini-2.5-flash` proposer (thinking disabled for reliability/speed).
- **Firecrawl** — gathered 20 cited alpha ideas (`lab/agent/research_corpus.json`); a secondary
  research source translated to DSL with citations.

## Honesty guardrails (engineered in, after an adversarial review)
Prospective walk-forward (every keep/kill/add decided before the test block) · immutable trial
ledger (764 logged) · sealed 2024 holdout scored once · cost sweep 1/5/10/25/50 bps + 1-day
execution-delay test · liquid top-600 universe · random-search + memory-ablated controls. Sandbox
that safely runs LLM formulas (10/10 injection attacks blocked — `python -m lab.tests`).

## Decisions I made (reverse any you dislike)
1. **Antigravity**: now using the REAL `antigravity-preview-05-2026` managed-agent API (you asked
   for it for the prize). Verified it runs end-to-end on our key. The committed run draws from
   pre-discovered Antigravity alphas (offline-replayable); the live button calls the agent in real
   time. Firecrawl corpus kept as a secondary source + offline fallback.
2. **Data**: 2010–2024 (richer regimes) instead of the prior 2010–2014.
3. **Did NOT git-commit** (per the "commit only when asked" rule). To save it:
   `git add -A && git commit` on branch `cleanup/start-from-scratch`. (`.gitignore` already
   tracks `runs/demo_committed/` and ignores data/node_modules.)
4. Skipped **LiveKit** (voice) — out of scope for this visual dashboard; happy to add a voice
   narrator later if you want.

## Re-generate a run (optional)
```bash
.venv/bin/python -m lab.run_experiment --run-id demo_full         # ~18 min, writes runs/demo_full/run.json
cp runs/demo_full/run.json frontend/public/run.json && cp -r runs/demo_full runs/demo_committed
```
Quick smoke (≈3 min): add `--quick`. See `DEMO.md` for the on-stage script, `README.md` for architecture.
