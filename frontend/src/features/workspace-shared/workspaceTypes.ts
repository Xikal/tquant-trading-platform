export type Page =
  | "monitor"
  | "monitor-market"
  | "analysis"
  | "playbook"
  | "strategy-tracking"
  | "backtest"
  | "paper"
  | "data"
  | "settings";
export type Tone = "up" | "down" | "neutral" | "warn";

export interface MetricItem {
  label: string;
  value: string;
  tone: Tone;
}

export interface StockCardView {
  name: string;
  symbol: string;
  identityNote?: string;
  identityTags?: string[];
  sectorText?: string;
  priceText: string;
  changeText: string;
  livePrice?: boolean;
  scoreText?: string;
  riskText: string;
  expectedText?: string;
  actionText: string;
  details: string;
  entryText?: string;
  stopText?: string;
  operationAmountText?: string;
  primaryReason?: string;
  executionHint?: string;
  failureText?: string;
  tone: Tone;
  badges?: string[];
  subBadges?: string[];
  highlight?: boolean;
}

export interface WatchDraft {
  symbol: string;
  name: string;
  base_position: string;
  available_position: string;
  cost_basis: string;
  memo: string;
}

export interface AnalysisDraft {
  symbol: string;
  prefer_strategy: "auto" | "positive_t" | "negative_t";
  base_position: string;
  available_position: string;
  cost_basis: string;
}

export interface BacktestDraft {
  symbol: string;
  bar_period: "1m" | "5m" | "15m";
  lookback_bars: string;
  initial_position: string;
  walk_forward_windows: string;
  low_buy_strategy: string;
  low_buy_lookback_days: string;
  low_buy_limit: string;
}

export interface PaperOrderDraft {
  symbol: string;
  name: string;
  side: "buy" | "sell";
  order_type: "market" | "limit";
  quantity: string;
  price: string;
  current_price: string;
  strategy_key: string;
  reason: string;
  require_intraday_confirmation: boolean;
}

export interface AuthDraft {
  username: string;
  password: string;
  remember: boolean;
}

export interface SettingsDraft {
  adminToken: string;
  llm_provider: string;
  llm_api_key: string;
  llm_base_url: string;
  llm_model: string;
  data_source: string;
  data_source_base_url: string;
  risk_max_single_loss_pct: string;
  risk_max_daily_loss_pct: string;
  risk_pause_after_losses: string;
  strategy_min_profit_pct: string;
}
