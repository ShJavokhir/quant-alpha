# Sponsor Tech Stack Guide — 2026 AI Engineer World's Fair Hackathon (Cerebral Valley, June 27–28, 2026, SF)

## TL;DR
- **Every sponsor publishes a working llms.txt** for AI-agent-readable docs: DigitalOcean (`docs.digitalocean.com/llms.txt`), LiveKit (`docs.livekit.io/llms.txt`), MiniMax (`platform.minimax.io/docs/llms.txt`), Modular (`docs.modular.com/llms.txt` + `llms-full.txt` + `mojolang.org/llms.txt`), MongoDB/Voyage (`mongodb.com/docs/llms.txt` + `docs.voyageai.com/llms.txt`), and Google (`ai.google.dev/gemini-api/docs/llms.txt` + `ai.google.dev/api/llms.txt`).
- **Best theme-fit:** DigitalOcean Gradient ADK and Google's Antigravity managed-agent harness map to "The Self-Improvement Stack" (evals/observability/deploy loops); MongoDB Atlas + Voyage AI map to "Continual Learning" (agent memory/RAG); Modular MAX + the MAX LLM Book map to "Recursive Intelligence/RSI" (model bring-up, weights, kernels); LiveKit and MiniMax/Gemini Live power real-time voice agents.
- **Credits:** DigitalOcean $200, MiniMax $30 API credits, MongoDB "500M Voyage AI tokens" + Atlas credits (Atlas Sandbox on GCP), Google free tier + AI Studio. Prizes include the Keychron Q3 Max (LiveKit) and tickets to the ModCon Developer Conference, Aug 18, 2026 (Modular).

## Key Findings
The hackathon's three required themes — Continual Learning, The Self-Improvement Stack, and Recursive Intelligence/RSI — map cleanly onto distinct layers of the sponsor stack. Below, each sponsor is documented with capabilities, the most useful docs/quickstart/API links, confirmed llms.txt/llms-full.txt URLs, SDKs/GitHub, and credit/pricing notes.

---

## 1. DigitalOcean — "From silicon to agent" AI cloud

**What it is.** DigitalOcean's AI offering spans three layers: (1) **GPU Droplets** — virtual machines with NVIDIA (H100, H200, RTX 4000/6000 Ada, L40S) and AMD (Instinct MI300X, MI325X) GPUs for training/inference/HPC; (2) the **Gradient AI Platform** (formerly GenAI Platform) — a fully-managed platform to build AI agents with knowledge bases (RAG), multi-agent routing, guardrails, and serverless inference to foundation models from OpenAI, Anthropic, Google and others; and (3) **1-Click Models** — deploy open models (Hugging Face, DeepSeek) on GPU Droplets in a single click.

**Agent/self-improvement features.** The **Gradient Agent Development Kit (ADK)** is a framework-agnostic Python toolkit (works with LangGraph, LangChain, CrewAI, PydanticAI) with built-in **observability (traces), evaluation framework (custom metrics + datasets), and one-command serverless deploy** — directly mapping to the Self-Improvement Stack theme. Knowledge Bases support RAG and agent memory; built-in evaluation tools let you test prompts, compare models, and review logs/traces to continuously improve agent behavior (Continual Learning).

**Docs & quickstarts.**
- AI Platform overview: `https://www.digitalocean.com/products/ai-platform`
- Gradient AI Platform docs: `https://docs.digitalocean.com/products/gradient-ai-platform/`
- Build agents with the ADK (how-to): `https://docs.digitalocean.com/products/gradient-ai-platform/how-to/build-agents-using-adk/`
- Gradient AI Platform API reference: `https://docs.digitalocean.com/reference/api/reference/gradientai-platform/`
- GPU Droplets: `https://www.digitalocean.com/products/gradient/gpu-droplets`
- GPU Droplets pricing: `https://www.digitalocean.com/pricing/gpu-droplets`

**llms.txt.** ✅ `https://docs.digitalocean.com/llms.txt` (the documentation index; markdown versions of any page available by appending `index.html.md`). No separate `llms-full.txt` was found for DigitalOcean.

