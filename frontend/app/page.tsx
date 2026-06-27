"use client";

import { useEffect, useState } from "react";
import { api, type Experiment } from "@/lib/api";
import { ResearchFeed } from "@/components/ResearchFeed";
import { ImprovementArc } from "@/components/ImprovementArc";
import { BasketHeatmap } from "@/components/BasketHeatmap";
import { OverfitReveal } from "@/components/OverfitReveal";
import { TradingSimulator } from "@/components/TradingSimulator";

export default function Page() {
  const [exps, setExps] = useState<Experiment[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .journal()
      .then((r) => {
        setExps(r.experiments);
        const hero = r.experiments.find((e) => e.gap > 0.5) ?? r.experiments[0];
        setSelected(hero?.iteration ?? null);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  const sel = exps.find((e) => e.iteration === selected) ?? null;
  const bestOOS = exps.reduce((m, e) => (e.accepted ? Math.max(m, e.oos_sharpe) : m), 0);
  const robustCount = exps.filter((e) => e.verdict === "ROBUST").length;

  return (
    <div className="min-h-screen">
      <header className="border-b border-line/70 bg-panel/40 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div>
            <h1 className="font-mono text-lg font-bold tracking-tight">
              QUANT RESEARCH LAB <span className="text-accent">/</span>{" "}
              <span className="text-muted">autonomous strategy discovery</span>
            </h1>
            <p className="mt-0.5 font-mono text-xs text-muted">
              the LLM proposes · the backtester disposes · the guardrail catches overfitting
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Kpi label="EXPERIMENTS" value={String(exps.length)} />
            <Kpi label="ROBUST" value={String(robustCount)} tone="robust" />
            <Kpi label="BEST OOS SHARPE" value={bestOOS.toFixed(2)} tone="accent" />
          </div>
        </div>
      </header>

      {err && (
        <p className="mx-auto max-w-7xl px-6 py-4 font-mono text-sm text-overfit">
          API error: {err} — is the backend running on :8077?
        </p>
      )}

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-5 p-6 lg:grid-cols-[1fr_1.15fr]">
        <section className="flex flex-col gap-3">
          <PanelTitle>Research Feed</PanelTitle>
          <ResearchFeed experiments={exps} selected={selected} onSelect={setSelected} />
        </section>

        <section className="flex flex-col gap-5">
          <Panel>
            <PanelTitle>
              Overfitting reveal{sel ? ` — exp #${sel.iteration} on SPY` : ""}
            </PanelTitle>
            <OverfitReveal iteration={selected} />
          </Panel>
          <Panel>
            <PanelTitle>Continual learning — best OOS Sharpe over experiments</PanelTitle>
            <ImprovementArc experiments={exps} />
          </Panel>
          {sel && (
            <Panel>
              <PanelTitle>Cross-sectional robustness — exp #{sel.iteration} across the basket</PanelTitle>
              <BasketHeatmap exp={sel} />
            </Panel>
          )}
        </section>

        <section className="lg:col-span-2">
          <Panel>
            <PanelTitle>Trading simulator — bar-by-bar replay</PanelTitle>
            <TradingSimulator />
          </Panel>
        </section>
      </main>
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: string }) {
  const c = tone === "robust" ? "text-robust" : tone === "accent" ? "text-accent" : "text-ink";
  return (
    <div className="rounded-lg border border-line bg-panel/60 px-3 py-1.5 text-right">
      <div className="font-mono text-[10px] text-muted">{label}</div>
      <div className={`font-mono text-sm font-bold ${c}`}>{value}</div>
    </div>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="rounded-xl border border-line bg-panel/50 p-4">{children}</div>;
}

function PanelTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 font-mono text-xs font-semibold uppercase tracking-wider text-muted">{children}</h2>
  );
}
