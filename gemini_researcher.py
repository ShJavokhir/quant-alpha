"""GeminiResearcher — the real LLM brain. Same .propose(history, constraints) interface
as the stub, but Gemini 2.5 Flash invents the hypotheses and parameter grids. The
deterministic routing policy (routing.enforce) still BINDS every proposal, so the live
path is creative but can never break the loop or re-propose a banned family.

Uses google-genai with structured JSON output (response_schema). Reads GEMINI_API_KEY
from the project .env (or env).

ROBUSTNESS (Task A live path): the model call gets RETRIES; on persistent failure it
falls back to a safe canned proposal derived from the active constraints, and it caches
the last good response. The verdict gate stays in walkforward.py — the LLM only proposes;
the backtester disposes. Note: LLM prose is NOT seed-reproducible — the demo runs off a
committed replay; live iteration is optional garnish.
"""
from __future__ import annotations

import math
import os
import time
from pathlib import Path

from pydantic import BaseModel

import strategies as st
from routing import default_grid, pick_family

DEFAULT_MODEL = "gemini-2.5-flash"     # broadly-GA. Override via GEMINI_MODEL in .env
ROOT = Path(__file__).parent
MAX_VALUES_PER_PARAM = 3
MAX_COMBOS = 36
N_RETRIES = 3

TEMPLATE_DESCS = {
    "sma_crossover": "Trend-following SMA crossover (params: fast, slow; need fast<slow). KIND: trend.",
    "rsi_reversion": "Mean-reversion: buy oversold RSI, exit overbought (params: period, low, high; low<high). KIND: mean_reversion.",
    "multi_filter": "Combined trend+RSI+momentum filter (sma_fast, sma_slow, rsi_period, rsi_max, "
                    "mom_lookback) — powerful but EASY TO OVERFIT with its 5 knobs. KIND: trend.",
}

SYSTEM = (
    "You are a rigorous quantitative researcher discovering systematic trading strategies. "
    "You PROPOSE; a walk-forward backtester over a 15-stock basket DISPOSES. The verdict gate is "
    "the APPRAISAL RATIO (beta-adjusted timing alpha vs buy-and-hold) — NOT absolute Sharpe, which "
    "just books market beta on a survivor-biased basket. Overfitting (too many free parameters, short "
    "in-sample windows, oversized grids) is caught and REJECTED. OBEY the routing policy: never propose "
    "a BANNED family; TIGHTEN families you were told to tighten (freeze knobs, lengthen IS); when a KIND "
    "of edge is exhausted, route to a different KIND. Learn from the metric-grounded lessons. Be creative "
    "but disciplined."
)


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class _Param(BaseModel):
    name: str
    values: list[int]


class _Proposal(BaseModel):
    template: str
    hypothesis: str
    rationale: str
    reflection: str          # the model's own words on the prior lesson (supplementary, NOT binding)
    params: list[_Param]
    is_years: int
    oos_years: int
    step_years: int


def _templates_blurb() -> str:
    lines = []
    for name, cfg in st.TEMPLATES.items():
        ex = ", ".join(f"{k}={v}" for k, v in cfg["grid"].items())
        lines.append(f"- {name}: {TEMPLATE_DESCS.get(name, '')} default grid: {ex}")
    return "\n".join(lines)


def _history_blurb(history: list) -> str:
    if not history:
        return "(no experiments yet — propose a sensible low-parameter baseline.)"
    return "\n".join(
        f"#{h['iteration']} {h['template']} [{h['verdict']}] "
        f"IS appraisal {h['is_appraisal']:+.2f}->OOS {h['oos_appraisal']:+.2f} "
        f"(Info-Ratio OOS {h['oos_excess_sharpe']:+.2f}); lesson: {h['llm_lesson']}"
        for h in history
    )


def _constraints_blurb(c) -> str:
    if c is None:
        return ""
    parts = []
    if c.banned_families:
        parts.append(f"BANNED families (never propose): {c.banned_families}")
    if c.tighten_families:
        parts.append(f"TIGHTEN these families (freeze knobs, IS>=6yr): {c.tighten_families}")
    if c.preferred_kind:
        parts.append(f"Preferred KIND of edge to explore next: {c.preferred_kind}")
    if c.carried_lesson:
        parts.append(f"Carried lesson from iter #{c.caused_by}: {c.carried_lesson}")
    return ("\nROUTING POLICY (binding):\n" + "\n".join(parts)) if parts else ""