**SDKs / GitHub.** Gradient ADK + CLI: `https://github.com/digitalocean/gradient-adk`. Official client libraries: PyDo (Python), DoTs (TypeScript), Gradient Go. SDK docs: `https://gradientai-sdk.digitalocean.com/`. CLI via `doctl genai`.

**Pricing / credits.** Hackathon gives **$200 credits**. GPU Droplets billed per-second (5-min minimum); on-demand list rates from DigitalOcean's official pricing page: NVIDIA RTX 4000 Ada **$0.76/GPU/hr**, NVIDIA RTX 6000 Ada and L40S both **$1.57/GPU/hr**, AMD Instinct MI300X **$1.99/GPU/hr**, NVIDIA HGX H100 **$3.39/GPU/hr**, NVIDIA HGX H200 **$3.44/GPU/hr** (12-month reserved rates are lower). ADK serverless agent hosting is "no compute cost during Public Preview." Per DigitalOcean: "When you power off your GPU Droplet, you are still billed for it… your disk space, CPU, RAM, and IP address are all reserved" — destroy instances to end billing.

---

## 2. LiveKit — Real-time voice, video & "physical AI" agents

**What it is.** LiveKit is an open-source (Apache-2.0) WebRTC platform plus a managed **LiveKit Cloud**. The **LiveKit Agents** framework lets you add Python or Node.js programs to LiveKit rooms as real-time participants — building conversational, multimodal voice agents that see, hear, and speak.

**Agent/voice features.** Handles the core challenges of realtime voice AI: streaming audio through an **STT-LLM-TTS pipeline**, semantic/transformer-based **turn detection**, interruption handling, and LLM orchestration. Supports tool use, multi-agent handoff, vision, and an extensive plugin ecosystem for most STT/TTS/LLM providers. **Telephony** (SIP) is fully integrated. **LiveKit Inference** runs popular LLM/STT/TTS models without separate API keys, with unified billing and built-in observability (transcripts, traces). A no-code **Agent Builder** and a built-in test framework (with judges) support eval loops (Self-Improvement Stack). Native OpenTelemetry support enables observability integrations.

**Docs & quickstarts.**
- Agents docs: `https://docs.livekit.io/agents/`
- Telephony: `https://docs.livekit.io/agents/start/telephony.md`
- Python API ref: `https://docs.livekit.io/reference/python/livekit/agents/llm/index.html`
- JS API ref: `https://docs.livekit.io/reference/agents-js/`
- Hackathon page: `https://www.livekit.info/aiewf-hackathon-2026`

**llms.txt / llms-full.txt.** ✅ `https://docs.livekit.io/llms.txt` (LiveKit also supports appending `/llms.txt` to any URL for a page-level index, and `.md` for markdown of any page). A full export is available through this same per-page system; the primary published file is `llms.txt`.

**SDKs / GitHub / skills.** `pip install "livekit-agents[openai,deepgram,cartesia]"`. Framework: `https://github.com/livekit/agents`. LiveKit publishes a **LiveKit Docs MCP server** and a **LiveKit Agent Skill** (architectural guidance/best practices for voice AI — workflow design, handoffs, tasks, testing) for coding agents.

**Pricing / credits.** Free **Build** tier (permanent, no credit card): per LiveKit's official pricing page it bundles **both 1,000 agent session minutes AND 5,000 WebRTC minutes per month**, **$2.50 in LiveKit Inference credits (≈50 minutes of usage based on model prices)**, 50 GB egress, and one free US local phone number; Inference concurrency is capped at 5 on Build. Critically, per LiveKit's quotas docs, "for projects on the free Build plan, the included allowance acts as a hard cap — after you exceed it, new requests fail rather than incurring overage charges." Paid: Ship ($50/mo) and Scale ($500/mo, adds HIPAA/SOC 2). Inference billed by model (LLM per token, STT per duration, TTS per character). **Prize: Keychron Q3 Max keyboard.**

---

## 3. MiniMax — Global multimodal AI lab

**What it is.** MiniMax exposes multiple modalities through one API platform: **LLMs** (M-series), **TTS / long-form TTS / voice cloning / voice design**, **Hailuo video generation**, **image generation (image-01)**, **music generation (music-2.6)**, and file management, with OpenAI- and Anthropic-compatible SDKs plus official MCP integrations.

