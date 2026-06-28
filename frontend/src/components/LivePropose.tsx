import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { familyColor, fmt } from "../lib";

interface LiveAlpha {
  name: string; family: string; formula: string; rationale?: string;
  ok?: boolean; ic_ir?: number; appraisal?: number; sharpe_net?: number;
  turnover?: number; verdict?: string; error?: string;
}

const verdictColor: Record<string, string> = {
  promising: "#07875a", weak: "#c2820a", invalid: "#d23b36",
};

type Backend = "gemini" | "do";

const BACKENDS: { id: Backend; label: string; sub: string }[] = [
  { id: "gemini", label: "Gemini", sub: "fast" },
  { id: "do", label: "MiniMax M2.5", sub: "on DigitalOcean · reasoning" },
];

export default function LivePropose() {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<LiveAlpha[] | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [backend, setBackend] = useState<Backend>("gemini");

  async function run() {
    setLoading(true); setErr(null); setItems(null); setModel(null);
    try {
      const r = await fetch(`/api/live_propose?n=4&backend=${backend}`, { method: "POST" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setItems(d.proposals || []);
      setModel(d.model || null);
    } catch {
      setErr("Live endpoint needs the backend running (./run_demo.sh).");
    } finally {
      setLoading(false);
    }
  }

  const busyLabel = backend === "do" ? "MiniMax is reasoning… (~60s)" : "researching…";

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-lg font-semibold text-ink">Watch it think — live</h3>
          <p className="text-sm text-muted">The agent authors brand-new alphas right now; we
            backtest each one on the spot. Same loop, swappable model.</p>
        </div>
        <button onClick={run} disabled={loading}
          className="shrink-0 px-4 py-2 rounded-xl bg-cyan/15 text-cyan font-medium text-sm
                     hover:bg-cyan/25 transition glow-cyan disabled:opacity-50">
          {loading ? busyLabel : "⚡ Propose live"}
        </button>
      </div>

      {/* model backend selector — one key, every model (DigitalOcean) */}
      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <span className="text-xs text-faint">model:</span>
        {BACKENDS.map((b) => (
          <button key={b.id} onClick={() => setBackend(b.id)} disabled={loading}
            className={`px-2.5 py-1 rounded-lg text-xs border transition disabled:opacity-50 ${
              backend === b.id
                ? "border-cyan/60 bg-cyan/15 text-cyan"
                : "border-border text-muted hover:text-ink"}`}>
            <span className="font-medium">{b.label}</span>
            <span className="ml-1.5 text-faint">{b.sub}</span>
          </button>
        ))}
      </div>

      {err && <div className="text-xs text-amber mt-3">{err}</div>}
      {model && !loading && (
        <div className="text-xs text-faint mt-3">authored by <span className="text-muted">{model}</span></div>
      )}

      <AnimatePresence>
        {items && (
          <motion.div className="mt-2 space-y-2"
            initial="hidden" animate="show"
            variants={{ show: { transition: { staggerChildren: 0.12 } } }}>
            {items.map((a) => (
              <motion.div key={a.name}
                variants={{ hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } }}
                className="bg-surface2/50 rounded-xl p-3 border border-border">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full" style={{ background: familyColor(a.family) }} />
                  <span className="font-mono text-sm text-ink">{a.name}</span>
                  <span className="ml-auto text-xs font-semibold"
                    style={{ color: verdictColor[a.verdict || "weak"] }}>
                    {a.verdict}
                  </span>
                </div>
                <pre className="text-xs font-mono text-cyan whitespace-pre-wrap break-words">{a.formula}</pre>
                {a.ok ? (
                  <div className="text-xs text-muted mt-1.5 flex gap-3 flex-wrap">
                    <span>IC-IR <span className="text-ink">{fmt(a.ic_ir)}</span></span>
                    <span>net Sharpe <span className="text-ink">{fmt(a.sharpe_net)}</span></span>
                    <span>turnover <span className="text-ink">{fmt(a.turnover)}</span></span>
                  </div>
                ) : (
                  <div className="text-xs text-rose mt-1">{a.error}</div>
                )}
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
