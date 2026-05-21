import { apiClient } from "./httpClient";

const request = apiClient.request;
const requestCached = apiClient.requestCached;

export type FactorStatus = "candidate" | "validated" | "production" | "archived" | "rejected";
export type FactorDirection = "higher_better" | "lower_better";

export interface FactorEvalResult {
  ic_mean: number;
  icir: number;
  ic_t_stat: number;
  half_life_days: number;
  top_quintile_return: number;
  spread_return: number;
  information_ratio: number;
  oos_ic_mean: number;
  is_oos_consistent: boolean;
  walk_forward_oos_ic_mean?: number;
  walk_forward_window_count?: number;
  walk_forward_positive_window_rate_pct?: number;
  walk_forward_no_negative_windows?: boolean;
  bootstrap_ci_lower: number;
  max_existing_factor_corr?: number;
  max_existing_factor_key?: string;
  passed_candidate_gate: boolean;
  passed_production_gate: boolean;
  sample_days: number;
  observation_count: number;
  symbol_count: number;
  warnings: string[];
}

export interface FactorDefinition {
  id?: number | null;
  factor_key: string;
  name: string;
  hypothesis: string;
  formula_code: string;
  data_deps: string[];
  direction: FactorDirection;
  category: string;
  status: FactorStatus;
  source: string;
  version: string;
  eval_result?: FactorEvalResult | null;
  created_by: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface FactorHypothesis {
  factor_name: string;
  factor_key: string;
  hypothesis: string;
  data_deps: string[];
  direction: FactorDirection;
  category: string;
  limitations: string[];
  source: string;
}

export interface FactorHealthItem {
  factor_key: string;
  name: string;
  status: FactorStatus;
  ic_mean: number;
  ic_t_stat: number;
  trend: "stable" | "decaying" | "improving" | string;
  run_count: number;
}

export interface FactorEvaluationRequest {
  start_date?: string;
  end_date?: string;
  holding_days: number;
  limit_symbols: number;
  min_cross_section: number;
}

export const factorMiningApi = {
  listFactors: (status = "") =>
    request<{ items: FactorDefinition[]; total: number }>(
      `/factor-mining/factors?limit=80${status ? `&status=${encodeURIComponent(status)}` : ""}`,
    ),
  createFactor: (payload: Partial<FactorDefinition>) =>
    request<FactorDefinition>("/factor-mining/factors", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  generateHypotheses: (payload: { topic: string; count: number; use_llm: boolean }) =>
    request<{ provider: string; items: FactorHypothesis[]; warning?: string }>("/factor-mining/hypotheses", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 60000,
    }),
  synthesizeCode: (hypothesis: FactorHypothesis, useLlm = true) =>
    request<{ factor_key: string; formula_code: string; unit_tests: string[]; safety_passed: boolean; warning?: string }>(
      "/factor-mining/code-synth",
      {
        method: "POST",
        body: JSON.stringify({ hypothesis, use_llm: useLlm }),
        timeoutMs: 60000,
      },
    ),
  evaluateFactor: (factorKey: string, payload: FactorEvaluationRequest) =>
    request<{ factor: FactorDefinition; result: FactorEvalResult; run_id?: number | null; elapsed_seconds: number }>(
      `/factor-mining/factors/${encodeURIComponent(factorKey)}/evaluate`,
      {
        method: "POST",
        body: JSON.stringify(payload),
        timeoutMs: 90000,
      },
    ),
  promoteFactor: (factorKey: string, targetStatus: FactorStatus, reason: string) =>
    request<FactorDefinition>(`/factor-mining/factors/${encodeURIComponent(factorKey)}/promote`, {
      method: "POST",
      body: JSON.stringify({ target_status: targetStatus, reason }),
    }),
  getActivation: (factorKey: string) =>
    request<{ factor_key: string; active: boolean }>(`/factor-mining/factors/${encodeURIComponent(factorKey)}/activation`),
  updateActivation: (factorKey: string, active: boolean) =>
    request<{ factor_key: string; active: boolean }>(`/factor-mining/factors/${encodeURIComponent(factorKey)}/activation`, {
      method: "PUT",
      body: JSON.stringify({ active }),
    }),
  getHealth: () =>
    requestCached<{ total: number; production: number; validated: number; items: FactorHealthItem[] }>("/factor-mining/health", 30000),
};
