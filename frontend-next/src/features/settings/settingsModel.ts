import type { ColumnDef } from "@tanstack/solid-table";
import { nested, numberText, pctText, readArray, readRecord, text } from "../shared/dataAccess";

export type SettingsRecord = Record<string, unknown>;

export function record(data: unknown): SettingsRecord {
  return readRecord(data);
}

export function runtimeMetrics(data: unknown): { label: string; value: string; tone?: "neutral" | "up" | "down" | "warn" }[] {
  const root = readRecord(data);
  const checks = readRecord(root.ready_checks);
  const failed = Object.entries(checks).filter(([, value]) => value === false).length;
  return [
    { label: "一致性", value: text(root.settings_consistency_status), tone: failed ? "warn" : "up" },
    { label: "数据源", value: text(root.data_source) },
    { label: "数据库", value: text(root.database_backend) },
    { label: "前端产物", value: text(root.frontend_dist_ready) },
    { label: "LLM", value: text(root.llm_configured) },
    { label: "失败检查", value: numberText(failed), tone: failed ? "warn" : "up" },
  ];
}

export function accountMetrics(data: unknown): { label: string; value: string; tone?: "neutral" | "up" | "down" | "warn" }[] {
  const user = readRecord(readRecord(data).user);
  return [
    { label: "账户", value: text(user.display_name ?? user.username) },
    { label: "角色", value: listText(user.roles) },
    { label: "MFA", value: text(user.mfa_totp_enabled), tone: user.mfa_totp_enabled ? "up" : "warn" },
  ];
}

export function accountPairs(data: unknown): { label: string; value: string }[] {
  const user = readRecord(readRecord(data).user);
  return [
    { label: "用户名", value: text(user.username) },
    { label: "显示名", value: text(user.display_name) },
    { label: "角色", value: listText(user.roles) },
    { label: "创建时间", value: dateText(user.created_at) },
    { label: "MFA 入口", value: user.mfa_totp_enabled ? "已启用" : "未启用" },
    { label: "配置保存", value: "本地记录" },
  ];
}

export function mfaActionFields(data: unknown): { key: string; label: string; value: string }[] {
  const user = readRecord(readRecord(data).user);
  return [
    { key: "action", label: "动作", value: user.mfa_totp_enabled ? "disable_totp" : "setup_totp" },
    { key: "username", label: "用户", value: text(user.username) },
    { key: "code", label: "动态口令", value: "" },
    { key: "reason", label: "原因", value: "账户安全复核" },
  ];
}

export function settingsPairs(data: unknown): { label: string; value: string }[] {
  const root = readRecord(data);
  return [
    { label: "数据源", value: text(root.data_source) },
    { label: "数据源地址", value: text(root.data_source_base_url) },
    { label: "数据库已配置", value: text(root.database_url_configured) },
    { label: "Admin 鉴权", value: text(root.admin_auth_required) },
    { label: "事件风险", value: text(root.event_risk_enabled) },
    { label: "微观结构", value: text(root.microstructure_enabled) },
    { label: "最大单笔亏损", value: pctText(Number(root.risk_max_single_loss_pct) / 100) },
    { label: "最大日亏损", value: pctText(Number(root.risk_max_daily_loss_pct) / 100) },
    { label: "连续亏损暂停", value: numberText(root.risk_pause_after_losses) },
    { label: "股票最小成交额", value: numberText(root.strategy_min_amount_stock) },
    { label: "ETF 最小成交额", value: numberText(root.strategy_min_amount_etf) },
    { label: "股票滑点 bps", value: numberText(root.strategy_slippage_stock_bps) },
    { label: "ETF 滑点 bps", value: numberText(root.strategy_slippage_etf_bps) },
  ];
}

export function llmPairs(data: unknown): { label: string; value: string }[] {
  const root = readRecord(data);
  return [
    { label: "Provider", value: text(root.llm_provider) },
    { label: "Model", value: text(root.llm_model) },
    { label: "Base URL", value: text(root.llm_base_url) },
    { label: "API Key", value: text(root.llm_api_key_configured) },
  ];
}

export function sectorRows(data: unknown): SettingsRecord[] {
  const root = readRecord(data);
  const available = readArray(root.available_sectors).map((sector) => String(sector));
  const excluded = new Set(readArray(root.excluded_sectors).map((sector) => String(sector)));
  return available.map((sector) => ({ sector, excluded: excluded.has(sector), updated_at: root.updated_at }));
}

export function factorRows(data: unknown): SettingsRecord[] {
  const root = readRecord(data);
  const weights = readRecord(root.weights);
  const defaults = readRecord(root.defaults);
  const factors = readArray<SettingsRecord>(root.factors);
  const fromFactors = factors.map((factor) => {
    const key = text(factor.factor_key ?? factor.key ?? factor.name, "");
    return {
      key,
      name: text(factor.name ?? factor.factor_name ?? key),
      status: text(factor.status ?? factor.status_text),
      weight: weights[key] ?? factor.weight,
      default_weight: defaults[key],
      activation_condition: text(factor.activation_condition),
    };
  });
  if (fromFactors.length) return fromFactors;
  return Object.entries(weights).map(([key, value]) => ({ key, name: key, weight: value, default_weight: defaults[key] }));
}

