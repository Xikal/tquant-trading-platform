import type {
  ActionType,
  Instrument,
  KlineBar,
  MarketEvent,
  MicrostructureSnapshot,
  QuoteSnapshot,
  RiskLevel,
  SectorSnapshot,
  TradingRule,
} from "./market";

export interface StrategySuggestion {
  action: ActionType;
  entry_price?: number | null;
  exit_price?: number | null;
  position_pct: number;
  stop_loss?: number | null;
  risk_level: RiskLevel;
  signal_score: number;
  tradability_score: number;
  confidence: number;
  expected_profit_pct: number;
  scenario: string;
  trade_scene?: string;
  trade_scene_text?: string;
  buyback_trigger?: string;
  reasons: string[];
  blocking_rules: string[];
  take_profit?: number | null;
  strategy_notes: string;
  plain_action_text?: string;
  plain_action_reason?: string;
  plain_execution_text?: string;
  plain_invalid_condition?: string;
  estimated_fee?: number;
  net_profit_pct?: number;
  breakeven_pct?: number;
  fee_warning?: string;
  elasticity_score?: number;
  elasticity_data_quality?: string;
  elasticity_tier?: string;
  liquidity_warning?: string;
  suggested_timing?: string;
  min_position_value?: number;
  direction?: string;
  min_shares_suggestion?: number;
  effective_action?: ActionType;
  is_actionable?: boolean;
}

export interface AiInsight {
  enabled: boolean;
  summary: string;
  confidence: number;
  suggestions: string[];
  warnings: string[];
  raw?: Record<string, unknown> | null;
}

export interface AnalysisResponse {
  symbol: string;
  instrument: Instrument;
  quote: QuoteSnapshot;
  rules: TradingRule;
  sector: SectorSnapshot;
  events: MarketEvent[];
  microstructure: MicrostructureSnapshot;
  bars: KlineBar[];
  metrics: Record<string, string | number>;
  suggestion: StrategySuggestion;
  ai: AiInsight;
  compliance_notes: string[];
  assumptions: string[];
  analysis_log_id?: number | null;
}
