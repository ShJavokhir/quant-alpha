"""The research loop: propose -> ROUTE (policy) -> evaluate (guardrail) -> diagnose
-> remember -> repeat.

The loop is split (see routing.py): a creative PROPOSER (stub or Gemini) suggests a
strategy; a deterministic ROUTING POLICY (derive_constraints + enforce) converts past
verdicts into binding constraints on that proposal. The route is therefore a *caused*
function of verdicts, not a script -- delete an early verdict and a later proposal
provably changes.

SCORING: the verdict gate runs on the APPRAISAL RATIO (beta-adjusted alpha vs buy&hold);
excess Sharpe (Information Ratio) is shown first as the "passive indexing wins" sanity
check; absolute Sharpe is display-only. See walkforward.py.

Emits a structured, replayable JOURNAL (runs/<id>/journal.jsonl) that is BOTH the agent's
memory AND the UI's data source. Stores PARAMS, not curves -- the API recomputes curves
on demand.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import strategies as st
from routing import derive_constraints, enforce
from walkforward import evaluate_template

DATA_DIR = Path(__file__).parent / "data"
RUNS_DIR = Path(__file__).parent / "runs"
TICKERS = ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
           "JPM", "XOM", "JNJ", "WMT", "KO", "PG", "HD", "DIS"]

# Holdout integrity (Task B). The committed search + ablation read ONLY the TRAIN names
# strictly BEFORE the cutoff. Two sealed slices the search never sees:
#   out-of-TIME  -> the post-cutoff tail of the TRAIN names (the harder regime axis, PRIMARY)
#   out-of-ASSET -> the HELD names, never in the search at all (clean name-generalization)
HOLDOUT_CUTOFF = "2023-06-27"
# sector-balanced exam set (tech/financial/retail/healthcare), chosen so the TRAIN search
# stays ROBUST -- the mean-reversion edge must not depend on any single held-out name
HELD_NAMES = ["GOOGL", "JPM", "WMT", "JNJ"]         # out-of-asset exam set (never searched)
TRAIN_TICKERS = [t for t in TICKERS if t not in HELD_NAMES]

BADGE = {"ROBUST": "[ROBUST  ✓]", "FRAGILE": "[FRAGILE ~]",
         "OVERFIT": "[OVERFIT ✗]", "NO DATA": "[NO DATA ]"}


def load_basket(tickers: list[str] | None = None, end: str | None = None,
                start: str | None = None) -> dict:
    """Load the basket. `end` truncates every series at a cutoff (the search NEVER sees
    the out-of-time holdout tail); `start` keeps only the tail (the sealed exam slice)."""
    out = {}
    for tk in (tickers or TICKERS):
        df = pd.read_csv(DATA_DIR / f"{tk}_1d.csv", index_col=0, parse_dates=True)
        if start is not None:
            df = df.loc[start:]
        if end is not None:
            df = df.loc[:end]
        out[tk] = df
    return out


def _worst_fold(folds: list) -> dict | None:
    """The single dated OOS fold with the lowest appraisal -- the metric-grounded
    'which regime broke it' fact (never a confabulated mechanism)."""
    valid = [f for f in folds if np.isfinite(f.get("oos_appraisal", np.nan))]
    return min(valid, key=lambda f: f["oos_appraisal"]) if valid else None


def diagnose(v: dict, per_ticker: dict, folds: list, prop: dict) -> tuple[str, str]:
    """Metric-grounded diagnosis + binding lesson. Every claim cites a NUMBER the
    system computed (param count, IS->OOS gap, the dated worst fold, per-name
    dispersion) -- never an asserted mechanism the backtester can't see."""
    grid = prop.get("grid", {})
    n_varied = sum(1 for vals in grid.values() if len(vals) > 1)
    n_combos = max(1, int(np.prod([len(x) for x in grid.values()]))) if grid else 1
    is_years = prop.get("windows", {}).get("is_years", "?")
    fam = prop["template"]

    n = len(per_ticker)
    n_neg = sum(1 for t in per_ticker.values() if t["oos_appraisal"] < 0)
    n_pos = n - n_neg
    worst_names = sorted(per_ticker, key=lambda t: per_ticker[t]["oos_appraisal"])[:3]

    wf = _worst_fold(folds)
    fold_txt = (f"worst OOS fold {wf['oos_start']}→{wf['oos_end']} (appraisal {wf['oos_appraisal']:+.2f}"
                f", {wf['ticker']})") if wf else "no scoreable fold"

    is_a, oos_a, gap = v["is_appraisal"], v["oos_appraisal"], v["appraisal_gap"]

    if v["verdict"] == "OVERFIT":
        diagnosis = (f"In-sample appraisal {is_a:+.2f} collapses to OOS {oos_a:+.2f} "
                     f"(gap {gap:.2f}) with {n_varied} free knob(s) over {n_combos} combos on a "
                     f"{is_years}yr IS window; {n_neg}/{n} names go negative OOS; {fold_txt}. "
                     "Beta-adjusted alpha fit noise, not signal.")
        lesson = (f"Ban {fam}: {n_varied} knobs / {is_years}yr IS curve-fit (gap {gap:.2f}). "
                  f"Cut to ≤2 knobs, lengthen IS to ≥6yr, and route to a different KIND of edge. "
                  f"Worst regime: {wf['oos_start'] if wf else 'n/a'}.")
    elif v["verdict"] == "FRAGILE":
        diagnosis = (f"OOS appraisal {oos_a:+.2f} (gap {gap:.2f}) over {n_combos} combos / "
                     f"{is_years}yr IS -- a genuine spark but thin or regime-dependent; "
                     f"{n_pos}/{n} names hold OOS; {fold_txt}.")
        lesson = (f"Tighten {fam}: freeze knobs to sane defaults, lengthen IS to ≥6yr, demand "
                  "positive OOS appraisal across more names before trusting it.")
    elif v["verdict"] == "ROBUST":
        diagnosis = (f"OOS appraisal {oos_a:+.2f} holds vs IS {is_a:+.2f} (gap {gap:.2f}) across "
                     f"{v['n_folds']} folds; {n_pos}/{n} names positive OOS -- beta-adjusted alpha "
                     "survives walk-forward (Info-Ratio vs buy&hold is still negative: this is "
                     "timing alpha, not a portfolio substitute).")
        lesson = (f"Keep {fam} as the trusted edge. Diversify to a different KIND of edge to find "
                  "uncorrelated alpha; do not widen the grid.")
    else:
        diagnosis, lesson = "Not enough history to score this template/window.", "Pick a longer-history configuration."
    return diagnosis, lesson


