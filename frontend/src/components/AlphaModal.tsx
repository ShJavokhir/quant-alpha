import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { familyColor, fmt } from "../lib";

interface AlphaMetrics {
  ic: number;
  ic_ir: number;
  appraisal: number;
  sharpe: number;
  sharpe_net: number;
  turnover: number;
  [k: string]: number;
}

interface AlphaDetail {
  name: string;
  formula: string;
  family: string;
  rationale: string;
  source: string;
  source_url?: string;
  source_title?: string;
  steps?: { n_steps: number; kinds: string[] };
  interaction_id?: string;
  metrics: AlphaMetrics;
  equity: { date: string; v: number }[];
  cum_ic: { date: string; v: number }[];
}

const tooltipStyle = {
  background: "#0e1320",
  border: "1px solid #1e2740",
  borderRadius: 10,
  fontSize: 12,
  color: "#e8eef6",
} as const;

function MiniChart({
  data,
  color,
  label,
}: {
  data: { date: string; v: number }[];
  color: string;
  label: string;
}) {
  const id = `grad-${label.replace(/\W/g, "")}`;
  return (
    <div className="bg-surface2/50 rounded-xl p-3 border border-border">
      <div className="text-faint text-[10px] uppercase tracking-wide mb-1">{label}</div>
      {data && data.length ? (
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" hide />
            <YAxis hide domain={["auto", "auto"]} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: "#8a97ad" }}
              formatter={(v) => [fmt(Number(v), 4), ""]}
            />
            <Area
              type="monotone"
              dataKey="v"
              stroke={color}
              strokeWidth={2}
              fill={`url(#${id})`}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-[140px] grid place-items-center text-faint text-xs">
          no series
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface2/50 rounded-lg px-3 py-2 border border-border">
      <div className="text-faint text-[10px] uppercase tracking-wide">{label}</div>
      <div className="stat-num text-ink font-semibold mt-0.5">{value}</div>
    </div>
  );
}

export default function AlphaModal({
  name,
  onClose,
}: {
  name: string | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<AlphaDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [similar, setSimilar] = useState<{ backend: string; neighbors: any[] } | null>(null);

  useEffect(() => {
    if (!name) return;
    const ctrl = new AbortController();
    setData(null);
    setError(null);
    setLoading(true);
    fetch(`/api/alpha/${name}`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: AlphaDetail) => {
        setData(d);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
    return () => ctrl.abort();
  }, [name]);

  useEffect(() => {
    if (!name) return;
    setSimilar(null);
    const ctrl = new AbortController();
    fetch(`/api/similar/${name}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setSimilar(d))
      .catch(() => {});
    return () => ctrl.abort();
  }, [name]);

  useEffect(() => {
    if (!name) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [name, onClose]);

  if (!name) return null;

  const m = data?.metrics;

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
        className="card w-full max-w-2xl max-h-[88vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-lg font-semibold tracking-tight font-mono truncate">
              {name}
            </h3>
            {data && (
              <span
                className="chip mt-1.5 text-[10px]"
                style={{ color: familyColor(data.family) }}
              >
                {data.family}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-faint hover:text-ink transition-colors text-xl leading-none shrink-0"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {loading && (
          <div className="py-12 grid place-items-center text-muted text-sm">
            <span className="animate-pulse">Loading alpha…</span>
          </div>
        )}

        {error && !loading && (
          <div className="py-10 text-rose text-sm">Failed to load: {error}</div>
        )}

        {data && !loading && (
          <div className="mt-4 space-y-4">
            {/* Formula */}
            <div>
              <div className="text-faint text-[10px] uppercase tracking-wide mb-1.5">
                Formula
              </div>
              <pre className="bg-surface2 rounded-lg p-3 text-xs font-mono text-cyan whitespace-pre-wrap break-words leading-relaxed">
                {data.formula}
              </pre>
            </div>

            {/* Rationale */}
            {data.rationale && (
              <p className="text-sm text-muted leading-relaxed">{data.rationale}</p>
            )}

            {/* Source / provenance */}
            {data.source === "antigravity" && (
              <div className="chip text-[11px] text-violet">
                🛰 Researched by the Antigravity managed agent
                {data.steps ? ` · ${data.steps.n_steps} steps in an isolated env` : ""}
              </div>
            )}
            {data.source_url ? (
              <a
                href={data.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-cyan hover:underline break-all block"
              >
                🔗 {data.source_title || data.source} · {data.source_url}
              </a>
            ) : (
              <div className="text-xs text-faint">source: {data.source}</div>
            )}

            {/* Metrics grid */}
            {m && (
              <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                <Metric label="IC" value={fmt(m.ic, 4)} />
                <Metric label="IC-IR" value={fmt(m.ic_ir)} />
                <Metric label="Appraisal" value={fmt(m.appraisal)} />
                <Metric label="Net Sharpe" value={fmt(m.sharpe_net)} />
                <Metric label="Turnover" value={fmt(m.turnover)} />
              </div>
            )}

            {/* Charts */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <MiniChart data={data.cum_ic} color="#22d3ee" label="Cumulative IC" />
              <MiniChart data={data.equity} color="#34d399" label="Equity (gross)" />
            </div>

            {/* Similar alphas via Atlas Vector Search */}
            {similar && similar.neighbors?.length > 0 && (
              <div>
                <div className="text-faint text-[10px] uppercase tracking-wide mb-1.5">
                  Nearest alphas in idea-space ·{" "}
                  <span className="text-violet">
                    {similar.backend === "mongo" ? "Atlas Vector Search" : "Voyage embeddings"}
                  </span>
                </div>
                <div className="space-y-1">
                  {similar.neighbors.slice(0, 5).map((nb: any) => (
                    <div key={nb.name}
                      className="flex items-center gap-2 text-xs bg-surface2/40 rounded-lg px-2.5 py-1.5">
                      <span className="w-2 h-2 rounded-full shrink-0"
                        style={{ background: familyColor(nb.family) }} />
                      <span className="font-mono text-ink truncate flex-1">{nb.name}</span>
                      <span className="text-faint shrink-0">{(nb.similarity * 100).toFixed(0)}% match</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </motion.div>
    </div>
  );
}
