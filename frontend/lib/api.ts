export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8077";

export type Verdict = "ROBUST" | "FRAGILE" | "OVERFIT" | "NO DATA";

export interface Experiment {
  iteration: number;
  researcher: string;
  template: string;
  hypothesis: string;
  rationale: string;
  grid: Record<string, number[]>;
  windows: { is_years: number; oos_years: number; step_years: number };
  verdict: Verdict;
  is_sharpe: number;
  oos_sharpe: number;
  gap: number;
  n_folds: number;
  per_ticker: Record<string, { verdict: Verdict; oos_sharpe: number }>;
  diagnosis: string;
  lesson: string;
  accepted: boolean;
  best_oos_so_far: number | null;
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
  is: { sharpe: number; from: string; curve: Point[] };
  oos: { sharpe: number; from: string; curve: Point[] };
  benchmark_oos: Point[];
  gap: number;
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
  simulate: (ticker: string, template: string, years = 5) =>
    get<SimulateResponse>(`/api/simulate?ticker=${ticker}&template=${template}&years=${years}`),
};
