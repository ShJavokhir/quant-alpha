"use client";

import type { Experiment } from "@/lib/api";

const bg = (v: string) =>
  v === "ROBUST" ? "bg-robust/80" : v === "FRAGILE" ? "bg-fragile/80" : v === "OVERFIT" ? "bg-overfit/80" : "bg-muted/40";

export function BasketHeatmap({ exp }: { exp: Experiment }) {
  const entries = Object.entries(exp.per_ticker);
  return (
    <div className="grid grid-cols-5 gap-1.5">
      {entries.map(([tk, v]) => (
        <div
          key={tk}
          className={`rounded-md ${bg(v.verdict)} px-2 py-1.5 text-center`}
          title={`${tk}: ${v.verdict} · OOS appraisal ${v.oos_appraisal.toFixed(2)} · IR ${v.oos_excess_sharpe.toFixed(2)}`}
        >
          <div className="font-mono text-[11px] font-bold text-canvas">{tk}</div>
          <div className="font-mono text-[10px] text-canvas/80">{v.oos_appraisal.toFixed(2)}</div>
        </div>
      ))}
    </div>
  );
}
