import { useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
  ScatterChart, Scatter, ZAxis, ReferenceLine,
} from "recharts";
import type { RunData } from "../types";
import { ARM_META, fmt } from "../lib";

type View = "discoveries" | "quality";

export default function LearningChart({ run }: { run: RunData }) {
  const [view, setView] = useState<View>("discoveries");
  const armKeys = Object.keys(run.arms).filter((a) => a !== "frozen" && run.arms[a]?.length);

  const cumData = useMemo(() => {
    const maxLen = Math.max(...armKeys.map((a) => run.arms[a].length), 0);
    const acc: Record<string, number> = {};
    const rows: any[] = [];
    for (let g = 0; g < maxLen; g++) {
      const row: any = { g, date: run.arms[armKeys[0]]?.[g]?.date };
      for (const a of armKeys) {
        const pt = run.arms[a][g];
        if (pt) { acc[a] = (acc[a] || 0) + pt.n_accepted; row[a] = acc[a]; }
      }
      rows.push(row);
    }
    return rows;
  }, [run, armKeys]);

  // scatter: each accepted proposal's prospective (next-block) IR, by arm
  const scatter = useMemo(() => {
    const byArm: Record<string, { g: number; ir: number }[]> = {};
    for (const q of run.proposals) {
      if (q.verdict !== "accept" || q.test_ir == null) continue;
      (byArm[q.arm] = byArm[q.arm] || []).push({ g: q.g + (Math.random() - 0.5) * 0.5, ir: q.test_ir });
    }
    return byArm;
  }, [run]);

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between flex-wrap gap-2 mb-3">
        <div>
          <h3 className="text-lg font-semibold text-ink">The researcher is learning</h3>
          <p className="text-sm text-muted">
            With memory of past wins &amp; failures, the agent discovers keepers faster than its
            memory-ablated self or random search — the core continual-learning proof.</p>
        </div>
        <div className="flex gap-1 bg-surface2 border border-border p-1">
          {(["discoveries", "quality"] as View[]).map((v) => (
            <button key={v} onClick={() => setView(v)}
              className={`px-3 py-1 text-xs font-medium capitalize transition ${
                view === v ? "bg-violet/12 text-violet" : "text-muted hover:text-ink"}`}>
              {v === "discoveries" ? "Cumulative discoveries" : "Proposal quality (OOS)"}
            </button>
          ))}
        </div>
      </div>

      {view === "discoveries" ? (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={cumData} margin={{ top: 6, right: 12, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="#e7eaef" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="g" stroke="#8b95a4" fontSize={11}
              tickFormatter={(g) => cumData[g]?.date?.slice(0, 7) ?? g} />
            <YAxis stroke="#8b95a4" fontSize={11} />
            <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e7eaef", borderRadius: 0 }}
              labelFormatter={(g) => `Gen ${g}`}
              formatter={(v: any, n: any) => [v, ARM_META[n]?.label ?? n]} />
            <Legend formatter={(v) => ARM_META[v]?.label ?? v} wrapperStyle={{ fontSize: 12 }} />
            {armKeys.map((a) => (
              <Line key={a} type="monotone" dataKey={a} stroke={ARM_META[a]?.color}
                strokeWidth={a === "adaptive" ? 2.8 : 1.8} strokeDasharray={ARM_META[a]?.dash}
                dot={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart margin={{ top: 6, right: 12, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="#e7eaef" strokeDasharray="3 3" />
            <XAxis type="number" dataKey="g" name="gen" stroke="#8b95a4" fontSize={11}
              domain={[0, "dataMax"]} />
            <YAxis type="number" dataKey="ir" name="OOS IR" stroke="#8b95a4" fontSize={11} />
            <ZAxis range={[40, 40]} />
            <ReferenceLine y={0} stroke="#c7cdd8" />
            <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e7eaef", borderRadius: 0 }}
              formatter={(v: any, n: any) => [fmt(v), n]} />
            <Legend formatter={(v) => ARM_META[v]?.label ?? v} wrapperStyle={{ fontSize: 12 }} />
            {armKeys.map((a) => (
              <Scatter key={a} name={a} data={scatter[a] || []}
                fill={ARM_META[a]?.color} fillOpacity={0.7} />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      )}
      <p className="text-xs text-faint mt-2">
        Every proposal is scored on the <em>next unseen</em> block — accepted alphas shown.
        Higher &amp; denser = the agent is finding genuinely predictive, non-redundant signals.
      </p>
    </div>
  );
}
