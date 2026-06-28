"""Gemini alpha proposer.

Given a memory context, proposes new alpha formulas in our DSL. The ONLY thing the
memory-ON vs memory-OFF ablation changes is whether the prompt is conditioned on
retrieved past winners/failures/gaps. Everything else is identical.
"""
import json
import re
import time

from .. import config
from ..engine import dsl, ops

config.load_env()

GRAMMAR = f"""You write CROSS-SECTIONAL equity alpha signals as single-expression formulas in a small DSL.
A formula is evaluated each day across ~1200 US stocks; its value RANKS stocks for a
dollar-neutral long/short book (high = long, low = short). It must be computable from
daily OHLCV ONLY.

FIELDS (each is a panel of daily values, one column per stock):
  open, high, low, close, volume, vwap, returns        # returns = daily % change of close

OPERATORS:
  cross-sectional (act across stocks each day):  rank(x), scale(x), indneutralize(x)
  element-wise:   log(x), sign(x), abs(x), signedpower(x, a), maximum(x, y), minimum(x, y),
                  iif(condition, a, b)   # ternary: where condition true use a else b
  time-series (per stock, window d in days):
                  delay(x, d), delta(x, d), ts_sum(x, d), sma(x, d), stddev(x, d),
                  ts_min(x, d), ts_max(x, d), ts_rank(x, d), ts_argmax(x, d), ts_argmin(x, d),
                  product(x, d), decay_linear(x, d), correlation(x, y, d), covariance(x, y, d)
  liquidity:      adv(d)    # d-day average daily volume
  arithmetic:     + - * / **  and comparisons < > <= >= for use inside iif(...)

RULES:
- Output a SINGLE expression. Use iif(c, a, b) for conditionals (NOT the ? : ternary).
- Use adv(20) form, not adv20. Use abs(x).
- No Python, no assignments, no field/operator other than those listed.
- Aim for signals that are PREDICTIVE *and* survive trading costs: prefer LOWER TURNOVER
  (longer windows, smoother signals) over hyper-reactive 1-day reversals, because net-of-cost
  performance is the real gate. Diversify across families.

EXAMPLE FORMULAS:
  -1 * correlation(rank(open), rank(volume), 10)
  ts_rank(close, 9) - ts_rank(adv(20), 9)
  iif(close > delay(close, 5), rank(returns), -1 * rank(returns))
  rank(delay(close, 21) / delay(close, 252) - 1)
  -1 * rank(covariance(rank(high), rank(volume), 5))
"""


class Proposer:
    def __init__(self, model=config.GEMINI_MODEL):
        self.model = model
        self._client = None

    def _genai(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=config.os.environ.get("GEMINI_API_KEY"))
        return self._client

    def _call(self, prompt, temperature=0.9, max_tokens=8000):
        from google.genai import types
        for attempt in range(4):
            try:
                resp = self._genai().models.generate_content(
                    model=self.model, contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature, max_output_tokens=max_tokens,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(thinking_budget=0)))
                return resp.text or ""
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    print(f"[proposer] gemini failed: {type(e).__name__}: {e}")
                    return ""
                time.sleep(2 * (attempt + 1))
        return ""

    def propose(self, n, memory_ctx="", regime_hint="", temperature=0.95):
        """Return a list of dicts: {name, family, formula, rationale}."""
        instruction = (
            f"{GRAMMAR}\n\n"
            f"{('MARKET CONTEXT: ' + regime_hint) if regime_hint else ''}\n"
            f"{memory_ctx}\n\n"
            f"Propose {n} NEW, DIVERSE alpha formulas. Be creative but disciplined.\n"
            "Return a JSON object: {\"alphas\": [{\"name\": snake_case_id, \"family\": one of "
            "[momentum, reversal, volume, volatility, microstructure, value, seasonality], "
            "\"formula\": DSL expression, \"rationale\": one sentence why it should predict returns}]}\n"
            "Make names short and descriptive. Output ONLY the JSON object."
        )
        raw = self._call(instruction, temperature=temperature)
        items = _parse_alphas(raw)
        out = []
        for it in items:
            f = (it.get("formula") or "").strip()
            if not f:
                continue
            try:
                dsl.validate(f)          # cheap structural check (no panel eval here)
            except dsl.DSLError as e:
                fixed = self._repair(f, str(e))
                if not fixed:
                    continue
                f = fixed
            out.append({
                "name": _slug(it.get("name", "alpha")),
                "family": (it.get("family") or "unknown").lower().strip(),
                "formula": f,
                "rationale": (it.get("rationale") or "").strip(),
            })
        return out

    def _repair(self, formula, error):
        prompt = (
            f"{GRAMMAR}\n\nThis DSL formula is INVALID:\n  {formula}\nError: {error}\n"
            "Return a corrected single-expression formula that keeps the same idea. "
            "Return JSON: {\"formula\": \"...\"}. Only JSON."
        )
        raw = self._call(prompt, temperature=0.3, max_tokens=600)
        try:
            obj = json.loads(_extract_json(raw))
            f = (obj.get("formula") or "").strip()
            dsl.validate(f)
            return f
        except Exception:
            return None


def build_memory_context(winners, failures, family_counts, lesson="", existing=None):
    """Assemble the memory block fed to the proposer (memory-ON only)."""
    lines = ["MEMORY — learn from past research on THIS task (this is your accumulated experience):"]
    if winners:
        lines.append("\nTOP-PERFORMING alphas currently in the fleet (create smart VARIATIONS or "
                     "decorrelated complements; do not copy verbatim):")
        for w in winners:
            lines.append(f"  - [{w.get('family','?')}] ir={w.get('ir',0):.2f} turn={w.get('turnover',0):.2f}: {w['formula']}")
    if existing:
        lines.append("\nALREADY TESTED — these formulas are taken; your proposals MUST be genuinely "
                     "DIFFERENT (different operators/structure), or they'll be rejected as duplicates:")
        for f in existing[:24]:
            lines.append(f"  - {f}")
    if failures:
        lines.append("\nRECENTLY REJECTED ideas and WHY (avoid these patterns and mistakes):")
        for fdoc in failures:
            lines.append(f"  - {fdoc.get('reject_reason','rejected')}: {fdoc['formula']}")
    if family_counts:
        gaps = sorted(family_counts.items(), key=lambda kv: kv[1])
        thin = [f for f, c in gaps[:3]]
        lines.append(f"\nUNDER-REPRESENTED families to favor for diversification: {', '.join(thin)}")
    if lesson:
        lines.append(f"\nDISTILLED LESSON: {lesson}")
    return "\n".join(lines)


def _parse_alphas(raw):
    txt = _extract_json(raw)
    try:
        obj = json.loads(txt)
    except Exception:
        return []
    if isinstance(obj, dict):
        for key in ("alphas", "formulas", "items", "data"):
            if key in obj and isinstance(obj[key], list):
                return obj[key]
        return [obj] if "formula" in obj else []
    return obj if isinstance(obj, list) else []


def _extract_json(raw):
    if not raw:
        return "{}"
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    # grab the outermost {...} or [...]
    start = min([i for i in (raw.find("{"), raw.find("[")) if i >= 0], default=-1)
    if start > 0:
        raw = raw[start:]
    return raw


def _slug(s):
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", str(s)).strip("_").lower()
    return (s or "alpha")[:40]
