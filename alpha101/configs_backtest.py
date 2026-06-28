"""Backtest every alpha under several realism configurations and save cumulative
IC + net-PnL time series, one set of columns per configuration.

Configs (realism axis):
  base   : delay 0, no cost, full universe           (idealized, what we had)
  delay1 : delay 1 day, no cost, full universe        (execution lag)
  cost   : delay 1 day, 10 bps/turnover, full         (lag + transaction cost)
  ooa    : delay 1 day, 10 bps, held-out HALF of stocks  (out-of-asset robustness)

Costs change PnL only (a correlation is cost-invariant), so IC differs across
base/delay1/ooa and PnL differs across all four. Both rank (Spearman) and
Pearson IC are kept. Also blends the top-20 alphas (by base IC-IR, sign-aligned)
into one combined signal evaluated under every config.
"""
import multiprocessing as mp
import pickle
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

import alpha_engine as E

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
RES.mkdir(exist_ok=True)
ANN = np.sqrt(252.0)

CONFIGS = [
    ("base",   dict(delay=0, cost_bps=0.0,  test=False)),
    ("delay1", dict(delay=1, cost_bps=0.0,  test=False)),
    ("cost",   dict(delay=1, cost_bps=10.0, test=False)),
    ("ooa",    dict(delay=1, cost_bps=10.0, test=True)),
]
TEST_COLS = None   # held-out stock half (set in parent, inherited via fork)


def _signal(name, p):
    sig = getattr(E.PanelAlphas(p), name)()
    if not isinstance(sig, pd.DataFrame):
        sig = pd.DataFrame(sig)
    return (sig.reindex(index=p["close"].index, columns=p["close"].columns)
            .astype(float).replace([np.inf, -np.inf], np.nan))


def _eval(sig, fwd, delay, cost_bps, cols):
    if cols is not None:
        sig, fwd = sig[cols], fwd[cols]
    if delay:
        sig = sig.shift(delay)                       # trade on yesterday's signal
    ic_rank = E._rowwise_corr(sig.rank(axis=1), fwd.rank(axis=1))
    ic_pear = E._rowwise_corr(sig, fwd)
    w = sig.sub(sig.mean(axis=1), axis=0)
    w = w.div(w.abs().sum(axis=1).replace(0, np.nan), axis=0)
    gross = (w * fwd).sum(axis=1, min_count=1).fillna(0.0)
    cost = (cost_bps / 1e4) * w.diff().abs().sum(axis=1).fillna(0.0)
    return ic_rank, ic_pear, gross - cost


def work(name):
    p = E.PANELS
    try:
        sig = _signal(name, p)
    except Exception:
        return name, None
    out = {}
    for cname, cfg in CONFIGS:
        cols = TEST_COLS if cfg["test"] else None
        ic_r, ic_p, pnl = _eval(sig, p["fwd"], cfg["delay"], cfg["cost_bps"], cols)
        out[cname] = {"ic_rank": ic_r, "ic_pear": ic_p, "pnl": pnl}
    return name, out


def _stack(results, cname, key):
    return pd.DataFrame({n: results[n][cname][key] for n in results}).sort_index()


def main():
    global TEST_COLS
    with open(HERE / "panels.pkl", "rb") as f:
        E.PANELS = pickle.load(f)
    TEST_COLS = sorted(E.PANELS["close"].columns)[1::2]   # deterministic OOA half
    names = E.ALPHA_NAMES
    nproc = min(31, mp.cpu_count() - 1)
    print(f"backtesting {len(names)} alphas x {len(CONFIGS)} configs on {nproc} workers ...",
          flush=True)

    t0 = time.time()
    results = {}
    ctx = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=nproc, mp_context=ctx) as ex:
        for name, out in ex.map(work, names):
            if out is not None:
                results[name] = out
    print(f"  computed in {time.time()-t0:.0f}s", flush=True)

    # save per-config matrices (date x alpha)
    for cname, _ in CONFIGS:
        _stack(results, cname, "ic_rank").to_csv(RES / f"cfg_{cname}_ic.csv")
        _stack(results, cname, "ic_pear").to_csv(RES / f"cfg_{cname}_icp.csv")
        _stack(results, cname, "pnl").to_csv(RES / f"cfg_{cname}_pnl.csv")

    # ---- per-alpha metric table across configs + attrition summary ----
    by_alpha, summ = {}, []
    base_ic = _stack(results, "base", "ic_rank")
    base_icir = (ANN * base_ic.mean() / base_ic.std()).sort_values(ascending=False)
    for cname, _ in CONFIGS:
        icr = _stack(results, cname, "ic_rank")
        pnl = _stack(results, cname, "pnl")
        icir = ANN * icr.mean() / icr.std()
        shp = ANN * pnl.mean() / pnl.std()
        by_alpha[f"{cname}_icir"] = icir
        by_alpha[f"{cname}_sharpe"] = shp
        summ.append({"config": cname, "alphas": len(results),
                     "mean_IC": float(icr.mean().mean()),
                     "IC_pos": int((icr.mean() > 0).sum()),
                     "ICIR>1": int((icir > 1).sum()),
                     "ICIR>0.5": int((icir > 0.5).sum()),
                     "Sharpe>1": int((shp > 1).sum()),
                     "Sharpe>0": int((shp > 0).sum()),
                     "mean_Sharpe": float(shp.mean())})
    pd.DataFrame(by_alpha).reindex(base_icir.index).to_csv(RES / "config_metrics_by_alpha.csv")
    summary = pd.DataFrame(summ).set_index("config")
    summary.to_csv(RES / "config_summary.csv")

    # ---- combined alpha: top-20 by base IC-IR, sign-aligned rank blend ----
    top = base_icir.head(20).index.tolist()
    base_meanic = base_ic.mean()
    p = E.PANELS
    combo, n = None, 0
    for a in top:
        s = np.sign(base_meanic[a]) * (_signal(a, p).rank(axis=1) - 0.5)
        combo = s if combo is None else combo.add(s, fill_value=0.0)
        n += 1
    combo /= n
    combo_ic, combo_pnl = {}, {}
    for cname, cfg in CONFIGS:
        cols = TEST_COLS if cfg["test"] else None
        ic_r, _, pnl = _eval(combo, p["fwd"], cfg["delay"], cfg["cost_bps"], cols)
        combo_ic[cname] = ic_r
        combo_pnl[cname] = pnl
    pd.DataFrame(combo_ic).to_csv(RES / "combo_ic.csv")
    pd.DataFrame(combo_pnl).to_csv(RES / "combo_pnl.csv")

    pd.set_option("display.width", 180)
    print("\n=== CONFIG SUMMARY (attrition as realism increases) ===")
    print(summary.round(3).to_string())
    print(f"\ncombined top-{len(top)} alphas:")
    for cname, _ in CONFIGS:
        ic = pd.Series(combo_ic[cname]).dropna()
        pnl = pd.Series(combo_pnl[cname])
        print(f"  {cname:7s}  IC {ic.mean():+.4f}  IC-IR {ANN*ic.mean()/ic.std():5.2f}  "
              f"net-Sharpe {ANN*pnl.mean()/pnl.std():5.2f}")
    print(f"\nwall={time.time()-t0:.0f}s | -> {RES}")


if __name__ == "__main__":
    main()
