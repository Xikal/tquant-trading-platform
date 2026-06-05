import { apiClient } from "../../api/httpClient";
import type { ReviewWorkspaceResponse, TradeJournalEntry, TradeJournalEntryUpdate } from "../../types";

export function getTradingExperienceReviewWorkspace(
  limit = 30,
  boardFilter: "include_all" | "main_only" = "include_all",
) {
  return apiClient.requestCached<ReviewWorkspaceResponse>(
    `/trading-experience/review-workspace?limit=${limit}&board_filter=${boardFilter}`,
    12000,
  );
}

export function updateTradingExperienceTradeJournal(entryId: number, payload: TradeJournalEntryUpdate) {
  return apiClient.request<TradeJournalEntry>(`/trading-experience/trade-journal/${entryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteTradingExperienceTradeJournal(entryId: number) {
  return apiClient.request<void>(`/trading-experience/trade-journal/${entryId}`, { method: "DELETE" });
}
