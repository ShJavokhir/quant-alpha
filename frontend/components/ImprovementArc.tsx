"use client";

import { useEffect, useState } from "react";
import { api, type AblationResponse } from "@/lib/api";

/** A grouped bar pair (memory-ON vs memory-OFF) with ±std error bars. */
function MetricBars({
  title,
  hint,
  on,
  off,
  max,
  better,
}: {
  title: string;
  hint: string;
  on: { mean: number; sem: number };
  off: { mean: number; sem: number };
  max: number;
  better: "lower" | "higher";
}) {
  const W = 250, H = 150, padL = 30, padB = 28, padT = 8;
  const innerH = H - padB - padT;
  const y = (v: number) => padT + innerH * (1 - Math.max(0, v) / max);
  const bars = [
    { label: "ON", color: "var(--color-robust)", mean: on.mean, std: on.sem, x: 70 },
    { label: "OFF", color: "var(--color-overfit)", mean: off.mean, std: off.sem, x: 150 },
  ];
  const bw = 46;
  return (
    <div className="flex-1">
      <div className="mb-1 font-mono text-[11px] text-ink">{title}</div>
      <div className="mb-1 font-mono text-[10px] text-muted">{hint}</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        <line x1={padL} x2={W - 6} y1={y(0)} y2={y(0)} stroke="var(--color-line)" />
        {bars.map((b) => (
          <g key={b.label}>
            <rect x={b.x} y={y(b.mean)} width={bw} height={Math.max(0, y(0) - y(b.mean))} fill={b.color} opacity={0.85} rx={2} />
            {/* error bar ±std */}
            <line x1={b.x + bw / 2} x2={b.x + bw / 2} y1={y(b.mean + b.std)} y2={y(Math.max(0, b.mean - b.std))} stroke="var(--color-ink)" strokeWidth={1.5} />
            <line x1={b.x + bw / 2 - 6} x2={b.x + bw / 2 + 6} y1={y(b.mean + b.std)} y2={y(b.mean + b.std)} stroke="var(--color-ink)" strokeWidth={1.5} />
            <line x1={b.x + bw / 2 - 6} x2={b.x + bw / 2 + 6} y1={y(Math.max(0, b.mean - b.std))} y2={y(Math.max(0, b.mean - b.std))} stroke="var(--color-ink)" strokeWidth={1.5} />
            <text x={b.x + bw / 2} y={y(b.mean) - 6} textAnchor="middle" fill="var(--color-ink)" fontSize="11" fontFamily="monospace" fontWeight="bold">
              {b.mean.toFixed(2)}
            </text>
            <text x={b.x + bw / 2} y={H - 10} textAnchor="middle" fill="var(--color-muted)" fontSize="10" fontFamily="monospace">
              memory-{b.label}
            </text>
          </g>
        ))}
      </svg>
      <div className="text-center font-mono text-[10px] text-muted">{better === "lower" ? "lower is better" : "higher is better"}</div>
    </div>
  );
}

export function ImprovementArc() {
  const [data, setData] = useState<AblationResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.ablation().then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="font-mono text-xs text-overfit">ablation API: {err}</p>;
  if (!data) return <p className="font-mono text-xs text-muted">loading ablation…</p>;

  const on = data.memory_on.agg, off = data.memory_off.agg;
  const e2rMax = Math.max(on.experiments_to_first_robust.mean + on.experiments_to_first_robust.sem,
    off.experiments_to_first_robust.mean + off.experiments_to_first_robust.sem, data.max_experiments) * 1.1;
  const bestMax = Math.max(on.best_oos_appraisal.mean + on.best_oos_appraisal.sem,
    off.best_oos_appraisal.mean + off.best_oos_appraisal.sem, 0.4) * 1.15;

  return (
    <div>
      <p className="mb-3 font-mono text-[11px] leading-relaxed text-muted">
        One knob changed: the routing policy ON vs OFF. Same seeded random-search proposer, randomized
        family order. <span className="text-ink">{data.n_seeds} seeds</span> each · error bars ±1 SEM.
      </p>
      <div className="flex flex-col gap-4 sm:flex-row">
        <MetricBars
          title="Experiments to first ROBUST"
          hint="how fast it finds a surviving edge"
          on={on.experiments_to_first_robust}
          off={off.experiments_to_first_robust}
          max={e2rMax}
          better="lower"
        />
        <MetricBars
          title="Best OOS alpha reached"
          hint="quality of the edge it discovers"
          on={on.best_oos_appraisal}
          off={off.best_oos_appraisal}
          max={bestMax}
          better="higher"
        />
      </div>
      <p className="mt-2 font-mono text-[11px] text-muted">
        Found a robust edge within budget:{" "}
        <span className="text-robust">{(on.found_robust_rate * 100).toFixed(0)}%</span> with memory ·{" "}
        <span className="text-overfit">{(off.found_robust_rate * 100).toFixed(0)}%</span> without. The policy
        accelerates <span className="text-ink">and</span> improves discovery.
      </p>
    </div>
  );
}
