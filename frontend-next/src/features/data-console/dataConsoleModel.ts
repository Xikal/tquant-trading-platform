import type { ColumnDef } from "@tanstack/solid-table";
import { nested, numberText, pickFirst, readArray, readRecord, text } from "../shared/dataAccess";

export type DataConsoleRecord = Record<string, unknown>;

export function record(data: unknown): DataConsoleRecord {
  return readRecord(data);
}

export function coverageRows(data: unknown): DataConsoleRecord[] {
  const root = readRecord(data);
  const missingSymbols = readArray<DataConsoleRecord>(root.missing_symbols);
  if (missingSymbols.length) return missingSymbols;
  return root.dataset_key ? [root] : readArray<DataConsoleRecord>(root.items);
}

export function slaRows(data: unknown): DataConsoleRecord[] {
  const root = readRecord(data);
  return readArray<DataConsoleRecord>(root.items ?? root.sla ?? root.snapshots);
}

export function repairRows(data: unknown): DataConsoleRecord[] {
  const root = readRecord(data);
  return readArray<DataConsoleRecord>(root.latest_repair_audits ?? root.repair_audits ?? root.items);
}

export function taskRows(data: unknown): DataConsoleRecord[] {
  const root = readRecord(data);
  return readArray<DataConsoleRecord>(root.items ?? root.tasks ?? nested(root, "runtime.items"));
}

export function adminTaskRows(data: unknown): DataConsoleRecord[] {
  const root = readRecord(data);
  return readArray<DataConsoleRecord>(root.items ?? root.tasks ?? root.recent_tasks ?? nested(root, "runtime_tasks.items"));
}

export function workerRows(data: unknown): DataConsoleRecord[] {
  const root = readRecord(data);
  const candidates = [
    root.workers,
    root.worker_status,
    root.runtime_workers,
    nested(root, "workers.items"),
    nested(root, "runtime.workers"),
  ];
  for (const candidate of candidates) {
    const rows = readArray<DataConsoleRecord>(candidate);
    if (rows.length) return rows;
  }
  return [];
}

export function qualityMetrics(coverage: DataConsoleRecord, sla: DataConsoleRecord[]): { label: string; value: string; tone?: "neutral" | "up" | "down" | "warn" }[] {
  const staleCount = sla.filter((item) => item.stale === true || item.status === "stale" || item.status === "blocked").length;
  return [
    { label: "数据集", value: text(coverage.dataset_key) },
    { label: "范围", value: text(coverage.scope) },
    { label: "缺失代码", value: numberText(readArray(coverage.missing_symbols).length) },
    { label: "缺失日期", value: numberText(readArray(coverage.missing_dates).length) },
    { label: "SLA 项", value: numberText(sla.length) },
    { label: "异常 SLA", value: numberText(staleCount), tone: staleCount ? "warn" : "up" },
  ];
}

export function adminMetrics(data: unknown): { label: string; value: string; tone?: "neutral" | "up" | "down" | "warn" }[] {
  const root = readRecord(data);
  return [
    { label: "API", value: text(pickFirst(root, ["api_status", "status", "health"])) },
    { label: "源", value: text(pickFirst(root, ["data_source", "source", "provider"])) },
    { label: "任务", value: numberText(pickFirst(root, ["task_count", "tasks", "runtime_task_count"])) },
    { label: "Worker", value: numberText(pickFirst(root, ["worker_count", "workers", "runtime_worker_count"])) },
    { label: "失败", value: numberText(pickFirst(root, ["failed", "failed_count", "runtime_failed_count"])), tone: "warn" },
    { label: "延迟", value: numberText(pickFirst(root, ["latency_ms", "p95_ms", "oldest_queued_age_seconds"])) },
  ];
}

