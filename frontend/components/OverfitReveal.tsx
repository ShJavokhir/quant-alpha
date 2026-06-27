"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  AreaSeries,
  LineSeries,
  createSeriesMarkers,
  ColorType,
  type Time,
} from "lightweight-charts";
import { api, type OverfitResponse } from "@/lib/api";

export function OverfitReveal({ iteration, ticker = "SPY" }: { iteration: number | null; ticker?: string }) {
  const elRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<OverfitResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (iteration == null) return;
    setData(null);
    setErr(null);
    api.overfit(iteration, ticker).then(setData).catch((e) => setErr(String(e)));
  }, [iteration, ticker]);

  useEffect(() => {
    if (!data || !elRef.current) return;
    const el = elRef.current;
    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8a97a8",
        fontFamily: "var(--font-geist-mono), monospace",
      },
      grid: {
        vertLines: { color: "rgba(31,41,55,0.45)" },
        horzLines: { color: "rgba(31,41,55,0.45)" },
      },
      rightPriceScale: { borderColor: "#1f2937" },
      timeScale: { borderColor: "#1f2937" },
      width: el.clientWidth || 600,
      height: 320,
    });

    const isData = data.is.curve.map((p) => ({ time: p.time as Time, value: p.value }));
    const factor = isData.length ? isData[isData.length - 1].value : 1;
    const oosData = data.oos.curve.map((p) => ({ time: p.time as Time, value: p.value * factor }));
    const benchData = data.benchmark_oos.map((p) => ({ time: p.time as Time, value: p.value * factor }));

    const isSeries = chart.addSeries(AreaSeries, {
      lineColor: "#34d399",
      topColor: "rgba(52,211,153,0.28)",
      bottomColor: "rgba(52,211,153,0)",
      lineWidth: 2,
      priceLineVisible: false,
    });
    isSeries.setData(isData);

    const oosSeries = chart.addSeries(AreaSeries, {
      lineColor: "#f87171",
      topColor: "rgba(248,113,113,0.22)",
      bottomColor: "rgba(248,113,113,0)",
      lineWidth: 2,
      priceLineVisible: false,
    });
    oosSeries.setData(oosData);

    const benchSeries = chart.addSeries(LineSeries, {
      color: "rgba(138,151,168,0.55)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });
    benchSeries.setData(benchData);

    if (oosData.length) {
      createSeriesMarkers(isSeries, [
        { time: oosData[0].time, position: "aboveBar", color: "#38bdf8", shape: "arrowDown", text: "OOS begins" },
      ]);
    }
    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [data]);

  const overfit = (data?.gap ?? 0) > 0.5;

  return (
    <div>
      {err && <p className="font-mono text-xs text-overfit">overfit API: {err}</p>}
      {data && (
        <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-xs">
          <span className="text-muted">
            {ticker} · {data.template}
          </span>
          <span className="text-robust">IN-SAMPLE Sharpe {data.is.sharpe?.toFixed(2)}</span>
          <span className="text-overfit">OUT-OF-SAMPLE Sharpe {data.oos.sharpe?.toFixed(2)}</span>
          <span
            className={`ml-auto rounded px-2 py-0.5 font-bold ${
              overfit ? "bg-overfit/15 text-overfit" : "bg-robust/15 text-robust"
            }`}
          >
            {overfit ? `OVERFIT · gap ${data.gap?.toFixed(2)}` : `HOLDS · gap ${data.gap?.toFixed(2)}`}
          </span>
        </div>
      )}
      <div ref={elRef} className="w-full" style={{ height: 320 }} />
      {data && (
        <p className="mt-2 font-mono text-[11px] leading-relaxed text-muted">
          Green = the optimizer&apos;s fitted in-sample window (params chosen here). Red = the very next
          out-of-sample window, same params. Dashed grey = buy &amp; hold over OOS.
        </p>
      )}
    </div>
  );
}
