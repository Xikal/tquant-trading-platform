import type { components } from "../generated/api-types";

export type WorkerTaskKind =
  | "monitorPriorityNormalize"
  | "strategyTrackingFilterSort"
  | "analysisBatchRank"
  | "chartDownsample";

export type GeneratedPriorityBoard = components["schemas"]["AppLowBuyPriorityBoard"];
export type GeneratedPriorityItem = components["schemas"]["LowBuyPriorityBoardItemOut"];
export type GeneratedStrategyTrackingItem = components["schemas"]["StrategyTrackingItemOut"];
export type GeneratedAnalysisResponse = components["schemas"]["AnalysisResponse"];
type GeneratedAnalysisSuggestion = GeneratedAnalysisResponse["suggestion"];

export interface WorkerRequestMap {
  monitorPriorityNormalize: MonitorPriorityNormalizeRequest;
  strategyTrackingFilterSort: StrategyTrackingFilterSortRequest;
  analysisBatchRank: AnalysisBatchRankRequest;
  chartDownsample: ChartDownsampleRequest;
}

export interface WorkerResponseMap {
  monitorPriorityNormalize: MonitorPriorityNormalizeResponse;
  strategyTrackingFilterSort: StrategyTrackingFilterSortResponse;
  analysisBatchRank: AnalysisBatchRankResponse;
  chartDownsample: ChartDownsampleResponse;
}

export interface WorkerEnvelope<K extends WorkerTaskKind = WorkerTaskKind> {
  id: string;
  kind: K;
  payload: WorkerRequestMap[K];
}

export interface WorkerResult<K extends WorkerTaskKind = WorkerTaskKind> {
  elapsed_ms: number;
  id: string;
  kind: K;
  payload?: WorkerResponseMap[K];
  error?: string;
}

export type WorkerComputeSource = "worker" | "sync_fallback" | "worker_error_fallback" | "worker_unavailable";

export interface WorkerComputeTelemetrySample {
  elapsed_ms: number;
  input_count: number;
  kind: WorkerTaskKind;
  source: WorkerComputeSource;
  total_ms: number;
}

export interface MonitorPriorityNormalizeRequest {
  board: Pick<GeneratedPriorityBoard, "items"> | null | undefined;
  limit?: number;
}

export interface MonitorPriorityNormalizeResponse {
  items: GeneratedPriorityItem[];
  total: number;
}

export interface StrategyTrackingFilterSortRequest {
  items: GeneratedStrategyTrackingItem[];
  filters?: {
    data_quality?: string;
    signal_state?: string;
    status?: string;
    stopped?: boolean | null;
    user_status?: string;
  };
  sort?: "max_gain_desc" | "current_return_desc" | "risk_desc" | string;
  limit?: number;
  offset?: number;
}

export interface StrategyTrackingFilterSortResponse {
  items: GeneratedStrategyTrackingItem[];
  total: number;
}

export interface AnalysisBatchRankRequest {
  items: AnalysisBatchRankItem[];
}

export interface AnalysisBatchRankResponse {
  items: AnalysisBatchRankItem[];
  total: number;
}

export type AnalysisBatchRankItem = Pick<GeneratedAnalysisResponse, "symbol"> & {
  suggestion: Pick<GeneratedAnalysisSuggestion, "is_actionable" | "signal_score">;
};

export interface ChartPoint {
  date?: string;
  x?: number;
  nav?: number | null;
  benchmark_nav?: number | null;
  drawdown_pct?: number | null;
  value?: number | null;
}

export interface ChartDownsampleRequest {
  points: ChartPoint[];
  maxPoints: number;
}

export interface ChartDownsampleResponse {
  points: ChartPoint[];
  input_count: number;
  output_count: number;
}
