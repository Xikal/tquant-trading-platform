import type {
  BacktestRunCreate,
  FactorWeightsUpdate,
  FeatureFlagUpdateRequest,
  PaperOrderCreate,
  SettingsPayload,
  UserSectorExclusionsUpdate,
} from "../../shared/api/types";

export function paperOrderPayload(draft: Record<string, unknown>): PaperOrderCreate {
  return {
    symbol: stringValue(draft.symbol),
    name: stringValue(draft.name),
    side: draft.side === "sell" || draft.side === "卖出" ? "sell" : "buy",
    order_type: draft.order_type === "limit" ? "limit" : "market",
    quantity: positiveNumber(draft.quantity, 100),
    price: optionalNumber(draft.price),
    current_price: optionalNumber(draft.price),
    up_limit: null,
    down_limit: null,
    is_suspended: false,
    reason: stringValue(draft.reason, "frontend-next shadow parity"),
    require_intraday_confirmation: false,
    source: "frontend-next-shadow",
    strategy_key: stringValue(draft.strategy_key),
  };
}

export function backtestPayload(draft: Record<string, unknown>): BacktestRunCreate {
  return {
    name: stringValue(draft.name, "frontend-next shadow backtest"),
    strategies: [normalizeStrategyKey(draft.strategy)],
    start_date: stringValue(draft.start, "2025-01-01"),
    end_date: stringValue(draft.end, "2026-06-05"),
    initial_capital: positiveNumber(draft.capital, 100000),
    benchmark: stringValue(draft.benchmark, "000300"),
    data_version: stringValue(draft.data_version),
    engine_version: "backtest-v2",
    fee_model_version: stringValue(draft.fee_model_version),
    max_duration_seconds: 1800,
    resource_tier: "light",
    slippage_bps: 8,
    strategy_version: stringValue(draft.strategy_version),
    params: { source: "frontend-next-shadow" },
  };
}

export function featureFlagPayload(draft: Record<string, unknown>): FeatureFlagUpdateRequest {
  return {
    key: normalizeFeatureFlagKey(draft.flag),
    enabled: normalizeBoolean(draft.value),
  };
}

export function settingsPayload(draft: Record<string, unknown>): Partial<SettingsPayload> {
  const key = stringValue(draft.key, "risk_max_single_loss_pct");
  const value = parseSettingValue(draft.value);
  return { [key]: value } as Partial<SettingsPayload>;
}

export function sectorExclusionsPayload(draft: Record<string, unknown>): UserSectorExclusionsUpdate {
  return {
    excluded_sectors: splitList(draft.sectors),
  };
}

export function factorWeightsPayload(draft: Record<string, unknown>): FactorWeightsUpdate {
  const key = stringValue(draft.factor, "volume_price");
  return {
    weights: { [key]: positiveNumber(draft.weight, 0) },
  };
}

export function genericMutationPayload(draft: Record<string, unknown>): Record<string, unknown> {
  return {
    ...draft,
    ...(draft.strategy !== undefined ? { strategy: normalizeStrategyKey(draft.strategy) } : {}),
    ...(draft.source !== undefined ? { source: normalizeDataSource(draft.source) } : { source: "frontend-next-shadow" }),
  };
}

function positiveNumber(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function optionalNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeFeatureFlagKey(value: unknown): string {
  const normalized = stringValue(value);
  if (!normalized || normalized === "新版前端性能孤岛") return "frontend_solid_island_enabled";
  return normalized;
}

function normalizeStrategyKey(value: unknown): string {
  const normalized = stringValue(value);
  if (!normalized || normalized === "N形洗盘低吸") return "n_pattern_long_wash";
  return normalized;
}

function normalizeDataSource(value: unknown): string {
  const normalized = stringValue(value);
  if (!normalized || normalized === "默认行情源") return "frontend-next-shadow";
  return normalized;
}

function normalizeBoolean(value: unknown): boolean {
  return value === "true" || value === "开启";
}

function parseSettingValue(value: unknown): string | number | boolean {
  const normalized = stringValue(value);
  if (normalized === "true" || normalized === "开启") return true;
  if (normalized === "false" || normalized === "关闭") return false;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : normalized;
}

function splitList(value: unknown): string[] {
  return stringValue(value)
    .split(/[,\n，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function stringValue(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}
