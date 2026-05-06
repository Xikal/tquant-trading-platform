import type { StrategySuggestion } from "./analysis"
import type { TradingRule, QuoteSnapshot } from "./market"
import type { LowBuyCandidate, LowBuyPriorityBoardResult } from "./playbook"
import type { WatchlistItem } from "./watchlist"

export interface AppResponseMeta {
  updated_at: string
  is_stale: boolean
  warnings: string[]
}

export interface AppMutationResponse {
  message: string
  symbol: string
}

export interface AppFeatureFlags {
  watchlist_enabled: boolean
  low_buy_enabled: boolean
  android_update_enabled?: boolean
}

export interface AppBootstrapTab {
  key: string
  title: string
}

export interface AppBootstrapResponse extends AppResponseMeta {
  app_name: string
  app_version: string
  min_supported_version: string
  tabs: AppBootstrapTab[]
  default_refresh_seconds: number
  market_disclaimer: string
  feature_flags: AppFeatureFlags
}

export interface AppAndroidUpdateResponse {
  platform: "android"
  current_version_code: number
  latest_version_code: number
  latest_version_name: string
  min_supported_version_code: number
  update_available: boolean
  mandatory: boolean
  title: string
  message: string
  changelog: string[]
  apk_url: string
  apk_size_bytes: number
  apk_sha256: string
  published_at: string
}

export interface AppHomeSummary {
  total: number
  positive_t_count: number
  negative_t_count: number
  hold_count: number
  high_risk_count: number
}

export interface AppWatchlistCard {
  symbol: string
  name: string
  base_position: number
  available_position: number
  cost_basis?: number | null
  memo: string
  quote: QuoteSnapshot
  signal: StrategySuggestion
  rules: TradingRule
  headline_reason: string
  headline_blocker: string
  plain_action_text?: string
  plain_action_reason?: string
  plain_execution_text?: string
  plain_invalid_condition?: string
  error?: string | null
  updated_at: string
  is_stale: boolean
}

export interface AppHomeResponse extends AppResponseMeta {
  summary: AppHomeSummary
  items: AppWatchlistCard[]
}

export interface AppWatchlistResponse extends AppResponseMeta {
  items: WatchlistItem[]
}

export interface AppWatchlistDetailSections {
  reasons: string[]
  blocking_rules: string[]
  strategy_notes: string
}

export interface AppWatchlistDetailResponse extends AppResponseMeta {
  symbol: string
  name: string
  base_position: number
  available_position: number
  cost_basis?: number | null
  memo: string
  quote: QuoteSnapshot
  signal: StrategySuggestion
  rules: TradingRule
  detail_sections: AppWatchlistDetailSections
}

export interface AppFavoriteStatus {
  in_watchlist: boolean
  watchlist_symbol?: string | null
}

export interface AppLowBuyDetailResponse extends AppResponseMeta {
  candidate: LowBuyCandidate
  favorite_status: AppFavoriteStatus
}

export interface AppLowBuyStrategySummary {
  strategy_key: string
  strategy_title: string
  strategy_subtitle: string
  strategy_logic: string
}

export interface AppLowBuySummary {
  as_of_date: string
  latest_trade_date: string
  pool_size: number
  scanned_count: number
  matched_count: number
  full_scan_ready: boolean
  full_scan_in_progress: boolean
}

export interface AppLowBuyResponse extends AppResponseMeta {
  strategy: AppLowBuyStrategySummary
  summary: AppLowBuySummary
  priority_board: LowBuyPriorityBoardResult
  confirmed_candidates: LowBuyCandidate[]
  watch_candidates: LowBuyCandidate[]
}
