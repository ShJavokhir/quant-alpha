"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { Experiment, Action } from "@/lib/api";
import { VerdictBadge } from "./VerdictBadge";

const ACTION_LABEL: Record<Action, string> = {
  baseline: "BASELINE",
  tighten: "TIGHTEN",
  abandon: "ABANDON",
  diversify: "DIVERSIFY",
};

function RouteChip({ e }: { e: Experiment }) {
  return (
    <span className="rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-accent">
      {ACTION_LABEL[e.action] ?? e.action}
      {e.caused_by ? ` ← #${e.caused_by}` : ""}
    </span>
  );
}

export function ResearchFeed({
  experiments,
  selected,
  onSelect,
}: {
  experiments: Experiment[];
  selected: number | null;
  onSelect: (i: number) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      {experiments.map((e, idx) => (
        <motion.button
          key={e.iteration}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: idx * 0.12, duration: 0.4, ease: "easeOut" }}
          onClick={() => onSelect(e.iteration)}
          className={`text-left rounded-xl border bg-panel/70 p-4 transition hover:border-accent/50 ${
            selected === e.iteration ? "border-accent" : "border-line"
          }`}
        >
          <div className="flex items-center justify-between gap-3">
            <span className="font-mono text-xs text-muted">
              EXPERIMENT #{e.iteration} · {e.template}
            </span>
            <VerdictBadge verdict={e.verdict} />
          </div>

          <p className="mt-2 text-sm leading-snug text-ink">{e.hypothesis}</p>

          {/* appraisal = the verdict basis (beta-adjusted alpha) */}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-xs">
            <span className="text-muted">
              IS α <span className="text-ink">{e.is_appraisal.toFixed(2)}</span>
            </span>
            <span className="text-accent">→</span>
            <span className="text-muted">
              OOS α{" "}
              <span className={e.oos_appraisal > 0 ? "text-robust" : "text-overfit"}>
                {e.oos_appraisal.toFixed(2)}
              </span>
            </span>
            <span className="text-muted">
              gap <span className={e.appraisal_gap > 0.5 ? "text-overfit" : "text-ink"}>{e.appraisal_gap.toFixed(2)}</span>
            </span>
            <RouteChip e={e} />
            <span className="ml-auto text-muted">{e.n_folds} folds</span>
          </div>

          {/* IR shown alongside: passive indexing wins on this universe */}
          <div className="mt-1 font-mono text-[10px] text-muted">
            vs buy&hold (Info-Ratio) <span className="text-overfit">{e.oos_excess_sharpe.toFixed(2)}</span>
            {" · "}buy&hold Sharpe {e.benchmark_oos_sharpe.toFixed(2)} (the beta we strip out)
          </div>

          <AnimatePresence>
            {selected === e.iteration && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 overflow-hidden border-t border-line pt-3 text-xs leading-relaxed text-muted"
              >
                <p>
                  <span className="text-accent">diagnosis</span> · {e.diagnosis}
                </p>
                <p className="mt-1">
                  <span className="text-fragile">lesson</span> · {e.llm_lesson}
                </p>
                {e.caused_by && e.carried_lesson_from_prev && (
                  <p className="mt-1">
                    <span className="text-robust">caused by #{e.caused_by}</span> · {e.carried_lesson_from_prev}
                  </p>
                )}
                {e.banned_families.length > 0 && (
                  <p className="mt-1 font-mono text-[10px]">
                    <span className="text-overfit">banned families</span> · {e.banned_families.join(", ")}
                  </p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.button>
      ))}
    </div>
  );
}
