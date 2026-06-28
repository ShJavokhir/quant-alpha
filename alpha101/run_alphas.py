"""Backtest all 82 Alpha101 signals in parallel; save daily IC + PnL matrices.

Panels are loaded once in the parent and inherited by forked workers (copy-on-
write). Each worker computes one alpha and returns its daily IC series (alpha[t]
vs next-day return), daily PnL, and metrics.
"""
import multiprocessing as mp
import pickle
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

import alpha_engine as E

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
RES.mkdir(exist_ok=True)


def work(name):
    try:
        return E.compute_and_backtest(name)
    except Exception as e:               # noqa: BLE001
        return name, None, {"error": f"{type(e).__name__}: {str(e)[:160]}"}


def main():
    with open(HERE / "panels.pkl", "rb") as f:
        E.PANELS = pickle.load(f)          # parent loads once; fork shares it

    names = E.ALPHA_NAMES
    nproc = min(31, mp.cpu_count() - 1, len(names))
    print(f"backtesting {len(names)} alphas on {nproc} workers "
          f"(cpu={mp.cpu_count()}) ...", flush=True)

    t0 = time.time()
    pnl, ic_rank, ic_pear, metrics, errs = {}, {}, {}, {}, {}
    ctx = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=nproc, mp_context=ctx) as ex:
        for i, (name, series, m) in enumerate(ex.map(work, names), 1):
            if series is None:
                errs[name] = m.get("error")
            else:
                pnl[name] = series["pnl"]
                ic_rank[name] = series["ic_rank"]
                ic_pear[name] = series["ic_pear"]
                metrics[name] = m
            if i % 20 == 0 or i == len(names):
                print(f"  {i}/{len(names)}  elapsed={time.time()-t0:.0f}s", flush=True)

    pd.DataFrame(pnl).sort_index().to_csv(RES / "alpha_pnl.csv")
    pd.DataFrame(ic_rank).sort_index().to_csv(RES / "alpha_ic.csv")          # Spearman
    pd.DataFrame(ic_pear).sort_index().to_csv(RES / "alpha_ic_pearson.csv")  # Pearson
    met = pd.DataFrame(metrics).T
    met.index.name = "alpha"
    met = met.sort_values("ic_ir", ascending=False)
    met.to_csv(RES / "alpha_metrics.csv")

    pd.set_option("display.width", 180)
    cols = ["ic", "ic_ir", "ic_hit", "ic_pearson", "sharpe", "ann_ret", "turnover"]
    print("\n=== TOP 15 by IC information-ratio (consistency of daily correlation) ===")
    print(met[cols].head(15).round(3).to_string())
    print("\n=== BOTTOM 5 ===")
    print(met[cols].tail(5).round(3).to_string())
    print(f"\nmean IC>0: {(met['ic'] > 0).sum()}/{len(met)} | "
          f"IC-IR>0.5: {(met['ic_ir'] > 0.5).sum()} | IC-IR>1: {(met['ic_ir'] > 1).sum()}")
    if errs:
        print(f"failed {len(errs)}: {errs}")
    print(f"backtested {len(pnl)}/{len(names)} | wall={time.time()-t0:.0f}s | -> {RES}")


if __name__ == "__main__":
    main()
