import type { EtfUniverseProfile } from "./market";

export type EtfUniverseIssueSeverity = "ok" | "info" | "warning" | "error";
export type EtfUniverseRiskLevel = "low" | "medium" | "high";

export interface EtfUniverseAdminProfile extends EtfUniverseProfile {
  source: "baseline" | "override";
  validation_severity: EtfUniverseIssueSeverity;
}

export interface EtfUniverseValidationIssue {
  symbol: string;
  severity: Exclude<EtfUniverseIssueSeverity, "ok">;
  field: string;
  message: string;
  suggested_value?: unknown;
}

export interface EtfUniverseValidationSummary {
  error_count: number;
  warning_count: number;
  info_count: number;
  issues: EtfUniverseValidationIssue[];
}

export interface EtfUniverseDiffItem {
  symbol: string;
  field: string;
  baseline_value: unknown;
  current_value: unknown;
  draft_value: unknown;
  risk_level: EtfUniverseRiskLevel;
  message: string;
}

export interface EtfUniverseVersionSummary {
  version: string;
  status: string;
  scope: string;
  description: string;
  created_by: string;
  created_at: string;
  activated_at: string;
}

export type EtfUniverseOverride = Partial<Omit<EtfUniverseProfile, "same_day_sell_allowed">> & {
  symbol: string;
  [key: string]: unknown;
};

export type EtfUniverseOverrideMap = Record<string, EtfUniverseOverride>;

export interface EtfUniverseAdminResponse {
  version: string;
  updated_at: string;
  audit_scope: string;
  baseline_count: number;
  current_count: number;
  override_count: number;
  t0_enabled_count: number;
  items: EtfUniverseAdminProfile[];
  overrides: EtfUniverseOverrideMap;
  normalized_overrides: EtfUniverseOverrideMap;
  validation: EtfUniverseValidationSummary;
  diff: EtfUniverseDiffItem[];
  recent_versions: EtfUniverseVersionSummary[];
  notes: string[];
}

export interface EtfUniverseApplyRequest {
  draft_overrides: EtfUniverseOverrideMap;
  version: string;
  description: string;
  activate: boolean;
  confirm_high_risk: boolean;
}

export interface EtfUniverseRollbackRequest {
  version: string;
  confirm: boolean;
}

export interface EtfUniverseMutationResponse {
  ok: boolean;
  message: string;
  version: string;
  admin: EtfUniverseAdminResponse;
}

export interface EtfUniverseRepairDraftResponse {
  draft_overrides: EtfUniverseOverrideMap;
  validation: EtfUniverseValidationSummary;
  requires_confirmation: boolean;
  notes: string[];
}
