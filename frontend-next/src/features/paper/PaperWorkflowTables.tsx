import type { ColumnDef } from "@tanstack/solid-table";
import { StatusPill, type StatusPillTone } from "../../shared/ui/StatusPill";
import { readRecord, text } from "../shared/dataAccess";

export const orderColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "时间", cell: (ctx) => text(ctx.row.original.created_at) },
  { header: "代码", cell: (ctx) => text(ctx.row.original.symbol) },
  { header: "方向", cell: (ctx) => text(ctx.row.original.side) },
  { header: "类型", cell: (ctx) => text(ctx.row.original.order_type) },
  { header: "数量", cell: (ctx) => <span class="tnum">{text(ctx.row.original.quantity)}</span> },
  { header: "价格", cell: (ctx) => <span class="tnum">{text(ctx.row.original.price ?? ctx.row.original.avg_fill_price)}</span> },
  { header: "状态", cell: (ctx) => <StatusPill label="订单" value={text(ctx.row.original.status)} tone={orderTone(ctx.row.original.status)} /> },
  { header: "来源", cell: (ctx) => text(ctx.row.original.source) },
];

export const tradeColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "时间", cell: (ctx) => text(ctx.row.original.trade_time) },
  { header: "代码", cell: (ctx) => text(ctx.row.original.symbol) },
  { header: "方向", cell: (ctx) => text(ctx.row.original.side) },
  { header: "数量", cell: (ctx) => <span class="tnum">{text(ctx.row.original.quantity)}</span> },
  { header: "价格", cell: (ctx) => <span class="tnum">{text(ctx.row.original.price)}</span> },
  { header: "净额", cell: (ctx) => <span class="tnum">{text(ctx.row.original.net_amount)}</span> },
  { header: "策略", cell: (ctx) => text(ctx.row.original.strategy_key) },
  { header: "原因", cell: (ctx) => text(ctx.row.original.entry_reason ?? ctx.row.original.exit_reason) },
];

export const riskColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "状态", cell: (ctx) => <StatusPill label="风险" value={text(ctx.row.original.status)} tone={riskTone(ctx.row.original.status)} /> },
  { header: "代码", cell: (ctx) => text(ctx.row.original.symbol) },
  { header: "类型", cell: (ctx) => text(ctx.row.original.event_type ?? ctx.row.original.type) },
  { header: "级别", cell: (ctx) => text(ctx.row.original.severity ?? ctx.row.original.level) },
  { header: "说明", cell: (ctx) => text(ctx.row.original.message ?? ctx.row.original.reason ?? ctx.row.original.detail) },
];

export const autoRunColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "时间", cell: (ctx) => text(ctx.row.original.created_at) },
  { header: "类型", cell: (ctx) => text(ctx.row.original.run_type) },
  { header: "状态", cell: (ctx) => <StatusPill label="运行" value={text(ctx.row.original.status)} tone={runTone(ctx.row.original.status)} /> },
  { header: "Provider", cell: (ctx) => text(ctx.row.original.provider) },
  { header: "摘要", cell: (ctx) => text(readRecord(ctx.row.original.response).summary ?? ctx.row.original.error_message) },
];

export const stockPnlColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "代码", cell: (ctx) => text(ctx.row.original.symbol) },
  { header: "名称", cell: (ctx) => text(ctx.row.original.name) },
  { header: "当前数量", cell: (ctx) => <span class="tnum">{text(ctx.row.original.current_quantity)}</span> },
  { header: "已实现", cell: (ctx) => <span class={metricClass(ctx.row.original.realized_pnl)}>{moneyText(ctx.row.original.realized_pnl)}</span> },
  { header: "浮动盈亏", cell: (ctx) => <span class={metricClass(ctx.row.original.unrealized_pnl)}>{moneyText(ctx.row.original.unrealized_pnl)}</span> },
  { header: "总盈亏", cell: (ctx) => <span class={metricClass(ctx.row.original.total_pnl)}>{moneyText(ctx.row.original.total_pnl)}</span> },
  { header: "回放", cell: (ctx) => text(ctx.row.original.replay_complete, "--") },
];

export function moneyText(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) : "--";
}

export function pctField(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${parsed.toFixed(2)}%` : "--";
}

export function metricTone(value: unknown): "neutral" | "up" | "down" | "warn" {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed === 0) return "neutral";
  return parsed > 0 ? "up" : "down";
}

export function metricClass(value: unknown): string {
  const tone = metricTone(value);
  if (tone === "up") return "tnum price-up";
  if (tone === "down") return "tnum price-down";
  return "tnum price-flat";
}

function orderTone(status: unknown): StatusPillTone {
  if (status === "filled") return "up";
  if (status === "rejected" || status === "cancelled") return "warn";
  return "neutral";
}

function riskTone(status: unknown): StatusPillTone {
  const value = text(status, "").toLowerCase();
  if (value.includes("解决") || value === "closed") return "up";
  if (value.includes("open") || value.includes("异常")) return "warn";
  return "neutral";
}

function runTone(status: unknown): StatusPillTone {
  if (status === "succeeded") return "up";
  if (status === "failed") return "warn";
  if (status === "running") return "info";
  return "neutral";
}
