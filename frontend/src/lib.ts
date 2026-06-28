import type { RunData } from "./types";

export const FAMILY_COLORS: Record<string, string> = {
  momentum: "#c2820a",
  reversal: "#0e88a8",
  volume: "#6645e6",
  volatility: "#d23b36",
  value: "#07875a",
  microstructure: "#1f7fd0",
  seasonality: "#c2459a",
  unknown: "#6b7280",
};

export const familyColor = (f: string) => FAMILY_COLORS[f] || FAMILY_COLORS.unknown;

export const ARM_META: Record<string, { label: string; color: string; dash?: string }> = {
  adaptive: { label: "Agent (memory ON)", color: "#0a6ce0" },
  memory_off: { label: "Memory ablated", color: "#c2820a", dash: "5 4" },
  random: { label: "Random search", color: "#a3acba", dash: "2 4" },
  frozen: { label: "Frozen fleet", color: "#cf7a5e", dash: "7 5" },
};

/* up / down semantics — legible on white */
export const UP = "#07875a";
export const DOWN = "#d23b36";

/* shared recharts theme so every chart matches the light, sharp surface */
export const CHART = {
  grid: "#e7eaef",
  axis: "#8b95a4",
  refLine: "#c7cdd8",
  dotStroke: "#ffffff",
  regimeFill: "#d23b36",
  regimeLabel: "#a85049",
};

export const tooltipStyle = {
  background: "#ffffff",
  border: "1px solid #d2d7e0",
  borderRadius: 0,
  fontSize: 12,
  color: "#0e1216",
  boxShadow: "0 6px 20px -8px rgba(14,18,22,0.22)",
} as const;

export const fmt = (x: number | null | undefined, d = 2) =>
  x === null || x === undefined || Number.isNaN(x) ? "–" : x.toFixed(d);

export const signed = (x: number | null | undefined, d = 2) =>
  x === null || x === undefined ? "–" : (x >= 0 ? "+" : "") + x.toFixed(d);

export const healthColor = (ir: number) => {
  if (ir >= 1.5) return "#07875a";
  if (ir >= 0.6) return "#4d9a16";
  if (ir >= 0.0) return "#c2820a";
  return "#d23b36";
};

export async function loadRun(): Promise<RunData> {
  // try API first, fall back to bundled static copy
  try {
    const r = await fetch("/api/run", { cache: "no-store" });
    if (r.ok) return await r.json();
  } catch { /* ignore */ }
  const r2 = await fetch("/run.json", { cache: "no-store" });
  return await r2.json();
}

export const pct = (x: number, d = 0) => (x * 100).toFixed(d) + "%";

export interface EquityRow {
  g: number; date: string;
  adaptive_net: number; frozen_net: number;
  adaptive_gross: number; frozen_gross: number;
}

/**
 * Build cumulative equity curves (base 100) by compounding each walk-forward
 * block's *realised* return from the committed run — genuine backtest output,
 * not a synthetic path. Gross uses ann_ret; net uses ann_ret_net (after costs).
 * Each block spans book_test.n_days, so the per-block factor is annual·(n/252).
 */
export function equityCurves(run: RunData): EquityRow[] {
  const A = run.arms?.adaptive ?? [];
  const F = run.arms?.frozen ?? [];
  const n = Math.max(A.length, F.length);
  let an = 100, ag = 100, fn = 100, fg = 100;
  const rows: EquityRow[] = [];
  for (let i = 0; i < n; i++) {
    const a = A[i]?.book_test, f = F[i]?.book_test;
    if (a) { const k = a.n_days / 252; an *= 1 + a.ann_ret_net * k; ag *= 1 + a.ann_ret * k; }
    if (f) { const k = f.n_days / 252; fn *= 1 + f.ann_ret_net * k; fg *= 1 + f.ann_ret * k; }
    rows.push({
      g: i, date: A[i]?.date ?? F[i]?.date ?? "",
      adaptive_net: +an.toFixed(2), frozen_net: +fn.toFixed(2),
      adaptive_gross: +ag.toFixed(2), frozen_gross: +fg.toFixed(2),
    });
  }
  return rows;
}