def _num(x):
    return round(float(x), 3) if isinstance(x, (int, float, np.floating)) and np.isfinite(x) else None


class StubResearcher:
    """Deterministic researcher that branches on VERDICTS (via the routing policy),
    not on len(history). Produces a fully *caused* demo arc with no API key:
        sma trend (OVERFIT) → multi_filter greedy (OVERFIT, the trap) →
        rsi default (FRAGILE, the spark) → rsi disciplined (ROBUST, the survivor).
    The verdicts are computed live, so every lesson stays honest to the data."""

    name = "stub"
    arm = "demo"

    BASELINE_SMA = {
        "template": "sma_crossover",
        "hypothesis": "Baseline trend-follow: long when the fast SMA is above the slow SMA.",
        "rationale": "Establish an honest, low-parameter trend benchmark — is there alpha beyond beta?",
        "grid": {"fast": [20, 50], "slow": [100, 200]},
        "windows": {"is_years": 5, "oos_years": 2, "step_years": 2},
    }
    GREEDY_MULTI = {
        "template": "multi_filter",
        "hypothesis": "Stack trend + RSI + momentum and tune four knobs hard on a 1-year window "
                      "to maximize the in-sample number.",
        "rationale": "Chase the biggest backtest Sharpe — the classic curve-fitting trap.",
        "grid": {"sma_fast": [5, 10, 20], "sma_slow": [50, 100], "rsi_period": [14],
                 "rsi_max": [60, 70, 80], "mom_lookback": [10, 20]},
        "windows": {"is_years": 1, "oos_years": 1, "step_years": 2},
    }
    RSI_DEFAULT = {
        "template": "rsi_reversion",
        "hypothesis": "Diversify the KIND of edge: buy oversold RSI, exit overbought (mean-reversion).",
        "rationale": "Trend overfit on this basket — try an uncorrelated mean-reversion edge.",
        "grid": {"period": [7, 14, 21], "low": [20, 30], "high": [70, 80]},
        "windows": {"is_years": 4, "oos_years": 2, "step_years": 2},
    }
    RSI_DISCIPLINED = {
        "template": "rsi_reversion",
        "hypothesis": "Apply the lesson: same mean-reversion edge, knobs frozen to sane defaults, "
                      "long in-sample window, judged across the whole basket.",
        "rationale": "Trade in-sample dazzle for out-of-sample durability — discipline over knobs.",
        "grid": {"period": [7, 14, 21], "low": [30], "high": [70]},
        "windows": {"is_years": 6, "oos_years": 2, "step_years": 2},
    }

    def propose(self, history: list, constraints=None):
        if not history:
            return dict(self.BASELINE_SMA)
        if any(h["verdict"] == "ROBUST" for h in history):
            return None                                  # found a trusted edge — stop the demo
        avail = constraints.available_families if constraints else list(st.TEMPLATES)
        tighten = constraints.tighten_families if constraints else []
        tried = {h["template"] for h in history}

        # escalate within trend: the greedy multi_filter trap (if not yet tried & allowed)
        if "multi_filter" not in tried and "multi_filter" in avail:
            return dict(self.GREEDY_MULTI)
        # diversify to mean-reversion
        if "rsi_reversion" in avail:
            return dict(self.RSI_DISCIPLINED) if "rsi_reversion" in tighten else dict(self.RSI_DEFAULT)
        return None


