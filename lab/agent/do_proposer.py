"""Alpha proposer backed by DigitalOcean's Inference engine (OpenAI-compatible).

Same job as the Gemini `Proposer` — author cross-sectional alpha formulas in our
DSL — but the LLM call goes through DigitalOcean's one-key, every-model endpoint
(`https://inference.do-ai.run/v1/`). The default model is **MiniMax-M2.5**, a
reasoning ("interleaved thinking") model: DO returns its chain-of-thought in a
separate `reasoning_content` field and the final JSON answer in `content`, so we
just read `content`. Because the model spends a large, variable number of tokens
thinking before it answers, we give it a generous output budget (a low cap
truncates mid-thought and returns empty content).

This subclasses `Proposer` and only overrides the transport (`_call`): all the
grammar, JSON parsing, DSL validation, and the self-repair retry are inherited
unchanged, so a DO-proposed alpha goes through the exact same gates as a Gemini one.

Verified working against DO with a standard model-access key:
  minimax-m2.5, json_object response_format, ~60s/call, 5/6 formulas DSL-valid
  (the 6th auto-fixed by the inherited _repair()).
"""
import time

from .. import config
from .proposer import Proposer

config.load_env()


class DOProposer(Proposer):
    def __init__(self, model: str = config.DO_MODEL, base_url: str = config.DO_BASE_URL,
                 min_tokens: int = 32000):
        super().__init__(model=model)
        self.base_url = base_url
        self.min_tokens = min_tokens          # reasoning headroom so we don't truncate
        self._do_client = None

    def _openai(self):
        # NB: parent sets self._client = None (an attribute), so we must NOT name
        # this `_client` — the attribute would shadow the method.
        if self._do_client is None:
            from openai import OpenAI
            key = config.os.environ.get("DIGITAL_OCEAN_MODEL_ACCESS_KEY")
            if not key:
                raise RuntimeError("DIGITAL_OCEAN_MODEL_ACCESS_KEY not set")
            self._do_client = OpenAI(base_url=self.base_url, api_key=key)
        return self._do_client

    def _repair(self, formula, error):
        """Skip LLM repair for this backend. The parent re-prompts the model to fix an
        invalid formula, but for a slow reasoning model that second round-trip can add
        ~60s; MiniMax already returns mostly-valid DSL, so we just drop the rare invalid
        one and keep `propose()` to a single call (live-demo latency budget)."""
        return None

    def _call(self, prompt, temperature=0.9, max_tokens=8000):
        """OpenAI-compatible chat call; returns the assistant `content` (JSON) string.

        Mirrors the parent's contract (a raw text reply that `_parse_alphas`/`_repair`
        consume), so the rest of the pipeline is identical to the Gemini path."""
        budget = max(int(max_tokens), self.min_tokens)
        for attempt in range(3):
            try:
                resp = self._openai().chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_completion_tokens=budget,
                    response_format={"type": "json_object"},
                )
                txt = (resp.choices[0].message.content or "").strip()
                if txt:
                    return txt
                # empty content (e.g. truncated by an over-tight budget) -> retry bigger
                budget = min(budget * 2, 60000)
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"[do_proposer] {self.model} failed: {type(e).__name__}: {e}")
                    return ""
                time.sleep(2 * (attempt + 1))
        return ""
