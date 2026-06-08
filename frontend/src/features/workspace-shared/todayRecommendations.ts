import type {
  LowBuyCandidate,
  LowBuyPriorityBoardItem,
  LowBuyPriorityBoardResult,
  LowBuyScreenerResult,
} from "../../types";

const CONFIRMED_RECOMMENDATION_STATES = new Set(["buy_now", "soft_buy_now"]);

export function beijingTodayString(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const year = parts.find((part) => part.type === "year")?.value ?? "";
  const month = parts.find((part) => part.type === "month")?.value ?? "";
  const day = parts.find((part) => part.type === "day")?.value ?? "";
  return year && month && day ? `${year}-${month}-${day}` : "";
}

export function normalizeTradeDate(value?: string | null): string {
  const cleaned = String(value ?? "").trim();
  if (!cleaned) {
    return "";
  }
  const compact = cleaned.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (compact) {
    return `${compact[1]}-${compact[2]}-${compact[3]}`;
  }
  const separated = cleaned.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (!separated) {
    return "";
  }
  return [
    separated[1],
    separated[2].padStart(2, "0"),
    separated[3].padStart(2, "0"),
  ].join("-");
}

export function isBeijingTodayTradeDate(value?: string | null, now: Date = new Date()): boolean {
  return normalizeTradeDate(value) === beijingTodayString(now);
}

export function isCurrentPublishedTradeDate(
  latestTradeDate?: string | null,
  expectedTradeDate?: string | null,
  stale?: boolean | null,
  now: Date = new Date(),
): boolean {
  const latest = normalizeTradeDate(latestTradeDate);
  const expected = normalizeTradeDate(expectedTradeDate);
  if (!latest) {
    return false;
  }
  if (stale === true) {
    return false;
  }
  if (latest && expected) {
    return latest === expected;
  }
  if (stale === false) {
    return true;
  }
  return isBeijingTodayTradeDate(latest, now);
}

export function isConfirmedRecommendationState(value?: string | null): boolean {
  return CONFIRMED_RECOMMENDATION_STATES.has(String(value ?? ""));
}

export function isTodayPriorityBoard(board: LowBuyPriorityBoardResult | null, now: Date = new Date()): boolean {
  return Boolean(board && isCurrentPublishedTradeDate(
    board.latest_trade_date,
    board.latest_available_trade_date,
    board.stale,
    now,
  ));
}

export function filterTodayConfirmedPriorityItems(
  board: LowBuyPriorityBoardResult | null,
  now: Date = new Date(),
): LowBuyPriorityBoardItem[] {
  if (!isTodayPriorityBoard(board, now)) {
    return [];
  }
  return (board?.items ?? []).filter((item) => isConfirmedRecommendationState(item.buy_signal_state));
}

export function countTodayConfirmedPriorityItems(
  board: LowBuyPriorityBoardResult | null,
  now: Date = new Date(),
): number {
  return filterTodayConfirmedPriorityItems(board, now).length;
}

export function filterTodayConfirmedCandidates(
  playbook: LowBuyScreenerResult | null,
  now: Date = new Date(),
): LowBuyCandidate[] {
  if (!playbook || !isCurrentPublishedTradeDate(playbook.latest_trade_date, null, playbook.stale, now)) {
    return [];
  }
  return uniqueBySymbol([
    ...(playbook.confirmed_candidates ?? []),
    ...(playbook.candidates ?? []),
  ].filter((item) => isConfirmedRecommendationState(item.buy_signal_state)));
}

function uniqueBySymbol<T extends { symbol?: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (!item.symbol || seen.has(item.symbol)) {
      return false;
    }
    seen.add(item.symbol);
    return true;
  });
}
