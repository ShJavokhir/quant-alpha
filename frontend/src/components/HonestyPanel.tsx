import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BookMetrics, RunData } from "../types";
import { ARM_META, fmt, pct } from "../lib";

const tooltipStyle = {
  background: "#0e1320",
  border: "1px solid #1e2740",
  borderRadius: 10,
  fontSize: 12,
  color: "#e8eef6",
} as const;

const GUARDRAILS = [
  "Prospective walk-forward — every keep / kill / add is decided before the test block is seen",
  "Sealed 2024 holdout, evaluated once",
  "Net-of-cost gate (10 bps) + cost sweep + 1-day delay",
  "Liquid top-N universe (no penny-stock illusions)",
  "Every trial logged (multiple-testing honesty)",
  "Random-search & memory-ablated controls",
];

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface2/50 rounded-lg px-3 py-2 border border-border">
      <div className="text-faint text-[10px] uppercase tracking-wide">{label}</div>
      <div className="stat-num text-ink font-semibold mt-0.5">{value}</div>
    </div>
  );
}

function HoldoutRow({
  label,
  book,
  color,
}: {
  label: string;
  book?: BookMetrics;
  color: string;
}) {
  return (
    <tr className="border-t border-border">
      <td className="py-2 pr-3">
        <span className="inline-flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: color }} />
          <span className="text-ink">{label}</span>
        </span>
      </td>
      <td className="py-2 px-3 text-right font-mono text-muted stat-num">
        {fmt(book?.sharpe)}
      </td>
      <td className="py-2 pl-3 text-right font-mono text-ink font-semibold stat-num">
        {fmt(book?.sharpe_net)}
      </td>
    </tr>
  );
}

export default function HonestyPanel({ run }: { run: RunData }) {
  const { summary, meta, holdout } = run;
  const sweep = holdout?.cost_sweep ?? [];

  const aDelay = holdout?.adaptive_delay1?.sharpe_net ?? null;
  const aBase = holdout?.adaptive?.sharpe_net ?? null;
  const delayDrop =
    aDelay !== null && aBase !== null ? aDelay - aBase : null;

  return (
    <section id="honesty" className="card p-6 scroll-mt-20">
      <h2 className="text-lg font-semibold tracking-tight">Methodology &amp; honesty</h2>
      <p className="text-sm text-muted mt-1">
        We engineered against the ways backtests fool you.
      </p>

      {/* Top stats */}
      <div className="grid grid-cols-3 gap-2 mt-5">
        <StatPill label="Trials run" value={summary.n_trials.toLocaleString()} />
        <StatPill label="Accept rate" value={pct(summary.accept_rate)} />
        <StatPill label="Generations" value={String(meta.n_generations)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {/* Sealed holdout table */}
        <div>
          <div className="text-faint text-[10px] uppercase tracking-wide mb-2">
            Sealed 2024 holdout
            {holdout?.window && (
              <span className="text-faint normal-case">
                {" "}· {holdout.window.start} → {holdout.window.end}
              </span>
            )}
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-faint text-[11px] uppercase tracking-wide">
                <th className="text-left font-medium pb-1">Strategy</th>
                <th className="text-right font-medium pb-1">Gross Sharpe</th>
                <th className="text-right font-medium pb-1">Net Sharpe</th>
              </tr>
            </thead>
            <tbody>
              <HoldoutRow
                label={ARM_META.adaptive.label}
                book={holdout?.adaptive}
                color={ARM_META.adaptive.color}
              />
              <HoldoutRow
                label={ARM_META.frozen.label}
                book={holdout?.frozen}
                color={ARM_META.frozen.color}
              />
            </tbody>
          </table>

          {/* 1-day delay robustness */}
          <div className="mt-4 bg-surface2/50 rounded-lg px-3 py-2.5 border border-border">
            <div className="text-faint text-[10px] uppercase tracking-wide">
              1-day execution delay
            </div>
            <div className="text-sm mt-1 flex items-baseline gap-2 flex-wrap">
              <span className="font-mono stat-num text-ink">{fmt(aDelay)}</span>
              <span className="text-faint text-xs">net Sharpe</span>
              <span className="text-faint text-xs">vs</span>
              <span className="font-mono stat-num text-muted">{fmt(aBase)}</span>
              <span className="text-faint text-xs">immediate</span>
              {delayDrop !== null && (
                <span
                  className={`chip text-[10px] ${
                    delayDrop >= 0 ? "text-emerald" : "text-rose"
                  }`}
                >
                  {delayDrop >= 0 ? "+" : ""}
                  {fmt(delayDrop)} from delay
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Cost sweep */}
        <div>
          <div className="text-faint text-[10px] uppercase tracking-wide mb-2">
            Net Sharpe vs trading cost (bps)
          </div>
          {sweep.length ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={sweep} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid stroke="#1e2740" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="bps"
                  stroke="#5a6477"
                  tick={{ fontSize: 11, fill: "#5a6477" }}
                  tickLine={false}
                  axisLine={{ stroke: "#1e2740" }}
                />
                <YAxis
                  stroke="#5a6477"
                  tick={{ fontSize: 11, fill: "#5a6477" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={{ color: "#8a97ad" }}
                  labelFormatter={(v) => `${v} bps`}
                />
                <Line
                  type="monotone"
                  dataKey="adaptive"
                  name={ARM_META.adaptive.label}
                  stroke={ARM_META.adaptive.color}
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="frozen"
                  name={ARM_META.frozen.label}
                  stroke={ARM_META.frozen.color}
                  strokeWidth={2}
                  strokeDasharray={ARM_META.frozen.dash}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] grid place-items-center text-faint text-xs">
              no cost sweep
            </div>
          )}
          <div className="flex items-center gap-4 mt-2 text-[11px]">
            <span className="inline-flex items-center gap-1.5 text-muted">
              <span
                className="h-2 w-3 rounded-full"
                style={{ background: ARM_META.adaptive.color }}
              />
              {ARM_META.adaptive.label}
            </span>
            <span className="inline-flex items-center gap-1.5 text-muted">
              <span
                className="h-2 w-3 rounded-full"
                style={{ background: ARM_META.frozen.color }}
              />
              {ARM_META.frozen.label}
            </span>
          </div>
        </div>
      </div>

      {/* Guardrails */}
      <div className="mt-6">
        <div className="text-faint text-[10px] uppercase tracking-wide mb-2">
          Guardrails
        </div>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-sm text-muted">
          {GUARDRAILS.map((g) => (
            <li key={g} className="flex items-start gap-2">
              <span className="text-emerald mt-0.5 shrink-0">✓</span>
              <span className="leading-snug">{g}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Caveats */}
      <p className="text-xs text-faint mt-5 leading-relaxed">
        Caveats: current-index universe (survivorship bias); formulas in-sample to their
        2015 publication; research demo, not investment advice.
      </p>
    </section>
  );
}
