import { apiClient } from "./httpClient";

const request = apiClient.request;
const FACTOR_LLM_TIMEOUT_MS = 120_000;
const FACTOR_EVAL_TIMEOUT_MS = 180_000;

export interface FactorEvalResult {
  ic_mean: number;
  ic_std: number;
  icir: number;
  ic_t_stat: number;
  half_life_days: number;
  top_quintile_return: number;
  spread_return: number;
  oos_ic_mean: number;
  is_oos_consistent: boolean;
  bootstrap_ci_lower: number;
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
  direction: "higher_better" | "lower_better";
  category: string;
  status: string;
  source: string;
  version: string;
  eval_result?: FactorEvalResult | null;
}

export interface FactorHypothesis {
  factor_name: string;
  factor_key: string;
  hypothesis: string;
  data_deps: string[];
  direction: "higher_better" | "lower_better";
  category: string;
  limitations: string[];
  source: string;
}

export interface FactorCodeSynthResponse {
  factor_key: string;
  formula_code: string;
  unit_tests: string[];
  safety_passed: boolean;
  warning: string;
}

export const factorMiningApi = {
  listFactors: (status = "") => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    params.set("limit", "80");
    return request<{ items: FactorDefinition[]; total: number }>(`/factor-mining/factors?${params.toString()}`);
  },
  generateHypotheses: (topic: string, count = 20) =>
    request<{ provider: string; items: FactorHypothesis[]; warning: string }>("/factor-mining/hypotheses", {
      method: "POST",
      body: JSON.stringify({ topic, count, use_llm: true }),
      timeoutMs: FACTOR_LLM_TIMEOUT_MS,
    }),
  synthesizeCode: (hypothesis: FactorHypothesis) =>
    request<FactorCodeSynthResponse>("/factor-mining/code-synth", {
      method: "POST",
      body: JSON.stringify({ hypothesis, use_llm: true }),
      timeoutMs: FACTOR_LLM_TIMEOUT_MS,
    }),
  createFactor: (payload: Partial<FactorDefinition>) =>
    request<FactorDefinition>("/factor-mining/factors", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  evaluateFactor: (factorKey: string, payload: Record<string, unknown>) =>
    request<{ factor: FactorDefinition; result: FactorEvalResult; interpretation: Record<string, unknown>; run_id: number }>(
      `/factor-mining/factors/${encodeURIComponent(factorKey)}/evaluate`,
      { method: "POST", body: JSON.stringify(payload), timeoutMs: FACTOR_EVAL_TIMEOUT_MS },
    ),
  promoteFactor: (factorKey: string, targetStatus: string, reason: string) =>
    request<FactorDefinition>(`/factor-mining/factors/${encodeURIComponent(factorKey)}/promote`, {
      method: "POST",
      body: JSON.stringify({ target_status: targetStatus, reason }),
    }),
};
