import type { ColumnDef } from "@tanstack/solid-table";
import type { Accessor } from "solid-js";
import type { ApiOperationName, OperationPathOptions } from "../../shared/api/operations";
import { readArray, readRecord, text } from "../shared/dataAccess";

export type TrackingRecord = Record<string, unknown>;
export type ViewMode = "research" | "production";
export type AnalysisTab = "performance" | "holding" | "drift" | "diagnostics" | "review";

export interface FiltersState {
  mode: ViewMode;
  status: string;
  signalState: string;
  strategyKey: string;
  keyword: string;
  needsReview: "all" | "yes" | "no";
  boardFilter: "include_all" | "main_only";
}

export interface StrategyQueries {
  workspace: OperationDataState;
  items: OperationDataState;
  summary: OperationDataState;
  performance: OperationDataState;
  holding: OperationDataState;
  review: OperationDataState;
  journal: OperationDataState;
  relativeStrength: OperationDataState;
  detail: OperationDataState;
}

export interface OperationDataState {
  data: Accessor<unknown>;
  pending: Accessor<boolean>;
  error: Accessor<Error | null>;
}

export interface OperationConfig {
  name: ApiOperationName;
  options?: OperationPathOptions;
}

export interface DriftDisplayRow {
  label: string;
  value: string;
  status: string;
  tone: "green" | "blue" | "amber" | "slate" | "red";
  hasData: boolean;
}

export type TableColumn = ColumnDef<TrackingRecord> & {
  meta?: {
    mobileHidden?: boolean;
  };
};

export function recordsFrom(...values: unknown[]): TrackingRecord[] {
  for (const value of values) {
    const direct = readArray<TrackingRecord>(value);
    if (direct.length) return direct;
    const record = readRecord(value);
    const keys = ["items", "tracking_items", "review_queue", "needs_review_items", "performance", "journal_entries"];
    for (const key of keys) {
      const nested = readArray<TrackingRecord>(record[key]);
      if (nested.length) return nested;
    }
  }
  return [];
}

export function firstRecord(...values: unknown[]): TrackingRecord {
  for (const value of values) {
    const record = readRecord(value);
    if (Object.keys(record).length) return record;
  }
  return {};
}

export function field(record: TrackingRecord, keys: string[], fallback = "--"): string {
  return text(firstValue(record, keys), fallback);
}

export function raw(record: TrackingRecord, keys: string[]): unknown {
  return firstValue(record, keys);
}

export function idOf(record: TrackingRecord, index = 0): string {
  return field(record, ["id", "item_id", "tracking_id", "review_key", "symbol"], `row-${index}`);
}

export function symbolOf(record: TrackingRecord): string {
  return field(record, ["symbol", "stock_code", "ticker"]);
}

export function nameOf(record: TrackingRecord): string {
  return field(record, ["name", "stock_name", "display_name"], "");
}

export function strategyOf(record: TrackingRecord): string {
  return field(record, ["strategy_name", "strategy_key", "strategy"]);
}

export function numericText(record: TrackingRecord, keys: string[], suffix = "", fallback = "--"): string {
  const value = firstValue(record, keys);
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return field(record, keys, fallback);
  return `${numeric.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}${suffix}`;
}

export function pctValue(value: unknown, fallback = "--"): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return text(value, fallback);
  const normalized = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
  return `${normalized.toFixed(1)}%`;
}

export function buildDriftRows(reviewPayload: TrackingRecord): DriftDisplayRow[] {
  const slippage = firstValue(reviewPayload, ["slippage_pct", "avg_slippage_pct", "slippage_cost_pct", "drift.slippage_pct"]);
  const latency = firstValue(reviewPayload, ["latency_ms", "avg_latency_ms", "signal_latency_ms", "drift.latency_ms"]);
  const latencyText = firstValue(reviewPayload, ["latency_text", "avg_latency", "drift.latency_text"]);
  const consistency = firstValue(reviewPayload, ["order_consistency", "shadow_consistency", "order_consistency_pct", "drift.order_consistency"]);
  return [
    metricRow("均化滑点损失", slippage, formatPctMetric, "slippage_status", reviewPayload, driftStatus(slippage, "slippage")),
    metricRow("实盘信号响应延时", latency ?? latencyText, formatLatencyMetric, "latency_status", reviewPayload, driftStatus(latency ?? latencyText, "latency")),
    metricRow("时序排序一致性", consistency, formatPctMetric, "order_consistency_status", reviewPayload, driftStatus(consistency, "consistency")),
  ];
}

export function boolValue(record: TrackingRecord, keys: string[]): boolean | undefined {
  const value = firstValue(record, keys);
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    if (["true", "1", "yes"].includes(value.toLowerCase())) return true;
    if (["false", "0", "no"].includes(value.toLowerCase())) return false;
  }
  return undefined;
}

export function chips(record: TrackingRecord, keys: string[], limit = 4): string[] {
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) return value.map((item) => text(item)).filter((item) => item !== "--").slice(0, limit);
    if (typeof value === "string" && value.trim()) return value.split(",").map((item) => item.trim()).filter(Boolean).slice(0, limit);
  }
  return [];
}

