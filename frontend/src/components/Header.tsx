import type { RunData } from "../types";

export default function Header({ meta }: { meta: RunData["meta"] }) {
  const memLabel = meta.memory_backend?.toLowerCase().includes("mongo")
    ? "MongoDB Atlas"
    : "Local vector store";
  const range = `${meta.timeline.first.slice(0, 4)}–${meta.timeline.last.slice(0, 4)}`;

  return (
    <header className="sticky top-0 z-40 backdrop-blur-xl bg-bg/70 border-b border-border">
      <div className="mx-auto max-w-7xl px-5 py-3 flex items-center justify-between gap-4">
        {/* Wordmark */}
        <div className="flex items-baseline gap-3 min-w-0">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-pulse-ring absolute inline-flex h-full w-full rounded-full bg-cyan" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan" />
            </span>
            <span
              className="text-xl font-bold tracking-tight"
              style={{
                background: "linear-gradient(90deg, #22d3ee, #a78bfa)",
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                color: "transparent",
              }}
            >
              DARWIN
            </span>
          </div>
          <span className="text-xs text-faint hidden sm:block truncate">
            Self-Evolving Alpha Research
          </span>
        </div>

        {/* Meta chips */}
        <div className="flex items-center gap-2">
          <span className="chip hidden sm:inline-flex">{meta.n_stocks} stocks</span>
          <span className="chip hidden md:inline-flex font-mono">{range}</span>
          <span className="chip hidden lg:inline-flex text-muted">{memLabel}</span>
          <span className="chip hidden lg:inline-flex text-violet">🛰 Antigravity</span>
          <a
            href="#honesty"
            className="chip text-cyan hover:bg-cyan/10 transition-colors"
          >
            Methodology
          </a>
        </div>
      </div>
    </header>
  );
}
