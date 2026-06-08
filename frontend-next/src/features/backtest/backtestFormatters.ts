import { text } from "../shared/dataAccess";
import type { BacktestRecord } from "./backtestModel";

export function runStatus(run: BacktestRecord): "running" | "completed" | "other" {
  const value = String(run.status ?? "").toLowerCase();
  if (["running", "queued", "pending", "started"].includes(value)) return "running";
  if (["finished", "completed", "succeeded", "success", "done"].includes(value)) return "completed";
  return "other";
}

export function listLength(value: unknown): string {
  if (Array.isArray(value)) return String(value.length);
  return value ? "1" : "--";
}

export function dateRange(record: BacktestRecord): string {
  const start = text(record.start_date, "--");
  const end = text(record.end_date, "--");
  return `${start} ~ ${end}`;
}

export function dateText(value: unknown): string {
  const raw = text(value, "");
  return raw ? raw.slice(0, 10) : "--";
}

export function pct(value: unknown): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  const normalized = Math.abs(parsed) <= 1 ? parsed * 100 : parsed;
  return `${normalized >= 0 ? "+" : ""}${normalized.toFixed(2)}%`;
}

export function num(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString("zh-CN", { maximumFractionDigits: 3 }) : "--";
}

export function navValue(values: number[]): string {
  const value = values.at(-1);
  if (!Number.isFinite(value)) return "--";
  const first = values[0] || 1;
  return (Number(value) / first).toFixed(4);
}

export function sideKind(value: unknown): "buy" | "sell" | "other" {
  const raw = String(value ?? "").toLowerCase();
  if (raw.includes("buy") || raw.includes("买")) return "buy";
  if (raw.includes("sell") || raw.includes("卖")) return "sell";
  return "other";
}

export function sideText(value: unknown): string {
  const kind = sideKind(value);
  if (kind === "buy") return "买入";
  if (kind === "sell") return "卖出";
  return text(value);
}

export function exitKind(value: unknown): string {
  const raw = String(value ?? "").toLowerCase();
  if (raw.includes("take_profit") || raw.includes("止盈")) return "take_profit";
  if (raw.includes("stop_loss") || raw.includes("止损")) return "stop_loss";
  if (raw.includes("max_holding") || raw.includes("holding") || raw.includes("期满")) return "max_holding_days";
  return "other";
}

export function toneClass(value: unknown): string {
  const parsed = Number(String(value).replace("%", ""));
  if (!Number.isFinite(parsed)) return "";
  if (parsed > 0) return "is-up";
  if (parsed < 0) return "is-down";
  return "";
}
