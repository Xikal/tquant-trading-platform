export interface PaperAccount {
  id: number
  name: string
  initial_cash: number
  cash_available: number
  frozen_cash: number
  market_value: number
  total_assets: number
  realized_pnl: number
  unrealized_pnl: number
  total_return_pct: number
  max_drawdown_pct: number
  status: string
  today_return_pct: number
}

export interface PaperPosition {
  id: number
  symbol: string
  name: string
  quantity: number
  available_quantity: number
  frozen_quantity: number
  cost_basis: number
  latest_price: number | null
  market_value: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  strategy_sources: string[]
  opened_at: string
  smart_exit_action?: string
  smart_exit_text?: string
  smart_exit_reason?: string
  smart_exit_invalid_condition?: string
  smart_exit_failure_action?: string
  smart_exit_quantity?: number
  smart_exit_net_profit_pct?: number
  smart_exit_fee_drag_pct?: number
}

export interface PaperPositionsResponse {
  positions: PaperPosition[]
  total_market_value: number
  total_unrealized_pnl: number
}

export type PaperSide = "buy" | "sell"
export type PaperOrderType = "market" | "limit"
export type PaperOrderStatus = "pending" | "filled" | "partial" | "rejected" | "cancelled"

export interface PaperOrder {
  id: number
  account_id: number
  symbol: string
  name: string
  side: PaperSide
  order_type: PaperOrderType
  price: number | null
  quantity: number
  filled_quantity: number
  avg_fill_price: number | null
  status: PaperOrderStatus
  reject_reason: string | null
  source: string
  strategy_key: string
  reason: string
  created_at: string
}

export interface PaperOrderCreate {
  symbol: string
  name?: string
  side: PaperSide
  order_type?: PaperOrderType
  quantity: number
  price?: number | null
  strategy_key?: string
  reason?: string
  source?: string
  require_intraday_confirmation?: boolean
  current_price?: number | null
}

export interface PaperTrade {
  id: number
  order_id: number
  account_id: number
  symbol: string
  side: PaperSide
  price: number
  quantity: number
  gross_amount: number
  commission: number
  stamp_tax: number
  transfer_fee: number
  net_amount: number
  strategy_key: string
  entry_reason: string
  entry_reason_code: string
  exit_reason: string
  exit_reason_code: string
  commission_warning: string
  trade_time: string
}

export interface PaperTradesResponse {
  trades: PaperTrade[]
}

export interface PaperStockPnlItem {
  symbol: string
  name: string
  buy_quantity: number
  sell_quantity: number
  current_quantity: number
  avg_cost: number | null
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
  total_fees: number
  replay_complete: boolean
}

export interface PaperStockPnlSummary {
  item_count: number
  account_total_pnl: number
  stock_total_pnl: number
  realized_pnl: number
  unrealized_pnl: number
  reconciliation_gap: number
}

export interface PaperStockPnlResponse {
  items: PaperStockPnlItem[]
  summary: PaperStockPnlSummary
}

export interface PaperLedgerRepairIssue {
  trade_id: number
  order_id: number
  symbol: string
  side: string
  original_quantity: number
  valid_quantity: number
  invalid_quantity: number
  reason: string
}

export interface PaperLedgerRepairResponse {
  account_id: number
  applied: boolean
  issue_count: number
  corrected_cash_available: number
  corrected_realized_pnl: number
  corrected_market_value: number
  corrected_total_assets: number
  reconciliation_gap_before: number
  reconciliation_gap_after: number
  issues: PaperLedgerRepairIssue[]
}

export interface PaperTradeTag {
  id: number
  trade_id: number
  tag: string
  note: string
  created_at: string
}

export interface PaperTradeTagCreate {
  tag: string
  note?: string
}

export interface PaperTagPerformance {
  tag: string
  trades: number
  win_rate_pct: number
  net_win_rate_pct: number
  avg_return_pct: number
  total_return_pct: number
}

export interface PaperPerformance {
  total_return_pct: number
  max_drawdown_pct: number
  win_rate_pct: number
  net_win_rate_pct: number
  avg_trade_return_pct: number
  avg_win_pct: number
  avg_loss_pct: number
  profit_factor: number | null
  stop_loss_rate_pct: number
  total_trades: number
  avg_hold_days: number
  win_loss_ratio: number | null
}