def _cap(grid: dict) -> dict:
    while math.prod(len(v) for v in grid.values()) > MAX_COMBOS:
        k = max(grid, key=lambda k: len(grid[k]))
        if len(grid[k]) <= 1:
            break
        grid[k] = grid[k][:-1]
    return grid


def _sanitize(p: _Proposal, iteration: int) -> dict:
    """Coerce whatever the model returned into a safe, runnable proposal (routing.enforce
    BINDS it afterward in the loop)."""
    from walkforward import _combos

    template = p.template if p.template in st.TEMPLATES else "sma_crossover"
    cfg = st.TEMPLATES[template]
    allowed = set(cfg["grid"].keys())

    grid: dict[str, list[int]] = {}
    for pr in p.params:
        if pr.name in allowed:
            vals = sorted({int(v) for v in pr.values if 1 <= int(v) <= 400})[:MAX_VALUES_PER_PARAM]
            if vals:
                grid[pr.name] = vals
    for k, v in cfg["grid"].items():
        grid.setdefault(k, list(v))
    grid = _cap(grid)
    if not any(True for _ in _combos(grid, cfg.get("valid"))):
        grid = {k: list(v) for k, v in cfg["grid"].items()}

    windows = {"is_years": min(8, max(1, int(p.is_years))),
               "oos_years": min(5, max(1, int(p.oos_years))),
               "step_years": min(5, max(1, int(p.step_years)))}
    return {"iteration": iteration, "template": template,
            "hypothesis": p.hypothesis.strip(), "rationale": p.rationale.strip(),
            "llm_reflection": p.reflection.strip(), "grid": grid, "windows": windows}


def _fallback(history: list, constraints, iteration: int) -> dict:
    """Safe canned proposal when the live call fails — honors the routing policy."""
    fam = (pick_family(constraints) if constraints else None) or "rsi_reversion"
    return {"iteration": iteration, "template": fam,
            "hypothesis": f"[fallback] Disciplined {fam} proposal after a live-model timeout.",
            "rationale": "Live call failed; falling back to a policy-compliant low-parameter config.",
            "llm_reflection": "(fallback — no live model output)",
            "grid": default_grid(fam),
            "windows": {"is_years": 6, "oos_years": 2, "step_years": 2}}


class GeminiResearcher:
    name = "gemini-2.5-flash"
    arm = "live"

    def __init__(self):
        _load_env()
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it to the project .env (GEMINI_API_KEY=...) — "
                "free key at https://aistudio.google.com/apikey")
        from google import genai
        self._client = genai.Client(api_key=key)
        self._model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self._last_good: dict | None = None

    def _call(self, history: list, constraints, iteration: int) -> dict:
        from google.genai import types

        prompt = (
            f"Available strategy templates:\n{_templates_blurb()}\n\n"
            "Verdict rules (on the APPRAISAL RATIO = beta-adjusted alpha vs buy&hold): ROBUST if OOS "
            "appraisal >= 0.2 AND (IS - OOS) gap <= 0.5; OVERFIT if OOS appraisal < 0; else FRAGILE.\n"
            "Walk-forward windows are in YEARS (is_years 4-6 recommended, oos_years 1-2, step_years 1-2). "
            "Keep grids small (<=3 values per parameter) to avoid overfitting.\n\n"
            f"Experiment history so far:\n{_history_blurb(history)}"
            f"{_constraints_blurb(constraints)}\n\n"
            f"Propose experiment #{iteration}: pick ONE allowed template, a crisp hypothesis and rationale, "
            "a short reflection on the carried lesson, a small parameter grid (only that template's "
            "parameters), and walk-forward windows."
        )
        resp = self._client.models.generate_content(
            model=self._model, contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM, response_mime_type="application/json",
                response_schema=_Proposal, temperature=0.8),
        )
        parsed = getattr(resp, "parsed", None)
        if not isinstance(parsed, _Proposal):
            parsed = _Proposal.model_validate_json(resp.text)
        return _sanitize(parsed, iteration)

    def propose(self, history: list, constraints=None):
        iteration = len(history) + 1
        last_err = None
        for attempt in range(N_RETRIES):
            try:
                prop = self._call(history, constraints, iteration)
                self._last_good = prop
                return prop
            except Exception as e:                                   # noqa: BLE001
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        print(f"[gemini] {N_RETRIES} attempts failed ({last_err!r}); using fallback.")
        if self._last_good is not None:
            cached = dict(self._last_good)
            cached["iteration"] = iteration
            cached["rationale"] = "[cached last-good proposal after live failure] " + cached.get("rationale", "")
            return cached
        return _fallback(history, constraints, iteration)
