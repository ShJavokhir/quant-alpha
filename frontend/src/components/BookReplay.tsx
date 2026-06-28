import { useEffect, useMemo, useState } from "react";
import {
  ComposedChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceArea, ReferenceLine, ReferenceDot,
} from "recharts";
import type { RunData } from "../types";
import { ARM_META, CHART, familyColor, fmt, tooltipStyle } from "../lib";

interface Constituent {
  name: string; family: string; weight: number; orient: number;
  metrics: Record<string, number>;
  pnl: number[]; turn: number[];
}
interface BookData {
  names: string[]; default_book: string[] | null;
  available: { name: string; family: string; ir: number; turnover: number }[];
  weighting: "book" | "equal";
  dates: string[]; pnl: number[]; turn: number[];
  metrics: Record<string, number>;
  constituents: Constituent[];
  corr: { names: string[]; matrix: number[][] };
  avg_pair_corr: number; book_top: number; cost_bps_default: number;
}

const LEVS = [1, 2, 3, 5];
const COSTS = [{ label: "Gross", v: 0 }, { label: "1 bps", v: 1 }, { label: "5 bps", v: 5 }, { label: "10 bps", v: 10 }];
const ANN = Math.sqrt(252);
const BOOK_COL = ARM_META.adaptive.color;   // the combined book line

