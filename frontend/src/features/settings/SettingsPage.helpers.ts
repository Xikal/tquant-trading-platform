import type { FactorWeightsResponse, SettingsPayload } from "../../types";
import type { SettingsDraft } from "../workspace-shared/workspaceTypes";

export type SettingsSectionKey = "llm" | "risk" | "data" | "factor";

export type SectionErrorMap = {
  adminTokenError: string;
  llmKeyError: string;
  llmBaseUrlError: string;
  dataSourceUrlError: string;
  singleLossError: string;
  dailyLossError: string;
  pauseLossError: string;
  minProfitError: string;
};

export function sectionError(section: SettingsSectionKey, errors: SectionErrorMap): string {
  if (errors.adminTokenError) return errors.adminTokenError;
  if (section === "llm") return errors.llmKeyError || errors.llmBaseUrlError;
  if (section === "data") return errors.dataSourceUrlError;
  if (section === "risk") return errors.singleLossError || errors.dailyLossError || errors.pauseLossError || errors.minProfitError;
  return "";
}

export function buildSettingsDirtyState(
  settings: SettingsPayload | null,
  factorWeights: FactorWeightsResponse | null,
  draft: SettingsDraft,
  factorDraft: Record<string, string>,
) {
  const llm = Boolean(
    draft.llm_api_key.trim() ||
    draft.llm_provider !== (settings?.llm_provider || "") ||
    draft.llm_base_url !== (settings?.llm_base_url || "") ||
    draft.llm_model !== (settings?.llm_model || "")
  );
  const data = Boolean(
    draft.data_source !== (settings?.data_source || "") ||
    draft.data_source_base_url !== (settings?.data_source_base_url || "")
  );
  const risk = Boolean(
    draft.risk_max_single_loss_pct !== String(settings?.risk_max_single_loss_pct ?? "") ||
    draft.risk_max_daily_loss_pct !== String(settings?.risk_max_daily_loss_pct ?? "") ||
    draft.risk_pause_after_losses !== String(settings?.risk_pause_after_losses ?? "") ||
    draft.strategy_min_profit_pct !== String(settings?.strategy_min_profit_pct ?? "")
  );
  const factor = Boolean(
    factorWeights &&
    Object.entries(factorDraft).some(([key, value]) => value !== String(factorWeights.weights[key] ?? ""))
  );
  return { llm, data, risk, factor };
}

export function urlFieldError(value: string, label: string): string {
  const cleaned = value.trim();
  if (!cleaned) {
    return "";
  }
  try {
    const parsed = new URL(cleaned);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return `${label}必须是 http 或 https 地址`;
    }
  } catch {
    return `${label}格式不正确`;
  }
  return "";
}

export function percentFieldError(value: string, label: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return `${label}必须是非负数字`;
  }
  if (parsed > 100) {
    return `${label}不能超过 100%`;
  }
  return "";
}

export function integerFieldError(value: string, label: string): string {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) {
    return `${label}必须是非负整数`;
  }
  return "";
}

export function sameStringSet(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false;
  }
  const rightSet = new Set(right);
  return left.every((item) => rightSet.has(item));
}
