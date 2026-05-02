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
  trade_time: string
}

export interface PaperTradesResponse {
  trades: PaperTrade[]
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

export interface PaperGroupedPerformance {
  key: string
  trades: number
  win_rate_pct: number
  net_win_rate_pct: number
  avg_return_pct: number
  profit_factor: number | null
}
