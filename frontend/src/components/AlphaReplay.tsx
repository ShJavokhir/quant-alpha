import { memo, useEffect, useMemo, useRef, useState } from "react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceArea, ReferenceLine, ReferenceDot,
} from "recharts";
import type { RunData } from "../types";
import { familyColor, fmt } from "../lib";
import BookReplay from "./BookReplay";

interface ReplayData {
  name: string;
  info: { formula: string; family: string; rationale?: string; source: string; source_url?: string; source_title?: string };
  dates: string[]; pnl: number[]; turn: number[];
  metrics: Record<string, number>;
  candidates: { symbol: string; contrib: number; episodes: number }[];
  series: { symbol: string; price: (number | null)[]; episodes: { dir: number; start: number; end: number }[] };
  cost_bps_default: number;
}

const LEVS = [1, 2, 3, 5, 10];
const COSTS = [{ label: "Gross", v: 0 }, { label: "1 bps", v: 1 }, { label: "5 bps", v: 5 }, { label: "10 bps", v: 10 }];
const ANN = Math.sqrt(252);

const money = (v: number) => {
  const a = Math.abs(v), s = v < 0 ? "-$" : "$";
  if (a >= 1e9) return `${s}${(a / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${s}${(a / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `${s}${(a / 1e3).toFixed(0)}k`;
  return `${s}${a.toFixed(0)}`;
};
const moneyFull = (v: number) => `$${Math.round(v).toLocaleString()}`;
const pctS = (x: number, d = 1) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(d)}%`;

function buildCatalog(run: RunData) {
  const map = new Map<string, { name: string; family: string; source: string }>();
  for (const g of run.generations) {
    for (const m of g.fleet) if (!map.has(m.name)) map.set(m.name, { name: m.name, family: m.family, source: m.source });
    for (const b of g.births) if (!map.has(b.name)) map.set(b.name, { name: b.name, family: b.family, source: b.source });
  }
  return [...map.values()].sort((a, b) =>
    a.family !== b.family ? a.family.localeCompare(b.family) : a.name.localeCompare(b.name));
}

function Seg<T extends string | number>({ value, options, onChange, fmt: f }:
  { value: T; options: { label: string; v: T }[] | T[]; onChange: (v: T) => void; fmt?: (v: T) => string }) {
  const opts = (options as any[]).map((o) => (typeof o === "object" ? o : { label: f ? f(o) : String(o), v: o }));
  return (
    <div className="flex gap-1 bg-surface2 border border-border p-1">
      {opts.map((o) => (
        <button key={String(o.v)} onClick={() => onChange(o.v)}
          className={`px-2.5 py-1 text-xs font-medium transition ${
            value === o.v ? "bg-cyan/12 text-cyan" : "text-muted hover:text-ink"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Stat({ label, value, accent = "text-ink", hint }: { label: string; value: string; accent?: string; hint?: string }) {
  return (
    <div className="bg-surface2/40 rounded-xl px-3 py-2.5 border border-border">
      <div className="text-faint text-[10px] uppercase tracking-wide truncate">{label}</div>
      <div className={`stat-num text-lg font-bold mt-0.5 ${accent}`}>{value}</div>
      {hint && <div className="text-[10px] text-faint mt-0.5 truncate">{hint}</div>}
    </div>
  );
}

const Tri = (p: any, dir: number) => (dir > 0
  ? <path d={`M${p.cx} ${p.cy - 9} L${p.cx - 5.5} ${p.cy - 1} L${p.cx + 5.5} ${p.cy - 1} Z`} fill="#07875a" stroke="#ffffff" strokeWidth={0.8} />
  : <path d={`M${p.cx} ${p.cy + 9} L${p.cx - 5.5} ${p.cy + 1} L${p.cx + 5.5} ${p.cy + 1} Z`} fill="#d23b36" stroke="#ffffff" strokeWidth={0.8} />);

/** Representative name's price with the alpha's conviction long/short episodes.
 *  We window the daily data ourselves (zoom presets + a scroll slider) so only
 *  in-window entries render, at exact daily positions — no recharts edge-clamping.
 *  Memoised so the equity replay sweep never forces it to re-render. */
const NameChart = memo(function NameChart({ data, onSymbol }: { data: ReplayData; onSymbol: (s: string) => void }) {
  const N = data.dates.length;
  const full = useMemo(() => data.dates.map((d, i) => ({ i, date: d, price: data.series.price[i] })), [data]);
  const eps = useMemo(() => data.series.episodes.map((e) => ({
    dir: e.dir, s: e.start, e: e.end, price: data.series.price[e.start],
  })).filter((x) => x.price != null), [data]);

  const [len, setLen] = useState(505);                    // window length (trading days)
  const [pos, setPos] = useState(Math.max(0, N - 505));   // window start index (scroll)
  useEffect(() => { setLen(505); setPos(Math.max(0, N - 505)); }, [data, N]);
  const zoom = (d: number) => { setLen(d); setPos(Math.max(0, N - d)); };

  const maxPos = Math.max(0, N - len);
  const startI = Math.min(pos, maxPos);
  const endI = Math.min(N - 1, startI + len - 1);
  const visible = full.slice(startI, endI + 1);
  const epiVis = eps.filter((x) => x.e >= startI && x.s <= endI).map((x) => ({
    dir: x.dir, x1: data.dates[Math.max(x.s, startI)], x2: data.dates[Math.min(x.e, endI)],
    mx: x.s >= startI && x.s <= endI ? data.dates[x.s] : null, price: x.price,
  }));
  const inView = epiVis.filter((e) => e.mx).length;
  const PRESETS: [string, number][] = [["6M", 126], ["1Y", 252], ["2Y", 505], ["5Y", 1260], ["All", N]];

  return (
    <div>
      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <h3 className="text-base font-semibold text-ink">
          One name in the book · <span className="font-mono text-cyan">{data.series.symbol}</span>
          <span className="text-muted font-normal text-sm"> · {inView} entries in view</span>
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs inline-flex items-center gap-1 text-muted"><span className="text-emerald">▲</span> long</span>
          <span className="text-xs inline-flex items-center gap-1 text-muted"><span className="text-rose">▼</span> short</span>
          <div className="flex gap-1 bg-surface2 border border-border p-1">
            {PRESETS.map(([l, d]) => (
              <button key={l} onClick={() => zoom(d)}
                className={`px-2 py-1 text-[11px] font-medium transition ${
                  len === d ? "bg-cyan/12 text-cyan" : "text-muted hover:text-ink"}`}>{l}</button>
            ))}
          </div>
          {data.candidates.length > 0 && (
            <select value={data.series.symbol} onChange={(e) => onSymbol(e.target.value)}
              className="bg-surface2 border border-border rounded-lg px-2 py-1 text-xs text-ink font-mono focus:outline-none focus:ring-1 focus:ring-cyan">
              {data.candidates.map((c) => <option key={c.symbol} value={c.symbol}>{c.symbol} · {c.episodes} trades</option>)}
            </select>
          )}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={252}>
        <ComposedChart data={visible} margin={{ top: 10, right: 14, bottom: 0, left: 4 }}>
          <CartesianGrid stroke="#e7eaef" strokeDasharray="3 3" vertical={false} />
          {epiVis.map((e, i) => (
            <ReferenceArea key={i} x1={e.x1} x2={e.x2} fill={e.dir > 0 ? "#07875a" : "#d23b36"} fillOpacity={0.12} />
          ))}
          <XAxis dataKey="date" stroke="#8b95a4" fontSize={10} minTickGap={44}
            tickFormatter={(d) => String(d).slice(0, 7)} />
          <YAxis stroke="#8b95a4" fontSize={11} width={52} domain={["auto", "auto"]} tickFormatter={(v) => `$${v}`} />
          <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e7eaef", borderRadius: 0 }}
            labelFormatter={(d) => d} formatter={(v: any) => [`$${fmt(v)}`, data.series.symbol]} />
          <Line type="monotone" dataKey="price" stroke="#334155" strokeWidth={1.7} dot={false} connectNulls isAnimationActive={false} />
          {epiVis.filter((e) => e.mx).map((e, i) => (
            <ReferenceDot key={`m${i}`} x={e.mx as string} y={e.price as number} shape={(p: any) => Tri(p, e.dir)} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-3 mt-1.5">
        <span className="text-[10px] font-mono text-faint w-[68px] shrink-0">{visible[0]?.date}</span>
        <input type="range" min={0} max={maxPos} value={startI} disabled={maxPos === 0}
          onChange={(e) => setPos(Number(e.target.value))} aria-label="Scroll the price window"
          className="flex-1 accent-cyan cursor-pointer disabled:opacity-40" />
        <span className="text-[10px] font-mono text-faint w-[68px] shrink-0 text-right">{visible[visible.length - 1]?.date}</span>
      </div>
    </div>
  );
});

export default function AlphaReplay({ run, selected, onSelect }:
  { run: RunData; selected: string | null; onSelect: (n: string) => void }) {
  const catalog = useMemo(() => buildCatalog(run), [run]);
  const families = useMemo(() => [...new Set(catalog.map((c) => c.family))], [catalog]);
  const name = selected ?? "alpha005";

  const [tab, setTab] = useState<"single" | "book">("single");
  const [deposit, setDeposit] = useState(100_000);
  const [lev, setLev] = useState(3);
  const [cost, setCost] = useState(0);
  const [symbol, setSymbol] = useState<string | undefined>(undefined);
  const [data, setData] = useState<ReplayData | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [t, setT] = useState(1e9);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  // reset name-specific bits when the alpha changes
  const prevName = useRef(name);
  useEffect(() => {
    if (prevName.current !== name) { prevName.current = name; setSymbol(undefined); setData(null); }
  }, [name]);

  useEffect(() => {
    if (tab !== "single") return;
    const ctrl = new AbortController();
    setLoading(true); setErr(null);
    const url = `/api/alpha_replay/${name}` + (symbol ? `?symbol=${encodeURIComponent(symbol)}` : "");
    fetch(url, { signal: ctrl.signal })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d: ReplayData) => {
        setData(d); setLoading(false); setT(1e9); setPlaying(false);
        if (symbol === undefined) setSymbol(d.series.symbol);
      })
      .catch((e) => {
        if (e.name === "AbortError") return;
        setErr("Strategy Replay needs the backend running — start it with ./run_demo.sh.");
        setLoading(false);
      });
    return () => ctrl.abort();
  }, [name, symbol, tab]);

  // compound daily (accurate), then downsample to ~520 pts for snappy rendering / replay
  const { display, stats, D } = useMemo(() => {
    if (!data) return { display: [] as any[], stats: null as any, D: 0 };
    const N = data.dates.length, c = cost / 1e4;
    const net = new Array(N), eq = new Array(N), dd = new Array(N);
    let v = deposit, pk = deposit, mdd = 0;
    for (let i = 0; i < N; i++) {
      net[i] = lev * (data.pnl[i] - c * data.turn[i]);
      v = Math.max(0, v * (1 + net[i])); eq[i] = v;       // floor at 0 (wipeout, not negative)
      pk = Math.max(pk, v); dd[i] = v / pk - 1; mdd = Math.min(mdd, dd[i]);
    }
    const mean = net.reduce((s, x) => s + x, 0) / N;
    const sd = Math.sqrt(net.reduce((s, x) => s + (x - mean) ** 2, 0) / N) || 0;
    const years = N / 252, final = eq[N - 1];
    const stats = {
      final, totRet: final / deposit - 1,
      cagr: final > 0 ? Math.pow(final / deposit, 1 / years) - 1 : -1,
      mdd, sharpe: sd > 0 ? (ANN * mean) / sd : 0, vol: ANN * sd,
      win: net.filter((x) => x > 0).length / N,
      turn: data.turn.reduce((s, x) => s + x, 0) / N,
      episodes: data.series.episodes.length,
    };
    const step = Math.max(1, Math.round(N / 520));
    const display: any[] = [];
    const push = (i: number, hi: number) => {
      let wdd = dd[i];                                    // worst drawdown in the window so troughs survive sampling
      for (let j = i + 1; j < hi; j++) if (dd[j] < wdd) wdd = dd[j];
      display.push({ di: display.length, i, date: data.dates[i], equity: eq[i],
        price: data.series.price[i], dd: wdd });
    };
    for (let i = 0; i < N; i += step) push(i, Math.min(i + step, N));
    if ((N - 1) % step !== 0) push(N - 1, N);
    return { display, stats, D: display.length };
  }, [data, deposit, lev, cost]);

  const tEff = Math.min(t, Math.max(0, D - 1));

  // replay sweep: animate t across the whole timeline over ~14s (speed-scaled)
  useEffect(() => {
    if (!playing || D < 2) return;
    const dur = 14000 / speed, t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / dur);
      setT(Math.round(p * (D - 1)));
      if (p < 1) raf = requestAnimationFrame(tick); else setPlaying(false);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, D]);

  const view = display.slice(0, tEff + 1);
  const cur = display[tEff];
  const regimes = useMemo(() => ([
    { s: "2020-01-01", e: "2020-06-01", l: "COVID" }, { s: "2022-01-01", e: "2022-10-01", l: "2022" },
  ].map((r) => ({ ...r, a: display.find((d) => d.date >= r.s)?.di, b: [...display].reverse().find((d) => d.date <= r.e)?.di }))
    .filter((r) => r.a != null && r.b != null)), [display]);

  const up = stats && stats.totRet >= 0;
  const sel = catalog.find((c) => c.name === name);

  return (
    <div className="card p-5 space-y-5">
      <div className="flex items-center gap-1 bg-surface2 border border-border p-1 w-fit">
        {([["single", "Single alpha"], ["book", "Combined book"]] as const).map(([v, label]) => (
          <button key={v} onClick={() => setTab(v)}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              tab === v ? "bg-cyan/12 text-cyan" : "text-muted hover:text-ink"}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === "book" ? <BookReplay run={run} /> : (<>
      {/* ---- controls ---- */}
      <div className="flex flex-wrap items-end gap-x-5 gap-y-3">
        <label className="block">
          <span className="text-faint text-[10px] uppercase tracking-wide">Strategy</span>
          <select value={name} onChange={(e) => onSelect(e.target.value)}
            className="mt-1 block w-60 bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-ink
                       font-mono focus:outline-none focus:ring-1 focus:ring-cyan">
            {families.map((f) => (
              <optgroup key={f} label={f}>
                {catalog.filter((c) => c.family === f).map((c) => (
                  <option key={c.name} value={c.name}>{c.name} · {c.source}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-faint text-[10px] uppercase tracking-wide">Initial deposit</span>
          <div className="mt-1 flex items-center bg-surface2 border border-border rounded-lg px-3 py-2 w-40">
            <span className="text-muted text-sm mr-1">$</span>
            <input type="number" min={1000} step={1000} value={deposit}
              onChange={(e) => setDeposit(Math.max(1000, Number(e.target.value) || 0))}
              className="bg-transparent text-sm text-ink w-full focus:outline-none stat-num" />
          </div>
        </label>
        <div>
          <span className="text-faint text-[10px] uppercase tracking-wide block mb-1">Leverage</span>
          <Seg value={lev} options={LEVS} onChange={setLev} fmt={(v) => `${v}×`} />
        </div>
        <div>
          <span className="text-faint text-[10px] uppercase tracking-wide block mb-1">Trading cost</span>
          <Seg value={cost} options={COSTS} onChange={setCost} />
        </div>
      </div>

      {/* selected formula + provenance */}
      {sel && (
        <div className="flex items-center flex-wrap gap-2 text-xs">
          <span className="chip" style={{ color: familyColor(sel.family) }}>{sel.family}</span>
          {data?.info?.source === "antigravity" && <span className="chip text-violet">🛰 Antigravity</span>}
          {data?.info?.formula && (
            <code className="font-mono text-cyan/90 bg-surface2/60 rounded px-2 py-1 truncate max-w-full">
              {data.info.formula}
            </code>
          )}
        </div>
      )}

      {err && <div className="text-amber text-sm py-6 text-center">{err}</div>}
      {loading && !data && <div className="text-muted text-sm py-16 text-center animate-pulse">Backtesting {name}…</div>}

      {data && stats && (
        <>
          {/* ---- stat strip ---- */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
            <Stat label="Final value" value={money(stats.final)} accent={up ? "text-emerald" : "text-rose"}
              hint={`from ${money(deposit)}`} />
            <Stat label="Total return" value={pctS(stats.totRet, 0)} accent={up ? "text-emerald" : "text-rose"}
              hint={`${lev}× · ${cost === 0 ? "gross" : cost + "bps"}`} />
            <Stat label="CAGR" value={pctS(stats.cagr)} accent={stats.cagr >= 0 ? "text-emerald" : "text-rose"} />
            <Stat label="Max drawdown" value={pctS(stats.mdd)} accent="text-rose" />
            <Stat label="Sharpe" value={fmt(stats.sharpe)} accent={stats.sharpe >= 1 ? "text-emerald" : "text-ink"}
              hint={cost === 0 ? "gross" : "net of cost"} />
            <Stat label="Ann. vol" value={pctS(stats.vol, 0).replace("+", "")} hint="annualized" />
            <Stat label="Win days" value={`${Math.round(stats.win * 100)}%`} hint={`turn ${fmt(stats.turn)}`} />
          </div>

          {/* ---- equity hero ---- */}
          <div>
            <div className="flex items-baseline justify-between flex-wrap gap-2 mb-1">
              <h3 className="text-base font-semibold text-ink">Portfolio equity
                <span className="text-muted font-normal"> · {moneyFull(deposit)} at {lev}× {cost === 0 ? "(gross)" : `· ${cost} bps`}</span>
              </h3>
              {cur && <span className="text-sm font-mono" style={{ color: up ? "#07875a" : "#d23b36" }}>
                {cur.date} · {money(cur.equity)}</span>}
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={view} margin={{ top: 6, right: 14, bottom: 0, left: 4 }}>
                <defs>
                  <linearGradient id="eqfill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={up ? "#07875a" : "#d23b36"} stopOpacity={0.32} />
                    <stop offset="100%" stopColor={up ? "#07875a" : "#d23b36"} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#e7eaef" strokeDasharray="3 3" vertical={false} />
                {regimes.map((r, i) => r.a! <= tEff && (
                  <ReferenceArea key={i} x1={r.a} x2={Math.min(r.b!, tEff)} fill="#d23b36" fillOpacity={0.05}
                    label={{ value: r.l, position: "insideTop", fill: "#d23b36", fontSize: 9 }} />
                ))}
                <ReferenceLine y={deposit} stroke="#c7cdd8" strokeDasharray="4 4" strokeOpacity={0.8} />
                <XAxis dataKey="di" type="number" domain={[0, D - 1]} hide />
                <YAxis tickFormatter={money} stroke="#8b95a4" fontSize={11} width={52} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e7eaef", borderRadius: 0 }}
                  labelFormatter={(d) => display[d]?.date ?? ""} formatter={(v: any) => [moneyFull(v), "Equity"]} />
                <Area type="monotone" dataKey="equity" stroke={up ? "#07875a" : "#d23b36"} strokeWidth={2.4}
                  fill="url(#eqfill)" dot={false} isAnimationActive={false} />
                {cur && <ReferenceDot x={tEff} y={cur.equity} ifOverflow="extendDomain" shape={(p: any) => (
                  <g><circle cx={p.cx} cy={p.cy} r={3.5} fill={up ? "#07875a" : "#d23b36"} stroke="#ffffff" strokeWidth={1.5} />
                    <circle cx={p.cx} cy={p.cy} fill="none" stroke={up ? "#07875a" : "#d23b36"} strokeWidth={1.3}>
                      <animate attributeName="r" values="4;11;4" dur="2.2s" repeatCount="indefinite" />
                      <animate attributeName="opacity" values="0.7;0;0.7" dur="2.2s" repeatCount="indefinite" /></circle></g>
                )} />}
              </ComposedChart>
            </ResponsiveContainer>
            {/* underwater */}
            <ResponsiveContainer width="100%" height={66}>
              <ComposedChart data={view} margin={{ top: 2, right: 14, bottom: 0, left: 4 }}>
                <defs>
                  <linearGradient id="ddfill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#d23b36" stopOpacity={0} />
                    <stop offset="100%" stopColor="#d23b36" stopOpacity={0.4} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="di" type="number" domain={[0, D - 1]}
                  stroke="#8b95a4" fontSize={10} tickFormatter={(d) => display[d]?.date?.slice(0, 4) ?? ""} />
                <YAxis tickFormatter={(v) => `${Math.round(v * 100)}%`} stroke="#8b95a4" fontSize={10} width={52} />
                <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e7eaef", borderRadius: 0 }}
                  labelFormatter={(d) => display[d]?.date ?? ""} formatter={(v: any) => [`${(v * 100).toFixed(1)}%`, "Drawdown"]} />
                <Area type="monotone" dataKey="dd" stroke="#d23b36" strokeWidth={1.2} fill="url(#ddfill)"
                  dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* ---- replay bar ---- */}
          <div className="flex items-center gap-4">
            <button onClick={() => { if (tEff >= D - 1) setT(0); setPlaying(!playing); }}
              className="shrink-0 w-10 h-10 bg-cyan text-white grid place-items-center hover:bg-cyan/90 transition">
              {playing
                ? <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="2" width="4" height="12" rx="1" /><rect x="9" y="2" width="4" height="12" rx="1" /></svg>
                : <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2.5v11l9-5.5z" /></svg>}
            </button>
            <div className="flex-1">
              <div className="flex justify-between text-xs text-muted mb-1">
                <span>{playing ? <span className="text-cyan">▮ replaying</span> : "Replay the trade"}</span>
                <span className="font-mono text-cyan">{cur?.date}</span>
              </div>
              <input type="range" min={0} max={Math.max(0, D - 1)} value={tEff}
                onChange={(e) => { setPlaying(false); setT(Number(e.target.value)); }}
                className="w-full accent-cyan cursor-pointer" />
            </div>
            <Seg value={speed} options={[0.5, 1, 2]} onChange={setSpeed} fmt={(v) => `${v}×`} />
          </div>

          {/* ---- representative name: buy/sell (full daily res + zoom/scroll) ---- */}
          <NameChart data={data} onSymbol={setSymbol} />

          <p className="text-xs text-faint leading-relaxed">
            Honest framing: this is a <span className="text-muted">dollar-neutral, unit-gross cross-sectional book</span> —
            each day it longs the top-decile names and shorts the bottom decile, rebalanced daily, scaled to {lev}× gross.
            The equity is the whole book from your deposit; the lower chart shows just <span className="font-mono">{data.series.symbol}</span>'s
            price — green where the alpha held it long, red where short, ▲/▼ at conviction entries. Costs ({cost === 0 ? "off" : `${cost} bps`}) and leverage are applied to the realised backtest, not assumed.
          </p>
        </>
      )}
      </>)}
    </div>
  );
}
