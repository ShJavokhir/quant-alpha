"use client";

import type { Experiment } from "@/lib/api";

export function ImprovementArc({ experiments }: { experiments: Experiment[] }) {
  if (!experiments.length) return null;

  const W = 540, H = 200, pad = 34;
  const iters = experiments.map((e) => e.iteration);
  const oos = experiments.map((e) => e.oos_sharpe);
  const minY = Math.min(0, ...oos) - 0.15;
  const maxY = Math.max(0.7, ...oos) + 0.15;
  const i0 = iters[0], i1 = iters[iters.length - 1];
  const X = (it: number) => pad + (W - 2 * pad) * ((it - i0) / Math.max(1, i1 - i0));
  const Y = (v: number) => H - pad - (H - 2 * pad) * ((v - minY) / (maxY - minY));

  let best = -Infinity;
  const bestPts = experiments.map((e) => {
    if (e.accepted) best = Math.max(best, e.oos_sharpe);
    return best === -Infinity ? null : { x: X(e.iteration), y: Y(best) };
  });
  const linePath = bestPts
    .filter((p): p is { x: number; y: number } => p !== null)
    .map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`)
    .join(" ");

  const color = (v: string) =>
    v === "ROBUST" ? "var(--color-robust)" : v === "FRAGILE" ? "var(--color-fragile)" : "var(--color-overfit)";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      <line x1={pad} x2={W - pad} y1={Y(0)} y2={Y(0)} stroke="var(--color-line)" strokeDasharray="3 3" />
      <text x={pad} y={Y(0) - 5} fill="var(--color-muted)" fontSize="10" fontFamily="monospace">
        0.0
      </text>

      {linePath && <path d={linePath} fill="none" stroke="var(--color-robust)" strokeWidth="2.5" />}

      {experiments.map((e) => (
        <g key={e.iteration}>
          <circle cx={X(e.iteration)} cy={Y(e.oos_sharpe)} r="5.5" fill={color(e.verdict)} />
          <text
            x={X(e.iteration)}
            y={Y(e.oos_sharpe) - 11}
            textAnchor="middle"
            fill="var(--color-ink)"
            fontSize="10"
            fontFamily="monospace"
          >
            {e.oos_sharpe.toFixed(2)}
          </text>
          <text
            x={X(e.iteration)}
            y={H - pad + 16}
            textAnchor="middle"
            fill="var(--color-muted)"
            fontSize="10"
            fontFamily="monospace"
          >
            #{e.iteration}
          </text>
        </g>
      ))}
    </svg>
  );
}
