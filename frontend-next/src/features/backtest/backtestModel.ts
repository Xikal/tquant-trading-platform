import type { ColumnDef } from "@tanstack/solid-table";
import type { ShadowActionField } from "../../shared/ui/ShadowActionPanel";
import { readArray, readRecord, text, numberText, pickFirst, nested } from "../shared/dataAccess";

export type BacktestRecord = Record<string, unknown>;

export interface BacktestStrategyOption {
  key: string;
  label: string;
  tier: string;
}

export interface BacktestAttributionDisplayRow {
  label: string;
  signal: number;
  trades: number;
  winRate: number | null;
  tone: string;
}

export interface BacktestLogDisplayRow {
  time: string;
  level: string;
  message: string;
  source: string;
  tone: string;
}

export interface BacktestOosDisplayRow {
  state: string;
  range: string;
  confidence: string;
  note: string;
  tone: string;
}

export interface ExecutionAssumptionRow {
  label: string;
  value: string;
}

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

export function backtestSubmitFields(defaults: {
  name?: unknown;
  strategy?: unknown;
  start?: unknown;
  end?: unknown;
  capital?: unknown;
  benchmark?: unknown;
  dataVersion?: unknown;
  strategyVersion?: unknown;
  feeModelVersion?: unknown;
} = {}): ShadowActionField[] {
  return [
    { key: "name", label: "名称", value: text(defaults.name, "frontend-next research backtest") },
    { key: "strategy", label: "策略", value: text(defaults.strategy, "") },
    { key: "start", label: "开始日期", value: text(defaults.start, "") },
    { key: "end", label: "结束日期", value: text(defaults.end, "") },
    { key: "capital", label: "初始资金", value: text(defaults.capital, "") },
    { key: "benchmark", label: "基准", value: text(defaults.benchmark, "") },
    { key: "data_version", label: "数据版本", value: text(defaults.dataVersion, "") },
    { key: "strategy_version", label: "策略版本", value: text(defaults.strategyVersion, "") },
    { key: "fee_model_version", label: "费率模型", value: text(defaults.feeModelVersion, "") },
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

export function strategyOptionsFromMeta(meta: unknown, runs: BacktestRecord[] = []): BacktestStrategyOption[] {
  const root = readRecord(meta);
  const fromMeta = readArray<Record<string, unknown>>(root.strategies)
    .filter((item) => item.enabled !== false && text(item.visibility, "full") !== "hidden")
    .sort((left, right) => Number(left.sort_order ?? 0) - Number(right.sort_order ?? 0))
    .map((item) => ({
      key: text(item.key, ""),
      label: text(item.display_name ?? item.name ?? item.key, ""),
      tier: text(item.tier ?? item.category_key, ""),
    }))
    .filter((item) => item.key && item.label);
  if (fromMeta.length) return uniqueStrategyOptions(fromMeta);

  const fromRuns = runs.flatMap((run) => strategyKeys(run.strategy_keys ?? run.strategies ?? run.strategy_key)).map((key) => ({
    key,
    label: key,
    tier: "from_backtest_run",
  }));
  return uniqueStrategyOptions(fromRuns);
}

export function attributionRowsFromDetail(detail: BacktestRecord): BacktestAttributionDisplayRow[] {
  const attribution = readRecord(detail.attribution ?? nested(detail, "result.attribution") ?? nested(detail, "result.metrics.attribution"));
  return [
    ...attributionBucketRows("行业", readArray<Record<string, unknown>>(attribution.industry), "indigo"),
    ...attributionBucketRows("市场", readArray<Record<string, unknown>>(attribution.market_state), "amber"),
    ...attributionBucketRows("数据", readArray<Record<string, unknown>>(attribution.data_quality), "slate"),
  ].slice(0, 8);
}

export function logRowsFromDetail(detail: BacktestRecord): BacktestLogDisplayRow[] {
  const rawRows = readArray<Record<string, unknown>>(detail.logs)
    .concat(readArray<Record<string, unknown>>(detail.events))
    .concat(readArray<Record<string, unknown>>(nested(detail, "result.logs")))
    .concat(readArray<Record<string, unknown>>(nested(detail, "result.events")));
  if (rawRows.length) {
    return rawRows.slice(0, 4).map((row) => ({
      time: shortTime(pickFirst(row, ["time", "timestamp", "created_at", "updated_at"])),
      level: text(pickFirst(row, ["level", "status", "kind"]), "INFO").toUpperCase(),
      message: text(pickFirst(row, ["message", "detail", "summary", "note"]), "--"),
      source: text(pickFirst(row, ["source", "component"]), "BACKTEST"),
      tone: logTone(pickFirst(row, ["level", "status", "kind"])),
    }));
  }
  const notes = readArray<string>(nested(detail, "result_quality.notes"))
    .concat(readArray<string>(nested(detail, "attribution.notes")))
    .concat(readArray<string>(nested(detail, "result.notes")));
  return notes.slice(0, 4).map((note) => ({
    time: shortTime(detail.updated_at ?? detail.finished_at ?? detail.created_at),
    level: "INFO",
    message: text(note),
    source: "BACKTEST",
    tone: "blue",
  }));
}

export function oosRowsFromDetail(detail: BacktestRecord): BacktestOosDisplayRow[] {
  const rows = readArray<Record<string, unknown>>(detail.validation_windows)
    .concat(readArray<Record<string, unknown>>(detail.oos_windows))
    .concat(readArray<Record<string, unknown>>(nested(detail, "result.validation_windows")))
    .concat(readArray<Record<string, unknown>>(nested(detail, "result.oos_windows")))
    .concat(readArray<Record<string, unknown>>(nested(detail, "result.walk_forward_windows")));
  return rows.slice(0, 8).map((row) => ({
    state: text(pickFirst(row, ["market_state", "regime", "state", "segment"]), "未标注"),
    range: `${text(pickFirst(row, ["oos_start", "validation_start", "test_start", "start_date", "start"]), "--")} ~ ${text(pickFirst(row, ["oos_end", "validation_end", "test_end", "end_date", "end"]), "--")}`,
    confidence: text(pickFirst(row, ["confidence", "score", "oos_score", "test_sharpe"]), "--"),
    note: text(pickFirst(row, ["note", "notes", "summary", "verdict", "gate_reason"]), "后端样本外窗口"),
    tone: oosTone(pickFirst(row, ["verdict", "status", "passed", "oos_failed"])),
  }));
}

export function executionAssumptionRows(detail: BacktestRecord): ExecutionAssumptionRow[] {
  const assumptions = readRecord(detail.execution_assumptions ?? nested(detail, "result.execution_assumptions") ?? nested(detail, "metrics.execution_assumptions"));
  const feeModel = readRecord(assumptions.fee_model);
  const slippageModel = readRecord(assumptions.slippage_model);
  const explicitRows = [
    { label: "费率模型", value: text(feeModel.version ?? assumptions.fee_model_version, "") },
    { label: "佣金", value: text(feeModel.commission ?? feeModel.commission_text, "") },
    { label: "印花税", value: text(feeModel.stamp_tax ?? feeModel.stamp_tax_text, "") },
    { label: "过户费", value: text(feeModel.transfer_fee ?? feeModel.transfer_fee_text, "") },
    { label: "滑点模型", value: text(slippageModel.version ?? slippageModel.name ?? assumptions.slippage_model_version, "") },
    { label: "执行假设来源", value: text(assumptions.source, "") },
  ].filter((row) => row.value);
  if (explicitRows.length) return explicitRows;

  const params = readRecord(detail.params);
  return [
    { label: "单笔最大仓位", value: text(params.max_position_pct ?? detail.max_position_pct, "--") },
    { label: "双向滑点 (bp)", value: text(detail.slippage_bps ?? params.slippage_bps, "--") },
    { label: "费率模型", value: text(detail.fee_model_version ?? params.fee_model_version, "--") },
  ];
}

function attributionBucketRows(group: string, rows: Record<string, unknown>[], tone: string): BacktestAttributionDisplayRow[] {
  return rows.map((row) => ({
    label: `${group}: ${text(row.label ?? row.bucket, "--")}`,
    signal: Number(pickFirst(row, ["signal_count", "signals", "candidate_count"]) ?? 0),
    trades: Number(pickFirst(row, ["trade_count", "filled_order_count", "trades"]) ?? 0),
    winRate: numericOrNull(pickFirst(row, ["win_rate_pct", "win_rate"])),
    tone,
  }));
}

function strategyKeys(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => text(item, "")).filter(Boolean);
  return text(value, "").split(/[,\n，、]/).map((item) => item.trim()).filter(Boolean);
}

function uniqueStrategyOptions(items: BacktestStrategyOption[]): BacktestStrategyOption[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.key)) return false;
    seen.add(item.key);
    return true;
  });
}

function numericOrNull(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function shortTime(value: unknown): string {
  const raw = text(value, "");
  if (!raw) return "--";
  const match = raw.match(/\d{2}:\d{2}:\d{2}/);
  return match?.[0] ?? raw.slice(0, 19).replace("T", " ");
}

function logTone(value: unknown): string {
  const raw = text(value, "").toLowerCase();
  if (raw.includes("warn")) return "amber";
  if (raw.includes("error") || raw.includes("fail")) return "red";
  if (raw.includes("succ") || raw.includes("done")) return "green";
  return "blue";
}

function oosTone(value: unknown): string {
  if (value === true) return "green";
  if (value === false) return "amber";
  const raw = text(value, "").toLowerCase();
  if (raw.includes("pass") || raw.includes("success")) return "green";
  if (raw.includes("block") || raw.includes("fail")) return "red";
  if (raw.includes("observe") || raw.includes("warn")) return "amber";
  return "blue";
}
