import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { familyColor, fmt } from "../lib";

interface AgAlpha {
  name: string; family: string; formula: string; rationale?: string;
  source_title?: string; source_url?: string;
  steps?: { n_steps: number; kinds: string[] };
  environment_id?: string; interaction_id?: string;
  ok?: boolean; ic_ir?: number; appraisal?: number; sharpe_net?: number;
  turnover?: number; verdict?: string; error?: string;
}

interface AgStep { type: string; detail: string }

interface JobStatus {
  job_id: string;
  status: "starting" | "running" | "completed" | "failed";
  phase: number; elapsed: number; n_steps: number;
  env_id?: string | null; interaction_id?: string | null;
  steps: AgStep[]; alpha?: AgAlpha | null; error?: string | null;
}

const verdictColor: Record<string, string> = {
  promising: "#34d399", weak: "#fbbf24", invalid: "#fb7185",
};

const PHASES = [
  { key: "shell", label: "Shell", blurb: "isolated environment" },
  { key: "browser", label: "Browser", blurb: "reading the literature" },
  { key: "editor", label: "Editor", blurb: "writing & running code" },
  { key: "backtest", label: "Backtest", blurb: "DSL → backtest" },
] as const;

// ---- ambient choreography (illustrates each phase; real numbers come from the agent) ----
const BOOT = [
  "$ antigravity provision --remote",
  "✓ sandbox up · ubuntu 24.04 · python 3.12",
  "✓ tools: web.browse · shell.run · fs",
  "✓ egress allow-list: ssrn · arxiv · quantpedia",
];
const PAPERS = [
  { src: "SSRN", t: "Liquidity and asset prices (Amihud 2002)" },
  { src: "arXiv", t: "Idiosyncratic volatility & the cross-section" },
  { src: "Quantpedia", t: "Short-term reversal in US equities" },
  { src: "JFE", t: "Volume-synchronized informed trading (VPIN)" },
];
const CODE = `import numpy as np, pandas as pd

def signal(df):            # daily OHLCV only, cross-sectional
    illiq = (df.close.pct_change().abs()
             / (df.dollar_vol)).rolling(21).mean()
    mom   = df.close.pct_change(63)
    return rank(mom) * rank(-illiq)   # liquidity-tilted momentum

assert np.isfinite(signal(sample)).mean() > 0.99`;

// deterministic-ish upward walk for the illustrative equity curve
function walk(seed: number, n: number, drift: number): number[] {
  let s = (seed >>> 0) || 1;
  const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  const raw: number[] = []; let v = 0;
  for (let i = 0; i < n; i++) { v += drift + (rnd() - 0.5); raw.push(v); }
  const mn = Math.min(...raw), mx = Math.max(...raw), span = mx - mn || 1;
  return raw.map((p) => (p - mn) / span);
}

function stepColor(type: string): string {
  const t = type.toLowerCase();
  if (/(browse|search|web|http|fetch|read)/.test(t)) return "#38bdf8";
  if (/(code|exec|python|shell|run|script)/.test(t)) return "#a78bfa";
  if (/(backtest|dsl|eval|sharpe)/.test(t)) return "#34d399";
  if (/(reason|think|plan)/.test(t)) return "#fbbf24";
  return "#5a6477";
}

