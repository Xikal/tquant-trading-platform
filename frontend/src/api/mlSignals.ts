import { request } from "./base";

export interface MLSignalModelOut {
  model_key: string;
  model_type: string;
  status: string;
  feature_names: string[];
  metrics: Record<string, unknown>;
  artifact_uri?: string;
  remote_artifact_uri?: string;
  artifact_checksum?: string;
  created_at?: string;
}

export interface MLSignalOnlineLearningStatus {
  generated_at: string;
  paper_sample_count: number;
  closed_trade_sample_count: number;
  positive_sample_count: number;
  negative_sample_count: number;
  ready_for_training: boolean;
  min_samples: number;
  feature_names: string[];
  sequence_feature_names: string[];
  latest_model?: MLSignalModelOut | null;
  production_model_key: string;
  latest_incremental_task_id?: number | null;
  latest_incremental_task_status: string;
  latest_incremental_task_progress_pct: number;
  latest_incremental_task_finished_at?: string | null;
  next_training_rule: string;
  warnings: string[];
}

export interface MLSignalIncrementalTrainRequest {
  model_key?: string;
  model_type?: "logistic" | "xgboost" | "lightgbm";
  source?: "paper";
  limit?: number;
  min_samples?: number;
  validation_ratio?: number;
  promote?: boolean;
  min_validation_accuracy?: number;
}

export interface MLSignalTrainResponse {
  model_key: string;
  model_type: string;
  status: "research" | "production" | "failed";
  sample_count: number;
  feature_names: string[];
  metrics: Record<string, unknown>;
  artifact_uri?: string;
  remote_artifact_uri?: string;
  artifact_checksum?: string;
  warning?: string;
}

export interface StrategyCapacityRequest {
  strategies?: string[];
  start_date?: string;
  end_date?: string;
  capital_levels?: number[];
  trade_limit?: number;
  bar_limit?: number;
}

export interface StrategyCapacityPoint {
  capital: number;
  participation_pct: number;
  expected_edge_pct: number;
  kyle_impact_pct: number;
  impact_cost_pct: number;
  slippage_cost_pct: number;
  net_edge_pct: number;
  capacity_status: string;
}

export interface StrategyCapacityItem {
  strategy_key: string;
  sample_count: number;
  symbol_count: number;
  avg_daily_amount: number;
  base_edge_pct: number;
  kyle_lambda: number;
  curve: StrategyCapacityPoint[];
  notes: string[];
}

export interface StrategyCapacityResponse {
  generated_at: string;
  capital_levels: number[];
  items: StrategyCapacityItem[];
  assumptions: Record<string, unknown>;
}

export const mlSignalsApi = {
  getOnlineLearningStatus: (minSamples = 100) =>
    request<MLSignalOnlineLearningStatus>(`/ml/signals/online-learning/status?min_samples=${minSamples}`),

  incrementalTrain: (payload: MLSignalIncrementalTrainRequest = {}) =>
    request<MLSignalTrainResponse>("/ml/signals/incremental-train", {
      method: "POST",
      body: JSON.stringify({ source: "paper", promote: false, ...payload }),
    }),

  evaluateCapacity: (payload: StrategyCapacityRequest) =>
    request<StrategyCapacityResponse>("/ml/signals/capacity", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
