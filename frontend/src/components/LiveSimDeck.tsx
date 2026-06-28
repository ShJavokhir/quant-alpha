import { useEffect, useMemo, useRef, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ReferenceArea, ReferenceLine, ReferenceDot, Legend,
} from "recharts";
import type { RunData } from "../types";
import { ARM_META, equityCurves, fmt } from "../lib";

/** Tween a number from its current displayed value to `target` (ease-out cubic).
 *  Re-runs whenever the generation changes, so the HUD ticks like a live tape. */
function useTween(target: number, ms = 650) {
  const [v, setV] = useState(target);
  const vRef = useRef(target); vRef.current = v;
  const raf = useRef(0);
  useEffect(() => {
    const a = vRef.current, b = target, start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const e = 1 - Math.pow(1 - t, 3);
      setV(a + (b - a) * e);
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [target, ms]);
  return v;
}

function Spark({ data, color, w = 92, h = 30 }: { data: number[]; color: string; w?: number; h?: number }) {
  if (data.length < 2) return <svg width={w} height={h} />;
  const min = Math.min(...data), max = Math.max(...data);
  const span = max - min || 1;
  const xy = data.map((val, i) => {
    const x = (i / (data.length - 1)) * (w - 3) + 1.5;
    const y = h - 3 - ((val - min) / span) * (h - 6);
    return [x, y] as const;
  });
  const pts = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const [lx, ly] = xy[xy.length - 1];
  const area = `${pts} ${(w - 1.5).toFixed(1)},${h} 1.5,${h}`;
  return (
    <svg width={w} height={h} className="overflow-visible shrink-0">
      <polyline points={area} fill={color} fillOpacity={0.08} stroke="none" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5}
        strokeLinejoin="round" strokeLinecap="round" opacity={0.92} />
      <circle cx={lx} cy={ly} r={2.3} fill={color} />
    </svg>
  );
}

interface TileDef {
  label: string; color: string; sub: string; goodUp: boolean;
  history: number[]; format: (n: number) => string;
}

function Tile({ def, idx }: { def: TileDef; idx: number }) {
  const target = def.history[idx] ?? 0;
  const v = useTween(target);
  const prev = def.history[Math.max(0, idx - 1)] ?? target;
  const delta = target - prev;
  const show = Math.abs(delta) > 1e-6 && idx > 0;
  const up = delta > 0;
  const good = up === def.goodUp;
  return (
    <div className="card p-4 relative overflow-hidden">
      <div className="text-faint text-[10px] tracking-wide uppercase truncate">{def.label}</div>
      <div className="flex items-end justify-between gap-2 mt-2">
        <div>
          <div className="stat-num text-[26px] leading-none font-bold" style={{ color: def.color }}>
            {def.format(v)}
          </div>
          {show && (
            <div className={`text-[11px] mt-1.5 font-medium ${good ? "text-emerald" : "text-rose"}`}>
              {up ? "▲" : "▼"} {def.format(Math.abs(delta))}
            </div>
          )}
        </div>
        <Spark data={def.history.slice(0, idx + 1)} color={def.color} />
      </div>
      <div className="text-[11px] text-muted mt-2 leading-snug">{def.sub}</div>
    </div>
  );
}

type Mode = "net" | "gross";

