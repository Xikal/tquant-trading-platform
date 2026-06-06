export type DataFreshnessStatus = "ok" | "waiting" | "stale" | "degraded" | "blocked" | "no_data";
export type DataFreshnessTone = "up" | "warn" | "down" | "neutral";

export interface DataFreshnessInput {
  status?: string | null;
  stale?: boolean | null;
  staleReason?: string | null;
  dataQuality?: string | null;
  latestTradeDate?: string | null;
  expectedTradeDate?: string | null;
  detail?: string | null;
  missingCount?: number | null;
}

export interface DataFreshnessView {
  status: DataFreshnessStatus;
  tone: DataFreshnessTone;
  title: string;
  detail: string;
  tradeDateText: string;
  reviewOnly: boolean;
}

export function buildDataFreshnessView(input: DataFreshnessInput): DataFreshnessView {
  const tradeDateText = buildTradeDateText(input.latestTradeDate, input.expectedTradeDate);
  if (input.stale || input.dataQuality === "stale") {
    return {
      status: "stale",
      tone: "warn",
      title: "数据已过期，仅供复盘",
      detail: input.staleReason || input.detail || "当前展示最近可用快照，不作为今日观察依据。",
      tradeDateText,
      reviewOnly: true,
    };
  }
  if (input.status === "blocked" || input.dataQuality === "blocked") {
    return {
      status: "blocked",
      tone: "down",
      title: "数据暂不可用",
      detail: input.detail || "数据链路未满足生成条件。",
      tradeDateText,
      reviewOnly: true,
    };
  }
  if (input.status === "no_data" || input.dataQuality === "no_data") {
    return {
      status: "no_data",
      tone: "neutral",
      title: "暂无可用数据",
      detail: input.detail || "等待数据生成后再展示。",
      tradeDateText,
      reviewOnly: true,
    };
  }
  if (input.status === "degraded" || input.dataQuality === "degraded" || input.dataQuality === "partial") {
    return {
      status: "degraded",
      tone: "warn",
      title: "数据部分降级",
      detail: input.detail || "主链路可用，部分辅助数据暂缺。",
      tradeDateText,
      reviewOnly: false,
    };
  }
  if ((input.missingCount ?? 0) > 0) {
    return {
      status: "waiting",
      tone: "warn",
      title: "策略快照待补齐",
      detail: input.detail || "日线已满足要求，仍需重建部分策略快照。",
      tradeDateText,
      reviewOnly: false,
    };
  }
  if (input.status === "success" && sameDate(input.latestTradeDate, input.expectedTradeDate)) {
    return {
      status: "ok",
      tone: "up",
      title: "数据已更新",
      detail: input.detail || "当前数据可用于今日观察。",
      tradeDateText,
      reviewOnly: false,
    };
  }
  return {
    status: "waiting",
    tone: "neutral",
    title: "等待最新数据发布",
    detail: input.detail || "数据检查通过后会自动发布给前端使用。",
    tradeDateText,
    reviewOnly: false,
  };
}

function buildTradeDateText(latest?: string | null, expected?: string | null): string {
  if (latest && expected) return `${latest} / 目标 ${expected}`;
  return latest || expected || "--";
}

function sameDate(latest?: string | null, expected?: string | null): boolean {
  return Boolean(latest && expected && latest === expected);
}