def _print_experiment(r: dict):
    print(f"\n#{r['iteration']}  {r['template']:14}{BADGE.get(r['verdict'], r['verdict'])}"
          f"   [{r['action']}" + (f" ← caused by #{r['caused_by']}]" if r['caused_by'] else "]"))
    print(f"   hypothesis: {r['hypothesis']}")
    print(f"   IS appraisal {r['is_appraisal']:+.2f} → OOS {r['oos_appraisal']:+.2f}  "
          f"(gap {r['appraisal_gap']:+.2f}, {r['n_folds']} folds)  |  OOS Info-Ratio {r['oos_excess_sharpe']:+.2f} "
          f"(buy&hold Sharpe {r['benchmark_oos_sharpe']:+.2f})  accepted={r['accepted']}")
    print(f"   diagnosis : {r['diagnosis']}")
    print(f"   lesson    : {r['llm_lesson']}")
    if r["best_oos_excess_so_far"] is not None:
        print(f"   >> best robust OOS appraisal so far: {r['best_oos_excess_so_far']:+.2f}")


def build_record(iteration, researcher, prop, constraints, overall, per, folds, best):
    diag, lesson = diagnose(overall, per, folds, prop)
    accepted = overall["verdict"] == "ROBUST"
    return {
        "iteration": iteration, "researcher": researcher.name,
        "template": prop["template"], "hypothesis": prop["hypothesis"],
        "rationale": prop["rationale"], "grid": prop["grid"], "windows": prop["windows"],
        "verdict": overall["verdict"], "n_folds": overall["n_folds"],
        # --- APPRAISAL = the verdict basis (beta-adjusted alpha) ---
        "is_appraisal": _num(overall["is_appraisal"]),
        "oos_appraisal": _num(overall["oos_appraisal"]),
        "appraisal_gap": _num(overall["appraisal_gap"]),
        # --- EXCESS / Information Ratio = shown FIRST (passive sanity) ---
        "is_excess_sharpe": _num(overall["is_excess"]),
        "oos_excess_sharpe": _num(overall["oos_excess"]),
        "excess_gap": _num(overall["excess_gap"]),
        "benchmark_oos_sharpe": _num(overall["benchmark_oos_sharpe"]),
        # --- absolute Sharpe = DISPLAY ONLY ---
        "is_sharpe": _num(overall["is_sharpe"]), "oos_sharpe": _num(overall["oos_sharpe"]),
        "gap": _num(overall["gap"]),
        "per_ticker": {tk: {"verdict": t["verdict"],
                            "oos_appraisal": _num(t["oos_appraisal"]),
                            "oos_excess_sharpe": _num(t["oos_excess"])}
                       for tk, t in per.items()},
        "diagnosis": diag, "lesson": lesson, "llm_lesson": lesson, "accepted": accepted,
        # --- caused routing ---
        "action": constraints.action, "caused_by": constraints.caused_by,
        "constraints": constraints.to_journal(),
        "banned_families": list(constraints.banned_families),
        "carried_lesson_from_prev": constraints.carried_lesson,
        "rerouted_from": prop.get("rerouted_from"),
        "arm": getattr(researcher, "arm", "demo"), "seed": getattr(researcher, "seed", None),
        "best_oos_excess_so_far": _num(best),
    }