export interface PaperSectorEtfT0Performance {
  simulated_trades: number
  simulated_closed_trades: number
  simulated_win_rate_pct: number
  simulated_net_win_rate_pct: number
  simulated_avg_return_pct: number
  simulated_profit_factor: number | null
  shadow_sample_count: number
  shadow_settled_count: number
  shadow_pending_count: number
  shadow_success_rate_pct: number
  shadow_avg_return_1d_pct: number
  shadow_avg_return_3d_pct: number
  notes: string[]
}

export interface PaperGroupedPerformance {
  key: string
  trades: number
  win_rate_pct: number
  net_win_rate_pct: number
  avg_return_pct: number
  profit_factor: number | null
}

export interface PaperStrategyMarketPerformance {
  strategy_key: string
  market_state: string
  trades: number
  win_rate_pct: number
  net_win_rate_pct: number
  avg_return_pct: number
  profit_factor: number | null
}

export interface PaperAutoTradingStatus {
  running: boolean
  engine_running?: boolean
  trading_time?: boolean
  dry_run?: boolean
  account_status?: string
  interval_seconds?: number
  max_orders_per_cycle?: number
  min_score?: number
  last_cycle_at?: string
  last_cycle_duration_ms?: number
  last_cycle_passed?: number
  last_cycle_filtered?: number
  last_cycle_executed?: number
  last_cycle_skipped?: number
  last_cycle_summary?: string
  total_cycles?: number
  total_executed?: number
  total_errors?: number
  circuit_open?: boolean
  circuit_reason?: string
  circuit_since?: string
  blocking_reason?: string
  sector_etf_t0_auto_enabled?: boolean
  sector_etf_t0_max_orders?: number
  sector_etf_t0_cash_pct?: number
  sector_etf_t0_min_confidence?: number
  sector_etf_t0_min_edge_pct?: number
  last_skip_reason?: string
  last_skip_symbol?: string
  last_skip_at?: string
  last_skip_reasons?: Array<{ symbol?: string; reason: string }>
  heartbeat_at?: string
  reason?: string
}

export interface PaperAgentRun {
  id: number
  account_id: number
  provider: string
  run_type: string
  status: string
  request: Record<string, unknown>
  response: Record<string, unknown>
  error_message: string
  created_at: string
}

export interface PaperStrategyPerfDailyPoint {
  date: string
  win_rate_pct: number
  net_win_rate_pct: number
  avg_return_pct: number
  trade_count: number
}

export interface PaperStrategyTrend {
  strategy_key: string
  points: PaperStrategyPerfDailyPoint[]
}

export interface PaperMarketPerfHeatmapItem {
  market_state: string
  avg_win_rate_pct: number
  avg_return_pct: number
  trade_count: number
  profit_factor: number | null
}

export interface PaperDailyReport {
  id: number
  report_date: string
  overall_summary: string
  strategy_highlights: Array<{
    strategy: string
    comment: string
    trend: "improving" | "stable" | "declining" | "new" | string
  }>
  risk_alerts: Array<{
    level: "info" | "warning" | "danger" | string
    content: string
  }>
  suggestion: string
  generated_at: string
  llm_model: string
}

export interface PaperPerformanceDashboard {
  account: {
    id: number
    total_assets: number
    total_return_pct: number
  }
  equity_curve: Array<{
    date: string
    total_assets: number
    cumulative_return_pct: number
  }>
  win_rate_trend: Array<{
    date: string
    win_rate_pct: number
    net_win_rate_pct: number
  }>
  strategy_trend: PaperStrategyTrend[]
  market_perf_heatmap: PaperMarketPerfHeatmapItem[]
  strategy_market_matrix: PaperStrategyMarketPerformance[]
  strategy_correlation?: PaperStrategyCorrelation
  today_report: PaperDailyReport | null
  updated_at: string
}

export interface PaperStrategyCorrelation {
  strategies: string[]
  sample_days: number
  matrix: Array<Array<number | null>>
  rows: Array<{
    strategy_key: string
    correlations: Record<string, number | null>
  }>
  notes: string[]
}
