import type { RunData } from "../types";

interface Sponsor {
  name: string;
  sub: string;
  color: string; // brand accent
  live: boolean; // genuinely exercised in this run
  title: string;
  show: string; // responsive visibility class
}

function buildStack(run: RunData): Sponsor[] {
  const src = new Set(run.proposals.map((p) => p.source));
  const usedAntigravity =
    src.has("antigravity") ||
    run.generations.some((g) => g.births.some((b) => b.interaction_id));
  const onMongo = !!run.meta.memory_backend?.toLowerCase().includes("mongo");

  return [
    {
      name: "Gemini",
      sub: "proposer",
      color: "var(--color-sky)",
      live: src.has("gemini"),
      title: "Google Gemini — proposes new alpha formulas in the DSL",
      show: "hidden sm:inline-flex",
    },
    {
      name: "Antigravity",
      sub: "managed agent",
      color: "var(--color-violet)",
      live: usedAntigravity,
      title:
        "Gemini Antigravity managed agent — browses quant literature in a hosted sandbox and returns citable alphas",
      show: "hidden md:inline-flex",
    },
    {
      name: "Voyage",
      sub: "embeddings",
      color: "var(--color-pink)",
      live: true,
      title: "Voyage AI embeddings — vectorize alphas for memory retrieval & dedup",
      show: "hidden lg:inline-flex",
    },
    {
      name: "MongoDB Atlas",
      sub: onMongo ? "$vectorSearch" : "local mirror",
      color: onMongo ? "var(--color-emerald)" : "var(--color-amber)",
      live: onMongo,
      title: onMongo
        ? "MongoDB Atlas Vector Search — agent memory store"
        : "MongoDB Atlas is wired in; this replay used the offline local vector mirror",
      show: "hidden lg:inline-flex",
    },
  ];
}

function StackBadge({ s }: { s: Sponsor }) {
  return (
    <span className={`chip ${s.show}`} title={s.title}>
      <span className="relative flex h-1.5 w-1.5">
        {s.live && (
          <span
            className="animate-pulse-ring absolute inline-flex h-full w-full rounded-full"
            style={{ background: s.color }}
          />
        )}
        <span
          className="relative inline-flex h-1.5 w-1.5 rounded-full"
          style={{ background: s.color, opacity: s.live ? 1 : 0.7 }}
        />
      </span>
      <span style={{ color: s.live ? s.color : "var(--color-muted)" }}>{s.name}</span>
      <span className="text-faint hidden xl:inline">{s.sub}</span>
    </span>
  );
}

export default function Header({ run }: { run: RunData }) {
  const stack = buildStack(run);

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

        {/* Tech-stack status badges */}
        <div className="flex items-center gap-2">
          {stack.map((s) => (
            <StackBadge key={s.name} s={s} />
          ))}
        </div>
      </div>
    </header>
  );
}
