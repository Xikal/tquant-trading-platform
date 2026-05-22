import type {
  BacktestExecutionModel,
  BacktestResourceTier,
} from "../../api/backtests";

export interface BacktestFormState {
  name: string;
  start_date: string;
  end_date: string;
  initial_capital: string;
  strategies: string[];
  execution_model: BacktestExecutionModel;
  resource_tier: BacktestResourceTier;
  max_position_pct: string;
  max_positions: string;
  max_daily_loss_pct: string;
  max_single_order_pct: string;
  min_cash_reserve: string;
  benchmark: string;
}

export interface OptimizationFormState {
  name: string;
  strategy: string;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  initial_capital: string;
  execution_model: BacktestExecutionModel;
  optimization_target: string;
  min_score: string;
  max_position_pct: string;
  max_holding_days: string;
  stop_loss_pct: string;
  take_profit_pct: string;
}

export interface ValidationFormState {
  name: string;
  strategy: string;
  start_date: string;
  end_date: string;
  window_count: string;
  train_ratio: string;
  initial_capital: string;
  execution_model: BacktestExecutionModel;
  optimization_target: string;
  auto_promote_state_params: boolean;
}

export const initialBacktestForm: BacktestFormState = {
  name: "低吸策略组合回测",
  start_date: "2025-01-02",
  end_date: "2026-04-30",
  initial_capital: "500000",
  strategies: ["first_board", "volume_shrink"],
  execution_model: "conservative_slippage",
  resource_tier: "full",
  max_position_pct: "30",
  max_positions: "8",
  max_daily_loss_pct: "5",
  max_single_order_pct: "30",
  min_cash_reserve: "5000",
  benchmark: "000300",
};

export const initialOptimizationForm: OptimizationFormState = {
  name: "first_board 参数优化",
  strategy: "first_board",
  train_start: "2024-01-02",
  train_end: "2025-12-31",
  test_start: "2026-01-02",
  test_end: "2026-04-30",
  initial_capital: "500000",
  execution_model: "conservative_slippage",
  optimization_target: "sharpe",
  min_score: "70,75,80,85,90",
  max_position_pct: "0.2,0.3",
  max_holding_days: "3,5,7,10",
  stop_loss_pct: "-0.03,-0.05,-0.07",
  take_profit_pct: "0.08,0.12",
};

export const initialValidationForm: ValidationFormState = {
  name: "first_board Walk-Forward 验证",
  strategy: "first_board",
  start_date: "2024-01-02",
  end_date: "2026-04-30",
  window_count: "4",
  train_ratio: "0.75",
  initial_capital: "500000",
  execution_model: "conservative_slippage",
  optimization_target: "sharpe",
  auto_promote_state_params: false,
};
