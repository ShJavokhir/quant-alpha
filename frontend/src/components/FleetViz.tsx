import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Generation, FleetMember } from "../types";
import { familyColor, healthColor, fmt, FAMILY_COLORS } from "../lib";

const W = 1000, H = 580;

// stable hash -> [0,1)
function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return ((h >>> 0) % 100000) / 100000;
}

function familyCentroid(family: string, families: string[]): [number, number] {
  const idx = Math.max(0, families.indexOf(family));
  const n = families.length;
  const ang = (idx / Math.max(1, n)) * Math.PI * 2 - Math.PI / 2;
  const r = Math.min(W, H) * 0.30;
  return [W / 2 + Math.cos(ang) * r, H / 2 + Math.sin(ang) * r];
}

function nodePos(m: FleetMember, families: string[]): [number, number] {
  const [cx, cy] = familyCentroid(m.family, families);
  const a = hash(m.name) * Math.PI * 2;
  const rr = (0.35 + hash(m.name + "r") * 0.65) * Math.min(W, H) * 0.17;
  return [cx + Math.cos(a) * rr, cy + Math.sin(a) * rr];
}

export default function FleetViz({ gen, onSelectAlpha }:
  { gen: Generation; onSelectAlpha: (n: string) => void }) {
  const [hover, setHover] = useState<FleetMember | null>(null);
  const families = useMemo(
    () => Object.keys(FAMILY_COLORS).filter((f) => f !== "unknown"), []);

  const bornNames = new Set(gen.births.map((b) => b.name));
  const nodes = gen.fleet.map((m) => {
    const [x, y] = nodePos(m, families);
    const size = Math.max(7, Math.min(26, 8 + (m.ir + 0.3) * 7));
    return { m, x, y, size, born: bornNames.has(m.name) };
  });

  const famCounts: Record<string, number> = {};
  gen.fleet.forEach((m) => (famCounts[m.family] = (famCounts[m.family] || 0) + 1));

  return (
    <div className="card p-5 relative overflow-hidden">
      <div className="flex items-start justify-between mb-1">
        <div>
          <h3 className="text-lg font-semibold text-ink">The Living Fleet</h3>
          <p className="text-sm text-muted">Each cell is an alpha. Bright = healthy edge · dim = decaying.
            Scrub time to watch the agent cull the weak and breed the strong.</p>
        </div>
        <div className="text-right">
          <div className="text-3xl stat-num text-cyan font-semibold">{gen.fleet_size}</div>
          <div className="text-xs text-faint">live alphas · gen {gen.g}</div>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap my-2">
        {gen.births.length > 0 && (
          <span className="chip text-emerald">▲ {gen.births.length} born</span>)}
        {gen.deaths.length > 0 && (
          <span className="chip text-rose">✕ {gen.deaths.length} retired</span>)}
        <span className="chip text-muted">{gen.date}</span>
      </div>

      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 560 }}>
          <defs>
            <radialGradient id="coreglow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(34,211,238,0.12)" />
              <stop offset="100%" stopColor="rgba(34,211,238,0)" />
            </radialGradient>
          </defs>
          <circle cx={W / 2} cy={H / 2} r={230} fill="url(#coreglow)" />
          <AnimatePresence>
            {nodes.map(({ m, x, y, size, born }) => {
              const col = familyColor(m.family);
              const hc = healthColor(m.ir);
              return (
                <motion.g
                  key={m.name}
                  initial={{ opacity: 0, scale: 0 }}
                  animate={{ opacity: 1, scale: 1, x, y }}
                  exit={{ opacity: 0, scale: 0 }}
                  transition={{ type: "spring", stiffness: 120, damping: 18, mass: 0.6 }}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHover(m)}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => onSelectAlpha(m.name)}
                >
                  {born && (
                    <circle r={size + 4} fill="none" stroke={hc} strokeWidth={2}
                      className="animate-pulse-ring" />)}
                  <circle r={size} fill={col} fillOpacity={0.16}
                    stroke={col} strokeWidth={1.5} />
                  <circle r={Math.max(2.5, size * 0.34)} fill={hc} />
                </motion.g>
              );
            })}
          </AnimatePresence>
        </svg>

        {hover && (
          <div className="absolute top-2 left-2 card px-3 py-2 text-xs pointer-events-none">
            <div className="font-mono text-ink">{hover.name}</div>
            <div className="text-muted">
              <span style={{ color: familyColor(hover.family) }}>{hover.family}</span>
              {" · "}IR {fmt(hover.ir)} · turn {fmt(hover.turnover)} · age {hover.age}
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-3 flex-wrap mt-1 justify-center">
        {families.map((f) => (
          <span key={f} className="inline-flex items-center gap-1.5 text-xs text-muted">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: familyColor(f) }} />
            {f}{famCounts[f] ? ` ${famCounts[f]}` : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
