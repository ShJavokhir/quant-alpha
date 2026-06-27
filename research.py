"""The research loop: propose -> evaluate (guardrail) -> diagnose -> remember -> repeat.

Emits a structured, replayable JOURNAL (runs/<id>/journal.jsonl) that is BOTH the
agent's memory AND the data source for the eventual UI. We store PARAMS, not equity
curves -- the UI backend recomputes any curve from params on demand (milliseconds),
so the journal stays light and any strategy stays re-simulatable.

A Researcher is an interface with .propose(history) -> proposal | None:
  StubResearcher    -- deterministic scripted narrative; runs with NO API key.
  GeminiResearcher  -- (later) Gemini proposes/diagnoses; same journal, same UI.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import strategies as st
from walkforward import evaluate_template

DATA_DIR = Path(__file__).parent / "data"
RUNS_DIR = Path(__file__).parent / "runs"
TICKERS = ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
           "JPM", "XOM", "JNJ", "WMT", "KO", "PG", "HD", "DIS"]

BADGE = {"ROBUST": "[ROBUST  ✓]", "FRAGILE": "[FRAGILE ~]",
         "OVERFIT": "[OVERFIT ✗]", "NO DATA": "[NO DATA ]"}


def load_basket() -> dict:
    return {tk: pd.read_csv(DATA_DIR / f"{tk}_1d.csv", index_col=0, parse_dates=True)
            for tk in TICKERS}


def diagnose(v: dict) -> tuple[str, str]:
    """Turn a walk-forward verdict into a (diagnosis, lesson). Rule-based for the
    stub; this is exactly the step the LLM will own later (read results, explain)."""
    if v["verdict"] == "OVERFIT":
        return ("In-sample Sharpe looked strong but out-of-sample is negative -- the "
                "parameters fit noise, not signal.",
                "Reject. Penalize many free parameters and short in-sample windows; "
                "demand positive OOS across the basket.")
    if v["verdict"] == "FRAGILE":
        return (f"OOS Sharpe {v['oos_sharpe']:.2f} with a {v['gap']:.2f} IS->OOS gap -- "
                "the edge is thin or regime-dependent.",
                "Lengthen in-sample, cut parameters, or require robustness across more "
                "names before trusting it.")
    return (f"OOS Sharpe {v['oos_sharpe']:.2f} holds vs IS {v['is_sharpe']:.2f} "
            f"(gap {v['gap']:.2f}) -- survives walk-forward.",
            "Keep as a candidate; try to raise OOS Sharpe without widening the gap.")


class StubResearcher:
    """Deterministic scripted researcher. Validates the loop AND gives a reliable
    demo arc with no API key: baseline -> greedy overfit -> corrected -> diversified.
    The verdicts below are computed live, so the lessons stay honest to the data."""

    name = "stub"
    SCRIPT = [
        {"template": "sma_crossover",
         "hypothesis": "Baseline trend-follow: long when the fast SMA is above the slow SMA.",
         "rationale": "Establish an honest, low-parameter benchmark to beat.",
         "grid": {"fast": [10, 20, 50], "slow": [50, 100, 200]},
         "windows": {"is_years": 4, "oos_years": 2, "step_years": 2}},

        {"template": "multi_filter",
         "hypothesis": "Stack trend + RSI + momentum filters and tune all five knobs "
                       "hard on short windows to maximize the in-sample Sharpe.",
         "rationale": "Chase the biggest backtest number -- the classic trap.",
         "grid": {"sma_fast": [5, 10, 20], "sma_slow": [50, 100], "rsi_period": [14],
                  "rsi_max": [65, 75], "mom_lookback": [10, 20]},
         "windows": {"is_years": 1, "oos_years": 1, "step_years": 2}},

        {"template": "multi_filter",
         "hypothesis": "Apply the lesson: same idea, knobs frozen to sane defaults, "
                       "long in-sample window, judged across the whole basket.",
         "rationale": "Trade in-sample dazzle for out-of-sample durability.",
         "grid": {"sma_fast": [20], "sma_slow": [100], "rsi_period": [14],
                  "rsi_max": [70], "mom_lookback": [20]},
         "windows": {"is_years": 5, "oos_years": 2, "step_years": 2}},

        {"template": "rsi_reversion",
         "hypothesis": "Add an uncorrelated mean-reversion sleeve (buy oversold).",
         "rationale": "Diversify the *kind* of edge, not just the parameters.",
         "grid": {"period": [7, 14, 21], "low": [20, 30], "high": [70, 80]},
         "windows": {"is_years": 4, "oos_years": 2, "step_years": 2}},
    ]

    def propose(self, history: list):
        i = len(history)
        if i >= len(self.SCRIPT):
            return None
        prop = dict(self.SCRIPT[i])
        prop["iteration"] = i + 1
        return prop


def _print_experiment(r: dict):
    print(f"\n#{r['iteration']}  {r['template']:14}{BADGE.get(r['verdict'], r['verdict'])}")
    print(f"   hypothesis: {r['hypothesis']}")
    print(f"   IS {r['is_sharpe']:+.2f} -> OOS {r['oos_sharpe']:+.2f}  "
          f"(gap {r['gap']:+.2f}, {r['n_folds']} folds)  "
          f"accepted={r['accepted']}")
    print(f"   diagnosis : {r['diagnosis']}")
    print(f"   lesson    : {r['lesson']}")
    if r["best_oos_so_far"] is not None:
        print(f"   >> best robust OOS Sharpe so far: {r['best_oos_so_far']:+.2f}")


def run_research(data: dict, researcher, max_iters: int = 12):
    RUNS_DIR.mkdir(exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir()
    journal_path = run_dir / "journal.jsonl"

    history, best_oos = [], None
    while len(history) < max_iters:
        prop = researcher.propose(history)
        if prop is None:
            break
        tmpl = st.TEMPLATES[prop["template"]]
        overall, per = evaluate_template(data, tmpl["fn"], prop["grid"],
                                         tmpl.get("valid"), **prop["windows"])
        diag, lesson = diagnose(overall)
        accepted = overall["verdict"] == "ROBUST"
        if accepted and (best_oos is None or overall["oos_sharpe"] > best_oos):
            best_oos = overall["oos_sharpe"]

        rec = {
            "iteration": prop["iteration"], "researcher": researcher.name,
            "template": prop["template"], "hypothesis": prop["hypothesis"],
            "rationale": prop["rationale"], "grid": prop["grid"],
            "windows": prop["windows"], "verdict": overall["verdict"],
            "is_sharpe": round(overall["is_sharpe"], 3),
            "oos_sharpe": round(overall["oos_sharpe"], 3),
            "gap": round(overall["gap"], 3), "n_folds": overall["n_folds"],
            "per_ticker": {tk: {"verdict": v["verdict"],
                                "oos_sharpe": round(v["oos_sharpe"], 3)}
                           for tk, v in per.items()},
            "diagnosis": diag, "lesson": lesson, "accepted": accepted,
            "best_oos_so_far": round(best_oos, 3) if best_oos is not None else None,
        }
        history.append(rec)
        with journal_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        _print_experiment(rec)

    summary = {"run_id": run_id, "researcher": researcher.name,
               "n_experiments": len(history), "best_oos_sharpe": best_oos,
               "accepted_iterations": [h["iteration"] for h in history if h["accepted"]]}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nJournal  -> {journal_path}")
    print(f"Summary  -> {run_dir / 'summary.json'}")
    print(f"Best robust OOS Sharpe discovered: "
          f"{best_oos:+.2f}" if best_oos is not None else "none")
    return run_dir, history


if __name__ == "__main__":
    import sys

    if "gemini" in sys.argv:
        from gemini_researcher import GeminiResearcher

        print("=== Autonomous Quant Research Lab -- Gemini 3.5 Flash ===")
        run_research(load_basket(), GeminiResearcher(), max_iters=6)
    else:
        print("=== Autonomous Quant Research Lab -- stub researcher ===")
        run_research(load_basket(), StubResearcher())