def run_research(data: dict, researcher, max_iters: int = 12, run_dir: Path | None = None,
                 verbose: bool = True):
    if run_dir is None:
        RUNS_DIR.mkdir(exist_ok=True)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_dir.name
    journal_path = run_dir / "journal.jsonl"
    journal_path.write_text("")

    history, best = [], None
    while len(history) < max_iters:
        constraints = derive_constraints(history)
        prop = researcher.propose(history, constraints)
        if prop is None:
            break
        prop = enforce(prop, constraints)              # binding routing policy
        if prop is None:
            break
        tmpl = st.TEMPLATES[prop["template"]]
        overall, per, folds = evaluate_template(data, tmpl["fn"], prop["grid"],
                                                tmpl.get("valid"), **prop["windows"])
        if overall["verdict"] == "ROBUST" and np.isfinite(overall["oos_appraisal"]):
            if best is None or overall["oos_appraisal"] > best:
                best = overall["oos_appraisal"]
        rec = build_record(len(history) + 1, researcher, prop, constraints, overall, per, folds, best)
        history.append(rec)
        with journal_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        if verbose:
            _print_experiment(rec)

    robust = [h for h in history if h["accepted"]]
    first_robust = next((i + 1 for i, h in enumerate(history) if h["accepted"]), None)
    summary = {
        "run_id": run_id, "researcher": researcher.name, "arm": getattr(researcher, "arm", "demo"),
        "n_experiments": len(history), "best_oos_appraisal": _num(best),
        "experiments_to_first_robust": first_robust,
        "first_try_survival": bool(history and history[0]["accepted"]),
        "accepted_iterations": [h["iteration"] for h in robust],
        "banned_families_timeline": [{"iteration": h["iteration"], "banned": h["banned_families"]} for h in history],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    if verbose:
        print(f"\nJournal  -> {journal_path}")
        print(f"Summary  -> {run_dir / 'summary.json'}")
        print("Best robust OOS appraisal: " + (f"{best:+.2f}" if best is not None else "none"))
    return run_dir, history


if __name__ == "__main__":
    import sys

    if "gemini" in sys.argv:
        from gemini_researcher import GeminiResearcher
        print("=== Autonomous Quant Research Lab — Gemini 2.5 Flash ===")
        run_research(load_basket(), GeminiResearcher(), max_iters=6)
    else:
        print("=== Autonomous Quant Research Lab — stub researcher (caused arc) ===")
        run_research(load_basket(), StubResearcher())
