"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  createSeriesMarkers,
  ColorType,
  type Time,
  type IChartApi,
} from "lightweight-charts";
import { api, type SimulateResponse } from "@/lib/api";

const TEMPLATES = ["sma_crossover", "rsi_reversion", "multi_filter"];
const TICKERS = ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "JPM", "XOM", "JNJ", "WMT", "KO", "PG", "HD", "DIS"];

export function TradingSimulator() {
  const elRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [ticker, setTicker] = useState("AAPL");
  const [template, setTemplate] = useState("rsi_reversion");
  const [data, setData] = useState<SimulateResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setErr(null);
    api.simulate(ticker, template, 5).then(setData).catch((e) => setErr(String(e)));
  }, [ticker, template]);

  useEffect(() => {
    if (!data || !elRef.current) return;
    const el = elRef.current;
    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8a97a8",
        fontFamily: "var(--font-geist-mono), monospace",
      },
      grid: { vertLines: { color: "rgba(31,41,55,0.4)" }, horzLines: { color: "rgba(31,41,55,0.4)" } },
      rightPriceScale: { borderColor: "#1f2937" },
      timeScale: { borderColor: "#1f2937", timeVisible: false },
      width: el.clientWidth || 700,
      height: 360,
    });
    chartRef.current = chart;

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399",
      downColor: "#f87171",
      borderVisible: false,
      wickUpColor: "#34d399",
      wickDownColor: "#f87171",
    });
    candle.setData(
      data.candles.map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close }))
    );

    createSeriesMarkers(
      candle,
      data.trades.map((t) => ({
        time: t.time as Time,
        position: t.type === "entry" ? ("belowBar" as const) : ("aboveBar" as const),
        color: t.type === "entry" ? "#34d399" : "#f87171",
        shape: t.type === "entry" ? ("arrowUp" as const) : ("arrowDown" as const),
        text: t.type === "entry" ? "BUY" : "SELL",
      }))
    );

    chart.timeScale().fitContent();
    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data]);

  const replay = () => {
    const chart = chartRef.current;
    if (!chart || !data) return;
    if (timerRef.current) clearInterval(timerRef.current);
    const n = data.candles.length;
    const win = Math.max(45, Math.floor(n / 6));
    let i = 0;
    chart.timeScale().setVisibleLogicalRange({ from: 0, to: win });
    timerRef.current = setInterval(() => {
      i += Math.max(1, Math.floor(n / 130));
      if (i + win >= n) {
        chart.timeScale().fitContent();
        if (timerRef.current) clearInterval(timerRef.current);
        return;
      }
      chart.timeScale().setVisibleLogicalRange({ from: i, to: i + win });
    }, 40);
  };

  const m = data?.metrics ?? {};
  const fmt = (v: number | null | undefined, suffix = "") =>
    v === null || v === undefined ? "—" : `${v.toFixed(2)}${suffix}`;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Select label="ticker" value={ticker} onChange={setTicker} options={TICKERS} />
        <Select label="strategy" value={template} onChange={setTemplate} options={TEMPLATES} />
        <button
          onClick={replay}
          className="rounded-md border border-accent/50 bg-accent/10 px-3 py-1 font-mono text-xs font-semibold text-accent transition hover:bg-accent/20"
        >
          ▶ Replay
        </button>
        <div className="ml-auto flex items-center gap-3 font-mono text-[11px] text-muted">
          <span className="text-robust">▲ BUY</span>
          <span className="text-overfit">▼ SELL</span>
        </div>
      </div>

      {err && <p className="font-mono text-xs text-overfit">simulate API: {err}</p>}

      <div ref={elRef} className="w-full" style={{ height: 360 }} />

      {data && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Metric label="Sharpe" value={fmt(m["Sharpe"])} tone={(m["Sharpe"] ?? 0) > 0 ? "robust" : "overfit"} />
          <Metric label="Max DD" value={fmt(m["Max Drawdown %"], "%")} tone="overfit" />
          <Metric label="Win Rate" value={fmt(m["Win Rate %"], "%")} />
          <Metric label="Total Ret" value={fmt(m["Total Return %"], "%")} tone="robust" />
          <Metric label="Trades" value={m["Trades"] != null ? String(m["Trades"]) : "—"} />
        </div>
      )}
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <label className="flex items-center gap-1.5 font-mono text-xs text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-line bg-panel px-2 py-1 font-mono text-xs text-ink outline-none focus:border-accent"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  const c = tone === "robust" ? "text-robust" : tone === "overfit" ? "text-overfit" : "text-ink";
  return (
    <div className="rounded-lg border border-line bg-panel/50 px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`font-mono text-sm font-bold ${c}`}>{value}</div>
    </div>
  );
}
