"""Random-grammar-search baseline.

Generates syntactically valid DSL formulas by random composition over the same
operators/fields the LLM uses. This is the honest control: "same grammar, same
compute budget, no LLM / no memory". If the LLM agent can't beat random search,
the intelligence claim is hollow (per the adversarial review).
"""
import random

from ..engine import dsl

FIELDS = ["open", "high", "low", "close", "volume", "vwap", "returns"]
UNARY_XS = ["rank", "scale", "sign"]                       # cross-sectional / elementwise unary
TS1 = ["delta", "delay", "ts_sum", "sma", "stddev", "ts_min", "ts_max",
       "ts_rank", "ts_argmax", "ts_argmin", "decay_linear"]   # (x, d)
TS2 = ["correlation", "covariance"]                        # (x, y, d)
WINDOWS = [3, 5, 6, 9, 10, 12, 15, 20, 22, 30, 40, 60, 120, 252]


class RandomProposer:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def _field(self):
        f = self.rng.choice(FIELDS + ["adv"])
        return f"adv({self.rng.choice(WINDOWS)})" if f == "adv" else f

    def _expr(self, depth):
        r = self.rng.random()
        if depth <= 0 or r < 0.30:
            return self._field()
        r = self.rng.random()
        if r < 0.30:
            return f"{self.rng.choice(UNARY_XS)}({self._expr(depth-1)})"
        if r < 0.55:
            fn = self.rng.choice(TS1)
            return f"{fn}({self._expr(depth-1)}, {self.rng.choice(WINDOWS)})"
        if r < 0.72:
            fn = self.rng.choice(TS2)
            return f"{fn}({self._expr(depth-1)}, {self._expr(depth-1)}, {self.rng.choice(WINDOWS)})"
        # binary arithmetic
        op = self.rng.choice(["+", "-", "*", "/"])
        a, b = self._expr(depth - 1), self._expr(depth - 1)
        sign = "-1 * " if self.rng.random() < 0.3 else ""
        return f"{sign}({a} {op} {b})"

    def propose(self, n, **_ignore):
        out, tries = [], 0
        fam = ["momentum", "reversal", "volume", "volatility", "value"]
        while len(out) < n and tries < n * 40:
            tries += 1
            f = self._expr(self.rng.randint(2, 4))
            try:
                dsl.validate(f)
            except dsl.DSLError:
                continue
            out.append({"name": f"rand_{len(out)}", "family": self.rng.choice(fam),
                        "formula": f, "rationale": "random grammar search"})
        return out
