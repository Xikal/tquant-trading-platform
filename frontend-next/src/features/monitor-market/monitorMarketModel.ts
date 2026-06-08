import type { ColumnDef } from "@tanstack/solid-table";
import { readArray, readRecord, text, numberText, pctText, pickFirst, nested } from "../shared/dataAccess";

export interface MarketPanelModel {
  root: Record<string, unknown>;
  snapshot: Record<string, unknown>;
  board: Record<string, unknown>;
  breadth: Record<string, unknown>;
  pulse: Record<string, unknown>;
  sectorStrength: Record<string, unknown>;
  sectorEtf: Record<string, unknown>;
  review: Record<string, unknown>;
  runtime: Record<string, unknown>;
  qualityMetrics: { label: string; value: string; tone?: "neutral" | "up" | "down" | "warn" }[];
  gateReasons: string[];
  breadthRows: Record<string, unknown>[];
  pulseRows: Record<string, unknown>[];
  sectorRows: Record<string, unknown>[];
  etfRows: Record<string, unknown>[];
  reviewRows: Record<string, unknown>[];
  runtimeRows: Record<string, unknown>[];
  breadthValues: number[];
}

export function createMonitorMarketModel(data: unknown): MarketPanelModel {
  const root = readRecord(data);
  const snapshot = readRecord(root.monitor_snapshot);
  const board = readRecord(snapshot.priority_board ?? root.priority_board);
  const breadth = readRecord(root.market_breadth ?? snapshot.market_breadth);
  const pulse = readRecord(root.market_pulse ?? snapshot.market_pulse);
  const sectorStrength = readRecord(root.market_sector_relative_strength ?? snapshot.sector_relative_strength ?? root.sector_relative_strength);
  const sectorEtf = readRecord(snapshot.sector_etf_t0 ?? root.sector_etf_t0 ?? root.etf_t0);
  const review = readRecord(root.review_summary ?? root.market_review ?? snapshot.market_review ?? root.review_status);
  const runtime = readRecord(root.runtime ?? root.instrument_sync_status ?? snapshot.instrument_sync_status);
  const breadthRows = normalizeRows(breadth.items ?? breadth.rows ?? breadth.distribution ?? snapshot.market_breadth_rows);
  const pulseRows = normalizeRows(pulse.items ?? pulse.rows ?? pulse.hourly ?? pulse.timeline);
  const sectorRows = normalizeRows(sectorStrength.items ?? sectorStrength.sectors ?? sectorStrength.rows ?? snapshot.sector_leaders);
  const etfRows = normalizeRows(sectorEtf.opportunities ?? sectorEtf.items ?? sectorEtf.rows);
  const reviewRows = [
    ...normalizeRows(review.items ?? review.reports),
    ...normalizeRows(root.review_reports),
    ...normalizeRows(snapshot.review_reports),
  ];
  const runtimeRows = normalizeRows(runtime.items ?? runtime.workers ?? runtime.tasks ?? root.runtime_tasks);

  return {
    root,
    snapshot,
    board,
    breadth,
    pulse,
    sectorStrength,
    sectorEtf,
    review,
    runtime,
    qualityMetrics: [
      { label: "市场状态", value: text(board.market_state_text ?? breadth.state_text) },
      { label: "市场火力", value: pctText(board.market_firepower_multiplier ?? 1) },
      { label: "上涨比例", value: pctText(board.stock_up_ratio ?? breadth.stock_up_ratio ?? breadth.up_ratio), tone: "up" },
      { label: "涨停数", value: text(board.limit_up_count ?? breadth.limit_up_count, "0") },
      { label: "跌停数", value: text(board.limit_down_count ?? breadth.limit_down_count, "0"), tone: "down" },
    ],
    gateReasons: readArray<string>(board.market_gate_reasons ?? breadth.market_gate_reasons ?? root.market_gate_reasons).slice(0, 8),
    breadthRows,
    pulseRows,
    sectorRows,
    etfRows,
    reviewRows,
    runtimeRows,
    breadthValues: chartValues(breadthRows, pulseRows, breadth, pulse),
  };
}

export const breadthColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "分组", cell: (ctx) => text(pickFirst(ctx.row.original, ["label", "name", "bucket", "time"])) },
  { header: "数量", cell: (ctx) => numberText(pickFirst(ctx.row.original, ["count", "value", "total"])) },
  { header: "比例", cell: (ctx) => pctText(pickFirst(ctx.row.original, ["ratio", "pct", "percent"])) },
];

