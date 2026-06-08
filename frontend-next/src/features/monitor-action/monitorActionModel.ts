import type { ColumnDef } from "@tanstack/solid-table";
import { createMemo } from "solid-js";
import { readArray, readRecord, text, numberText, pctText, pickFirst } from "../shared/dataAccess";
import type { StockCardItem } from "../../shared/ui/StockCard";

export type MonitorLane = "all" | "buy_now" | "observe" | "risk";

export interface MonitorPriorityItem {
  raw: Record<string, unknown>;
  order: number;
  symbol: string;
  name: string;
  strategy: string;
  lane: MonitorLane;
  price: string;
  change: string;
  score: string;
  action: string;
  risk: string;
  summary: string;
  position: string;
  keyLevel: string;
  badges: string[];
}

export interface MonitorActionModel {
  root: Record<string, unknown>;
  snapshot: Record<string, unknown>;
  board: Record<string, unknown>;
  priorityItems: MonitorPriorityItem[];
  watchItems: MonitorPriorityItem[];
  positions: Record<string, unknown>[];
  selected: () => MonitorPriorityItem | undefined;
  metrics: { label: string; value: string; tone?: "neutral" | "up" | "down" | "warn" }[];
  laneOptions: { value: MonitorLane; label: string; disabled?: boolean }[];
  laneItems: (lane: MonitorLane) => MonitorPriorityItem[];
  orderHash: string;
  aiInsight: string;
  keyLevels: Record<string, unknown>;
  runtime: Record<string, unknown>;
  dataQuality: Record<string, unknown>;
  stockCard: (item: MonitorPriorityItem) => StockCardItem;
}

export function createMonitorActionModel(data: unknown, selectedSymbol: () => string | undefined): MonitorActionModel {
  const root = readRecord(data);
  const snapshot = readRecord(root.monitor_snapshot);
  const board = readRecord(snapshot.priority_board ?? root.priority_board);
  const priorityItems = priorityBoardRecords(board, root).map(priorityItem);
  const watchSource = readArray<Record<string, unknown>>(
    snapshot.watchlist_signals ?? root.watchlist_signals ?? root.watchlist ?? snapshot.watchlist,
  );
  const watchItems = watchSource.map((item, index) => priorityItem(item, index));
  const positions = readArray<Record<string, unknown>>(root.positions ?? snapshot.positions ?? root.paper_positions);
  const keyLevels = readRecord(root.stock_key_levels ?? snapshot.stock_key_levels ?? snapshot.key_levels);
  const runtime = readRecord(root.runtime ?? snapshot.runtime ?? root.instrument_sync_status);
  const dataQuality = readRecord(root.data_quality ?? snapshot.data_quality ?? board.data_quality);
  const selected = createMemo(() => {
    const symbol = selectedSymbol();
    return priorityItems.find((item) => item.symbol === symbol) ?? priorityItems[0] ?? watchItems[0];
  });

  return {
    root,
    snapshot,
    board,
    priorityItems,
    watchItems,
    positions,
    selected,
    metrics: [
      { label: "立即处理", value: text(board.immediate_count ?? laneCount(priorityItems, "buy_now"), "0"), tone: "up" },
      { label: "观察数量", value: text(board.focus_count ?? board.track_count ?? watchItems.length, "0") },
      { label: "市场火力", value: pctText(board.market_firepower_multiplier, "--"), tone: board.market_gate_decision === "block" ? "down" : "neutral" },
      { label: "总候选", value: text(board.total_candidates, String(priorityItems.length)) },
    ],
    laneOptions: [
      { value: "all", label: `全部 ${priorityItems.length}` },
      { value: "buy_now", label: `立即 ${laneCount(priorityItems, "buy_now")}` },
      { value: "observe", label: `观察 ${laneCount(priorityItems, "observe")}` },
      { value: "risk", label: `风险 ${laneCount(priorityItems, "risk")}` },
    ],
    laneItems: (lane) => (lane === "all" ? priorityItems : priorityItems.filter((item) => item.lane === lane)),
    orderHash: priorityItems.map((item) => item.symbol).join(">"),
    aiInsight: text(
      pickFirst(board, [
        "plain_language_summary",
        "ai_summary",
        "ai_interpretation",
        "board_interpretation",
        "action_summary",
        "summary",
      ]),
      "--",
    ),
    keyLevels,
    runtime,
    dataQuality,
    stockCard: priorityStockCard,
  };
}

