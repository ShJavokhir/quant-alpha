import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import type { ArmPoint, RunData } from "../types";
import { fmt, pct, signed } from "../lib";

/** Animate a number from 0 → target on mount with an ease-out cubic. */
function useCountUp(target: number | null, duration = 1200) {
  const [val, setVal] = useState(0);
  const rafRef = useRef(0);
  useEffect(() => {
    if (target === null || Number.isNaN(target)) return;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setVal(target * eased);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);
  return val;
}

function StatCard({
  label,
  target,
  format,
  sub,
  accent = "text-ink",
  delay = 0,
}: {
  label: string;
  target: number | null;
  format: (n: number) => string;
  sub?: ReactNode;
  accent?: string;
  delay?: number;
}) {
  const v = useCountUp(target);
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
      className="card p-5"
    >
      <div className="text-faint text-xs tracking-wide uppercase">{label}</div>
      <div className={`stat-num text-4xl font-bold mt-2 ${accent}`}>
        {target === null ? "–" : format(v)}
      </div>
      {sub && <div className="text-xs text-muted mt-1.5">{sub}</div>}
    </motion.div>
  );
}

const meanAppr = (arr?: ArmPoint[]): number | null =>
  arr && arr.length ? arr.reduce((s, a) => s + (a.book_test?.appraisal ?? 0), 0) / arr.length : null;
const totalAccepted = (arr?: ArmPoint[]): number | null =>
  arr && arr.length ? arr.reduce((s, a) => s + a.n_accepted, 0) : null;

export default function Hero({ run }: { run: RunData }) {
  const { summary, arms } = run;

  // out-of-sample appraisal: the agent's evolving book vs the frozen seed fleet (21 blocks)
  const aAppr = meanAppr(arms?.adaptive);
  const fAppr = meanAppr(arms?.frozen);
  const apprAccent =
    aAppr !== null && fAppr !== null && aAppr > fAppr ? "text-emerald" : "text-ink";

  // memory advantage: discoveries with memory ON vs OFF
  const aAcc = totalAccepted(arms?.adaptive);
  const offAcc = totalAccepted(arms?.memory_off);
  const lift =
    aAcc !== null && offAcc && offAcc > 0 ? (aAcc / offAcc - 1) * 100 : null;
  const liftAccent = lift !== null && lift >= 0 ? "text-emerald" : "text-rose";

  return (
    <section className="mx-auto max-w-7xl px-5 pt-14 pb-8">
      {/* Eyebrow */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="chip text-cyan"
      >
        <span className="relative flex h-1.5 w-1.5">
          <span className="animate-pulse-ring absolute inline-flex h-full w-full rounded-full bg-cyan" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-cyan" />
        </span>
        CONTINUAL LEARNING · SELF-IMPROVEMENT · RSI
      </motion.div>

      {/* Headline */}
      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.05 }}
        className="mt-5 text-4xl sm:text-5xl font-bold tracking-tight leading-[1.05] max-w-3xl"
      >
        An AI that researches alpha —{" "}
        <span
          style={{
            background: "linear-gradient(90deg, #22d3ee, #a78bfa)",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
          }}
        >
          and gets better at it.
        </span>
      </motion.h1>

      {/* Subhead */}
      <motion.p
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.12 }}
        className="mt-4 text-muted max-w-2xl text-base sm:text-lg leading-relaxed"
      >
        Each generation it proposes new trading signals, kills the weak, breeds the
        strong — accumulating research memory that compounds into a sharper fleet over
        time.
      </motion.p>

      {/* Stat cards */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Alphas researched"
          target={summary.n_trials}
          format={(n) => Math.round(n).toLocaleString()}
          accent="text-cyan"
          delay={0.18}
          sub="proposed across all generations"
        />
        <StatCard
          label="Survived selection"
          target={summary.n_accepted}
          format={(n) => Math.round(n).toString()}
          accent="text-violet"
          delay={0.24}
          sub={`${pct(summary.accept_rate)} accept rate`}
        />
        <StatCard
          label="Out-of-sample appraisal"
          target={aAppr}
          format={(n) => fmt(n, 2)}
          accent={apprAccent}
          delay={0.3}
          sub={`vs ${fmt(fAppr, 2)} frozen fleet`}
        />
        <StatCard
          label="Memory advantage"
          target={lift}
          format={(n) => `${signed(n, 0)}%`}
          accent={liftAccent}
          delay={0.36}
          sub="more alphas discovered vs memory-off"
        />
      </div>
    </section>
  );
}