export const pulseColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "时间", cell: (ctx) => text(pickFirst(ctx.row.original, ["time", "hour", "label"])) },
  { header: "上涨", cell: (ctx) => numberText(pickFirst(ctx.row.original, ["up_count", "up", "rise_count"])) },
  { header: "下跌", cell: (ctx) => numberText(pickFirst(ctx.row.original, ["down_count", "down", "fall_count"])) },
  { header: "强度", cell: (ctx) => pctText(pickFirst(ctx.row.original, ["strength", "ratio", "pulse"])) },
];

export const sectorColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "板块", cell: (ctx) => text(pickFirst(ctx.row.original, ["sector_name", "name", "sector"])) },
  { header: "龙头", cell: (ctx) => text(pickFirst(ctx.row.original, ["leader", "leader_symbol", "top_symbol"])) },
  { header: "相对强度", cell: (ctx) => pctText(pickFirst(ctx.row.original, ["relative_strength", "rs", "strength"])) },
  { header: "状态", cell: (ctx) => text(pickFirst(ctx.row.original, ["state", "status", "gate_status"])) },
];

export const etfColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "标的", cell: (ctx) => text(pickFirst(ctx.row.original, ["name", "symbol", "etf_name"])) },
  { header: "方向", cell: (ctx) => text(pickFirst(ctx.row.original, ["direction", "action", "side"])) },
  { header: "价差", cell: (ctx) => pctText(pickFirst(ctx.row.original, ["spread_pct", "premium_pct", "edge_pct"])) },
  { header: "说明", cell: (ctx) => text(pickFirst(ctx.row.original, ["reason", "summary", "edge_text"])) },
];

export const runtimeColumns: ColumnDef<Record<string, unknown>>[] = [
  { header: "项目", cell: (ctx) => text(pickFirst(ctx.row.original, ["name", "key", "worker", "task_type"])) },
  { header: "状态", cell: (ctx) => text(pickFirst(ctx.row.original, ["status", "state", "health"])) },
  { header: "更新时间", cell: (ctx) => text(pickFirst(ctx.row.original, ["updated_at", "last_run_at", "ts"])) },
];

export function gateTone(value: unknown): "neutral" | "up" | "down" | "warn" {
  const raw = String(value ?? "");
  if (raw.includes("block") || raw.includes("阻断")) return "down";
  if (raw.includes("reduce") || raw.includes("谨慎") || raw.includes("warning")) return "warn";
  if (raw.includes("pass") || raw.includes("正常") || raw.includes("ok")) return "up";
  return "neutral";
}

function normalizeRows(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) return value.filter((item) => item && typeof item === "object") as Record<string, unknown>[];
  const record = readRecord(value);
  return Object.entries(record).map(([key, raw]) => {
    const item = readRecord(raw);
    return Object.keys(item).length ? { key, ...item } : { key, value: raw };
  });
}

function chartValues(
  breadthRows: Record<string, unknown>[],
  pulseRows: Record<string, unknown>[],
  breadth: Record<string, unknown>,
  pulse: Record<string, unknown>,
): number[] {
  const source = [...pulseRows, ...breadthRows];
  const values = source
    .map((row) => Number(pickFirst(row, ["value", "ratio", "strength", "up_ratio", "pulse"])))
    .filter((value) => Number.isFinite(value))
    .map((value) => (value > 1 ? value : value * 100));
  if (values.length) return values.slice(0, 24);
  return [
    toPercentValue(pickFirst(breadth, ["stock_up_ratio", "up_ratio"])),
    toBoundedBarValue(breadth.limit_up_count, 80),
    toPercentValue(pickFirst(pulse, ["strength", "pulse_strength"])),
    toPercentValue(nested(pulse, "latest.up_ratio")),
    toPercentValue(nested(breadth, "quality_score")),
  ].filter((value) => Number.isFinite(value));
}

function toPercentValue(value: unknown): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return Number.NaN;
  return parsed > 1 ? parsed : parsed * 100;
}

function toBoundedBarValue(value: unknown, cap: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return Number.NaN;
  return Math.max(0, Math.min(cap, parsed));
}