export const slaColumns: ColumnDef<DataConsoleRecord>[] = [
  { header: "数据集", cell: (ctx) => text(ctx.row.original.dataset_key) },
  { header: "范围", cell: (ctx) => text(ctx.row.original.scope) },
  { header: "日期", cell: (ctx) => text(ctx.row.original.as_of_date) },
  { header: "覆盖", cell: (ctx) => percentText(ctx.row.original.coverage_pct) },
  { header: "缺失", cell: (ctx) => numberText(ctx.row.original.missing_days) },
  { header: "异常", cell: (ctx) => numberText(ctx.row.original.invalid_rows) },
  { header: "状态", cell: (ctx) => text(ctx.row.original.status) },
  { header: "阻断", cell: (ctx) => listText(ctx.row.original.blockers) },
];

export const coverageColumns: ColumnDef<DataConsoleRecord>[] = [
  { header: "代码/数据集", cell: (ctx) => text(ctx.row.original.symbol ?? ctx.row.original.dataset_key) },
  { header: "名称/范围", cell: (ctx) => text(ctx.row.original.name ?? ctx.row.original.scope) },
  { header: "缺失天数", cell: (ctx) => numberText(ctx.row.original.missing_days ?? readArray(ctx.row.original.missing_dates).length) },
  { header: "缺失日期", cell: (ctx) => listText(ctx.row.original.missing_dates) },
];

export const taskColumns: ColumnDef<DataConsoleRecord>[] = [
  { header: "任务", cell: (ctx) => text(ctx.row.original.id ?? ctx.row.original.task_id) },
  { header: "类型", cell: (ctx) => text(ctx.row.original.task_type ?? ctx.row.original.type) },
  { header: "状态", cell: (ctx) => text(ctx.row.original.status) },
  { header: "进度", cell: (ctx) => percentText(Number(ctx.row.original.progress_pct ?? 0) / 100) },
  { header: "优先级", cell: (ctx) => numberText(ctx.row.original.priority) },
  { header: "更新时间", cell: (ctx) => dateText(ctx.row.original.updated_at ?? ctx.row.original.created_at) },
  { header: "错误", cell: (ctx) => text(ctx.row.original.error_message) },
];

export const workerColumns: ColumnDef<DataConsoleRecord>[] = [
  { header: "Worker", cell: (ctx) => text(ctx.row.original.worker_id ?? ctx.row.original.id) },
  { header: "组件", cell: (ctx) => text(ctx.row.original.component ?? ctx.row.original.name) },
  { header: "状态", cell: (ctx) => text(ctx.row.original.status) },
  { header: "运行任务", cell: (ctx) => numberText(ctx.row.original.running_task_count ?? ctx.row.original.task_count) },
  { header: "心跳", cell: (ctx) => numberText(ctx.row.original.heartbeat_age_seconds) },
  { header: "更新时间", cell: (ctx) => dateText(ctx.row.original.heartbeat_updated_at ?? ctx.row.original.updated_at) },
];

export const repairColumns: ColumnDef<DataConsoleRecord>[] = [
  { header: "修复", cell: (ctx) => text(ctx.row.original.repair_id ?? ctx.row.original.id) },
  { header: "数据集", cell: (ctx) => text(ctx.row.original.dataset_key) },
  { header: "删除行", cell: (ctx) => numberText(ctx.row.original.deleted_rows_count) },
  { header: "伪造", cell: (ctx) => text(ctx.row.original.fabricated) },
  { header: "操作人", cell: (ctx) => text(ctx.row.original.operator) },
  { header: "时间", cell: (ctx) => dateText(ctx.row.original.created_at) },
  { header: "原因", cell: (ctx) => text(ctx.row.original.reason ?? ctx.row.original.refetch_result) },
];

function listText(value: unknown): string {
  if (!Array.isArray(value)) return text(value);
  const labels = value.map((item) => text(item, "")).filter(Boolean);
  if (!labels.length) return "--";
  return labels.slice(0, 4).join("、") + (labels.length > 4 ? ` 等 ${labels.length} 项` : "");
}

function dateText(value: unknown): string {
  const raw = text(value, "");
  if (!raw) return "--";
  return raw.length > 19 ? raw.slice(0, 19).replace("T", " ") : raw;
}

function percentText(value: unknown): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  const normalized = Math.abs(parsed) > 1 ? parsed : parsed * 100;
  return `${normalized.toFixed(0)}%`;
}
