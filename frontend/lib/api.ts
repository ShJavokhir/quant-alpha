export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Verdict = "ROBUST" | "FRAGILE" | "OVERFIT" | "NO DATA";
export type Action = "baseline" | "tighten" | "abandon" | "diversify";

export interface Experiment {
  iteration: number;
  researcher: string;
  template: string;
  hypothesis: string;
  rationale: string;
  grid: Record<string, number[]>;
  windows: { is_years: number; oos_years: number; step_years: number };
  verdict: Verdict;
  n_folds: number;
  // APPRAISAL = the verdict basis (beta-adjusted alpha vs buy&hold)
  is_appraisal: number;
  oos_appraisal: number;
  appraisal_gap: number;
  // EXCESS / Information Ratio = shown FIRST (passive-indexing sanity check)
  is_excess_sharpe: number;
  oos_excess_sharpe: number;
  excess_gap: number;
  benchmark_oos_sharpe: number;
  // absolute Sharpe = DISPLAY ONLY
  is_sharpe: number;
  oos_sharpe: number;
  gap: number;
  per_ticker: Record<string, { verdict: Verdict; oos_appraisal: number; oos_excess_sharpe: number }>;
  diagnosis: string;
  lesson: string;
  llm_lesson: string;
  accepted: boolean;
  // caused routing
  action: Action;
  caused_by: number | null;
  constraints: {
    banned_families: string[];
    tighten_families: string[];
    preferred_kind: string | null;
    min_is_years: number;
    max_combos: number;
  };
  banned_families: string[];
  carried_lesson_from_prev: string | null;
  arm: string;
  best_oos_excess_so_far: number | null;
}

export interface JournalResponse {
  run_id: string;
  experiments: Experiment[];
}

export interface Point {
  time: string;
  value: number;
}

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface OverfitResponse {
  ticker: string;
  template: string;
  iteration: number;
  params: Record<string, number>;
  verdict: Verdict;
  is: { appraisal: number; excess: number; sharpe: number; from: string; curve: Point[] };
  oos: { appraisal: number; excess: number; sharpe: number; from: string; curve: Point[] };
  benchmark_oos: Point[];
  benchmark_oos_sharpe: number;
  appraisal_gap: number;
  gap: number;
}

export interface Stat {
  mean: number;
  std: number;
  sem: number;
}
export interface ArmAgg {
  n_seeds: number;
  experiments_to_first_robust: Stat;
  best_oos_appraisal: Stat;
  first_try_survival_rate: number;
  found_robust_rate: number;
}

export interface ArmSeed {
  seed: number;
  arm: string;
  experiments_to_first_robust: number;
  best_oos_appraisal: number | null;
  found_robust: boolean;
}

export interface AblationResponse {
  run_id: string;
  n_seeds: number;
  max_experiments: number;
  memory_on: { agg: ArmAgg; seeds: ArmSeed[] };
  memory_off: { agg: ArmAgg; seeds: ArmSeed[] };
}

export interface HoldoutFamily {
  family: string;
  role: string;
  note: string;
}
export interface HoldoutResponse {
  cutoff: string;
  train_names: string[];
  held_names: string[];
  tail_from: string;
  benchmark_tail_sharpe: number;
  headline: string;
  sealed_declaration: string;
  proof: boolean;
  out_of_time: {
    winner: HoldoutFamily & {
      sealed_tail: { appraisal: number | null; verdict: Verdict };
      decade: { by_decade: Record<string, number>; post_cutoff_appraisal: number | null; post_cutoff_verdict: Verdict };
    };
    rejected: HoldoutFamily & {
      sealed_tail: { appraisal: number | null; verdict: Verdict };
      decade: { by_decade: Record<string, number>; post_cutoff_appraisal: number | null; post_cutoff_verdict: Verdict };
    };
  };
  out_of_asset: {
    winner: HoldoutFamily & { appraisal: number | null; appraisal_gap: number | null; verdict: Verdict; n_names_positive: number; names: string[] };
    rejected: HoldoutFamily & { appraisal: number | null; appraisal_gap: number | null; verdict: Verdict; n_names_positive: number; names: string[] };
  };
}

export interface SimulateResponse {
  ticker: string;
  template: string;
  params: Record<string, number>;
  metrics: Record<string, number | null>;
  candles: Candle[];
  equity: Point[];
  trades: { time: string; type: "entry" | "exit"; price: number }[];
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export const api = {
  health: () => get<{ ok: boolean; tickers: string[]; runs: string[] }>("/api/health"),
  journal: (run = "latest") => get<JournalResponse>(`/api/runs/${run}/journal`),
  overfit: (iter: number, ticker = "SPY", run = "latest") =>
    get<OverfitResponse>(`/api/runs/${run}/experiments/${iter}/overfit?ticker=${ticker}`),
  ablation: (run = "latest") => get<AblationResponse>(`/api/runs/${run}/ablation`),
  holdout: (run = "latest") => get<HoldoutResponse>(`/api/runs/${run}/holdout`),
  simulate: (ticker: string, template: string, years = 5) =>
    get<SimulateResponse>(`/api/simulate?ticker=${ticker}&template=${template}&years=${years}`),
};
