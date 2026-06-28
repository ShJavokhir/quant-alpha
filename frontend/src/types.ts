export interface BookMetrics {
  ic: number; ic_ir: number; appraisal: number; appraisal_net: number;
  sharpe: number; sharpe_net: number; ann_ret: number; ann_ret_net: number;
  turnover: number; beta: number; n_days: number;
}

export interface FleetMember {
  name: string; family: string; ir: number; turnover: number;
  source: string; age: number;
}

export interface AgentSteps { n_steps: number; kinds: string[]; }

export interface Birth {
  name: string; family: string; formula: string; rationale: string;
  source: string; source_url?: string;
  train_ir: number; test_ir: number; turnover: number;
  steps?: AgentSteps; interaction_id?: string; environment_id?: string;
}

export interface Death { name: string; reason: string; lived_gens: number; }

export interface Proposal {
  g: number; date: string; arm: string; memory_on: boolean;
  name: string; family: string; formula: string;
  verdict: "accept" | "reject"; reject_reason: string | null;
  train_ir: number | null; test_ir: number | null; turnover: number | null;
  source: string; source_url?: string; rationale?: string;
}

export interface Generation {
  arm: string; mode: string; memory_on: boolean;
  g: number; date: string; fleet_size: number;
  deaths: Death[]; births: Birth[]; proposals: Proposal[];
  hit_rate: number; n_proposed: number; n_accepted: number;
  mean_proposal_test_ir: number; median_proposal_test_ir: number;
  book_train: BookMetrics; book_test: BookMetrics;
  fleet: FleetMember[];
}

export interface ArmPoint {
  g: number; date: string; fleet_size: number; hit_rate: number;
  n_proposed: number; n_accepted: number;
  median_proposal_test_ir: number; mean_proposal_test_ir: number;
  book_train: BookMetrics; book_test: BookMetrics;
}

export interface Holdout {
  window?: { start: string; end: string };
  adaptive?: BookMetrics; frozen?: BookMetrics; adaptive_delay1?: BookMetrics;
  cost_sweep?: { bps: number; adaptive: number; frozen: number }[];
}

export interface RunData {
  meta: {
    run_id: string; created: string; panel: string; universe_n: number;
    n_stocks: number; n_generations: number;
    timeline: { first: string; last: string; holdout_start: string };
    config: Record<string, number>;
    memory_backend: string; wall_seconds: number;
  };
  generations: Generation[];
  arms: Record<string, ArmPoint[]>;
  proposals: Proposal[];
  holdout: Holdout;
  summary: {
    n_trials: number; n_accepted: number; accept_rate: number;
    final_fleet_size: number;
  };
}
