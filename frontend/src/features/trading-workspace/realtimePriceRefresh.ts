import type {
  LowBuyPriorityBoardItem,
  LowBuyPriorityBoardResult,
  LowBuyQuoteRefreshItem,
  SectorEtfT0Opportunity,
  SectorEtfT0Response,
  WatchlistQuoteItem,
  WatchlistSignal,
} from "../../types";

const REALTIME_REFRESH_TRADING_MS = 20_000;
const REALTIME_REFRESH_IDLE_MS = 5 * 60 * 1000;
const SHANGHAI_TIMEZONE = "Asia/Shanghai";

type ShanghaiPart = "weekday" | "hour" | "minute";

export function realtimePriceRefreshIntervalMs(now = new Date()): number {
  return isTradingSession(now) ? REALTIME_REFRESH_TRADING_MS : REALTIME_REFRESH_IDLE_MS;
}

export function shouldRefreshRealtimePrices(): boolean {
  return typeof document === "undefined" || document.visibilityState === "visible";
}

export function collectPrioritySymbolsByStrategy(
  items: LowBuyPriorityBoardItem[],
): Array<{ strategy: string; symbols: string[] }> {
  const groups = new Map<string, Set<string>>();
  for (const item of items) {
    const strategy = item.strategy_key?.trim();
    const symbol = item.symbol?.trim();
    if (!strategy || !symbol) {
      continue;
    }
    if (!groups.has(strategy)) {
      groups.set(strategy, new Set<string>());
    }
    groups.get(strategy)!.add(symbol);
  }
  return [...groups.entries()].map(([strategy, symbols]) => ({
    strategy,
    symbols: [...symbols],
  }));
}

export function applyPriorityBoardQuoteRefresh(
  payload: LowBuyPriorityBoardResult,
  quoteMap: Record<string, LowBuyQuoteRefreshItem>,
): LowBuyPriorityBoardResult {
  return {
    ...payload,
    items: payload.items.map((item) => applyPriorityItemQuote(item, quoteMap[item.symbol])),
    family_sections: payload.family_sections?.map((section) => ({
      ...section,
      items: section.items.map((item) => applyPriorityItemQuote(item, quoteMap[item.symbol])),
    })),
  };
}

export function applyWatchlistQuoteRefresh(
  signals: WatchlistSignal[],
  quotes: WatchlistQuoteItem[],
): WatchlistSignal[] {
  if (!signals.length || !quotes.length) {
    return signals;
  }
  const quoteMap = new Map(quotes.map((item) => [item.symbol, item]));
  return signals.map((signal) => {
    const quote = quoteMap.get(signal.symbol);
    if (!quote?.quote) {
      return signal;
    }
    return {
      ...signal,
      name: quote.name || signal.name,
      base_position: quote.base_position,
      available_position: quote.available_position,
      cost_basis: quote.cost_basis,
      memo: quote.memo,
      quote: quote.quote,
      error: quote.error ?? signal.error,
    };
  });
}

export function applySectorEtfQuoteRefresh(
  payload: SectorEtfT0Response,
  quoteMap: Record<string, LowBuyQuoteRefreshItem>,
): SectorEtfT0Response {
  return {
    ...payload,
    opportunities: payload.opportunities.map((item) => {
      const quote = quoteMap[item.etf_symbol];
      if (!quote) {
        return item;
      }
      return {
        ...item,
        last_price: quote.latest_price,
        change_pct: quote.change_pct,
        data_quality_text: quote.data_quality_text || item.data_quality_text,
      } satisfies SectorEtfT0Opportunity;
    }),
  };
}

function applyPriorityItemQuote(
  item: LowBuyPriorityBoardItem,
  quote?: LowBuyQuoteRefreshItem,
): LowBuyPriorityBoardItem {
  if (!quote) {
    return item;
  }
  return {
    ...item,
    latest_price: quote.latest_price,
    change_pct: quote.change_pct,
    quote_timestamp: quote.quote_timestamp,
    data_quality: quote.data_quality ?? item.data_quality,
    data_quality_text: quote.data_quality_text ?? item.data_quality_text,
    data_quality_tags: quote.data_quality_tags ?? item.data_quality_tags,
    suggested_position_pct: quote.suggested_position_pct ?? item.suggested_position_pct,
    suggested_position_text: quote.suggested_position_text ?? item.suggested_position_text,
    position_breakdown_text: quote.position_breakdown_text ?? item.position_breakdown_text,
    execution_quality_score: quote.execution_quality_score ?? item.execution_quality_score,
    execution_quality_text: quote.execution_quality_text ?? item.execution_quality_text,
    buy_signal_state: quote.buy_signal_state ?? item.buy_signal_state,
    buy_signal_text: quote.buy_signal_text ?? item.buy_signal_text,
    trigger_condition: quote.trigger_condition ?? item.trigger_condition,
    invalid_condition: quote.invalid_condition ?? item.invalid_condition,
    risk_tier: quote.risk_tier ?? item.risk_tier,
    next_watch_price: quote.next_watch_price ?? item.next_watch_price,
  };
}

function isTradingSession(now: Date): boolean {
  const weekday = shanghaiPart(now, "weekday");
  if (weekday === "Sat" || weekday === "Sun") {
    return false;
  }
  const hour = Number(shanghaiPart(now, "hour"));
  const minute = Number(shanghaiPart(now, "minute"));
  const minutes = hour * 60 + minute;
  return (minutes >= 570 && minutes < 690) || (minutes >= 780 && minutes < 900);
}

function shanghaiPart(now: Date, type: ShanghaiPart): string {
  return (
    new Intl.DateTimeFormat("en-US", {
      timeZone: SHANGHAI_TIMEZONE,
      hour12: false,
      weekday: type === "weekday" ? "short" : undefined,
      hour: type === "hour" ? "2-digit" : undefined,
      minute: type === "minute" ? "2-digit" : undefined,
    })
      .formatToParts(now)
      .find((part) => part.type === type)?.value || ""
  );
}
