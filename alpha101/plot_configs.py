"""Plot the multi-configuration comparison: one column per configuration.

  ic_grid   : rows=alphas, cols=[base, delay-1, out-of-asset]; each cell is the
              cumulative IC time series (Spearman solid, Pearson dotted).
  pnl_grid  : rows=alphas, cols=[gross d0, gross d1, net+cost, net OOA]; cumulative
              net PnL.
  combined  : the top-20 blended alpha's cumulative IC and net PnL across configs.
  attrition : how many alphas survive as realism increases.
Full (all 82) and a readable top-30 crop are produced for each grid.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
GREEN, RED = "#1a7f37", "#cf222e"

IC_COLS = [("base", "base (d0)"), ("delay1", "delay-1"), ("ooa", "out-of-asset")]
PNL_COLS = [("base", "gross d0"), ("delay1", "gross d1"),
            ("cost", "net (d1+10bps)"), ("ooa", "net OOA (held-out)")]
COMBO = [("base", "base d0"), ("delay1", "delay-1"),
         ("cost", "net +cost"), ("ooa", "out-of-asset")]


def load(prefix):
    return {c: pd.read_csv(RES / f"cfg_{c}_{prefix}.csv", index_col=0, parse_dates=True)
            for c, _ in PNL_COLS}


cum = lambda df: df.fillna(0).cumsum()
ic = {c: cum(d) for c, d in load("ic").items()}
icp = {c: cum(d) for c, d in load("icp").items()}
pnl = {c: cum(d) for c, d in load("pnl").items()}
by_alpha = pd.read_csv(RES / "config_metrics_by_alpha.csv", index_col=0)
order_all = list(by_alpha.index)                          # sorted by base IC-IR desc
signs = {a: (1 if ic["base"][a].iloc[-1] >= 0 else -1) for a in order_all}


def grid(order, cols, solid, dash, signfrom, fname, suptitle, hpr=0.62):
    nr, nc = len(order), len(cols)
    fig, axes = plt.subplots(nr, nc, figsize=(nc * 2.7, max(2.0, nr * hpr)), squeeze=False)
    for r, a in enumerate(order):
        for c, (ck, clabel) in enumerate(cols):
            ax = axes[r][c]
            if a in solid[ck].columns:
                color = GREEN if signs[a] >= 0 else RED
                ax.plot(solid[ck].index, solid[ck][a].values, color=color, lw=0.8)
            if dash is not None and a in dash[ck].columns:
                ax.plot(dash[ck].index, dash[ck][a].values, color="0.45", lw=0.6, ls=":")
            ax.axhline(0, color="gray", lw=0.3)
            ax.set_xticks([]); ax.set_yticks([])
            if r == 0:
                ax.set_title(clabel, fontsize=9)
            if c == 0:
                ax.set_ylabel(a, rotation=0, ha="right", va="center", fontsize=6)
    fig.suptitle(suptitle, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.997])
    fig.savefig(RES / fname, dpi=85)
    plt.close(fig)


# IC grids (Spearman solid, Pearson dotted)
for tag, rows in [("full", order_all), ("top", order_all[:30])]:
    grid(rows, IC_COLS, ic, icp, signs, f"cfg_ic_grid_{tag}.png",
         "Cumulative IC across configs (Spearman solid · Pearson dotted) — rows sorted by base IC-IR")
# PnL grids
for tag, rows in [("full", order_all), ("top", order_all[:30])]:
    grid(rows, PNL_COLS, pnl, None, signs, f"cfg_pnl_grid_{tag}.png",
         "Cumulative NET PnL across configs — rows sorted by base IC-IR")

# combined top-20 alpha
ci = pd.read_csv(RES / "combo_ic.csv", index_col=0, parse_dates=True)
cp = pd.read_csv(RES / "combo_pnl.csv", index_col=0, parse_dates=True)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 5.5))
for ck, lbl in COMBO:
    a1.plot(ci.index, ci[ck].fillna(0).cumsum(), lw=1.9, label=lbl)
    a2.plot(cp.index, cp[ck].cumsum(), lw=1.9, label=lbl)
for ax, t in [(a1, "Combined top-20 alpha — cumulative IC"),
              (a2, "Combined top-20 alpha — cumulative net PnL")]:
    ax.axhline(0, color="gray", lw=0.5); ax.legend(fontsize=9); ax.set_title(t)
fig.tight_layout()
fig.savefig(RES / "cfg_combined.png", dpi=120)
plt.close(fig)

# attrition
summ = pd.read_csv(RES / "config_summary.csv", index_col="config")
fig, ax = plt.subplots(figsize=(9, 5))
mets = ["IC_pos", "ICIR>1", "Sharpe>0", "Sharpe>1"]
x = np.arange(len(summ)); width = 0.2
for i, m in enumerate(mets):
    ax.bar(x + i * width, summ[m].values, width, label=m)
ax.set_xticks(x + 1.5 * width)
ax.set_xticklabels([f"{c}\n{lbl}" for (c, lbl) in
                    [("base", "d0"), ("delay1", "d1"), ("cost", "d1+cost"), ("ooa", "OOA")]],
                   fontsize=9)
ax.set_ylabel("# of 82 alphas"); ax.legend()
ax.set_title("Alpha survival as realism increases (out of 82)")
fig.tight_layout()
fig.savefig(RES / "cfg_attrition.png", dpi=120)
plt.close(fig)

print("saved:", ", ".join(p.name for p in sorted(RES.glob("cfg_*.png")) if "grid" not in p.name),
      "+ grids")
