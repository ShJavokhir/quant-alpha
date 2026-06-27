const MAP: Record<string, { cls: string; dot: string }> = {
  ROBUST: { cls: "text-robust border-robust/40 bg-robust/10", dot: "bg-robust" },
  FRAGILE: { cls: "text-fragile border-fragile/40 bg-fragile/10", dot: "bg-fragile" },
  OVERFIT: { cls: "text-overfit border-overfit/40 bg-overfit/10", dot: "bg-overfit" },
  "NO DATA": { cls: "text-muted border-line bg-panel", dot: "bg-muted" },
};

export function VerdictBadge({ verdict }: { verdict: string }) {
  const v = MAP[verdict] ?? MAP["NO DATA"];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-mono text-xs font-semibold tracking-wide ${v.cls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${v.dot}`} />
      {verdict}
    </span>
  );
}