export default function AntigravityLab() {
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [alpha, setAlpha] = useState<AgAlpha | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [, force] = useState(0);                    // animation heartbeat

  const startRef = useRef(0);
  const jobRef = useRef<string | null>(null);
  const phaseStart = useRef<Record<number, number>>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const animRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stop() {
    if (pollRef.current) clearInterval(pollRef.current);
    if (animRef.current) clearInterval(animRef.current);
    pollRef.current = animRef.current = null;
  }
  useEffect(() => () => stop(), []);

  async function run() {
    stop();
    setRunning(true); setErr(null); setAlpha(null); setStatus(null);
    startRef.current = Date.now(); phaseStart.current = {}; jobRef.current = null;
    try {
      const r = await fetch("/api/antigravity_research/start", { method: "POST" });
      const d = await r.json();
      if (!d.ok || !d.job_id) throw new Error("no job");
      jobRef.current = d.job_id;
    } catch {
      setRunning(false);
      setErr("Live Antigravity needs the backend running (./run_demo.sh). It spins up a real Google-hosted agent (~1 min).");
      return;
    }
    animRef.current = setInterval(() => force((x) => x + 1), 280);
    pollRef.current = setInterval(poll, 1200);
    poll();
  }

  async function poll() {
    const id = jobRef.current;
    if (!id) return;
    try {
      const r = await fetch(`/api/antigravity_research/status/${id}`);
      if (!r.ok) return;
      const d: JobStatus = await r.json();
      setStatus(d);
      if (d.status === "completed") {
        setAlpha(d.alpha || null); setRunning(false); stop(); force((x) => x + 1);
      } else if (d.status === "failed") {
        setErr(d.error || "Antigravity returned no result."); setRunning(false); stop();
      }
    } catch { /* transient — keep polling */ }
  }

  const completed = status?.status === "completed";
  const elapsed = startRef.current && (running || completed)
    ? (Date.now() - startRef.current) / 1000 : 0;

  // effective phase: backend telemetry, floored by elapsed so panes never look frozen,
  // but never claim "backtest" before the agent actually reports it / completes.
  const floor = elapsed > 16 ? 2 : elapsed > 5 ? 1 : 0;
  let effPhase = Math.max(status?.phase ?? 0, floor);
  if (!completed && (status?.phase ?? 0) < 3) effPhase = Math.min(effPhase, 2);
  if (completed) effPhase = 3;

  // stamp when each phase first became active (for typing reveals)
  if (running || completed) {
    if (phaseStart.current[effPhase] == null) phaseStart.current[effPhase] = Date.now();
  }
  const sincePhase = (p: number) =>
    phaseStart.current[p] ? (Date.now() - phaseStart.current[p]) / 1000 : 0;

  const steps = status?.steps ?? [];
  const realBrowse = steps.filter((s) => /(browse|search|web|http|read|url)/i.test(s.type + s.detail)
    && s.detail).slice(-4);

  const seed = useMemo(
    () => (status?.job_id || "ag").split("").reduce((a, c) => (a * 33 + c.charCodeAt(0)) >>> 0, 7),
    [status?.job_id]);
  const drift = alpha ? Math.max(-0.1, Math.min(0.55, 0.18 + (alpha.sharpe_net ?? 0.6) * 0.18)) : 0.22;
  const idle = !running && !completed && !err;

  return (
    <div className="card p-5 relative overflow-hidden">
      <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, rgba(167,139,250,0.18), transparent 70%)" }} />

      {/* header */}
      <div className="flex items-center justify-between gap-3 flex-wrap relative">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold text-ink">🛰 Antigravity research — live</h3>
            <span className="chip text-violet">Gemini managed agent</span>
          </div>
          <p className="text-sm text-muted mt-0.5 max-w-xl">
            One API call spins up an <span className="text-ink">isolated Google-hosted Linux box</span>;
            watch it browse the literature, run code, and hand back a <span className="text-ink">cited</span>{" "}
            alpha — backtested on the spot.</p>
        </div>
        <button onClick={run} disabled={running}
          className="shrink-0 px-4 py-2 rounded-xl bg-violet/15 text-violet font-medium text-sm
                     hover:bg-violet/25 transition disabled:opacity-50"
          style={{ boxShadow: "0 0 30px -8px rgba(167,139,250,0.5)" }}>
          {running ? "researching…" : alpha ? "🛰 Research again" : "🛰 Research live"}
        </button>
      </div>

      {err && <div className="text-xs text-amber mt-3">{err}</div>}

      {/* ---------------- the machine screen ---------------- */}
      {(running || completed) && (
        <div className="mt-4 rounded-2xl border border-border overflow-hidden"
          style={{ background: "linear-gradient(180deg,#080b12,#0b1018)" }}>
          {/* title bar */}
          <div className="flex items-center gap-3 px-3 py-2 border-b border-border bg-black/30">
            <div className="flex gap-1.5">
              <span className="w-3 h-3 rounded-full bg-rose/70" />
              <span className="w-3 h-3 rounded-full bg-amber/70" />
              <span className="w-3 h-3 rounded-full bg-emerald/70" />
            </div>
            <span className="font-mono text-[11px] text-muted truncate">
              antigravity-preview-05-2026
            </span>
            <span className="chip text-[10px] text-faint font-mono">
              env {status?.env_id ? status.env_id.slice(0, 8) + "…" : "provisioning…"}
            </span>
            <div className="ml-auto flex items-center gap-2 text-[11px] font-mono">
              <span className={`w-2 h-2 rounded-full ${completed ? "bg-emerald" : "bg-violet animate-pulse"}`} />
              <span className={completed ? "text-emerald" : "text-violet"}>
                {completed ? "done" : "live"}
              </span>
              <span className="text-faint tabular-nums">{elapsed.toFixed(0)}s</span>
              <span className="text-faint">· step {status?.n_steps ?? 0}</span>
            </div>
          </div>

          <div className="grid grid-cols-[150px_1fr]">
            {/* left rail — REAL agent steps streaming in */}
            <div className="border-r border-border p-2.5 bg-black/20 min-h-[300px]">
              <div className="text-[10px] uppercase tracking-wide text-faint mb-2">
                agent steps · {status?.n_steps ?? 0}
              </div>
              <div className="space-y-1.5">
                <AnimatePresence initial={false}>
                  {steps.slice(-9).map((s, i) => (
                    <motion.div key={`${s.type}-${steps.length - 9 + i}`}
                      initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
                      className="flex items-start gap-1.5 text-[10px] leading-tight">
                      <span className="mt-1 w-1.5 h-1.5 rounded-full shrink-0"
                        style={{ background: stepColor(s.type) }} />
                      <div className="min-w-0">
                        <div className="font-mono text-ink/90 truncate">{s.type}</div>
                        {s.detail && <div className="text-faint truncate">{s.detail}</div>}
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
                {!steps.length && (
                  <div className="text-[10px] text-faint font-mono flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-violet animate-pulse" />
                    awaiting telemetry…
                  </div>
                )}
              </div>
            </div>

            {/* main stage — four windows that light up by phase */}
            <div className="p-3 space-y-2.5">
              <Win idx={0} eff={effPhase} done={effPhase > 0}>
                <pre className="font-mono text-[11px] leading-relaxed text-emerald/90 whitespace-pre-wrap">
                  {BOOT.slice(0, Math.min(BOOT.length, 1 + Math.floor(sincePhase(0) / 0.6))).join("\n")}
                  {status?.env_id && effPhase >= 0 && (
                    <span className="text-faint">{"\n"}env {status.env_id.slice(0, 12)}… ready</span>
                  )}
                  {effPhase === 0 && <span className="animate-caret text-emerald">▋</span>}
                </pre>
              </Win>

              <Win idx={1} eff={effPhase} done={effPhase > 1}>
                <div className="space-y-1.5">
                  {(realBrowse.length
                    ? realBrowse.map((s) => ({ src: "web", t: s.detail }))
                    : PAPERS.slice(0, 1 + Math.floor(sincePhase(1) / 1.1))
                  ).map((p, i) => (
                    <div key={i} className="flex items-center gap-2 text-[11px]">
                      <span className="chip text-[9px] text-sky px-1.5 py-0">{p.src}</span>
                      <span className="text-ink/80 truncate font-mono">{p.t}</span>
                      {effPhase === 1 && i === 0 && (
                        <span className="ml-auto text-[9px] text-faint">GET…</span>
                      )}
                    </div>
                  ))}
                </div>
              </Win>

              <Win idx={2} eff={effPhase} done={effPhase > 2}>
                <pre className="font-mono text-[10.5px] leading-snug text-cyan/90 whitespace-pre-wrap">
                  {effPhase < 2 ? "" : CODE.slice(0, Math.min(CODE.length, Math.floor(sincePhase(2) * 60)))}
                  {effPhase === 2 && <span className="animate-caret text-cyan">▋</span>}
                  {effPhase > 2 && (
                    <span className="text-emerald">{"\n$ python sanity.py  →  finite 99.4% · cross-sectional ✓"}</span>
                  )}
                </pre>
              </Win>

              <Win idx={3} eff={effPhase} done={completed}>
                <div className="flex items-center gap-3">
                  <Equity seed={seed} drift={drift}
                    progress={completed ? 1 : Math.min(0.92, sincePhase(3) / 7)} />
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] font-mono">
                    <Metric label="IC-IR" v={alpha ? fmt(alpha.ic_ir) : "···"} />
                    <Metric label="appraisal" v={alpha ? fmt(alpha.appraisal) : "···"} />
                    <Metric label="net Sharpe" v={alpha ? fmt(alpha.sharpe_net) : "···"} />
                    <Metric label="turnover" v={alpha ? fmt(alpha.turnover) : "···"} />
                  </div>
                </div>
              </Win>
            </div>
          </div>

          {/* honesty footnote */}
          <div className="px-3 py-1.5 border-t border-border text-[10px] text-faint">
            env id, step count & metrics are live telemetry from the agent · panes illustrate each phase
          </div>
        </div>
      )}

      {/* ---------------- result card ---------------- */}
      <AnimatePresence>
        {alpha && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="mt-4 bg-surface2/50 rounded-xl p-4 border border-border">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: familyColor(alpha.family) }} />
              <span className="font-mono text-sm text-ink">{alpha.name}</span>
              <span className="chip text-[10px]" style={{ color: familyColor(alpha.family) }}>{alpha.family}</span>
              <span className="ml-auto text-xs font-semibold"
                style={{ color: verdictColor[alpha.verdict || "weak"] }}>{alpha.verdict}</span>
            </div>
            <pre className="text-xs font-mono text-cyan whitespace-pre-wrap break-words">{alpha.formula}</pre>
            {alpha.rationale && <p className="text-xs text-muted mt-1.5">{alpha.rationale}</p>}
            {alpha.ok && (
              <div className="text-xs text-muted mt-2 flex gap-3 flex-wrap">
                <span>IC-IR <span className="text-ink">{fmt(alpha.ic_ir)}</span></span>
                <span>appraisal <span className="text-ink">{fmt(alpha.appraisal)}</span></span>
                <span>net Sharpe <span className="text-ink">{fmt(alpha.sharpe_net)}</span></span>
                <span>turnover <span className="text-ink">{fmt(alpha.turnover)}</span></span>
              </div>
            )}
            <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border text-[11px] text-faint flex-wrap">
              {alpha.steps && <span className="chip text-violet">🛰 {alpha.steps.n_steps} agent steps</span>}
              {alpha.environment_id && (
                <span className="font-mono">env {alpha.environment_id.slice(0, 8)}…</span>)}
              {alpha.source_url && (
                <a href={alpha.source_url} target="_blank" rel="noreferrer"
                  className="text-cyan hover:underline truncate max-w-[60%]">
                  🔗 {alpha.source_title || alpha.source_url}</a>)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {idle && !alpha && (
        <p className="text-[11px] text-faint mt-3">
          Hit <span className="text-violet">Research live</span> to watch the managed agent work in its own sandbox.
        </p>
      )}
    </div>
  );
}

// a single "window" row in the machine view
function Win({ idx, eff, done, children }:
  { idx: number; eff: number; done: boolean; children: React.ReactNode }) {
  const active = eff === idx && !done;
  const pending = eff < idx;
  const ph = PHASES[idx];
  return (
    <motion.div
      animate={{ opacity: pending ? 0.4 : 1 }}
      className={`relative rounded-lg border overflow-hidden ${active ? "machine-scan" : ""}`}
      style={{
        borderColor: active ? "rgba(167,139,250,0.5)" : "var(--color-border)",
        background: active ? "rgba(167,139,250,0.06)" : "rgba(255,255,255,0.015)",
        boxShadow: active ? "0 0 24px -10px rgba(167,139,250,0.6)" : "none",
      }}>
      <div className="flex items-center gap-2 px-2.5 py-1 border-b border-border/60">
        <span className="text-[10px] font-mono"
          style={{ color: done ? "#34d399" : active ? "#a78bfa" : "#5a6477" }}>
          {done ? "✓" : active ? "▸" : "○"}
        </span>
        <span className="text-[10px] font-semibold text-ink/80">{ph.label}</span>
        <span className="text-[10px] text-faint">{ph.blurb}</span>
      </div>
      <div className="px-2.5 py-2 min-h-[40px]">{children}</div>
    </motion.div>
  );
}

function Metric({ label, v }: { label: string; v: string }) {
  return (
    <div>
      <span className="text-faint">{label} </span>
      <span className="text-ink">{v}</span>
    </div>
  );
}

function Equity({ seed, drift, progress }: { seed: number; drift: number; progress: number }) {
  const N = 64, W = 168, H = 56;
  const ys = useMemo(() => walk(seed, N, drift), [seed, drift]);
  const shown = Math.max(2, Math.floor(progress * N));
  const pts = ys.slice(0, shown).map((y, i) =>
    [(i / (N - 1)) * W, H - 4 - y * (H - 12)] as const);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const area = pts.length ? `${line} L${pts[pts.length - 1][0].toFixed(1)} ${H} L0 ${H} Z` : "";
  const tip = pts[pts.length - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="shrink-0">
      <defs>
        <linearGradient id="agEq" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#34d399" stopOpacity={0.35} />
          <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
        </linearGradient>
      </defs>
      {area && <path d={area} fill="url(#agEq)" />}
      <path d={line} fill="none" stroke="#34d399" strokeWidth={1.6} />
      {tip && <circle cx={tip[0]} cy={tip[1]} r={2.4} fill="#34d399" />}
    </svg>
  );
}
