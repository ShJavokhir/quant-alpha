import { motion } from "framer-motion";
import type { Generation } from "../types";
import { familyColor, fmt } from "../lib";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.035 } },
};
const item = {
  hidden: { opacity: 0, x: -8 },
  show: { opacity: 1, x: 0, transition: { duration: 0.28 } },
};

function SectionLabel({ children }: { children: string }) {
  return (
    <div className="text-faint text-[10px] font-semibold tracking-[0.12em] uppercase mt-4 mb-1.5">
      {children}
    </div>
  );
}

export default function ResearchFeed({
  generations,
  selectedGen,
  onSelectAlpha,
}: {
  generations: Generation[];
  selectedGen: number;
  onSelectAlpha: (name: string) => void;
}) {
  const gen = generations.find((g) => g.g === selectedGen);

  const rejected = (gen?.proposals ?? [])
    .filter((p) => p.verdict === "reject")
    .slice(0, 4);

  const stable = gen ? gen.births.length === 0 && gen.deaths.length === 0 : false;

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold tracking-tight">Research Log</h2>
        <span className="chip text-faint">live lab</span>
      </div>

      {!gen ? (
        <div className="text-muted text-sm mt-6">No data for this generation.</div>
      ) : (
        <motion.div
          key={selectedGen}
          variants={container}
          initial="hidden"
          animate="show"
          className="mt-4 max-h-[520px] overflow-y-auto pr-1 grid-fade"
        >
          {/* Generation header */}
          <motion.div
            variants={item}
            className="text-sm font-mono text-muted sticky top-0 bg-surface/80 backdrop-blur py-1 -mx-1 px-1 z-10"
          >
            <span className="text-cyan font-semibold">Generation {gen.g}</span>
            <span className="text-faint"> · {gen.date} · fleet {gen.fleet_size}</span>
          </motion.div>

          {stable && (
            <motion.div variants={item} className="text-muted text-sm italic mt-4">
              stable generation — no kills or new alphas
            </motion.div>
          )}

          {/* Deaths */}
          {gen.deaths.length > 0 && (
            <>
              <SectionLabel>{`Deaths · ${gen.deaths.length}`}</SectionLabel>
              {gen.deaths.map((d) => (
                <motion.div
                  key={`death-${d.name}`}
                  variants={item}
                  className="flex items-start gap-2 py-1 text-sm"
                >
                  <span className="text-rose mt-0.5 shrink-0">✕</span>
                  <span className="font-mono text-ink shrink-0">{d.name}</span>
                  <span className="text-muted text-xs leading-5">{d.reason}</span>
                </motion.div>
              ))}
            </>
          )}

          {/* Births */}
          {gen.births.length > 0 && (
            <>
              <SectionLabel>{`Births · ${gen.births.length}`}</SectionLabel>
              {gen.births.map((b) => (
                <motion.div
                  key={`birth-${b.name}`}
                  variants={item}
                  className="flex items-center flex-wrap gap-x-2 gap-y-1 py-1.5 text-sm"
                >
                  <span className="text-emerald shrink-0">▲</span>
                  <span
                    className="h-2 w-2 rounded-full shrink-0"
                    style={{ background: familyColor(b.family) }}
                  />
                  <button
                    type="button"
                    onClick={() => onSelectAlpha(b.name)}
                    className="font-mono text-ink hover:text-cyan underline-offset-2 hover:underline transition-colors"
                  >
                    {b.name}
                  </button>
                  <span className="text-muted text-xs">
                    IR train {fmt(b.train_ir)} → test {fmt(b.test_ir)}
                  </span>
                  <span
                    className="chip text-[10px] py-0.5"
                    style={{ color: familyColor(b.family) }}
                  >
                    {b.family}
                  </span>
                  {b.source === "antigravity" && (
                    <span className="chip text-[10px] py-0.5 text-violet" title="Researched by the Gemini Antigravity managed agent in an isolated environment">
                      🛰 Antigravity{b.steps ? ` · ${b.steps.n_steps} steps` : ""}
                    </span>
                  )}
                  {(b.source === "web" || b.source === "antigravity") && b.source_url && (
                    <a
                      href={b.source_url}
                      target="_blank"
                      rel="noreferrer"
                      title={b.source_url}
                      className="text-faint hover:text-cyan transition-colors"
                    >
                      🔗
                    </a>
                  )}
                </motion.div>
              ))}
            </>
          )}

          {/* Rejected */}
          {rejected.length > 0 && (
            <>
              <SectionLabel>{`Rejected · ${rejected.length}`}</SectionLabel>
              {rejected.map((p, i) => (
                <motion.div
                  key={`rej-${p.name}-${i}`}
                  variants={item}
                  className="flex items-start gap-2 py-0.5 text-xs text-faint"
                >
                  <span className="shrink-0">·</span>
                  <span className="font-mono shrink-0">{p.name}</span>
                  <span className="leading-5">{p.reject_reason}</span>
                </motion.div>
              ))}
            </>
          )}
        </motion.div>
      )}
    </div>
  );
}
