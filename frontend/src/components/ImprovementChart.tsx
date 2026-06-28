import { useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ReferenceArea, ReferenceLine, Legend,
} from "recharts";
import type { RunData } from "../types";
import { ARM_META, fmt } from "../lib";

type Metric = "appraisal" | "ic_ir" | "sharpe_net";
const METRICS: { key: Metric; label: string }[] = [
  { key: "appraisal", label: "Appraisal ratio (risk-adj alpha)" },
  { key: "ic_ir", label: "IC information ratio" },
  { key: "sharpe_net", label: "Net Sharpe (after 10bps)" },
];

const REGIMES = [
  { start: "2020-01-01", end: "2020-06-01", label: "COVID" },
  { start: "2022-01-01", end: "2022-10-01", label: "2022 bear" },
];

export default function ImprovementChart({ run }: { run: RunData }) {
  const [metric, setMetric] = useState<Metric>("appraisal");
  const armKeys = Object.keys(run.arms).filter((a) => run.arms[a]?.length);

  const data = useMemo(() => {
    const maxLen = Math.max(...armKeys.map((a) => run.arms[a].length), 0);
    const rows: any[] = [];
    // running average of the OOS metric per arm (cuts single-block regime noise)
    const sums: Record<string, number> = {};
    for (let g = 0; g < maxLen; g++) {
      const row: any = { g, date: run.arms[armKeys[0]]?.[g]?.date };
      for (const a of armKeys) {
        const pt = run.arms[a][g];
        if (pt) {
          sums[a] = (sums[a] || 0) + (pt.book_test[metric] || 0);
          row[a] = +(sums[a] / (g + 1)).toFixed(3);
        }
      }
      rows.push(row);
    }
    return rows;
  }, [run, metric, armKeys]);

  const regimeBands = REGIMES.map((r) => {
    const x1 = data.find((d) => d.date >= r.start)?.g;
    const x2 = [...data].reverse().find((d) => d.date <= r.end)?.g;
    return { ...r, x1, x2 };
  }).filter((r) => r.x1 != null && r.x2 != null);

  const finalA = run.arms.adaptive?.at(-1);
  const finalF = run.arms.frozen?.at(-1);

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between flex-wrap gap-2 mb-3">
        <div>
          <h3 className="text-lg font-semibold text-ink">Adaptive vs. Frozen — out-of-sample</h3>
          <p className="text-sm text-muted">Running-average out-of-sample quality on each unseen block.
            The evolving fleet adapts through regimes; the frozen seed fleet drifts.</p>
        </div>
        <div className="flex gap-1 bg-surface2 rounded-lg p-1">
          {METRICS.map((m) => (
            <button key={m.key} onClick={() => setMetric(m.key)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                metric === m.key ? "bg-cyan/15 text-cyan" : "text-muted hover:text-ink"}`}>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="#1e2740" strokeDasharray="3 3" vertical={false} />
          {regimeBands.map((r, i) => (
            <ReferenceArea key={i} x1={r.x1} x2={r.x2} fill="#fb7185" fillOpacity={0.06}
              label={{ value: r.label, position: "insideTop", fill: "#fb7185", fontSize: 10 }} />
          ))}
          <ReferenceLine y={0} stroke="#3a4658" strokeOpacity={0.6} />
          <XAxis dataKey="g" stroke="#5a6477" fontSize={11}
            tickFormatter={(g) => data[g]?.date?.slice(0, 7) ?? g} />
          <YAxis stroke="#5a6477" fontSize={11} />
          <Tooltip contentStyle={{ background: "#0e1320", border: "1px solid #1e2740", borderRadius: 10 }}
            labelFormatter={(g) => `Gen ${g} · ${data[g]?.date ?? ""}`}
            formatter={(v: any, n: any) => [fmt(v), ARM_META[n]?.label ?? n]} />
          <Legend formatter={(v) => ARM_META[v]?.label ?? v} wrapperStyle={{ fontSize: 12 }} />
          {armKeys.map((a) => (
            <Line key={a} type="monotone" dataKey={a} stroke={ARM_META[a]?.color}
              strokeWidth={a === "adaptive" ? 2.8 : 1.8} strokeDasharray={ARM_META[a]?.dash}
              dot={false} isAnimationActive />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {finalA && finalF && (
        <div className="text-sm text-muted mt-2">
          Final running-avg {METRICS.find((m) => m.key === metric)!.label.toLowerCase()}:{" "}
          <span className="text-cyan font-semibold">agent {fmt(
            data.at(-1)?.adaptive)}</span> vs{" "}
          <span className="text-rose font-semibold">frozen {fmt(data.at(-1)?.frozen)}</span>.
        </div>
      )}
    </div>
  );
}