function EquityPanel({ run, gen }: { run: RunData; gen: number }) {
  const [mode, setMode] = useState<Mode>("net");
  const all = useMemo(() => equityCurves(run), [run]);
  const aKey = mode === "net" ? "adaptive_net" : "adaptive_gross";
  const fKey = mode === "net" ? "frozen_net" : "frozen_gross";
  const idx = Math.min(gen, all.length - 1);
  const data = all.slice(0, idx + 1);
  const cur = all[idx];

  const domain = useMemo(() => {
    const vals = all.flatMap((r) => [r[aKey], r[fKey]]);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.1 || 2;
    return [Math.floor(lo - pad), Math.ceil(hi + pad)];
  }, [all, aKey, fKey]);

  const regimes = useMemo(() => ([
    { start: "2020-01-01", end: "2020-06-01", label: "COVID" },
    { start: "2022-01-01", end: "2022-10-01", label: "2022 bear" },
  ].map((r) => {
    const x1 = all.find((d) => d.date >= r.start)?.g;
    const x2 = [...all].reverse().find((d) => d.date <= r.end)?.g;
    return { ...r, x1, x2 };
  }).filter((r) => r.x1 != null && r.x2 != null)), [all]);

  const aCol = ARM_META.adaptive.color, fCol = ARM_META.frozen.color;
  const leads = cur && cur[aKey] >= cur[fKey];

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between flex-wrap gap-2 mb-2">
        <div>
          <h3 className="text-base font-semibold text-ink">The book, traded block by block</h3>
          <p className="text-sm text-muted">Cumulative equity (base 100), compounded from each unseen
            block's realised return. Secondary view — net P&amp;L is the hard frontier.</p>
        </div>
        <div className="flex gap-1 bg-surface2 rounded-lg p-1 shrink-0">
          {(["net", "gross"] as Mode[]).map((m) => (
            <button key={m} onClick={() => setMode(m)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                mode === m ? "bg-cyan/15 text-cyan" : "text-muted hover:text-ink"}`}>
              {m === "net" ? "Net of 10bps" : "Gross"}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={210}>
        <LineChart data={data} margin={{ top: 6, right: 14, bottom: 0, left: -14 }}>
          <CartesianGrid stroke="#1e2740" strokeDasharray="3 3" vertical={false} />
          {regimes.map((r, i) => r.x1! <= idx && (
            <ReferenceArea key={i} x1={r.x1} x2={Math.min(r.x2!, idx)} fill="#fb7185" fillOpacity={0.06}
              label={{ value: r.label, position: "insideTop", fill: "#fb7185", fontSize: 9 }} />
          ))}
          <ReferenceLine y={100} stroke="#3a4658" strokeOpacity={0.7} strokeDasharray="4 4" />
          <XAxis dataKey="g" type="number" domain={[0, all.length - 1]} allowDecimals={false}
            stroke="#5a6477" fontSize={11}
            tickFormatter={(g) => all[g]?.date?.slice(0, 7) ?? g} />
          <YAxis domain={domain} stroke="#5a6477" fontSize={11} width={46} />
          <Tooltip contentStyle={{ background: "#0e1320", border: "1px solid #1e2740", borderRadius: 10 }}
            labelFormatter={(g) => `Gen ${g} · ${all[g]?.date ?? ""}`}
            formatter={(v: any, n: any) => [v, n === aKey ? "Agent" : "Frozen"]} />
          <Legend formatter={(v) => (v === aKey ? "Agent (memory ON)" : "Frozen fleet")}
            wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey={fKey} stroke={fCol} strokeWidth={1.8}
            strokeDasharray="7 5" dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey={aKey} stroke={aCol} strokeWidth={2.6}
            dot={false} isAnimationActive={false} />
          {cur && (
            <ReferenceDot x={idx} y={cur[aKey]} ifOverflow="extendDomain"
              shape={(p: any) => (
                <g>
                  <circle cx={p.cx} cy={p.cy} r={3.5} fill={aCol} stroke="#06080d" strokeWidth={1.5} />
                  <circle cx={p.cx} cy={p.cy} fill="none" stroke={aCol} strokeWidth={1.4}>
                    <animate attributeName="r" values="4;11;4" dur="2.2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.7;0;0.7" dur="2.2s" repeatCount="indefinite" />
                  </circle>
                </g>
              )} />
          )}
        </LineChart>
      </ResponsiveContainer>

      {cur && (
        <div className="text-xs text-muted mt-1">
          At {cur.date}: <span style={{ color: aCol }} className="font-semibold">agent {fmt(cur[aKey], 1)}</span>{" "}
          vs <span style={{ color: fCol }} className="font-semibold">frozen {fmt(cur[fKey], 1)}</span>
          {mode === "net" && !leads && (
            <span className="text-faint"> · net edge is razor-thin — the agent's win is signal quality &amp; discovery, above.</span>
          )}
        </div>
      )}
    </div>
  );
}

export default function LiveSimDeck({ run, gen, playing }:
  { run: RunData; gen: number; playing: boolean }) {
  const gens = run.generations;
  const idx = Math.min(gen, gens.length - 1);

  const tiles: TileDef[] = useMemo(() => {
    let keep = 0, acc = 0, prop = 0, irSum = 0;
    const keepers = gens.map((g) => (keep += g.n_accepted));
    const irRoll = gens.map((g, i) => ((irSum += g.book_test.ic_ir), irSum / (i + 1)));
    const hitCum = gens.map((g) => ((acc += g.n_accepted), (prop += g.n_proposed), prop ? acc / prop : 0));
    return [
      { label: "Signal quality · IC-IR", color: "#22d3ee", goodUp: true,
        history: irRoll, format: (n) => n.toFixed(2),
        sub: "rank-IC info ratio · rolling avg (≥1 is strong)" },
      { label: "Keepers discovered", color: "#a78bfa", goodUp: true,
        history: keepers, format: (n) => Math.round(n).toString(),
        sub: "alphas that survived selection (cumulative)" },
      { label: "Live fleet", color: "#34d399", goodUp: true,
        history: gens.map((g) => g.fleet_size), format: (n) => Math.round(n).toString(),
        sub: "alphas trading this block" },
      { label: "Hit rate", color: "#38bdf8", goodUp: true,
        history: hitCum, format: (n) => `${Math.round(n * 100)}%`,
        sub: "proposals admitted · cumulative" },
      { label: "Turnover", color: "#fbbf24", goodUp: false,
        history: gens.map((g) => g.book_test.turnover), format: (n) => n.toFixed(2),
        sub: "daily name turnover · lower = cheaper" },
    ];
  }, [gens]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="chip text-cyan">
          <span className="relative flex h-1.5 w-1.5">
            {playing && <span className="animate-pulse-ring absolute inline-flex h-full w-full rounded-full bg-cyan" />}
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-cyan" />
          </span>
          {playing ? "SIMULATING" : "WALK-FORWARD"}
        </span>
        <span className="text-xs text-muted">Live signal &amp; discovery as the agent steps through {gens.length} unseen blocks</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {tiles.map((def) => <Tile key={def.label} def={def} idx={idx} />)}
      </div>

      <EquityPanel run={run} gen={idx} />
    </div>
  );
}
