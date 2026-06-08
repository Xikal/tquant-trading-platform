import type { ColumnDef } from "@tanstack/solid-table";
import type { ShadowActionField } from "../../shared/ui/ShadowActionPanel";
import { readArray, readRecord, text, numberText, pickFirst, nested } from "../shared/dataAccess";

export type BacktestRecord = Record<string, unknown>;

export function backtestRunId(run: BacktestRecord): string {
  return text(pickFirst(run, ["id", "run_id"]), "");
}

export function extractRuns(data: unknown): BacktestRecord[] {
  const root = readRecord(data);
  return readArray<BacktestRecord>(root.items ?? root.runs);
}

export function extractDetail(data: unknown): BacktestRecord {
  return readRecord(data);
}

export function extractEquityPoints(data: unknown): BacktestRecord[] {
  const root = readRecord(data);
  return readArray<BacktestRecord>(root.items ?? root.points ?? root.equity ?? root.curve ?? nested(root, "result.equity"));
}

export function extractTradeRows(data: unknown): BacktestRecord[] {
  const root = readRecord(data);
  return readArray<BacktestRecord>(root.items ?? root.trades ?? nested(root, "result.trades"));
}

export function equityValues(points: BacktestRecord[]): number[] {
  const values = points
    .map((point) => Number(pickFirst(point, ["equity", "total_equity", "value", "nav", "portfolio_value"])))
    .filter((value) => Number.isFinite(value));
  return downsample(values, 40);
}

export function runMetrics(detail: BacktestRecord): { label: string; value: string; tone?: "neutral" | "up" | "down" | "warn" }[] {
  const result = readRecord(detail.result);
  const summary = readRecord(detail.summary);
  return [
    { label: "状态", value: text(detail.status) },
    { label: "进度", value: percentText(Number(detail.progress_pct ?? 0) / 100) },
    { label: "初始资金", value: numberText(pickFirst(detail, ["initial_cash", "initial_capital"])) },
    { label: "最终权益", value: numberText(pickFirst(detail, ["final_equity", "ending_equity"])) },
    { label: "收益率", value: percentText(pickFirst(summary, ["total_return", "total_return_pct"]) ?? pickFirst(result, ["total_return", "total_return_pct"])) },
    { label: "最大回撤", value: percentText(pickFirst(summary, ["max_drawdown", "max_drawdown_pct"]) ?? pickFirst(result, ["max_drawdown", "max_drawdown_pct"])), tone: "warn" },
    { label: "PF", value: numberText(pickFirst(summary, ["profit_factor", "pf"]) ?? pickFirst(result, ["profit_factor", "pf"])) },
    { label: "胜率", value: percentText(pickFirst(summary, ["win_rate", "win_rate_pct"]) ?? pickFirst(result, ["win_rate", "win_rate_pct"])) },
  ];
}

export function detailPairs(detail: BacktestRecord): { label: string; value: string }[] {
  return [
    { label: "名称", value: text(detail.name) },
    { label: "策略", value: listText(detail.strategy_keys ?? detail.strategies ?? detail.strategy_key) },
    { label: "区间", value: `${text(detail.start_date)} ~ ${text(detail.end_date)}` },
    { label: "基准", value: text(detail.benchmark_symbol ?? detail.benchmark) },
    { label: "数据版本", value: text(detail.data_version) },
    { label: "策略版本", value: text(detail.strategy_version) },
    { label: "引擎", value: text(detail.engine_version) },
    { label: "资源", value: text(detail.resource_tier) },
    { label: "滑点 bps", value: numberText(detail.slippage_bps) },
    { label: "排队", value: queueText(detail) },
    { label: "创建", value: dateText(detail.created_at) },
    { label: "完成", value: dateText(detail.finished_at) },
    { label: "错误", value: text(detail.error_message) },
  ];
}

export const runColumns: ColumnDef<BacktestRecord>[] = [
  { header: "编号", cell: (ctx) => text(ctx.row.original.id ?? ctx.row.original.run_id) },
  { header: "名称", cell: (ctx) => text(ctx.row.original.name) },
  { header: "状态", cell: (ctx) => text(ctx.row.original.status) },
  { header: "策略", cell: (ctx) => listText(ctx.row.original.strategy_keys ?? ctx.row.original.strategies ?? ctx.row.original.strategy_key) },
  { header: "区间", cell: (ctx) => `${text(ctx.row.original.start_date)} ~ ${text(ctx.row.original.end_date)}` },
  { header: "权益", cell: (ctx) => numberText(ctx.row.original.final_equity) },
  { header: "创建", cell: (ctx) => dateText(ctx.row.original.created_at) },
];

export const tradeColumns: ColumnDef<BacktestRecord>[] = [
  { header: "时间", cell: (ctx) => dateText(pickFirst(ctx.row.original, ["trade_date", "date", "created_at", "timestamp"])) },
  { header: "代码", cell: (ctx) => text(ctx.row.original.symbol) },
  { header: "方向", cell: (ctx) => text(ctx.row.original.side ?? ctx.row.original.action) },
  { header: "数量", cell: (ctx) => numberText(ctx.row.original.quantity ?? ctx.row.original.shares) },
  { header: "价格", cell: (ctx) => numberText(ctx.row.original.price ?? ctx.row.original.fill_price) },
  { header: "收益", cell: (ctx) => percentText(ctx.row.original.return_pct ?? ctx.row.original.pnl_pct) },
  { header: "原因", cell: (ctx) => text(ctx.row.original.reason ?? ctx.row.original.signal) },
];

export function backtestSubmitFields(): ShadowActionField[] {
  return [
    { key: "name", label: "名称", value: "研究回测" },
    { key: "strategy", label: "策略", value: "N形洗盘低吸" },
    { key: "start", label: "开始日期", value: "2025-01-01" },
    { key: "end", label: "结束日期", value: "2026-06-05" },
    { key: "capital", label: "初始资金", value: "100000" },
    { key: "benchmark", label: "基准", value: "000300" },
    { key: "data_version", label: "数据版本", value: "default" },
    { key: "strategy_version", label: "策略版本", value: "stable" },
    { key: "fee_model_version", label: "费率模型", value: "cn-a-share-v1" },
  ];
}

export function taskControlFields(runId: string): ShadowActionField[] {
  return [
    { key: "run_id", label: "任务编号", value: runId || "手工输入" },
    { key: "reason", label: "原因", value: "前端观察取消" },
  ];
}

export function researchFields(runId: string): ShadowActionField[] {
  return [
    { key: "run_id", label: "任务编号", value: runId || "手工输入" },
    { key: "target", label: "目标", value: "profit_factor" },
    { key: "mode", label: "模式", value: "样本外验证" },
  ];
}

function downsample(values: number[], limit: number): number[] {
  if (values.length <= limit) return values;
  const step = (values.length - 1) / (limit - 1);
  return Array.from({ length: limit }, (_, index) => values[Math.round(index * step)]);
}

function listText(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => text(item, "")).filter(Boolean).join("、") || "--";
  return text(value);
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

function queueText(detail: BacktestRecord): string {
  const position = text(detail.queue_position, "");
  const depth = text(detail.queue_depth, "");
  if (!position && !depth) return "--";
  return `位置 ${position || "--"} / 深度 ${depth || "--"}`;
}
