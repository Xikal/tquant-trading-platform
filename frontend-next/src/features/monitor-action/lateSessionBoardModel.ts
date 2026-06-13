import { readArray, readRecord, text, numberText, pickFirst } from "../shared/dataAccess";

export type LateSessionState = "late_confirmed" | "late_watch" | "late_rejected" | "late_unavailable";
export type LateSessionSlot = "preview_1450" | "snapshot_1455" | "final_1457" | "latest";

export interface LateSessionBoardItem {
  raw: Record<string, unknown>;
  order: number;
  symbol: string;
  name: string;
  strategy: string;
  state: LateSessionState;
  stateLabel: string;
  score: string;
  reason: string;
  price: string;
  vwap: string;
  snapshotSlot: LateSessionSlot;
  riskTags: string[];
  rejectReasons: string[];
}

export interface LateSessionBoardModel {
  raw: Record<string, unknown>;
  slot: LateSessionSlot;
  slotLabel: string;
  status: string;
  statusText: string;
  generatedAt: string;
  degradationReason: string;
  degradationText: string;
  dataQualityTags: string[];
  items: LateSessionBoardItem[];
  confirmedCount: number;
  watchCount: number;
  isDegraded: boolean;
  emptyText: string;
}

export function createLateSessionBoardModel(data: unknown): LateSessionBoardModel {
  const raw = readRecord(data);
  const slot = normalizeSlot(text(raw.snapshot_slot, "latest"));
  const status = text(raw.status, "unavailable");
  const degradationReason = text(raw.degradation_reason, "");
  const items = readArray<Record<string, unknown>>(raw.items).map((item, order) => lateSessionItem(item, order, slot));
  const confirmedCount = items.filter((item) => item.state === "late_confirmed").length;
  const watchCount = items.filter((item) => item.state === "late_watch").length;
  return {
    raw,
    slot,
    slotLabel: lateSessionSlotLabel(slot),
    status,
    statusText: lateSessionStatusText(status),
    generatedAt: text(raw.generated_at, "--"),
    degradationReason,
    degradationText: degradationReasonText(degradationReason),
    dataQualityTags: readArray<string>(raw.data_quality_tags),
    items,
    confirmedCount,
    watchCount,
    isDegraded: status !== "ok" || Boolean(degradationReason),
    emptyText: emptyText(status, degradationReason),
  };
}

export function lateSessionSlotLabel(slot: string): string {
  const labels: Record<string, string> = {
    preview_1450: "14:50 预警",
    snapshot_1455: "14:55 快照",
    final_1457: "14:57 终版",
    latest: "最新尾盘",
  };
  return labels[slot] ?? "最新尾盘";
}

export function lateSessionStateLabel(state: string): string {
  const labels: Record<string, string> = {
    late_confirmed: "尾盘确认",
    late_watch: "尾盘观察",
    late_rejected: "不满足尾盘确认",
    late_unavailable: "数据不足",
  };
  return labels[state] ?? "尾盘观察";
}

function lateSessionItem(item: Record<string, unknown>, order: number, responseSlot: LateSessionSlot): LateSessionBoardItem {
  const state = normalizeState(text(item.late_session_state, "late_unavailable"));
  return {
    raw: item,
    order,
    symbol: text(pickFirst(item, ["symbol", "ts_code"])),
    name: text(pickFirst(item, ["name", "stock_name"]), ""),
    strategy: text(pickFirst(item, ["strategy_title", "strategy_name", "strategy_key"]), "综合"),
    state,
    stateLabel: lateSessionStateLabel(state),
    score: numberText(item.late_session_score, "--"),
    reason: text(item.late_session_reason, state === "late_unavailable" ? "数据不足，仅供观察。" : "等待后端尾盘确认。"),
    price: numberText(item.latest_price, "--"),
    vwap: numberText(item.vwap, "--"),
    snapshotSlot: normalizeSlot(text(item.snapshot_slot, responseSlot)),
    riskTags: readArray<string>(item.risk_tags),
    rejectReasons: readArray<string>(item.reject_reasons),
  };
}

function normalizeState(value: string): LateSessionState {
  if (value === "late_confirmed" || value === "late_watch" || value === "late_rejected" || value === "late_unavailable") return value;
  return "late_unavailable";
}

function normalizeSlot(value: string): LateSessionSlot {
  if (value === "preview_1450" || value === "snapshot_1455" || value === "final_1457" || value === "latest") return value;
  return "latest";
}

function lateSessionStatusText(status: string): string {
  if (status === "ok") return "正常";
  if (status === "partial_data") return "部分数据可用";
  if (status === "blocked") return "等待主榜";
  return "数据不足";
}

function degradationReasonText(reason: string): string {
  const labels: Record<string, string> = {
    blocked_by_materialization: "主榜尚未物化完成",
    quote_unavailable: "实时行情缺失",
    minute_data_missing: "分钟线缺失",
    vwap_unavailable: "VWAP 不可计算",
    market_context_missing: "市场状态缺失",
    partial_data: "部分数据可用",
    refresh_queued: "后台刷新中",
  };
  return labels[reason] ?? "";
}

function emptyText(status: string, reason: string): string {
  if (reason === "refresh_queued") return "尾盘榜暂无确认项，后台刷新中。";
  if (status === "blocked") return "尾盘榜暂无确认项，等待主榜物化完成。";
  if (status === "partial_data") return "尾盘榜暂无确认项，部分数据不足。";
  return "尾盘榜暂无确认项。";
}