function priorityBoardRecords(board: Record<string, unknown>, root: Record<string, unknown>): Record<string, unknown>[] {
  const direct = readArray<Record<string, unknown>>(board.items);
  if (direct.length) return direct;

  const familyItems = readArray<Record<string, unknown>>(board.family_sections).flatMap((section) =>
    readArray<Record<string, unknown>>(readRecord(section).items),
  );
  if (familyItems.length) return familyItems;

  const bucketItems = readArray<Record<string, unknown>>(board.simple_buckets).flatMap((bucket) => {
    const bucketRecord = readRecord(bucket);
    const explicitItems = readArray<Record<string, unknown>>(bucketRecord.items ?? bucketRecord.candidates ?? bucketRecord.rows);
    if (explicitItems.length) return explicitItems;
    const bucketKey = text(bucketRecord.key, "");
    const bucketTitle = text(bucketRecord.title, bucketKey || "候选");
    return readArray<string | number>(bucketRecord.symbols).map((symbol) => ({
      symbol,
      simple_bucket: bucketKey,
      simple_bucket_text: bucketTitle,
      buy_signal_text: bucketTitle,
      action_summary: text(bucketRecord.description, ""),
    }));
  });
  if (bucketItems.length) return bucketItems;

  return readArray<Record<string, unknown>>(root.priority_items);
}

export const positionColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "代码", cell: (ctx) => text(pickFirst(ctx.row.original, ["symbol", "ts_code"])) },
  { header: "名称", cell: (ctx) => text(pickFirst(ctx.row.original, ["name", "stock_name"])) },
  { header: "持仓", cell: (ctx) => numberText(pickFirst(ctx.row.original, ["quantity", "shares", "volume"])) },
  { header: "成本", cell: (ctx) => numberText(pickFirst(ctx.row.original, ["cost_price", "avg_cost", "price"])) },
  { header: "盈亏", cell: (ctx) => pctText(pickFirst(ctx.row.original, ["pnl_pct", "profit_pct", "return_pct"])) },
];

export const keyLevelColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "类型", cell: (ctx) => text(pickFirst(ctx.row.original, ["type", "level_type", "name"])) },
  { header: "价格", cell: (ctx) => numberText(pickFirst(ctx.row.original, ["price", "level", "value"])) },
  { header: "说明", cell: (ctx) => text(pickFirst(ctx.row.original, ["label", "reason", "summary"])) },
];

export function priorityRowsForTable(items: MonitorPriorityItem[]): Record<string, unknown>[] {
  return items.map((item) => ({
    order: item.order + 1,
    symbol: item.symbol,
    name: item.name,
    strategy: item.strategy,
    action: item.action,
    score: item.score,
    risk: item.risk,
  }));
}

export const priorityColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "序", cell: (ctx) => numberText(ctx.row.original.order), enableSorting: false },
  { header: "标的", cell: (ctx) => `${text(ctx.row.original.name, "")} ${text(ctx.row.original.symbol)}`, enableSorting: false },
  { header: "策略", cell: (ctx) => text(ctx.row.original.strategy), enableSorting: false },
  { header: "动作", cell: (ctx) => text(ctx.row.original.action), enableSorting: false },
  { header: "分", cell: (ctx) => text(ctx.row.original.score), enableSorting: false },
  { header: "风险", cell: (ctx) => text(ctx.row.original.risk), enableSorting: false },
];