**Models.** The LLM API currently spans **MiniMax-M3** (flagship, MoE, ~428B total/~23B active, 1M-token context via MiniMax Sparse Attention, natively multimodal — text/image/video in, text out) plus M2.7, M2.7-highspeed, M2.5, M2.1, and the original **MiniMax-M2** (230B total / 10B active MoE, MIT-licensed, built for coding & agentic workflows). M2/M-series are "interleaved thinking" models using `<think>...</think>` tags. Strong on coding/agentic benchmarks (SWE-Bench, Terminal-Bench, BrowseComp). These models — designed for long-horizon, self-correcting agent loops — fit Continual Learning and agentic self-improvement.

**Audio/media.** 300+ system voices + custom cloned voices; T2A supports up to 10,000 chars/request, 40 languages, streaming; rapid voice cloning (temporary voices kept by first synthesis within 168 hrs). Hailuo video (text/image-to-video, async). Music (music-2.6, plus cover/free variants).

**Docs.**
- API overview: `https://platform.minimax.io/docs/api-reference/api-overview`
- Pay-as-you-go pricing: `https://platform.minimax.io/docs/guides/pricing-paygo`
- Token Plan (subscription): `https://platform.minimax.io/subscribe/token-plan`
- M2 open weights: `https://github.com/MiniMax-AI/MiniMax-M2`

**llms.txt.** ✅ `https://platform.minimax.io/docs/llms.txt` (referenced as "Fetch the complete documentation index at: /docs/llms.txt").

**SDKs.** OpenAI-compatible (`https://api.minimax.io/v1`) and Anthropic-compatible (`https://api.minimax.io/anthropic`) endpoints; works with OpenAI SDK, Anthropic SDK, or raw HTTP.

**Pricing / credits.** Hackathon gives **$30 in API credits**. Text (M-series) pay-as-you-go: M3 at promotional **$0.30/1M input, $1.20/1M output** (standard list $0.60/$2.40 with permanent 50% off) at ≤512K input; doubles above 512K. M3 Priority tier = 1.5× standard; M2.7-highspeed = 2× standard. Speech bills per character, video per clip, music per track, image per image. New accounts get 30-day trial credits.

---

## 4. Modular — MAX inference platform + Mojo language

**What it is.** The Modular Platform is an open, integrated AI stack: **MAX** (developer framework that serves high-performance GenAI models on NVIDIA/AMD/Apple GPUs and CPUs with OpenAI-compatible endpoints) and **Mojo** (a Pythonic systems language — "write like Python, run like C++" — for high-performance CPU/GPU/accelerator kernels). Both ship in one `modular` pip/conda package.

**Provided links (verified).**
- **The MAX LLM Book** — `https://llm.modular.com/` ✅ A complete guide to building an LLM (GPT-2) from scratch using the MAX Python API: 12 chapters from config, feed-forward, causal masking, multi-head attention, layer norm, transformer blocks, LM head, weight adaptation, KV cache, pipeline model, to architecture registration with `max serve`. Repo: `https://github.com/modular/max-llm-book`. (Strong RSI/Recursive-Intelligence fit — understand and modify model internals.)
- **Model bring-up workflow** — `https://docs.modular.com/max/develop/model-bringup-workflow/` ✅ How to implement a custom architecture in MAX: map config fields, translate weight names, connect to the KV cache, extend the compute graph (RSI: architecture updates).
- **Mojo getting started** — `https://mojolang.org/` ✅ (Mojo docs moved to mojolang.org; get-started tutorial at `https://mojolang.org/docs/manual/get-started/`).
- **Modular Agent Skills** — `https://github.com/modular/skills` ✅ Official AI agent skills (following the Agent Skills Standard) that make any coding agent fluent in Mojo/MAX: skills include a project-creation wizard, `mojo-syntax`, `mojo-gpu-fundamentals`, Mojo↔Python interop, model-import-into-MAX (HF model ID → MAX), and model profiling. Install via `npx` (one command). Docs: `https://docs.modular.com/mojo/tools/skills/`.

