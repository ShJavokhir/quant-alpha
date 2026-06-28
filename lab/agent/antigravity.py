"""Antigravity managed-agent researcher (Google Gemini Interactions API).

Uses the `antigravity-preview-05-2026` managed agent: one API call spins up an
isolated, ephemeral Google-hosted Linux environment where the agent reasons,
browses the web, and runs code. We use it as a genuine "alpha researcher" — it
reads the quant literature and returns new cross-sectional alpha formulas (in our
DSL) WITH real citations. The environment id is reused across calls so the sandbox
carries state between research sessions (continual learning, sponsor-grade).

Verified working against google-genai 2.10.0 with a standard AI Studio key:
  client.interactions.create(agent="antigravity-preview-05-2026",
                             input=<task str>, environment={"type": "remote"},
                             background=True, store=True)
  -> poll client.interactions.get(id) until status=="completed"; read .output_text,
     .environment_id (reuse), .steps (the agent's tool/browse/code steps).
"""
import json
import re
import time

from .. import config
from ..engine import dsl
from .proposer import GRAMMAR, _extract_json, _slug

config.load_env()

AGENT_ID = "antigravity-preview-05-2026"


class AntigravityResearcher:
    def __init__(self, poll_interval=8, max_wait=240, reuse_env=True):
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self.reuse_env = reuse_env
        self.environment_id = None
        self._client = None

    def _genai(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=config.os.environ.get("GEMINI_API_KEY"))
        return self._client

    def available(self) -> bool:
        """Cheap check that the managed agent is reachable with our key."""
        try:
            r = self._run("Reply with exactly: OK", max_wait=90)
            return bool(r and (r.output_text or "").strip())
        except Exception:
            return False

    def _run(self, task: str, system_instruction: str | None = None, max_wait=None,
             on_progress=None):
        """Run one Antigravity interaction to completion; return the Interaction or None.

        If `on_progress` is given it is called once right after the interaction is
        created and again on every poll with a dict
        {status, steps, environment_id, interaction_id}, where `steps` is the live,
        accumulating list of the agent's real tool/browse/code steps. This powers the
        live 'machine screen' — the UI streams what the managed agent is actually doing.
        """
        c = self._genai()
        env = self.environment_id if (self.reuse_env and self.environment_id) else {"type": "remote"}
        body = dict(agent=AGENT_ID, input=task, environment=env, background=True, store=True)
        if system_instruction:
            body["system_instruction"] = system_instruction
        r = c.interactions.create(**body)
        iid = r.id
        if on_progress:
            on_progress({"status": "running", "steps": [],
                         "environment_id": self.environment_id, "interaction_id": iid})
        deadline = time.time() + (max_wait or self.max_wait)
        while time.time() < deadline:
            time.sleep(self.poll_interval)
            g = c.interactions.get(iid)
            if getattr(g, "environment_id", None):
                self.environment_id = g.environment_id   # reuse for statefulness
            if on_progress:
                on_progress({"status": getattr(g, "status", "running"),
                             "steps": self._steps_detail(g),
                             "environment_id": getattr(g, "environment_id", None) or self.environment_id,
                             "interaction_id": iid})
            if g.status in ("completed", "failed", "cancelled", "budget_exceeded", "incomplete"):
                return g
        return None  # timed out

    @staticmethod
    def _steps_summary(interaction):
        steps = getattr(interaction, "steps", None) or []
        kinds = []
        for s in steps:
            t = getattr(s, "type", None) or type(s).__name__
            kinds.append(str(t))
        return {"n_steps": len(steps), "kinds": kinds[:24]}

    @staticmethod
    def _steps_detail(interaction):
        """A per-step view of an interaction: [{type, detail}], for the live UI."""
        steps = getattr(interaction, "steps", None) or []
        return [AntigravityResearcher._step_detail(s) for s in steps]

    @staticmethod
    def _step_detail(step):
        """Defensively pull a (type, human detail) out of one step object.

        The managed-agent step schema is preview-grade and varies, so we probe a
        range of likely attribute names (and one level of nesting) rather than
        assuming a fixed shape."""
        def grab(obj, *names):
            for nm in names:
                v = getattr(obj, nm, None)
                if v is None and isinstance(obj, dict):
                    v = obj.get(nm)
                if v not in (None, "", [], {}):
                    return v
            return None

        kind = grab(step, "type", "kind") or type(step).__name__
        detail = None
        for path in ("text", "content", "query", "url", "command", "code",
                     "output", "title", "summary", "name", "action", "description"):
            v = grab(step, path)
            if isinstance(v, str) and v.strip():
                detail = v.strip()
                break
        if detail is None:
            for nest in ("action", "tool_call", "tool", "browse", "web_search",
                         "code_execution", "function_call"):
                sub = grab(step, nest)
                if sub is None:
                    continue
                for path in ("query", "url", "command", "code", "text", "title", "name"):
                    v = grab(sub, path)
                    if isinstance(v, str) and v.strip():
                        detail = v.strip()
                        break
                if detail:
                    break
        return {"type": str(kind)[:48], "detail": (detail or "")[:200]}

    def research_alphas(self, n=4, avoid=None, families=None, extra="", on_progress=None):
        """Ask the managed agent to research `n` NOVEL, citable cross-sectional alphas.
        Returns a list of dicts: name, family, formula, rationale, source_url,
        source_title, source='antigravity', interaction_id, environment_id, steps."""
        avoid = avoid or []
        avoid_block = ""
        if avoid:
            avoid_block = ("\nThese formulas are ALREADY in our fleet — propose genuinely DIFFERENT "
                           "ideas (different structure/operators), not minor variants:\n  - "
                           + "\n  - ".join(avoid[:24]))
        fam = f"\nPrefer these families: {', '.join(families)}." if families else ""
        task = (
            f"You are a quantitative researcher. Browse the web (papers on SSRN/arXiv, Journal of "
            f"Finance/JFE, AQR/Robeco/Alpha Architect, Quantpedia, reputable quant blogs) and design "
            f"{n} NOVEL cross-sectional US-equity alpha signals, each computable from daily OHLCV only "
            f"and each backed by a REAL, citable source you actually found.{fam}{avoid_block}\n\n"
            f"{extra}\n\nExpress each as a single formula in this DSL:\n{GRAMMAR}\n\n"
            "Return ONLY a JSON array of objects with EXACTLY these keys: "
            '{"name": snake_case_id, "family": one of [momentum,reversal,volume,volatility,'
            'microstructure,value,seasonality], "formula": "<dsl expression>", '
            '"rationale": "one sentence economic intuition", "source_title": "...", '
            '"source_url": "https://..."}. No prose outside the JSON.')
        interaction = self._run(task, on_progress=on_progress)
        if not interaction or interaction.status != "completed":
            return []
        items = _parse_array(interaction.output_text or "")
        steps = self._steps_summary(interaction)
        out = []
        for it in items:
            f = (it.get("formula") or "").strip()
            if not f:
                continue
            try:
                dsl.validate(f)
            except dsl.DSLError:
                continue
            out.append({
                "name": _slug(it.get("name", "ag_alpha")),
                "family": (it.get("family") or "unknown").lower().strip(),
                "formula": f,
                "rationale": (it.get("rationale") or "").strip(),
                "source": "antigravity",
                "source_title": it.get("source_title", ""),
                "source_url": it.get("source_url", ""),
                "interaction_id": interaction.id,
                "environment_id": self.environment_id,
                "steps": steps,
            })
        return out


def _parse_array(raw: str):
    txt = _extract_json(raw)
    try:
        obj = json.loads(txt)
    except Exception:
        # salvage the first [...] block
        m = re.search(r"\[.*\]", raw, re.S)
        if not m:
            return []
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return []
    if isinstance(obj, dict):
        for k in ("alphas", "items", "data", "results"):
            if isinstance(obj.get(k), list):
                return obj[k]
        return [obj] if "formula" in obj else []
    return obj if isinstance(obj, list) else []
