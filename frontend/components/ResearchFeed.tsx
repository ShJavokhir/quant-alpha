"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { Experiment } from "@/lib/api";
import { VerdictBadge } from "./VerdictBadge";

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

          <div className="mt-3 flex items-center gap-4 font-mono text-xs">
            <span className="text-muted">
              IS <span className="text-ink">{e.is_sharpe.toFixed(2)}</span>
            </span>
            <span className="text-accent">→</span>
            <span className="text-muted">
              OOS{" "}
              <span className={e.oos_sharpe > 0 ? "text-robust" : "text-overfit"}>
                {e.oos_sharpe.toFixed(2)}
              </span>
            </span>
            <span className="text-muted">
              gap <span className={e.gap > 0.5 ? "text-overfit" : "text-ink"}>{e.gap.toFixed(2)}</span>
            </span>
            <span className="ml-auto text-muted">{e.n_folds} folds</span>
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
                  <span className="text-fragile">lesson</span> · {e.lesson}
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.button>
      ))}
    </div>
  );
}
