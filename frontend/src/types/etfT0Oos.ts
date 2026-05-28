import type {
  EtfT0ResearchRequest,
  EtfT0ResearchResponse,
} from "../api/backtestTypes";

export type EtfT0OosStage = "research_only" | "paper_small" | "candidate_production";

export interface EtfT0OosQuality {
  bar_count: number;
  missing_bar_ratio: number;
  stale_ratio: number;
  symbol_coverage_ratio: number;
}

export interface EtfT0OosValidationIssue {
  severity: "info" | "warning" | "error";
  field: string;
  message: string;
}

export interface EtfT0OosRegimeSegment {
  regime: string;
  label: string;
  start_time: string;
  end_time: string;
  confidence: number;
  source: string;
  source_version: string;
  notes: string;
}

export interface EtfT0OosDataset {
  dataset_key: string;
  version: string;
  created_at: string;
  symbols: string[];
  period: string;
  start_time: string;
  end_time: string;
  checksum: string;
  quality: EtfT0OosQuality;
  regime_segments: EtfT0OosRegimeSegment[];
  covered_regimes: string[];
  missing_regimes: string[];
  validation_issues: EtfT0OosValidationIssue[];
  quality_ok: boolean;
  notes: string[];
}

export interface EtfT0OosDatasetListResponse {
  items: EtfT0OosDataset[];
  total: number;
}

export interface EtfT0OosValidationRequest extends EtfT0ResearchRequest {
  dataset_key: string;
}

export interface EtfT0OosValidationResponse {
  run_id: string;
  dataset: EtfT0OosDataset;
  research_report: EtfT0ResearchResponse;
  verdict: "pass" | "observe" | "blocked";
  stage: EtfT0OosStage;
  passed: boolean;
  gate_reasons: string[];
  missing_regimes: string[];
  notes: string[];
}

export interface EtfT0OosPromoteCheckResponse {
  dataset_key: string;
  symbol: string;
  stage: EtfT0OosStage;
  allowed: boolean;
  verdict: string;
  gate_reasons: string[];
  notes: string[];
}

export interface EtfT0OosLatestResponse {
  available: boolean;
  run_id: string;
  created_at: string;
  dataset_key: string;
  dataset_version: string;
  checksum: string;
  symbol: string;
  name: string;
  stage: EtfT0OosStage;
  verdict: string;
  passed: boolean;
  gate_reasons: string[];
  missing_regimes: string[];
  quality: Record<string, unknown>;
}