export function flagRows(data: unknown): SettingsRecord[] {
  const root = readRecord(data);
  const source = readArray<SettingsRecord>(root.items).length ? readArray<SettingsRecord>(root.items) : Object.entries(root).map(([key, value]) => ({ key, value }));
  return source.map((item) => {
    const row = readRecord(item);
    const value = row.value ?? row.enabled;
    return {
      key: text(row.key ?? row.name),
      enabled: typeof value === "object" ? text(row.enabled) : text(value),
      scope: text(row.scope),
      updated_at: text(row.updated_at ?? row.changed_at),
    };
  });
}

export function auditRows(data: unknown): SettingsRecord[] {
  const root = readRecord(data);
  const items = readArray<SettingsRecord>(root.items ?? root.audit ?? root.records);
  if (items.length) return items;
  return Object.entries(root).map(([key, value]) => ({ key, value: safeValue(value) }));
}

export function quantRows(data: unknown): SettingsRecord[] {
  const root = readRecord(data);
  return readArray<SettingsRecord>(root.items).map((item) => ({
    ...item,
    current_version: root.current_version,
    param_count: Object.keys(readRecord(item.params)).length,
  }));
}

export function governanceRows(data: unknown): SettingsRecord[] {
  const root = readRecord(data);
  const governance = readRecord(root.strategy_governance ?? nested(root, "settings.strategy_governance"));
  return readArray<SettingsRecord>(governance.items);
}

export const sectorColumns: ColumnDef<SettingsRecord>[] = [
  { header: "行业", cell: (ctx) => text(ctx.row.original.sector) },
  { header: "排除", cell: (ctx) => text(ctx.row.original.excluded) },
  { header: "更新时间", cell: (ctx) => dateText(ctx.row.original.updated_at) },
];

export const factorColumns: ColumnDef<SettingsRecord>[] = [
  { header: "因子", cell: (ctx) => text(ctx.row.original.name ?? ctx.row.original.key) },
  { header: "状态", cell: (ctx) => text(ctx.row.original.status) },
  { header: "权重", cell: (ctx) => numberText(ctx.row.original.weight) },
  { header: "默认", cell: (ctx) => numberText(ctx.row.original.default_weight) },
  { header: "条件", cell: (ctx) => text(ctx.row.original.activation_condition) },
];

export const flagColumns: ColumnDef<SettingsRecord>[] = [
  { header: "开关", cell: (ctx) => text(ctx.row.original.key) },
  { header: "状态", cell: (ctx) => text(ctx.row.original.enabled) },
  { header: "范围", cell: (ctx) => text(ctx.row.original.scope) },
  { header: "更新时间", cell: (ctx) => dateText(ctx.row.original.updated_at) },
];

export const auditColumns: ColumnDef<SettingsRecord>[] = [
  { header: "时间", cell: (ctx) => dateText(ctx.row.original.created_at ?? ctx.row.original.updated_at) },
  { header: "对象", cell: (ctx) => text(ctx.row.original.key ?? ctx.row.original.flag_key ?? ctx.row.original.version) },
  { header: "动作", cell: (ctx) => text(ctx.row.original.action ?? ctx.row.original.event) },
  { header: "操作人", cell: (ctx) => text(ctx.row.original.operator ?? ctx.row.original.user) },
  { header: "值", cell: (ctx) => text(ctx.row.original.value ?? ctx.row.original.after) },
];

export const quantColumns: ColumnDef<SettingsRecord>[] = [
  { header: "版本", cell: (ctx) => text(ctx.row.original.version) },
  { header: "名称", cell: (ctx) => text(ctx.row.original.name) },
  { header: "范围", cell: (ctx) => text(ctx.row.original.scope) },
  { header: "市场状态", cell: (ctx) => text(ctx.row.original.market_state_scope) },
  { header: "状态", cell: (ctx) => text(ctx.row.original.status) },
  { header: "参数数", cell: (ctx) => numberText(ctx.row.original.param_count) },
  { header: "创建", cell: (ctx) => dateText(ctx.row.original.created_at) },
];

export const governanceColumns: ColumnDef<SettingsRecord>[] = [
  { header: "策略", cell: (ctx) => text(ctx.row.original.strategy_title ?? ctx.row.original.strategy_key) },
  { header: "层级", cell: (ctx) => text(ctx.row.original.layer) },
  { header: "状态", cell: (ctx) => text(ctx.row.original.status_text ?? ctx.row.original.status) },
  { header: "优先榜", cell: (ctx) => text(ctx.row.original.participates_priority_board) },
  { header: "验证", cell: (ctx) => text(ctx.row.original.validation_phase_text ?? ctx.row.original.validation_phase) },
  { header: "健康", cell: (ctx) => numberText(ctx.row.original.strategy_health_score) },
];

function listText(value: unknown): string {
  if (!Array.isArray(value)) return text(value);
  const labels = value.map((item) => text(item, "")).filter(Boolean);
  return labels.length ? labels.join("、") : "--";
}

function safeValue(value: unknown): string {
  if (value === null || value === undefined) return "--";
  if (typeof value === "object") return "--";
  return text(value);
}

function dateText(value: unknown): string {
  const raw = text(value, "");
  if (!raw) return "--";
  return raw.length > 19 ? raw.slice(0, 19).replace("T", " ") : raw;
}
