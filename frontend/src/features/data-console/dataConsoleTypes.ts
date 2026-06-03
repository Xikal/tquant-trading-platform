import type {
  DataQualityCoverageResponse,
  DataQualitySlaResponse,
  DataQualitySnapshotItem,
  RuntimeFallbackStatus,
  TradeDataGateResponse,
} from "../../api/dataQuality";
import type { InstrumentInspectorResponse } from "../../api/dataConsoleInspector";
import type { RuntimeTaskOut } from "../../api/runtimeTasks";
import type { DataSourceProbeResponse } from "../../types";

export type DataConsoleStatus = "ok" | "warn" | "blocked";

export interface DataConsoleSummary {
  status: DataConsoleStatus;
  conclusion: string;
  total: number;
  blocked: number;
  stale: number;
  missing: number;
  checkedAt: string;
}

export interface DataConsoleData {
  sla: DataQualitySlaResponse | null;
  sourceHealth: DataSourceProbeResponse | null;
  coverage: DataQualityCoverageResponse | null;
  tasks: RuntimeTaskOut[];
  inspector: InstrumentInspectorResponse | null;
  gate: TradeDataGateResponse | null;
  runtimeFallback: RuntimeFallbackStatus | null;
}

export interface DataConsoleActions {
  refreshSla: () => Promise<void>;
  refreshSources: () => Promise<void>;
  refreshCoverage: (next?: { dataset_key: string; scope: string }) => Promise<void>;
  refreshTasks: () => Promise<void>;
  refreshGate: () => Promise<void>;
  refreshRuntimeFallback: () => Promise<void>;
  refreshAll: () => Promise<void>;
  syncInstruments: () => Promise<void>;
  refreshCloseData: () => Promise<void>;
  backfill: () => Promise<void>;
  repairDryRun: () => Promise<void>;
  repairApply: () => Promise<void>;
  inspectSymbol: () => Promise<void>;
}

export function buildDataConsoleSummary(items: DataQualitySnapshotItem[]): DataConsoleSummary {
  const blocked = items.filter((item) => criticalStatus(item.status)).length;
  const stale = items.filter((item) => item.stale || item.status === "stale").length;
  const missing = items.reduce((total, item) => total + Number(item.missing_days || 0), 0);
  const checkedValues = items.map((item) => item.checked_at || item.as_of_date).filter(Boolean).sort();
  const checkedAt = checkedValues[checkedValues.length - 1] ?? "--";
  const status: DataConsoleStatus = blocked > 0 ? "blocked" : stale > 0 || missing > 0 ? "warn" : "ok";
  return {
    status,
    conclusion: conclusionText(status),
    total: items.length,
    blocked,
    stale,
    missing,
    checkedAt,
  };
}

export function criticalStatus(status: string): boolean {
  return ["fail", "blocked_by_data", "unavailable", "missing"].includes(status);
}

export function conclusionText(status: DataConsoleStatus): string {
  if (status === "blocked") return "关键数据不可用，先暂停使用";
  if (status === "warn") return "部分数据待更新，使用前先确认";
  return "数据正常，可以使用";
}

export function gateTone(gate: TradeDataGateResponse | null): DataConsoleStatus {
  if (!gate) return "warn";
  if (gate.checks.some((item) => item.severity === "red")) return "blocked";
  if (gate.checks.some((item) => item.severity === "yellow")) return "warn";
  return "ok";
}

const STATUS_LABELS: Record<string, string> = {
  ok: "正常",
  stale: "待更新",
  fail: "异常",
  blocked_by_data: "缺数据已停用",
  unavailable: "取不到",
  missing: "缺失",
  warn: "注意",
  partial: "部分可用",
};

const QUALITY_LABELS: Record<string, string> = {
  ok: "正常",
  realtime: "正常",
  degraded: "质量下降",
  stale: "偏旧",
  failed: "不可用",
  partial: "部分可用",
  missing: "缺失",
};

const SEVERITY_LABELS: Record<string, string> = {
  green: "通过",
  yellow: "注意",
  red: "不通过",
};

const TASK_STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  running: "进行中",
  succeeded: "已完成",
  failed: "失败",
};