export function toneFromRecord(record: TrackingRecord): "neutral" | "up" | "down" | "warn" | "danger" | undefined {
  if (boolValue(record, ["stop_triggered", "abnormal_return"])) return "danger";
  if (boolValue(record, ["needs_review"])) return "warn";
  const returnValue = Number(raw(record, ["current_return_pct", "return_pct", "avg_current_return_pct"]));
  if (Number.isFinite(returnValue)) {
    if (returnValue > 0) return "up";
    if (returnValue < 0) return "down";
  }
  return undefined;
}

export function safeJsonPreview(value: unknown): string {
  if (value === null || value === undefined || value === "") return "--";
  if (typeof value !== "object") return text(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "--";
  }
}

export function filterItems(items: TrackingRecord[], filters: FiltersState): TrackingRecord[] {
  const keyword = filters.keyword.trim().toLowerCase();
  return items.filter((item) => {
    if (filters.status && !matchesAny(item, ["lifecycle_status", "status", "user_friendly_status"], filters.status)) return false;
    if (filters.signalState && !matchesAny(item, ["signal_state", "signal_status"], filters.signalState)) return false;
    if (filters.strategyKey && !matchesAny(item, ["strategy_key", "strategy_name", "strategy"], filters.strategyKey)) return false;
    if (filters.needsReview === "yes" && boolValue(item, ["needs_review"]) !== true) return false;
    if (filters.needsReview === "no" && boolValue(item, ["needs_review"]) === true) return false;
    if (filters.boardFilter === "main_only" && !isMainBoard(item)) return false;
    if (keyword && !searchText(item).includes(keyword)) return false;
    return true;
  });
}

export function uniqueOptions(items: TrackingRecord[], keys: string[]): string[] {
  const values = new Set<string>();
  items.forEach((item) => {
    const value = field(item, keys, "");
    if (value) values.add(value);
  });
  return [...values].sort((a, b) => a.localeCompare(b, "zh-CN"));
}

export function calloutClass(tone?: "up" | "down" | "warn" | "danger" | "neutral"): string {
  return `strategy-tracking-callout${tone ? ` strategy-tracking-callout--${tone}` : ""}`;
}

function firstValue(record: TrackingRecord, keys: string[]): unknown {
  for (const key of keys) {
    const value = readPath(record, key);
    if (value !== null && value !== undefined && value !== "") return value;
  }
  return undefined;
}

function metricRow(
  label: string,
  value: unknown,
  formatter: (value: unknown) => string,
  statusKey: string,
  record: TrackingRecord,
  derived: { status: string; tone: DriftDisplayRow["tone"] },
): DriftDisplayRow {
  const hasData = hasMetricValue(value);
  return {
    label,
    value: hasData ? formatter(value) : "--",
    status: hasData ? text(record[statusKey], derived.status) : "暂无数据",
    tone: hasData ? derived.tone : "slate",
    hasData,
  };
}

function hasMetricValue(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return false;
  if (typeof value === "string") return value.trim() !== "";
  return Number.isFinite(Number(value));
}

function formatPctMetric(value: unknown): string {
  return pctValue(value, "--");
}

function formatLatencyMetric(value: unknown): string {
  if (typeof value === "string" && value.trim()) return value;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  if (Math.abs(numeric) >= 1000) return `${(numeric / 1000).toFixed(2)} 秒`;
  return `${numeric.toFixed(0)} ms`;
}

function driftStatus(value: unknown, kind: "slippage" | "latency" | "consistency"): { status: string; tone: DriftDisplayRow["tone"] } {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return { status: "按后端数据", tone: "blue" };
  const normalizedPct = Math.abs(numeric) <= 1 ? Math.abs(numeric) * 100 : Math.abs(numeric);
  if (kind === "slippage") {
    if (normalizedPct <= 0.2) return { status: "可观察", tone: "green" };
    if (normalizedPct <= 0.8) return { status: "需复核", tone: "amber" };
    return { status: "漂移偏高", tone: "red" };
  }
  if (kind === "latency") {
    if (numeric <= 500) return { status: "响应正常", tone: "green" };
    if (numeric <= 1500) return { status: "需观察", tone: "amber" };
    return { status: "延时偏高", tone: "red" };
  }
  const ratio = Math.abs(numeric) <= 1 ? numeric : numeric / 100;
  if (ratio >= 0.98) return { status: "一致性稳定", tone: "green" };
  if (ratio >= 0.9) return { status: "需观察", tone: "amber" };
  return { status: "一致性偏弱", tone: "red" };
}

function readPath(record: TrackingRecord, key: string): unknown {
  return key.split(".").reduce<unknown>((current, part) => readRecord(current)[part], record);
}

function matchesAny(record: TrackingRecord, keys: string[], expected: string): boolean {
  const normalized = expected.toLowerCase();
  return keys.some((key) => field(record, [key], "").toLowerCase() === normalized);
}

function isMainBoard(record: TrackingRecord): boolean {
  const board = field(record, ["board_type", "board", "board_name"], "").toLowerCase();
  if (!board) return true;
  return board.includes("main") || board.includes("主板");
}

function searchText(record: TrackingRecord): string {
  return [
    symbolOf(record),
    nameOf(record),
    strategyOf(record),
    field(record, ["plain_language_summary", "review_text", "reason", "user_friendly_reason"], ""),
  ].join(" ").toLowerCase();
}