**Other docs.** Main docs: `https://docs.modular.com/`. Quickstart: `https://docs.modular.com/max/get-started/`. Serving/OpenAI-compatible endpoints + function calling: `https://docs.modular.com/max/serve/function-calling`. Supported GPUs: NVIDIA (driver 580+), AMD (ROCm 6.3.3+/7.0 for MI355X); recommended datacenter GPUs B200/H200/H100, MI355X/MI325X/MI300X; Apple silicon for Mojo GPU programming.

**llms.txt / llms-full.txt.** ✅ `https://docs.modular.com/llms.txt` (compact index) **and** ✅ `https://docs.modular.com/llms-full.txt`. Modular also publishes purpose-specific files: `llms-max-guides.txt`, `llms-python.txt`, `llms-kernels.txt`, `llms-c-api.txt`, `llms-glossary.txt`, plus ✅ `https://mojolang.org/llms.txt` for Mojo. Markdown of any page by appending `.md`.

**SDKs / GitHub.** Monorepo: `https://github.com/modular/modular` (MAX + Mojo, 450K+ lines open source). MAX Python API, `max` CLI, MAX container (Docker). Agentic Cookbook: `https://github.com/modular/max-agentic-cookbook`.

**Pricing / prizes.** MAX self-hosting is free (Modular Community License); managed cloud and VPC options available. **Prize: tickets to the ModCon Developer Conference (Aug 18, 2026)**, where Modular plans a Mojo open-source update (ModCon '26).

---

## 5. MongoDB Atlas + Voyage AI — Database, vector search, embeddings & rerankers

**What it is.** **MongoDB Atlas** is a fully-managed multi-cloud database (AWS/Azure/GCP) with native **Vector Search** ($vectorSearch, HNSW ANN), full-text (BM25), and hybrid search on document data. **Voyage AI** (acquired by MongoDB) provides state-of-the-art **embedding models and rerankers**, now offered directly through Atlas via the **Embedding and Reranking API** (in Preview).

**Agent/continual-learning features.** Store vector embeddings alongside operational data for **RAG and agent memory** (Continual Learning). **Automated Embedding** (autoEmbed index type) generates and syncs embeddings with a Voyage AI model at index- and query-time — no embedding pipeline to manage. Voyage models: `voyage-4-large`/`voyage-4`/`voyage-4-lite`/`voyage-4-nano` (general; shared embedding space, Matryoshka 256–2048 dims), `voyage-code-3`, `voyage-finance-2`, `voyage-law-2`, `voyage-multimodal-3.5`, and rerankers `rerank-2.5`/`rerank-2.5-lite`. "Build AI Agents with MongoDB" guidance covers orchestration, memory, and agentic RAG.

**Docs.**
- Vector Search overview: `https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/`
- Voyage AI by MongoDB: `https://www.mongodb.com/docs/voyageai/`
- Voyage quickstart: `https://www.mongodb.com/docs/voyageai/quickstart/`
- Voyage models overview: `https://www.mongodb.com/docs/voyageai/models/`
- Voyage AI standalone docs: `https://docs.voyageai.com/` (pricing: `https://docs.voyageai.com/docs/pricing`; rerankers: `https://docs.voyageai.com/docs/reranker`)

**llms.txt.** ✅ MongoDB: `https://www.mongodb.com/docs/llms.txt` (markdown of any page by appending `.md`). ✅ Voyage AI: `https://docs.voyageai.com/llms.txt` (index of all pages in Markdown + OpenAPI endpoints). No separate `llms-full.txt` was found for either.

**SDKs / GitHub.** Voyage Python client (`voyageai`); `langchain-mongodb`, `langchain-voyageai`; community Voyage AI CLI (`vai`) at `https://github.com/mrlynn/voyageai-cli`; tokenizers on Hugging Face. **`voyage-4-nano` is free, open-weight (Apache 2.0) and runs locally** with no API key or network.

**Pricing / credits.** Prizes: **"500M Voyage AI Tokens" + Atlas credits**, with an **Atlas Sandbox on GCP**. Per Voyage AI's official pricing docs: "The first 200 million tokens for voyage-4-large, voyage-4, voyage-4-lite, voyage-context-3, and voyage-code-3, or the first 50 million tokens for voyage-multilingual-2, voyage-finance-2, voyage-law-2, and voyage-code-2, are free for every account," and "the first 200 million tokens for rerank-2.5, rerank-2.5-lite, rerank-2, and rerank-2-lite are free for each account." Per-token list rates (Apr 2026): voyage-4-large $0.12/MTok, voyage-4 $0.06, voyage-4-lite $0.02. The Atlas Embedding/Reranking API is pay-as-you-go (per token, or per pixel for multimodal). Atlas vector infra starts at a $20/month tier for production.

---

## 6. Google DeepMind / Gemini 3.5 ecosystem (most current — mid-2026)

**Overview.** Gemini 3.5 Flash launched at Google I/O 2026 (May 19, 2026), positioned as "frontier intelligence with action" — outperforming Gemini 3.1 Pro on agentic/coding benchmarks (Terminal-Bench 2.1 76.2%, MCP Atlas 83.6%, GDPval-AA 1656 Elo, CharXiv 84.2%) while running ~4× faster in output tokens/sec. Now GA. The new **Interactions API** is the recommended primitive for agentic, stateful, multimodal workflows.

**Provided links (verified):**
- Get Started: `https://ai.google.dev/gemini-api/docs/get-started` (Gemini API quickstart hub at `https://ai.google.dev/gemini-api/docs`).
- Live translate: `https://ai.google.dev/gemini-api/docs/live-api/live-translate` ✅
- What's new in Gemini 3.5 Flash: `https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5` (canonical: `.../interactions/whats-new-gemini-3.5`) ✅
- Gemma get started: `https://ai.google.dev/gemma/docs/get_started` ✅
- API keys: `https://aistudio.google.com/api-keys` ✅
- Antigravity download: `https://antigravity.google/download` ✅

**Named features/models:**

**(i) Managed Agents / Antigravity agent (Interactions API).** With one API call you spin up a Google-hosted autonomous agent (`agent="antigravity-preview-05-2026"`) that reasons, browses, and executes code in an **isolated/ephemeral Google-hosted Linux environment**. Powered by the **Antigravity agent harness** (built on Gemini 3.5 Flash). Supports stateful memory via **environment IDs** (continue work in the same environment across interactions), background/parallel execution, function calling, code execution, and connection to external tools via **remote MCP servers** (streamable HTTP). Skills defined via local `AGENTS.md`/`SKILL.md` files. Docs: `https://ai.google.dev/gemini-api/docs/antigravity-agent`. (Strong Self-Improvement Stack + RSI fit — "builder + player" self-improvement loops are a Google-demoed use case.)

**(ii) Computer Use in Gemini 3.5 Flash.** Announced June 24, 2026 as a **public preview** — computer use is now a **native built-in tool** in `gemini-3.5-flash` (previously a standalone Gemini 2.5 model). The model looks at screenshots and generates UI actions (mouse/keyboard) across browser, desktop, and mobile, collapsing perception + action into one inference pass. Available via Gemini API and Gemini Enterprise Agent Platform, with a Browserbase-hosted demo + GitHub reference implementation, and optional enterprise safeguards (confirmation for sensitive actions; auto-stop on detected prompt injection). **⚠️ Conflict to flag:** Google's own "What's new in Gemini 3.5 Flash" docs page (last updated 2026-06-18) states "Computer Use is not supported in Gemini 3.5 Flash," which predates the June 24 announcement — verify current status in the changelog before building.

**(iii) Live Translate via the Gemini Live API.** Model `gemini-3.5-live-translate-preview` — real-time **speech-to-speech** translation across **70+ languages** (2,000+ language pairs), streaming continuously over WebSockets, staying a few seconds behind the speaker and preserving intonation/pace/pitch. Configured via `translationConfig` (targetLanguageCode BCP-47, echoTargetLanguage); audio-only (16kHz in / 24kHz out), no tools/function-calling/system-instructions in translation mode; ephemeral tokens on v1alpha for client apps. Launched June 9, 2026; public preview via Live API + AI Studio. Partner integrations include LiveKit, Agora, Pipecat, Fishjam, Vision Agents. SynthID watermark on output.

**(iv) On-device & GenMedia.** **Nano Banana** = Gemini's native image generation; **Nano Banana 2** = `gemini-3.1-flash-image` (high-speed, high-volume, strong text-in-image rendering), **Nano Banana Pro** = `gemini-3-pro-image` (professional, "Thinking"-driven, high-fidelity text). **Veo 3.1** = video generation. **Lyria 3** = music (`lyria-3-clip-preview` 30s clips, `lyria-3-pro-preview` full songs). **Gemma 4** = lightweight open models for on-device reasoning (`gemma-4-26b-a4b-it`, `gemma-4-31b-it`), on AI Studio + Gemini API. **Gemini Omni** (multimodal video generation, "any output from any input") was announced for rollout in the weeks after I/O.

**Docs & SDKs.**
- Gemini API hub: `https://ai.google.dev/gemini-api/docs`
- API reference: `https://ai.google.dev/api`
- Image generation: `https://ai.google.dev/gemini-api/docs/image-generation`
- Changelog (check for current preview/GA status): `https://ai.google.dev/gemini-api/docs/changelog`
- Coding agents (Gemini MCP + skills): `https://ai.google.dev/gemini-api/docs/coding-agents` (public MCP at `https://gemini-api-docs-mcp.dev`)
- SDKs: `google-genai` (Python), `@google/genai` (JS/TS).

**llms.txt.** ✅ `https://ai.google.dev/gemini-api/docs/llms.txt` (docs + API reference index) **and** ✅ `https://ai.google.dev/api/llms.txt` (API reference index). Every page has a `.md.txt` plain-markdown mirror (e.g., `pricing.md.txt`).

**Pricing / credits (official Gemini API pricing page, retrieved June 27, 2026).**
- **Free tier** exists: limited model access, free input/output tokens, AI Studio access — but content may be used to improve Google's products. Paid tier removes that and adds higher limits, caching, Batch API (50% off).
- **gemini-3.5-flash:** Standard input **$1.50/1M**, output (incl. thinking) **$9.00/1M**; Batch/Flex $0.75/$4.50; Priority $2.70/$16.20. Free tier is free.
- **gemini-3.5-live-translate-preview:** input **$3.50/1M (≈$0.0053/min)**, output **$21.00/1M (≈$0.0315/min)**; combined effective **~$0.0368/min** (Google's stated figure). ⚠️ The secondhand "$0.023/min" figure does **not** match Google's official page.
- **Nano Banana 2 (`gemini-3.1-flash-image`):** image output $60/1M tokens ≈ **$0.067/1K image** (Batch ≈ $0.034).
- **Nano Banana Pro (`gemini-3-pro-image`):** image output $120/1M tokens ≈ **$0.134/1K–2K image, $0.24/4K**.
- **Veo 3.1:** Standard **$0.40/sec** (720p/1080p), $0.60/sec (4K); Fast $0.10/sec (720p); Lite $0.05/sec (720p).
- **Lyria 3:** Clip (30s) **$0.04/song**; Pro (full song) **$0.08/song**.
- **Gemma 4:** **Free** via the Gemini API (free tier only; no paid pricing).

---

## Recommendations
1. **Pick your theme, then your stack.** For **Continual Learning** (memory/feedback/RAG): build on **MongoDB Atlas Vector Search + Voyage AI Automated Embedding** for agent memory, optionally with DigitalOcean Knowledge Bases. For **The Self-Improvement Stack** (evals/observability/deploy): use **DigitalOcean Gradient ADK** (traces + eval framework + one-command deploy) or **Google's Antigravity managed-agent harness** (stateful environments, parallel subagents). For **RSI/Recursive Intelligence** (weights/architecture): use **Modular MAX + the MAX LLM Book + model bring-up workflow** to build/modify model internals, plus LoRA/speculative decoding in MAX serve.
2. **Claim credits early and front-load free tiers:** DigitalOcean $200, MiniMax $30 (plus 30-day trial credits), MongoDB 500M Voyage tokens + Atlas Sandbox on GCP, Voyage's 200M free embedding tokens, Google's free tier + free Gemma 4, LiveKit Build tier. This combination can run a full multimodal agent at near-zero cost during the hackathon.
3. **Wire AI coding agents to the llms.txt files first.** Install **Modular Agent Skills** (`npx`/`github.com/modular/skills`), the **LiveKit Agent Skill + Docs MCP**, and the **Gemini Docs MCP** (`gemini-api-docs-mcp.dev`); point Cursor/Claude Code at each sponsor's `llms.txt`. This materially improves generated code for fast-moving APIs (Mojo, LiveKit Agents, Gemini Interactions API).
4. **For voice/real-time builds**, combine **LiveKit Agents** (pipeline, turn detection, telephony) with **MiniMax TTS/voice cloning** or **Gemini Live**; LiveKit is an official Gemini Live partner.
5. **Verify preview status before relying on it.** Gemini Computer Use, Live Translate, Nano Banana variants, Veo 3.1, Lyria 3, and the Antigravity agent are all **previews** — check the Gemini API changelog. Benchmark numbers (Gemini, MiniMax) are largely vendor-reported.

**Thresholds that change the plan:** If your build needs >512K-token context on MiniMax, expect 2× cost (use retrieval/chunking instead). If LiveKit usage exceeds the Build tier's 1,000 agent session minutes (a hard cap — requests fail rather than incurring overage), plan to demo within it. If you need raw GPU training (RSI weight updates), DigitalOcean GPU Droplets bill even when powered off — destroy instances after use.

## Caveats
- **Preview/near-cutoff features:** Several Google features (Computer Use in 3.5 Flash, Live Translate, Antigravity managed agents, Nano Banana 2/Pro, Veo 3.1, Lyria 3, Gemini Omni) are public/private previews announced May–June 2026; pricing and availability may change before GA. The `antigravity-preview-05-2026` agent ID and `gemini-3.5-live-translate-preview` model ID are preview identifiers.
- **Documentation conflict (Google):** The "What's new in Gemini 3.5 Flash" docs page (updated 2026-06-18) says Computer Use is *not* supported in 3.5 Flash, while Google's June 24, 2026 blog/changelog says it *is* now native. Treat the changelog as authoritative and verify at build time.
- **Vendor-reported benchmarks:** MiniMax and Gemini benchmark claims are largely self-reported; OSWorld-Verified computer-use scores are self-reported by providers with no independent verification as of June 2026.
- **MiniMax pricing nuance:** M3's $0.30/$1.20 is a promotional ("permanent 50% off") rate on a $0.60/$2.40 list price; long-context (>512K) and faster tiers cost more.
- **llms.txt completeness:** All six sponsors publish a working `llms.txt`. Confirmed `llms-full.txt` only for Modular (`docs.modular.com/llms-full.txt`); LiveKit, MongoDB, Voyage, DigitalOcean, and Google use per-page markdown mirrors (`.md`, `index.html.md`, or `.md.txt`) rather than a single full file.

## Appendix — All llms.txt / llms-full.txt links found
- **DigitalOcean:** `https://docs.digitalocean.com/llms.txt`
- **LiveKit:** `https://docs.livekit.io/llms.txt` (+ append `/llms.txt` to any path; `.md` per page)
- **MiniMax:** `https://platform.minimax.io/docs/llms.txt`
- **Modular (MAX):** `https://docs.modular.com/llms.txt`, `https://docs.modular.com/llms-full.txt`, plus `llms-max-guides.txt`, `llms-python.txt`, `llms-kernels.txt`, `llms-c-api.txt`, `llms-glossary.txt`
- **Modular (Mojo):** `https://mojolang.org/llms.txt`
- **MongoDB:** `https://www.mongodb.com/docs/llms.txt`
- **Voyage AI:** `https://docs.voyageai.com/llms.txt`
- **Google Gemini (docs):** `https://ai.google.dev/gemini-api/docs/llms.txt`
- **Google Gemini (API reference):** `https://ai.google.dev/api/llms.txt`
- **(Conference bonus) AI Engineer World's Fair:** `https://ai.engineer/worldsfair/llms.md` and `https://ai.engineer/worldsfair/llms-full.md`