const DATASET_LABELS: Record<string, string> = {
  daily_bars: "日线",
  minute_bars: "分钟线",
  tick_trades: "逐笔成交",
  instruments: "标的库",
};

const SCOPE_LABELS: Record<string, string> = {
  all: "全市场",
  production_universe: "交易标的池",
  watchlist: "我的自选",
};

const TASK_TYPE_LABELS: Record<string, string> = {
  daily_bar_refresh: "拉取今日收盘数据",
  data_quality_backfill: "补历史数据",
  data_quality_repair: "数据修复",
  data_repair_run: "数据修复",
  instrument_sync: "更新标的库",
  sync_instruments: "更新标的库",
  data_quality_sla_refresh: "数据状态检查",
};

const REPAIR_REASON_LABELS: Record<string, string> = {
  invalid_rows: "异常行",
  duplicate_rows: "重复行",
  missing: "缺失",
  stale: "待更新",
};

const TEXT_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bminute_bars_partial\b/g, "分钟线部分缺失"],
  [/\bdaily_bars\b/g, DATASET_LABELS.daily_bars],
  [/\bminute_bars\b/g, DATASET_LABELS.minute_bars],
  [/\btick_trades\b/g, DATASET_LABELS.tick_trades],
  [/\binstruments\b/g, DATASET_LABELS.instruments],
  [/\bproduction_universe\b/g, SCOPE_LABELS.production_universe],
  [/\bwatchlist\b/g, SCOPE_LABELS.watchlist],
  [/\bblocked_by_data\b/g, STATUS_LABELS.blocked_by_data],
  [/\bunavailable\b/g, STATUS_LABELS.unavailable],
  [/\bmissing\b/g, STATUS_LABELS.missing],
  [/\bstale\b/g, STATUS_LABELS.stale],
  [/\bdegraded\b/g, QUALITY_LABELS.degraded],
  [/\bfailed\b/g, TASK_STATUS_LABELS.failed],
  [/\bqueued\b/g, TASK_STATUS_LABELS.queued],
  [/\brunning\b/g, TASK_STATUS_LABELS.running],
  [/\bsucceeded\b/g, TASK_STATUS_LABELS.succeeded],
  [/\binvalid_rows\b/g, REPAIR_REASON_LABELS.invalid_rows],
  [/\bduplicate_rows\b/g, REPAIR_REASON_LABELS.duplicate_rows],
  [/\bok\b/g, STATUS_LABELS.ok],
  [/source offline/gi, "数据源离线"],
];

export function statusLabel(status: string | null | undefined): string {
  return labelFrom(STATUS_LABELS, status);
}

export function qualityLabel(quality: string | null | undefined): string {
  return labelFrom(QUALITY_LABELS, quality);
}

export function severityLabel(severity: string | null | undefined): string {
  return labelFrom(SEVERITY_LABELS, severity);
}

export function taskStatusLabel(status: string | null | undefined): string {
  return labelFrom(TASK_STATUS_LABELS, status);
}

export function datasetLabel(dataset: string | null | undefined): string {
  return labelFrom(DATASET_LABELS, dataset);
}

export function scopeLabel(scope: string | null | undefined): string {
  return labelFrom(SCOPE_LABELS, scope);
}

export function taskTypeLabel(taskType: string | null | undefined): string {
  return labelFrom(TASK_TYPE_LABELS, taskType);
}

export function repairReasonLabel(reason: string | null | undefined): string {
  return labelFrom(REPAIR_REASON_LABELS, reason);
}

export function booleanLabel(value: boolean | null | undefined): string {
  if (value === true) return "是";
  if (value === false) return "否";
  return "--";
}

export function dataConsoleText(value: string | null | undefined): string {
  const text = String(value || "--");
  return TEXT_REPLACEMENTS.reduce((next, [pattern, replacement]) => next.replace(pattern, replacement), text);
}

function labelFrom(labels: Record<string, string>, value: string | null | undefined): string {
  const key = String(value || "");
  if (!key) return "--";
  return labels[key] ?? dataConsoleText(key);
}