export function keyLevelRows(levels: Record<string, unknown>, selected?: MonitorPriorityItem): Record<string, unknown>[] {
  const direct = readArray<Record<string, unknown>>(levels.items ?? levels.levels ?? levels.key_levels);
  if (direct.length) return direct;
  const support = pickFirst(selected?.raw ?? {}, ["support_price", "support", "buy_price"]);
  const pressure = pickFirst(selected?.raw ?? {}, ["pressure_price", "pressure", "target_price"]);
  const stop = pickFirst(selected?.raw ?? {}, ["stop_loss_price", "stop_loss", "risk_price"]);
  return [
    { type: "支撑", price: support, summary: "接近后观察承接" },
    { type: "压力", price: pressure, summary: "接近后看量价确认" },
    { type: "止损", price: stop, summary: "跌破后降低观察优先级" },
  ].filter((row) => row.price !== undefined && row.price !== null && row.price !== "");
}

export function marketGateTone(value: unknown): "neutral" | "up" | "down" | "warn" {
  const raw = String(value ?? "");
  if (raw.includes("block") || raw.includes("阻断")) return "down";
  if (raw.includes("reduce") || raw.includes("谨慎")) return "warn";
  if (raw.includes("pass") || raw.includes("正常")) return "up";
  return "neutral";
}

function priorityItem(item: Record<string, unknown>, index: number): MonitorPriorityItem {
  const action = text(pickFirst(item, ["buy_signal_text", "next_action_text", "signal_state", "action_text", "action"]), "观察");
  const risk = text(pickFirst(item, ["risk_text", "risk_tier", "data_quality_text", "blocked_reason", "exclusion_reason", "risk_level"]), "");
  const lane = classifyLane(action, risk, item);
  return {
    raw: item,
    order: index,
    symbol: text(pickFirst(item, ["symbol", "ts_code"])),
    name: text(pickFirst(item, ["name", "stock_name", "display_name"]), ""),
    strategy: text(
      pickFirst(item, ["strategy_title", "strategy_name", "strategy", "strategy_key", "strategy_family_text", "strategy_family", "strategy_variant", "family"]),
      "综合",
    ),
    lane,
    price: text(pickFirst(item, ["latest_price", "price", "current_price"]), "--"),
    change: text(pickFirst(item, ["change_pct", "pct_chg", "changeText"]), ""),
    score: text(pickFirst(item, ["production_score", "score", "priority_score"]), "--"),
    action,
    risk,
    summary: text(pickFirst(item, ["plain_language_summary", "reason", "action_summary", "strategy_notes"]), ""),
    position: text(pickFirst(item, ["suggested_position_text", "position_breakdown_text", "position_text"]), ""),
    keyLevel: text(pickFirst(item, ["key_level_text", "support_pressure_text", "entry_level_text"]), ""),
    badges: readArray<string>(item.warning_tags ?? item.tags ?? item.badges).slice(0, 5),
  };
}

function classifyLane(action: string, risk: string, item: Record<string, unknown>): MonitorLane {
  const rawLane = String(
    pickFirst(item, ["lane", "bucket", "priority_lane", "simple_bucket", "buy_signal_state", "display_lane", "production_decision"]) ?? "",
  ).toLowerCase();
  const raw = `${rawLane} ${action} ${risk}`.toLowerCase();
  if (raw.includes("risk") || raw.includes("avoid") || raw.includes("block") || raw.includes("give_up") || raw.includes("风险") || raw.includes("放弃")) return "risk";
  if (raw.includes("buy") || raw.includes("立即") || raw.includes("production")) return "buy_now";
  if (raw.includes("watch") || raw.includes("observe") || raw.includes("wait") || raw.includes("near_entry") || raw.includes("观察") || raw.includes("等待")) return "observe";
  return "observe";
}

function laneCount(items: MonitorPriorityItem[], lane: MonitorLane): number {
  return items.filter((item) => item.lane === lane).length;
}

function priorityStockCard(item: MonitorPriorityItem): StockCardItem {
  return {
    symbol: item.symbol,
    name: item.name,
    priceText: item.price,
    changeText: item.change,
    scoreText: item.score,
    actionText: item.action,
    riskText: item.risk,
    details: [item.summary, item.position, item.keyLevel].filter(Boolean).join(" · "),
    badges: item.badges,
  };
}
