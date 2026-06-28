"use client";

import { useEffect, useState } from "react";
import { api, type HoldoutResponse } from "@/lib/api";
import { VerdictBadge } from "./VerdictBadge";

function Row({ role, family, value, verdict, extra }: { role: string; family: string; value: number | null; verdict: string; extra?: string }) {
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="w-16 font-mono text-[10px] uppercase text-muted">{role}</span>
      <span className="w-28 font-mono text-xs text-ink">{family}</span>
      <span className={`w-14 font-mono text-xs font-bold ${(value ?? 0) > 0 ? "text-robust" : "text-overfit"}`}>
        {value === null ? "—" : value.toFixed(2)}
      </span>
      <VerdictBadge verdict={verdict} />
      {extra && <span className="font-mono text-[10px] text-muted">{extra}</span>}
    </div>
  );
}

function DecadeSpark({ table }: { table: Record<string, number> }) {
  const entries = Object.entries(table);
  if (!entries.length) return null;
  const W = 220, H = 40, pad = 4;
  const vals = entries.map(([, v]) => v);
  const lo = Math.min(0, ...vals), hi = Math.max(0.4, ...vals);
  const x = (i: number) => pad + (W - 2 * pad) * (i / Math.max(1, entries.length - 1));
  const y = (v: number) => H - pad - (H - 2 * pad) * ((v - lo) / (hi - lo));
  const path = entries.map(([, v], i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxWidth: 220 }}>
      <line x1={pad} x2={W - pad} y1={y(0)} y2={y(0)} stroke="var(--color-line)" strokeDasharray="2 2" />
      <path d={path} fill="none" stroke="var(--color-fragile)" strokeWidth={1.5} />
      {entries.map(([, v], i) => (
        <circle key={i} cx={x(i)} cy={y(v)} r={2} fill={v > 0.2 ? "var(--color-robust)" : v > 0 ? "var(--color-fragile)" : "var(--color-overfit)"} />
      ))}
    </svg>
  );
}

export function Holdout() {
  const [data, setData] = useState<HoldoutResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.holdout().then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="font-mono text-xs text-overfit">holdout API: {err}</p>;
  if (!data) return <p className="font-mono text-xs text-muted">loading holdout…</p>;

  const oot = data.out_of_time, ooa = data.out_of_asset;
  const decades = Object.entries(oot.winner.decade.by_decade);

  return (
    <div className="space-y-3">
      <p className="font-mono text-[11px] leading-relaxed text-muted">{data.headline}</p>

      <div>
        <div className="mb-1 font-mono text-[11px] font-semibold text-accent">
          OUT-OF-TIME · sealed tail {data.tail_from}→now (the harder regime axis)
        </div>
        <Row role="trusted" family={oot.winner.family} value={oot.winner.sealed_tail.appraisal} verdict={oot.winner.sealed_tail.verdict} extra="positive, decayed" />
        <Row role="rejected" family={oot.rejected.family} value={oot.rejected.sealed_tail.appraisal} verdict={oot.rejected.sealed_tail.verdict} extra="fails" />
        <div className="mt-1 flex items-center gap-3">
          <DecadeSpark table={oot.winner.decade.by_decade} />
          <span className="font-mono text-[10px] text-muted">
            persistent sign, decaying magnitude
            <br />
            {decades[0]?.[0]} {decades[0]?.[1].toFixed(2)} → {decades.at(-1)?.[0]} {decades.at(-1)?.[1].toFixed(2)}
          </span>
        </div>
      </div>

      <div>
        <div className="mb-1 font-mono text-[11px] font-semibold text-accent">
          OUT-OF-ASSET · names never searched: {data.held_names.join(", ")}
        </div>
        <Row role="trusted" family={ooa.winner.family} value={ooa.winner.appraisal} verdict={ooa.winner.verdict} extra={`${ooa.winner.n_names_positive}/${data.held_names.length} names +`} />
        <Row role="rejected" family={ooa.rejected.family} value={ooa.rejected.appraisal} verdict={ooa.rejected.verdict} extra={`${ooa.rejected.n_names_positive}/${data.held_names.length} names +`} />
      </div>

      <p className="border-t border-line pt-2 font-mono text-[10px] leading-relaxed text-muted">
        Sealed &amp; declared in advance — winner/rejected committed from pre-cutoff evidence before either
        slice was opened, opened once. buy&amp;hold tail Sharpe {data.benchmark_tail_sharpe?.toFixed(2)}.
      </p>
    </div>
  );
}
