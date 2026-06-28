"""Researcher: turns web-sourced literature ideas into runnable DSL alphas.

The corpus in research_corpus.json was gathered from quant literature/blogs via
Firecrawl (SSRN, arXiv, Journal of Finance, Robeco, Alpha Architect, ...). Here we
use Gemini to translate each idea's plain-English signal into our DSL, validate it,
and cache the result with its citation. This is the agent's "read the web, propose a
new alpha" capability; citations make the demo credible.
"""
import json
import time
from pathlib import Path

from .. import config
from ..engine import dsl
from .proposer import GRAMMAR, _extract_json

config.load_env()

CORPUS = Path(__file__).resolve().parent / "research_corpus.json"
DSL_CACHE = Path(__file__).resolve().parent / "research_dsl.json"
AG_ALPHAS = Path(__file__).resolve().parent / "antigravity_alphas.json"


class Researcher:
    """Draws researched alphas from two real sources (offline-replayable):
      * Antigravity managed-agent discoveries (browsed the web + ran code in an isolated
        env; each carries a citation + the agent's step trace) — preferred, prize-grade.
      * a Firecrawl-gathered literature corpus translated to DSL via Gemini.
    """
    def __init__(self, model=config.GEMINI_MODEL):
        self.model = model
        self._client = None
        self.corpus = json.loads(CORPUS.read_text()) if CORPUS.exists() else []
        self.cache = json.loads(DSL_CACHE.read_text()) if DSL_CACHE.exists() else {}
        self.antigravity = json.loads(AG_ALPHAS.read_text()) if AG_ALPHAS.exists() else []

    def _genai(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=config.os.environ.get("GEMINI_API_KEY"))
        return self._client

    def _convert(self, idea):
        prompt = (
            f"{GRAMMAR}\n\n"
            "Translate the following published alpha idea into ONE valid DSL formula "
            "(cross-sectional, computable from OHLCV only). Keep its economic intent.\n\n"
            f"Idea name: {idea['name']}\nFamily: {idea['family']}\n"
            f"Intuition: {idea.get('intuition','')}\n"
            f"Signal: {idea['signal_description']}\n\n"
            "Return JSON: {\"formula\": \"<dsl expression>\"}. Only JSON."
        )
        from google.genai import types
        for attempt in range(3):
            try:
                resp = self._genai().models.generate_content(
                    model=self.model, contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.4, max_output_tokens=1200,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(thinking_budget=0)))
                obj = json.loads(_extract_json(resp.text or ""))
                f = (obj.get("formula") or "").strip()
                dsl.validate(f)
                return f
            except Exception:
                time.sleep(1.5 * (attempt + 1))
        return None

    def build_cache(self, panel=None, verbose=True):
        """Convert all corpus ideas to validated DSL (and optionally backtest-check)."""
        from ..engine import backtest
        ok = 0
        for idea in self.corpus:
            name = idea["name"]
            if name in self.cache and self.cache[name].get("formula"):
                ok += 1
                continue
            f = self._convert(idea)
            entry = {"name": name, "family": idea["family"], "formula": f,
                     "rationale": idea.get("intuition", ""),
                     "source_title": idea.get("source_title", ""),
                     "source_url": idea.get("source_url", "")}
            if f and panel is not None:
                try:
                    sig = dsl.evaluate(f, panel)
                    backtest.evaluate_signal(sig, panel)
                    entry["valid"] = True
                except Exception as e:  # noqa: BLE001
                    entry["valid"] = False
                    entry["error"] = str(e)[:120]
            self.cache[name] = entry
            ok += 1 if f else 0
            DSL_CACHE.write_text(json.dumps(self.cache, indent=2))   # incremental -> resumable
            if verbose:
                print(f"  research convert {name}: {'OK' if f else 'FAIL'}", flush=True)
        return self.cache

    def fresh_ideas(self, n, used_names):
        """Return up to n researched alphas not yet used (with citations). Antigravity
        managed-agent discoveries are offered first (richer provenance), then the corpus."""
        out = []
        for e in self.antigravity:                       # prize-grade source first
            if e["name"] in used_names or not e.get("formula"):
                continue
            out.append({"name": e["name"], "family": e.get("family", "unknown"),
                        "formula": e["formula"], "rationale": e.get("rationale", ""),
                        "source": "antigravity", "source_title": e.get("source_title", ""),
                        "source_url": e.get("source_url", ""), "steps": e.get("steps"),
                        "interaction_id": e.get("interaction_id"),
                        "environment_id": e.get("environment_id")})
            if len(out) >= n:
                return out
        for name, e in self.cache.items():
            if name in used_names or not e.get("formula") or e.get("valid") is False:
                continue
            out.append({"name": e["name"], "family": e["family"], "formula": e["formula"],
                        "rationale": e.get("rationale", ""), "source": "web",
                        "source_title": e.get("source_title", ""),
                        "source_url": e.get("source_url", "")})
            if len(out) >= n:
                break
        return out
