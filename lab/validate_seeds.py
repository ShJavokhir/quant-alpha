"""Run every seed through the DSL + backtester; report what parses and its edge.

This is the end-to-end smoke test of the engine: DSL -> signal -> metrics.
"""
import sys, time
from lab import config, seeds
from lab.engine import dsl, backtest


def main(which="base"):
    panel = config.load_panel(which)
    print(f"panel: {panel['close'].shape[0]} days x {panel['close'].shape[1]} stocks "
          f"({panel['close'].index.min().date()} -> {panel['close'].index.max().date()})\n")
    ok, bad = [], []
    t0 = time.time()
    for s in seeds.SEEDS:
        try:
            sig = dsl.evaluate(s["formula"], panel)
            m = backtest.evaluate_signal(sig, panel, cost_bps=10.0)
            ok.append((s["name"], s["family"], m))
        except Exception as e:  # noqa: BLE001
            bad.append((s["name"], str(e)[:90]))
    ok.sort(key=lambda r: r[2]["ic_ir"], reverse=True)
    print(f"{'name':<18}{'family':<14}{'ic':>8}{'ic_ir':>8}{'ic_hit':>8}{'apprais':>9}{'shrp_net':>9}{'turn':>7}")
    for name, fam, m in ok:
        print(f"{name:<18}{fam:<14}{m['ic']:>8.4f}{m['ic_ir']:>8.2f}{m['ic_hit']:>8.2f}"
              f"{m['appraisal']:>9.2f}{m['sharpe_net']:>9.2f}{m['turnover']:>7.2f}")
    pos = sum(1 for _, _, m in ok if m["ic_ir"] > 0)
    strong = sum(1 for _, _, m in ok if m["ic_ir"] > 1)
    print(f"\nparsed OK: {len(ok)}/{len(seeds.SEEDS)} | IC-IR>0: {pos} | IC-IR>1: {strong} | wall={time.time()-t0:.1f}s")
    if bad:
        print(f"\nFAILED {len(bad)}:")
        for name, err in bad:
            print(f"  {name}: {err}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "base")
