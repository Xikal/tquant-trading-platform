import type {
  LowBuyCandidate,
  LowBuyHistoryResult,
  LowBuyQuoteRefreshItem,
  LowBuyScreenerResult,
} from "../../types";

const CONFIRMED_STATES = new Set<LowBuyCandidate["buy_signal_state"]>(["buy_now", "soft_buy_now"]);

export function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function formatSignedPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function isInLowBuyZone(candidate: LowBuyCandidate) {
  return candidate.latest_price >= candidate.entry_zone_low && candidate.latest_price <= candidate.entry_zone_high;
}

export function applyQuoteRefresh(candidate: LowBuyCandidate, quote?: LowBuyQuoteRefreshItem) {
  if (!quote) {
    return candidate;
  }
  return {
    ...candidate,
    latest_price: quote.latest_price,
    change_pct: quote.change_pct,
    quote_timestamp: quote.quote_timestamp,
    data_source: quote.data_source ?? candidate.data_source,
    source_quality: quote.source_quality ?? candidate.source_quality,
    is_stale: quote.is_stale ?? candidate.is_stale,
    entry_distance_pct: quote.distance_to_entry_pct,
    suggested_position_pct: quote.suggested_position_pct,
    suggested_position_text: quote.suggested_position_text,
    position_breakdown_text: quote.position_breakdown_text ?? candidate.position_breakdown_text,
    execution_quality_score: quote.execution_quality_score ?? candidate.execution_quality_score,
    execution_quality_text: quote.execution_quality_text ?? candidate.execution_quality_text,
    buy_signal_state: quote.buy_signal_state,
    buy_signal_text: quote.buy_signal_text,
    buy_signal_hint: quote.buy_signal_hint,
    trigger_condition: quote.trigger_condition ?? candidate.trigger_condition,
    invalid_condition: quote.invalid_condition ?? candidate.invalid_condition,
    risk_tier: quote.risk_tier ?? candidate.risk_tier,
    next_watch_price: quote.next_watch_price ?? candidate.next_watch_price,
  };
}

export function applyQuoteRefreshToResponse(
  payload: LowBuyScreenerResult,
  quoteMap: Record<string, LowBuyQuoteRefreshItem>
): LowBuyScreenerResult {
  const refreshed = [...payload.confirmed_candidates, ...payload.candidates].map((candidate) =>
    applyQuoteRefresh(candidate, quoteMap[candidate.symbol])
  );
  return {
    ...payload,
    confirmed_candidates: refreshed.filter((candidate) => CONFIRMED_STATES.has(candidate.buy_signal_state)),
    candidates: refreshed.filter((candidate) => !CONFIRMED_STATES.has(candidate.buy_signal_state)),
  };
}

export function applyQuoteRefreshToHistory(
  payload: LowBuyHistoryResult,
  quoteMap: Record<string, LowBuyQuoteRefreshItem>
): LowBuyHistoryResult {
  return {
    ...payload,
    history_sections: payload.history_sections.map((section) => ({
      ...section,
      candidates: section.candidates.map((candidate) =>
        quoteMap[candidate.symbol]
          ? {
              ...candidate,
              latest_price: quoteMap[candidate.symbol].latest_price,
              change_pct: quoteMap[candidate.symbol].change_pct,
              quote_timestamp: quoteMap[candidate.symbol].quote_timestamp,
              data_source: quoteMap[candidate.symbol].data_source ?? candidate.data_source,
              source_quality: quoteMap[candidate.symbol].source_quality ?? candidate.source_quality,
              is_stale: quoteMap[candidate.symbol].is_stale ?? candidate.is_stale,
            }
          : candidate
      ),
    })),
  };
}

export function getStateBadgeClass(state: LowBuyCandidate["buy_signal_state"]) {
  if (state === "buy_now" || state === "soft_buy_now") {
    return "playbook-state-badge buy";
  }
  if (state === "near_entry") {
    return "playbook-state-badge near";
  }
  if (state === "avoid") {
    return "playbook-state-badge avoid";
  }
  return "playbook-state-badge watch";
}

export function filterTrackedCandidates<T extends { symbol: string }>(
  candidates: T[],
  trackedSymbols: Set<string>
) {
  return candidates.filter((candidate) => !trackedSymbols.has(candidate.symbol));
}
