"""Plot Alpha101 results — headline is CUMULATIVE IC (the running sum of the
daily cross-sectional correlation between each alpha and the next-day return).

Rising line  -> the alpha keeps predicting (edge persists)
Flat line    -> no predictive power / edge has plateaued
Falling line -> the signal reverses (anti-predictive)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RES = HERE / "results"

ic = pd.read_csv(RES / "alpha_ic.csv", index_col=0, parse_dates=True)   # daily rank IC
pnl = pd.read_csv(RES / "alpha_pnl.csv", index_col=0, parse_dates=True)
met = pd.read_csv(RES / "alpha_metrics.csv", index_col="alpha")
cum_ic = ic.fillna(0).cumsum()
order = [a for a in met.index if a in cum_ic.columns]    # sorted by IC-IR desc
GREEN, RED, BLUE = "#1a7f37", "#cf222e", "#0969da"

# 1) HEADLINE: faceted cumulative-IC curve for every alpha ---------------------
ncol = 8
nrow = int(np.ceil(len(order) / ncol))
fig, axes = plt.subplots(nrow, ncol, figsize=(ncol * 2.6, nrow * 1.9))
for ax, a in zip(axes.flat, order):
    icir = met.loc[a, "ic_ir"]
    ax.plot(cum_ic.index, cum_ic[a].values, color=GREEN if icir >= 0 else RED, lw=0.9)
    ax.axhline(0, color="gray", lw=0.4)
    ax.set_title(f"{a}  ICIR{icir:.2f}", fontsize=7)
    ax.set_xticks([]); ax.set_yticks([])
for ax in axes.flat[len(order):]:
    ax.axis("off")
fig.suptitle("Alpha101 — CUMULATIVE daily IC (corr of alpha vs next-day return), "
             "2010–2014, sorted by IC-IR", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.99])
fig.savefig(RES / "ic_cumulative_grid.png", dpi=95)
plt.close(fig)

# 2) HEADLINE overlay: top 10 / bottom 3 by IC-IR -----------------------------
fig, ax = plt.subplots(figsize=(12, 7))
for a in order[:10]:
    ax.plot(cum_ic.index, cum_ic[a], lw=1.6,
            label=f"{a}  IC {met.loc[a,'ic']:+.3f}  IR {met.loc[a,'ic_ir']:.2f}")
for a in order[-3:]:
    ax.plot(cum_ic.index, cum_ic[a], lw=1.1, ls="--",
            label=f"{a}  IC {met.loc[a,'ic']:+.3f}  IR {met.loc[a,'ic_ir']:.2f}")
ax.axhline(0, color="gray", lw=0.5)
ax.legend(fontsize=8, ncol=2, loc="upper left")
ax.set_title("Cumulative IC — top 10 & bottom 3 alphas by IC information-ratio")
ax.set_ylabel("cumulative daily rank-IC")
fig.tight_layout()
fig.savefig(RES / "ic_cumulative_top.png", dpi=120)
plt.close(fig)

# 3) ranking: mean IC and IC-IR ----------------------------------------------
fig, (a1, a2) = plt.subplots(2, 1, figsize=(16, 8))
s_ic = met["ic"].sort_values(ascending=False)
a1.bar(range(len(s_ic)), s_ic.values, color=[GREEN if v >= 0 else RED for v in s_ic.values])
a1.set_xticks(range(len(s_ic))); a1.set_xticklabels(s_ic.index, rotation=90, fontsize=5)
a1.axhline(0, color="k", lw=0.6); a1.set_ylabel("mean daily IC")
a1.set_title("Alpha101 — mean daily IC (rank correlation with next-day return)")
s_ir = met["ic_ir"].sort_values(ascending=False)
a2.bar(range(len(s_ir)), s_ir.values, color=[GREEN if v >= 0 else RED for v in s_ir.values])
a2.set_xticks(range(len(s_ir))); a2.set_xticklabels(s_ir.index, rotation=90, fontsize=5)
a2.axhline(0, color="k", lw=0.6); a2.set_ylabel("IC information-ratio (annualized)")
a2.set_title("Alpha101 — IC-IR (consistency of the daily correlation)")
fig.tight_layout()
fig.savefig(RES / "ic_ranking.png", dpi=110)
plt.close(fig)

# 4) secondary: cumulative PnL grid (portfolio view) --------------------------
cum_p = pnl.cumsum()
porder = met.sort_values("sharpe", ascending=False).index.tolist()
porder = [a for a in porder if a in cum_p.columns]
fig, axes = plt.subplots(nrow, ncol, figsize=(ncol * 2.6, nrow * 1.9))
for ax, a in zip(axes.flat, porder):
    sh = met.loc[a, "sharpe"]
    ax.plot(cum_p.index, cum_p[a].values, color=GREEN if sh >= 0 else RED, lw=0.9)
    ax.axhline(0, color="gray", lw=0.4)
    ax.set_title(f"{a}  Sh{sh:.2f}", fontsize=7)
    ax.set_xticks([]); ax.set_yticks([])
for ax in axes.flat[len(porder):]:
    ax.axis("off")
fig.suptitle("Alpha101 — cumulative dollar-neutral PnL (portfolio view), 2010–2014",
             fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.99])
fig.savefig(RES / "pnl_cumulative_grid.png", dpi=95)
plt.close(fig)

print("saved:", ", ".join(p.name for p in sorted(RES.glob("*.png"))))
