"""Discover novel alphas with the Antigravity managed agent; cache them for the run.

Runs the antigravity-preview-05-2026 agent (isolated Google-hosted env, web browse +
code exec) across family groups, reusing one environment for stateful research. Each
returned formula is DSL-validated and backtested on the base panel. Valid ones are
saved with full provenance (citation, interaction id, environment id, agent steps) to
lab/agent/antigravity_alphas.json — the agent's real, citable research output that the
evolution loop then draws from (offline-replayable for the demo).
"""
import json, time
from pathlib import Path

from lab import config, seeds
from lab.engine import dsl, backtest
from lab.agent.antigravity import AntigravityResearcher

OUT = Path(__file__).resolve().parent / "agent" / "antigravity_alphas.json"
GROUPS = [
    ["seasonality", "value"],
    ["volatility", "microstructure"],
    ["momentum", "reversal"],
    ["volume", "value"],
    ["microstructure", "volatility"],
]


def main(per_group=3):
    panel = config.load_panel("base")
    ag = AntigravityResearcher(max_wait=260)
    existing = {e["name"]: e for e in (json.loads(OUT.read_text()) if OUT.exists() else [])}
    avoid = [s["formula"] for s in seeds.SEEDS] + [e["formula"] for e in existing.values()]
    print(f"starting with {len(existing)} cached; avoiding {len(avoid)} formulas", flush=True)

    for gi, fams in enumerate(GROUPS):
        t = time.time()
        try:
            res = ag.research_alphas(n=per_group, avoid=avoid, families=fams)
        except Exception as e:  # noqa: BLE001
            print(f"  group {fams} error: {type(e).__name__}: {str(e)[:120]}", flush=True)
            continue
        kept = 0
        for a in res:
            if a["name"] in existing:
                continue
            try:
                m = backtest.evaluate_signal(dsl.evaluate(a["formula"], panel), panel)
            except dsl.DSLError:
                continue
            a["ic"] = round(m["ic"], 4); a["ic_ir"] = round(m["ic_ir"], 2)
            a["turnover"] = round(m["turnover"], 2)
            existing[a["name"]] = a
            avoid.append(a["formula"]); kept += 1
        OUT.write_text(json.dumps(list(existing.values()), indent=2))  # incremental
        print(f"  group {gi} {fams}: +{kept} (total {len(existing)}) in {time.time()-t:.0f}s "
              f"env={ag.environment_id}", flush=True)

    valid = list(existing.values())
    print(f"DONE: {len(valid)} antigravity alphas saved -> {OUT.name}", flush=True)
    for a in sorted(valid, key=lambda x: x.get("ic_ir", 0), reverse=True):
        print(f"  [{a['family']:<13}] ic_ir={a.get('ic_ir',0):>5} turn={a.get('turnover',0):>4} "
              f"{a['name']}  <{a.get('source_url','')[:48]}>", flush=True)


if __name__ == "__main__":
    main()
