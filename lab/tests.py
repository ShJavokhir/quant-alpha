"""Sanity tests: DSL sandbox safety + engine consistency. Run: python -m lab.tests"""
from lab.engine import dsl, backtest
from lab import config, seeds

ATTACKS = [
    "__import__('os').system('x')", "().__class__.__bases__[0]", "open('/etc/passwd')",
    "close.__class__", "eval('1+1')", "[x for x in range(10)]", "lambda: 1",
    "close.values", "exec('x=1')",
]
LEGIT = ["rank(returns)", "-1 * correlation(rank(open), rank(volume), 10)",
         "iif(close > delay(close,5), rank(returns), -1*rank(returns))", "adv20 / volume"]


def test_sandbox():
    for a in ATTACKS:
        try:
            dsl.validate(a)
            raise AssertionError(f"SECURITY LEAK: accepted {a!r}")
        except dsl.DSLError:
            pass
    for f in LEGIT:
        dsl.validate(f)
    print(f"[ok] sandbox: blocked {len(ATTACKS)} attacks, passed {len(LEGIT)} legit formulas")


def test_engine_consistency():
    """Top alphas should reproduce the validated alpha101 numbers on the base panel."""
    panel = config.load_panel("base")
    by_name = {s["name"]: s["formula"] for s in seeds.SEEDS}
    m = backtest.evaluate_signal(dsl.evaluate(by_name["alpha013"], panel), panel)
    assert m["ic_ir"] > 4.5, f"alpha013 IC-IR regressed: {m['ic_ir']:.2f}"
    parsed = sum(1 for s in seeds.SEEDS if _ok(s["formula"], panel))
    assert parsed >= len(seeds.SEEDS) - 2, f"only {parsed}/{len(seeds.SEEDS)} seeds parse"
    print(f"[ok] engine: alpha013 IC-IR={m['ic_ir']:.2f}; {parsed}/{len(seeds.SEEDS)} seeds valid")


def _ok(f, panel):
    try:
        dsl.evaluate(f, panel); return True
    except dsl.DSLError:
        return False


if __name__ == "__main__":
    test_sandbox()
    test_engine_consistency()
    print("ALL TESTS PASSED")
