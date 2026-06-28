import { useEffect, useState } from "react";
import type { RunData } from "./types";
import { loadRun } from "./lib";
import Header from "./components/Header";
import Hero from "./components/Hero";
import TimelineScrubber from "./components/TimelineScrubber";
import LiveSimDeck from "./components/LiveSimDeck";
import FleetViz from "./components/FleetViz";
import ResearchFeed from "./components/ResearchFeed";
import ImprovementChart from "./components/ImprovementChart";
import LearningChart from "./components/LearningChart";
import HonestyPanel from "./components/HonestyPanel";
import AlphaModal from "./components/AlphaModal";
import LivePropose from "./components/LivePropose";
import AntigravityLab from "./components/AntigravityLab";

export default function App() {
  const [run, setRun] = useState<RunData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [gen, setGen] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [alpha, setAlpha] = useState<string | null>(null);

  useEffect(() => {
    loadRun().then((r) => {
      setRun(r);
      setGen(Math.max(0, r.generations.length - 1));
    }).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <Centered>Failed to load run data: {err}</Centered>;
  if (!run) return <Centered><span className="animate-pulse text-cyan">Loading the lab…</span></Centered>;
  if (!run.generations.length) return <Centered>Run has no generations.</Centered>;

  const curGen = run.generations[Math.min(gen, run.generations.length - 1)];

  return (
    <div className="min-h-screen">
      <Header meta={run.meta} />
      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 pb-24 space-y-6">
        <Hero run={run} />

        <section className="space-y-3">
          <SectionLabel n="01" title="Watch it evolve"
            sub="A walk-forward backtest, one unseen block at a time. Hit play: the HUD tracks signal quality and discoveries live, the book trades each block, and the fleet breeds and culls." />
          <TimelineScrubber generations={run.generations} value={gen} onChange={setGen}
            playing={playing} setPlaying={setPlaying} />
          <LiveSimDeck run={run} gen={curGen.g} playing={playing} />
          <div className="grid lg:grid-cols-5 gap-6">
            <div className="lg:col-span-3"><FleetViz gen={curGen} onSelectAlpha={setAlpha} /></div>
            <div className="lg:col-span-2">
              <ResearchFeed generations={run.generations} selectedGen={curGen.g} onSelectAlpha={setAlpha} />
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <SectionLabel n="02" title="Proof it's improving"
            sub="Two honest, controlled views: the fleet adapts out-of-sample, and the researcher itself learns." />
          <div className="grid lg:grid-cols-2 gap-6">
            <ImprovementChart run={run} />
            <LearningChart run={run} />
          </div>
        </section>

        <section className="space-y-3">
          <SectionLabel n="03" title="See it research — live"
            sub="Two ways to watch the agent work in real time: instant Gemini proposals, and the Antigravity managed agent researching in an isolated environment." />
          <div className="grid lg:grid-cols-2 gap-6">
            <AntigravityLab />
            <LivePropose />
          </div>
        </section>

        <section className="space-y-3">
          <SectionLabel n="04" title="Why you can trust it"
            sub="Engineered against the ways backtests fool you." />
          <HonestyPanel run={run} />
        </section>
      </main>

      <footer className="border-t border-border py-8 text-center text-xs text-faint">
        DARWIN · self-evolving alpha research · {run.meta.n_stocks} stocks ·{" "}
        {run.meta.timeline.first}–{run.meta.timeline.last} · research demo, not investment advice
      </footer>

      <AlphaModal name={alpha} onClose={() => setAlpha(null)} />
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen grid place-items-center text-muted">{children}</div>;
}

function SectionLabel({ n, title, sub }: { n: string; title: string; sub: string }) {
  return (
    <div className="flex items-baseline gap-3 pt-4">
      <span className="text-xs font-mono text-cyan/70">{n}</span>
      <div>
        <h2 className="text-xl font-semibold text-ink tracking-tight">{title}</h2>
        <p className="text-sm text-muted">{sub}</p>
      </div>
    </div>
  );
}
