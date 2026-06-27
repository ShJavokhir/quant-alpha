"""GeminiResearcher — the real LLM brain. Same .propose(history) interface as the
stub, but Gemini 3.5 Flash invents the hypotheses and parameter grids.

Uses google-genai 2.x:
    client.models.generate_content(
        model="gemini-3.5-flash",
        config=GenerateContentConfig(response_mime_type="application/json",
                                     response_schema=<pydantic model>))
for structured JSON output. Reads GEMINI_API_KEY from the project .env (or env).

Guardrails stay in walkforward.py — the LLM only proposes; the backtester disposes.
We validate/clamp whatever the model returns so it can never break the loop.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

from pydantic import BaseModel

import strategies as st

DEFAULT_MODEL = "gemini-2.5-flash"  # broadly-GA; 3.5 may be gated. Override via GEMINI_MODEL in .env
ROOT = Path(__file__).parent
MAX_VALUES_PER_PARAM = 3
MAX_COMBOS = 36

TEMPLATE_DESCS = {
    "sma_crossover": "Trend-following SMA crossover (params: fast, slow; need fast<slow).",
    "rsi_reversion": "Mean-reversion: buy oversold RSI, exit overbought (params: period, low, high; low<high).",
    "multi_filter": "Combined trend+RSI+momentum filter (sma_fast, sma_slow, rsi_period, rsi_max, "
                    "mom_lookback) — powerful but EASY TO OVERFIT with its 5 knobs.",
}

SYSTEM = (
    "You are a rigorous quantitative researcher discovering systematic trading strategies. "
    "You PROPOSE; a walk-forward backtester over a 15-stock basket DISPOSES. Strategies are scored "
    "by out-of-sample Sharpe and the in-sample->out-of-sample gap. Overfitting (too many free "
    "parameters, short in-sample windows, oversized grids) gets caught and REJECTED. Learn from the "
    "history: if a prior idea overfit, simplify it; build on what proved robust. Be creative but "
    "disciplined."
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
        f"IS {h['is_sharpe']:.2f}->OOS {h['oos_sharpe']:.2f} gap {h['gap']:.2f}; lesson: {h['lesson']}"
        for h in history
    )


def _cap(grid: dict) -> dict:
    while math.prod(len(v) for v in grid.values()) > MAX_COMBOS:
        k = max(grid, key=lambda k: len(grid[k]))
        if len(grid[k]) <= 1:
            break
        grid[k] = grid[k][:-1]
    return grid


def _sanitize(p: _Proposal, iteration: int) -> dict:
    """Coerce whatever the model returned into a safe, runnable proposal."""
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
    for k, v in cfg["grid"].items():       # fill any params the model omitted
        grid.setdefault(k, list(v))
    grid = _cap(grid)

    if not any(True for _ in _combos(grid, cfg.get("valid"))):  # guarantee a valid combo
        grid = {k: list(v) for k, v in cfg["grid"].items()}

    windows = {
        "is_years": min(8, max(1, int(p.is_years))),
        "oos_years": min(5, max(1, int(p.oos_years))),
        "step_years": min(5, max(1, int(p.step_years))),
    }
    return {"iteration": iteration, "template": template,
            "hypothesis": p.hypothesis.strip(), "rationale": p.rationale.strip(),
            "grid": grid, "windows": windows}


class GeminiResearcher:
    name = "gemini-3.5-flash"

    def __init__(self):
        _load_env()
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it to the project .env (GEMINI_API_KEY=...) — "
                "free key at https://aistudio.google.com/apikey"
            )
        from google import genai  # lazy import so the stub never needs google-genai
        self._client = genai.Client(api_key=key)
        self._model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    def propose(self, history: list):
        from google.genai import types

        prompt = (
            f"Available strategy templates:\n{_templates_blurb()}\n\n"
            "Verdict rules: ROBUST if out-of-sample Sharpe >= 0.3 AND (in-sample - OOS) gap <= 0.5; "
            "otherwise FRAGILE or OVERFIT.\n"
            "Walk-forward windows are in YEARS (is_years 3-6 recommended, oos_years 1-2, step_years 1-2). "
            "Keep grids small (<=3 values per parameter) to avoid overfitting.\n\n"
            f"Experiment history so far:\n{_history_blurb(history)}\n\n"
            f"Propose experiment #{len(history) + 1}: pick ONE template, give a crisp hypothesis and "
            "rationale, a small parameter grid (only that template's parameters), and walk-forward windows."
        )
        resp = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_schema=_Proposal,
                temperature=0.8,
            ),
        )
        parsed = getattr(resp, "parsed", None)
        if not isinstance(parsed, _Proposal):
            parsed = _Proposal.model_validate_json(resp.text)
        return _sanitize(parsed, len(history) + 1)
