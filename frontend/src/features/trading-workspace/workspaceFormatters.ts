import type { LowBuyTradeLifecycle } from "../../types";
import { ALL_PLAYBOOK_TABS } from "./workspaceConstants";
import type { Tone } from "./workspaceTypes";

export function actionText(action: string): string {
  if (action === "positive_t") return "回踩可做正T";
  if (action === "negative_t") return "冲高可做反T";
  if (action === "hold") return "暂不操作";
  return action;
}

const PLAIN_TEXT_REPLACEMENTS: Array<[RegExp, string]> = [
  [/弱扩散防守/g, "指数可能被少数大票托住，多数个股跟不上，先防守观察"],
  [/权重护盘/g, "指数被权重大票托住，普通个股仍要谨慎"],
  [/缩量观望/g, "成交量不足，先等资金重新活跃"],
  [/轮动过快/g, "热点切换太快，避免追涨"],
  [/高位退潮/g, "高位股在退潮，先控制仓位"],
  [/风险释放/g, "市场还在释放风险，暂不急着加仓"],
  [/修复中/g, "情绪正在修复，只看强势票"],
  [/普涨扩散/g, "多数股票一起走强，可适当提高关注"],
  [/冲高钝化/g, "冲高后动力变弱，适合先锁定利润"],
  [/回踩承接/g, "回落时有人接盘，等重新走强再操作"],
  [/低开回踩/g, "低开后先看能否站回均价线"],
  [/放量滞涨/g, "成交放大但价格涨不动，警惕抛压"],
  [/假突破/g, "突破没有站稳，不要追高"],
  [/急跌修复/g, "急跌后反弹，先确认是否真正企稳"],
  [/缩量横盘/g, "成交清淡横盘，等方向明确"],
  [/分时回收/g, "盘中重新收回关键价位"],
  [/承接确认/g, "买盘承接已出现"],
  [/硬规则/g, "底线规则"],
  [/阻断/g, "暂时不允许操作"],
  [/降级/g, "降低仓位或只观察"],
  [/观望/g, "暂不操作"],
];

export function plainTradingText(value?: string | null): string {
  let text = (value ?? "").trim();
  if (!text) return "";
  for (const [pattern, replacement] of PLAIN_TEXT_REPLACEMENTS) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

export function strategyLabel(strategyKey: string): string {
  return ALL_PLAYBOOK_TABS.find((tab) => tab.key === strategyKey)?.label ?? strategyKey;
}

export function lifecycleStatusText(status: string): string {
  if (status === "planned") return "计划中";
  if (status === "entered") return "已买入";
  if (status === "holding") return "持仓中";
  if (status === "exited") return "已退出";
  if (status === "invalid") return "已失效";
  return status || "--";
}

export function executionStatusText(status: string): string {
  if (status === "filled") return "已成交";
  if (status === "not_filled") return "未成交";
  if (status === "invalid") return "无效";
  return status || "--";
}

export function summarizeLifecycle(items: LowBuyTradeLifecycle[]): string {
  if (!items.length) {
    return "--";
  }
  const planned = items.filter((item) => item.status === "planned").length;
  const holding = items.filter((item) => item.status === "holding" || item.status === "entered").length;
  const exited = items.filter((item) => item.status === "exited").length;
  return `计划 ${planned} / 持仓 ${holding} / 退出 ${exited}`;
}

export function riskText(level?: string): string {
  if (level === "low") return "低";
  if (level === "medium") return "中";
  if (level === "high") return "高";
  return "--";
}

export function riskTierText(level?: string): string {
  if (level === "block") return "阻断";
  if (level === "degrade") return "降级";
  if (level === "note") return "提示";
  return "正常";
}

export function riskLevelText(level: string): string {
  if (level === "block") return "阻断";
  if (level === "degrade") return "偏高";
  if (level === "note") return "注意";
  return "清晰";
}

export function toneFromChange(value?: number | null): Tone {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral";
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "neutral";
}

export function formatPrice(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value >= 100 ? value.toFixed(2) : value.toFixed(3);
}

export function formatPct(value?: number | null, digits = 2): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatNumber(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2);
}

export function formatAmount(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}亿`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(0)}万`;
  return value.toFixed(0);
}

export function parseNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function nullableNumber(value: string): number | null {
  const parsed = Number(value);
  return value.trim() && Number.isFinite(parsed) ? parsed : null;
}

export function shortTime(value?: string | null): string {
  if (!value) return "";
  const trimmed = value.trim();
  const normalized = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(trimmed)
    ? `${trimmed.replace(" ", "T")}+08:00`
    : trimmed;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return value.slice(11, 19);
  return parsed.toLocaleTimeString("zh-CN", { hour12: false, timeZone: "Asia/Shanghai" });
}

export function average(values: number[]): number {
  const finite = values.filter((value) => Number.isFinite(value));
  if (!finite.length) return 0;
  return finite.reduce((sum, value) => sum + value, 0) / finite.length;
}

export function readySummary(checks: Record<string, boolean>): string {
  const values = Object.values(checks);
  if (!values.length) return "--";
  const ready = values.filter(Boolean).length;
  return `${ready}/${values.length} 正常`;
}

export function normalizeLines(items: string[]): string[] {
  return items
    .flatMap((item) => String(item).split(/\r?\n/))
    .map((item) => item.replace(/^\s*[-*•]\s*/, "").replace(/^\s*\d+[.、)]\s*/, "").trim())
    .filter(Boolean);
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "请求失败";
}