const money = (v: number) => {
  const a = Math.abs(v), s = v < 0 ? "-$" : "$";
  if (a >= 1e9) return `${s}${(a / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${s}${(a / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `${s}${(a / 1e3).toFixed(0)}k`;
  return `${s}${a.toFixed(0)}`;
};
const pctS = (x: number, d = 1) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(d)}%`;
const median = (xs: number[]) => {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

/** Compound a daily L/S book to an equity multiple (base 1) under leverage + cost,
 *  returning the path plus the stats that react to those controls. */
function curveStats(pnl: number[], turn: number[], lev: number, costBps: number) {
  const N = pnl.length, c = costBps / 1e4;
  const eq = new Array<number>(N), dd = new Array<number>(N), net = new Array<number>(N);
  let v = 1, pk = 1, mdd = 0;
  for (let i = 0; i < N; i++) {
    net[i] = lev * (pnl[i] - c * turn[i]);
    v = Math.max(0, v * (1 + net[i])); eq[i] = v;
    pk = Math.max(pk, v); dd[i] = v / pk - 1; mdd = Math.min(mdd, dd[i]);
  }
  const mean = net.reduce((s, x) => s + x, 0) / N || 0;
  const sd = Math.sqrt(net.reduce((s, x) => s + (x - mean) ** 2, 0) / N) || 0;
  const years = N / 252, final = eq[N - 1];
  return {
    eq, dd, final, mdd,
    totRet: final - 1,
    cagr: final > 0 ? Math.pow(final, 1 / years) - 1 : -1,
    sharpe: sd > 0 ? (ANN * mean) / sd : 0,
    vol: ANN * sd,
    turn: turn.reduce((s, x) => s + x, 0) / N,
  };
}

function corrColor(v: number) {
  const t = Math.max(-1, Math.min(1, v));
  return t >= 0
    ? `rgba(210,59,54,${(0.08 + 0.8 * t).toFixed(3)})`     // warm = positively correlated (redundant)
    : `rgba(31,127,208,${(0.08 + 0.8 * -t).toFixed(3)})`;  // cool = negatively correlated (diversifying)
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

function Stat({ label, value, accent = "text-ink", hint }:
  { label: string; value: string; accent?: string; hint?: string }) {
  return (
    <div className="bg-surface2/40 rounded-xl px-3 py-2.5 border border-border">
      <div className="text-faint text-[10px] uppercase tracking-wide truncate">{label}</div>
      <div className={`stat-num text-lg font-bold mt-0.5 ${accent}`}>{value}</div>
      {hint && <div className="text-[10px] text-faint mt-0.5 truncate">{hint}</div>}
    </div>
  );
}

/** A book-vs-single comparison bar: two stacked tracks scaled to a shared max. */
function Versus({ label, book, single, fmt: f, bookWins, note }:
  { label: string; book: number; single: number; fmt: (n: number) => string; bookWins: boolean; note: string }) {
  const max = Math.max(Math.abs(book), Math.abs(single), 1e-9);
  const bar = (v: number, col: string) => (
    <div className="h-2 rounded-full" style={{ width: `${Math.max(4, (Math.abs(v) / max) * 100)}%`, background: col }} />
  );
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] mb-1">
        <span className="text-muted">{label}</span>
        <span className={bookWins ? "text-emerald font-medium" : "text-muted"}>{note}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-16 shrink-0 text-[10px] text-faint text-right">book</span>
        {bar(book, BOOK_COL)}<span className="stat-num text-[11px] text-ink ml-1">{f(book)}</span>
      </div>
      <div className="flex items-center gap-2 mt-0.5">
        <span className="w-16 shrink-0 text-[10px] text-faint text-right">avg single</span>
        {bar(single, "#9aa4b2")}<span className="stat-num text-[11px] text-muted ml-1">{f(single)}</span>
      </div>
    </div>
  );
}

export default function BookReplay({ run }: { run: RunData }) {
  const [sel, setSel] = useState<Set<string> | null>(null);   // null until first load fills it from the agent's book
  const [touched, setTouched] = useState(false);
  const [weighting, setWeighting] = useState<"book" | "equal">("book");
  const [deposit, setDeposit] = useState(100_000);
  const [lev, setLev] = useState(1);
  const [cost, setCost] = useState(0);
  const [showCons, setShowCons] = useState(true);
  const [pickerOpen, setPickerOpen] = useState(false);

  const [data, setData] = useState<BookData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const namesParam = touched && sel ? [...sel].sort().join(",") : "";

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true); setErr(null);
    const qs = new URLSearchParams();
    if (namesParam) qs.set("names", namesParam);
    if (weighting === "equal") qs.set("weighting", "equal");
    fetch(`/api/book_replay${qs.toString() ? `?${qs}` : ""}`, { signal: ctrl.signal })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d: BookData) => {
        setData(d); setLoading(false);
        if (!touched && d.default_book) setSel(new Set(d.default_book));
      })
      .catch((e) => {
        if (e.name === "AbortError") return;
        setErr("Combined-book replay needs the backend running — start it with ./run_demo.sh.");
        setLoading(false);
      });
    return () => ctrl.abort();
  }, [namesParam, weighting]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (name: string) => {
    const base = sel ?? new Set(data?.default_book ?? []);
    const next = new Set(base);
    if (next.has(name)) next.delete(name); else next.add(name);
    if (next.size >= 2) { setSel(next); setTouched(true); }
  };
  const reset = () => { setTouched(false); setSel(new Set(data?.default_book ?? [])); };

  // ---- client-side compounding of the book + every constituent under the chosen lev/cost ----
  const calc = useMemo(() => {
    if (!data) return null;
    const book = curveStats(data.pnl, data.turn, lev, cost);
    const cons = data.constituents.map((c) => ({ c, s: curveStats(c.pnl, c.turn, lev, cost) }));
    const N = data.dates.length;
    const step = Math.max(1, Math.round(N / 520));
    const display: any[] = [];
    for (let i = 0; i < N; i += step) {
      const row: any = { di: display.length, i, date: data.dates[i], book: +(book.eq[i] * 100).toFixed(2) };
      if (showCons) for (const { c, s } of cons) row[c.name] = +(s.eq[i] * 100).toFixed(2);
      display.push(row);
    }
    const singleSharpes = cons.map((x) => x.s.sharpe);
    const cmp = {
      bestSingleSharpe: singleSharpes.length ? Math.max(...singleSharpes) : 0,
      avgSingleTurn: cons.reduce((s, x) => s + x.s.turn, 0) / (cons.length || 1),
      medSingleMDD: median(cons.map((x) => x.s.mdd)),
      avgSingleIR: cons.reduce((s, x) => s + (x.c.metrics.ic_ir || 0), 0) / (cons.length || 1),
    };
    return { book, cons, display, D: display.length, cmp };
  }, [data, lev, cost, showCons]);

  // ---- replay playhead (sweeps a marker across fully-rendered curves; cheap) ----
  const [t, setT] = useState(1e9);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const D = calc?.D ?? 0;
  const tEff = Math.min(t, Math.max(0, D - 1));
  useEffect(() => { setT(1e9); setPlaying(false); }, [data]);
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

  // correlation matrix reordered by family so redundant clusters read as blocks
  const heat = useMemo(() => {
    if (!data) return null;
    const fam = new Map(data.constituents.map((c) => [c.name, c.family]));
    const order = [...data.corr.names].sort((a, b) =>
      (fam.get(a) || "").localeCompare(fam.get(b) || "") || a.localeCompare(b));
    const idx = new Map(data.corr.names.map((n, i) => [n, i]));
    const m = order.map((a) => order.map((b) => data.corr.matrix[idx.get(a)!][idx.get(b)!]));
    return { order, m, fam };
  }, [data]);

  const regimes = useMemo(() => {
    const disp = calc?.display ?? [];
    return [{ s: "2020-01-01", e: "2020-06-01", l: "COVID" }, { s: "2022-01-01", e: "2022-10-01", l: "2022" }]
      .map((r) => ({ ...r, a: disp.find((d) => d.date >= r.s)?.di, b: [...disp].reverse().find((d) => d.date <= r.e)?.di }))
      .filter((r) => r.a != null && r.b != null);
  }, [calc]);

  if (err) return <div className="text-amber text-sm py-16 text-center">{err}</div>;
  if (!data || !calc) return <div className="text-muted text-sm py-16 text-center animate-pulse">Backtesting the book…</div>;

  const { book, cmp, display } = calc;
  const cur = display[tEff];
  const up = book.totRet >= 0;
  const m = data.metrics;
  const isDefault = !touched;
  const wByName = new Map(data.constituents.map((c) => [c.name, c.weight]));

  return (
    <div className="space-y-5 relative">
      {loading && (
        <div className="absolute -top-2 right-0 z-10 chip text-cyan animate-pulse">re-blending…</div>
      )}

      {/* ---- controls ---- */}
      <div className="flex flex-wrap items-end gap-x-5 gap-y-3">
        <div>
          <span className="text-faint text-[10px] uppercase tracking-wide block mb-1">Weighting</span>
          <Seg value={weighting} options={[{ label: "Track-record", v: "book" }, { label: "Equal", v: "equal" }]}
            onChange={(v) => setWeighting(v as "book" | "equal")} />
        </div>
        <label className="block">
          <span className="text-faint text-[10px] uppercase tracking-wide">Initial deposit</span>
          <div className="mt-1 flex items-center bg-surface2 border border-border rounded-lg px-3 py-2 w-36">
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
        <label className="flex items-center gap-2 text-xs text-muted cursor-pointer pb-2">
          <input type="checkbox" checked={showCons} onChange={(e) => setShowCons(e.target.checked)} className="accent-cyan" />
          show constituents
        </label>
      </div>

      {/* ---- constituent basket (editable) ---- */}
      <div className="bg-surface2/40 border border-border rounded-xl">
        <button onClick={() => setPickerOpen((o) => !o)}
          className="w-full flex items-center justify-between gap-2 px-4 py-2.5 text-left">
          <span className="text-sm font-semibold text-ink">
            Book constituents · <span className="text-cyan">{data.names.length}</span> alphas
            {isDefault
              ? <span className="text-muted font-normal"> · the agent's traded book (top {data.book_top} by track record)</span>
              : <span className="text-amber font-normal"> · custom basket (edited)</span>}
          </span>
          <span className="flex items-center gap-3 shrink-0">
            {!isDefault && (
              <span onClick={(e) => { e.stopPropagation(); reset(); }}
                className="text-xs text-cyan hover:underline">reset to agent's book</span>
            )}
            <span className="text-muted text-xs">{pickerOpen ? "▲ hide" : "▼ edit"}</span>
          </span>
        </button>
        {pickerOpen && (
          <div className="px-4 pb-3 pt-1 border-t border-border grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
            {[...data.available]
              .sort((a, b) => (a.family.localeCompare(b.family) || b.ir - a.ir))
              .map((a) => {
                const on = (sel ?? new Set(data.default_book ?? [])).has(a.name);
                const w = wByName.get(a.name);
                return (
                  <button key={a.name} onClick={() => toggle(a.name)}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded-lg border text-left transition ${
                      on ? "border-border bg-surface2" : "border-transparent opacity-45 hover:opacity-80"}`}>
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: familyColor(a.family) }} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-mono text-ink truncate">{a.name}</span>
                      <span className="block text-[10px] text-faint">IR {fmt(a.ir)} · {on && w != null ? `${(w * 100).toFixed(1)}% wt` : "off"}</span>
                    </span>
                  </button>
                );
              })}
          </div>
        )}
      </div>

      {/* ---- stat strip: combined book, with 'vs single' context ---- */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
        <Stat label="Final value" value={money(deposit * book.final)} accent={up ? "text-emerald" : "text-rose"}
          hint={`from ${money(deposit)}`} />
        <Stat label="Total return" value={pctS(book.totRet, 0)} accent={up ? "text-emerald" : "text-rose"}
          hint={`${lev}× · ${cost === 0 ? "gross" : cost + "bps"}`} />
        <Stat label="CAGR" value={pctS(book.cagr)} accent={book.cagr >= 0 ? "text-emerald" : "text-rose"} />
        <Stat label="Max drawdown" value={pctS(book.mdd)} accent="text-rose"
          hint={`single med ${pctS(cmp.medSingleMDD)}`} />
        <Stat label="Sharpe" value={fmt(book.sharpe)} accent={book.sharpe >= 1 ? "text-emerald" : "text-ink"}
          hint={`best single ${fmt(cmp.bestSingleSharpe)}`} />
        <Stat label="IC-IR" value={fmt(m.ic_ir)} accent={m.ic_ir >= 1 ? "text-emerald" : "text-ink"}
          hint={`avg single ${fmt(cmp.avgSingleIR)}`} />
        <Stat label="Turnover" value={fmt(book.turn)} accent="text-ink"
          hint={`avg single ${fmt(cmp.avgSingleTurn)}`} />
        <Stat label="Avg pair corr" value={fmt(data.avg_pair_corr)} accent="text-ink" hint="lower = diversified" />
      </div>

      {/* ---- equity hero: book over the cloud of its constituents ---- */}
      <div>
        <div className="flex items-baseline justify-between flex-wrap gap-2 mb-1">
          <h3 className="text-base font-semibold text-ink">
            The book vs its parts <span className="text-muted font-normal">· base 100 · {lev}× {cost === 0 ? "gross" : `· ${cost} bps`}</span>
          </h3>
          <div className="flex items-center gap-3 text-xs">
            <span className="inline-flex items-center gap-1"><span className="inline-block w-4 h-[3px]" style={{ background: BOOK_COL }} /> <span className="text-ink font-medium">combined book</span></span>
            {showCons && <span className="inline-flex items-center gap-1 text-muted"><span className="inline-block w-4 h-px bg-muted" /> {data.names.length} single alphas</span>}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={display} margin={{ top: 6, right: 14, bottom: 0, left: 2 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" vertical={false} />
            {regimes.map((r, i) => r.a! <= tEff && (
              <ReferenceArea key={i} x1={r.a} x2={Math.min(r.b!, tEff)} fill={CHART.regimeFill} fillOpacity={0.05}
                label={{ value: r.l, position: "insideTop", fill: CHART.regimeLabel, fontSize: 9 }} />
            ))}
            <ReferenceLine y={100} stroke={CHART.refLine} strokeDasharray="4 4" />
            <XAxis dataKey="di" type="number" domain={[0, D - 1]} hide />
            <YAxis stroke={CHART.axis} fontSize={11} width={42} domain={["auto", "auto"]} />
            <Tooltip contentStyle={tooltipStyle} labelFormatter={() => ""}
              content={({ active, payload }: any) => {
                if (!active || !payload?.length) return null;
                const row = payload[0]?.payload;
                const b = row?.book;
                return (
                  <div style={tooltipStyle as any} className="px-2.5 py-1.5">
                    <div className="text-[11px] text-muted">{row?.date}</div>
                    <div className="text-sm font-semibold" style={{ color: BOOK_COL }}>book {fmt(b, 1)}</div>
                  </div>
                );
              }} />
            {showCons && data.constituents.map((c) => (
              <Line key={c.name} type="monotone" dataKey={c.name} stroke={familyColor(c.family)} strokeWidth={1}
                strokeOpacity={0.16} dot={false} isAnimationActive={false} legendType="none" />
            ))}
            <Line type="monotone" dataKey="book" stroke={BOOK_COL} strokeWidth={2.6} dot={false} isAnimationActive={false} />
            <ReferenceLine x={tEff} stroke={BOOK_COL} strokeOpacity={0.4} strokeDasharray="3 3" />
            {cur && <ReferenceDot x={tEff} y={cur.book} ifOverflow="extendDomain" shape={(p: any) => (
              <g><circle cx={p.cx} cy={p.cy} r={3.5} fill={BOOK_COL} stroke="#ffffff" strokeWidth={1.5} />
                <circle cx={p.cx} cy={p.cy} fill="none" stroke={BOOK_COL} strokeWidth={1.3}>
                  <animate attributeName="r" values="4;11;4" dur="2.2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.7;0;0.7" dur="2.2s" repeatCount="indefinite" /></circle></g>
            )} />}
          </ComposedChart>
        </ResponsiveContainer>

        {/* replay bar */}
        <div className="flex items-center gap-4 mt-1">
          <button onClick={() => { if (tEff >= D - 1) setT(0); setPlaying(!playing); }}
            className="shrink-0 w-9 h-9 bg-cyan text-white grid place-items-center hover:bg-cyan/90 transition">
            {playing
              ? <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="2" width="4" height="12" rx="1" /><rect x="9" y="2" width="4" height="12" rx="1" /></svg>
              : <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2.5v11l9-5.5z" /></svg>}
          </button>
          <div className="flex-1">
            <div className="flex justify-between text-xs text-muted mb-1">
              <span>{playing ? <span className="text-cyan">▮ replaying</span> : "Scrub the book through time"}</span>
              <span className="font-mono text-cyan">{cur?.date} · {money(deposit * (cur?.book ?? 100) / 100)}</span>
            </div>
            <input type="range" min={0} max={Math.max(0, D - 1)} value={tEff}
              onChange={(e) => { setPlaying(false); setT(Number(e.target.value)); }}
              className="w-full accent-cyan cursor-pointer" />
          </div>
          <Seg value={speed} options={[0.5, 1, 2]} onChange={setSpeed} fmt={(v) => `${v}×`} />
        </div>
      </div>

      {/* ---- diversification: why blending wins + correlation heatmap ---- */}
      <div className="grid lg:grid-cols-2 gap-5">
        <div className="card p-4 space-y-3">
          <h3 className="text-base font-semibold text-ink">Why blending wins</h3>
          <Versus label="Turnover (cost drag)" book={book.turn} single={cmp.avgSingleTurn} fmt={(n) => fmt(n)}
            bookWins={book.turn < cmp.avgSingleTurn}
            note={book.turn < cmp.avgSingleTurn ? `${Math.round((1 - book.turn / (cmp.avgSingleTurn || 1)) * 100)}% lower` : ""} />
          <Versus label="Signal quality (IC-IR)" book={m.ic_ir} single={cmp.avgSingleIR} fmt={(n) => fmt(n)}
            bookWins={m.ic_ir > cmp.avgSingleIR}
            note={m.ic_ir > cmp.avgSingleIR ? "above the average alpha" : ""} />
          <Versus label="Max drawdown (depth)" book={Math.abs(book.mdd)} single={Math.abs(cmp.medSingleMDD)} fmt={(n) => pctS(-n)}
            bookWins={Math.abs(book.mdd) < Math.abs(cmp.medSingleMDD)}
            note={Math.abs(book.mdd) < Math.abs(cmp.medSingleMDD) ? "shallower than the median alpha" : ""} />
          <p className="text-[11px] text-faint leading-relaxed pt-1">
            The book ranks each name across stocks, flips signs so every alpha points the same way, weights by
            track-record ÷ turnover, sums, and smooths — the engine's exact recipe. Netting offsetting trades is
            why book turnover lands well below the average single alpha.
          </p>
        </div>

        <div className="card p-4">
          <div className="flex items-baseline justify-between gap-2 mb-2">
            <h3 className="text-base font-semibold text-ink">Constituent correlation</h3>
            <span className="text-xs text-muted">avg pair <span className="stat-num text-ink">{fmt(data.avg_pair_corr)}</span></span>
          </div>
          {heat && (
            <div className="flex flex-col items-center">
              <div className="grid gap-[1px] w-full max-w-[360px]"
                style={{ gridTemplateColumns: `repeat(${heat.order.length}, 1fr)` }}>
                {heat.m.map((rowv, i) => rowv.map((v, j) => (
                  <div key={`${i}-${j}`} title={`${heat.order[i]} × ${heat.order[j]}: ${fmt(v)}`}
                    className="aspect-square" style={{ background: i === j ? "#cbd2dc" : corrColor(v) }} />
                )))}
              </div>
              <div className="flex items-center gap-3 mt-2 text-[10px] text-faint">
                <span className="inline-flex items-center gap-1"><span className="w-3 h-3" style={{ background: corrColor(0.7) }} /> redundant (+)</span>
                <span className="inline-flex items-center gap-1"><span className="w-3 h-3" style={{ background: corrColor(0) }} /> independent (0)</span>
                <span className="inline-flex items-center gap-1"><span className="w-3 h-3" style={{ background: corrColor(-0.7) }} /> hedging (–)</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <p className="text-xs text-faint leading-relaxed">
        Honest framing: this is the <span className="text-muted">real combined book</span> — a dollar-neutral, unit-gross blend of the
        selected alphas over {run.meta.timeline.first}–{run.meta.timeline.last}, costs and leverage applied to the realised backtest.
        Combining lifts signal quality and cuts turnover versus any single alpha, but
        <span className="text-muted"> net of {data.cost_bps_default} bps it's still the hard frontier</span> — the win here is risk-adjusted
        signal and diversification, not a free lunch.
      </p>
    </div>
  );
}
