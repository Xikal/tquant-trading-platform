from __future__ import annotations

from typing import Any

from app.services.ml_signal.model_defaults import DEFAULT_TRAINING_PARAMS

BACKTEST_EXECUTION_DEFAULTS: dict[str, Any] = {
    "max_concurrent_backtests": 2,
    "queue_depth_warning_threshold": 10,
    "queue_estimate_sample_size": 10,
    "queue_estimate_max_age_days": 30,
    "market_impact_no_turnover_rate": 0.008,
    "market_impact_participation_thresholds": [0.02, 0.05, 0.10],
    "market_impact_rates": [0.0008, 0.0015, 0.003, 0.008],
    "capacity_impact_eta": 0.50,
    "capacity_default_volatility_pct": 2.0,
    "capacity_max_impact_pct": 8.0,
    "paper_slippage_stock_bps": 5.0,
    "paper_slippage_etf_bps": 2.0,
    "paper_slippage_mid_liquidity_bps": 8.0,
    "paper_slippage_low_liquidity_bps": 15.0,
    "paper_slippage_mid_liquidity_amount": 100_000_000.0,
    "paper_slippage_low_liquidity_amount": 30_000_000.0,
}

CAPACITY_ANALYSIS_DEFAULTS: dict[str, Any] = {
    "impact_eta": 0.50,
    "min_avg_amount": 100_000_000.0,
    "max_impact_pct": 8.0,
    "default_volatility_pct": 2.0,
    "almgren_temporary_eta": 0.65,
    "almgren_permanent_eta": 0.18,
    "execution_slices": 5,
    "max_slice_participation_pct": 2.0,
}

RISK_VOLATILITY_SIZING_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "low_atr_pct_max": 2.5,
    "medium_atr_pct_max": 5.0,
    "high_atr_pct_max": 8.0,
    "low_position_cap_pct": 20.0,
    "medium_position_cap_pct": 15.0,
    "high_position_cap_pct": 10.0,
    "extreme_position_cap_pct": 5.0,
    "unavailable_position_cap_pct": 10.0,
    "min_position_cap_pct": 3.0,
}

PAPER_DYNAMIC_EXIT_DEFAULTS: dict[str, Any] = {
    "hard_stop_loss_pct": -3.0,
    "first_take_profit_pct": 2.0,
    "first_take_profit_sell_ratio": 0.3,
    "protect_profit_trigger_pct": 3.0,
    "protect_profit_sell_ratio": 0.5,
    "take_profit_pct": 5.0,
    "take_profit_sell_ratio": 0.7,
    "strong_take_profit_pct": 8.0,
    "strong_take_profit_sell_ratio": 1.0,
    "wash_buffer_profit_pct": 1.2,
    "wash_pullback_loss_floor_pct": -2.5,
    "wash_volume_ratio_max": 0.85,
    "no_volume_take_profit_pct": 2.0,
    "no_volume_release_ratio": 0.8,
    "no_volume_take_profit_sell_ratio": 0.35,
    "high_pullback_ratio": 0.45,
    "vwap_break_sell_ratio": 0.5,
    "min_net_profit_pct": 0.6,
    "smart_t_add_enabled": True,
    "smart_t_add_cash_pct": 0.08,
    "smart_t_add_cash_pct_profit": 0.12,
    "smart_t_add_cash_pct_loss": 0.04,
    "smart_t_add_max_position_pct": 0.25,
    "smart_t_expected_rebound_pct": 1.2,
    "smart_t_expected_rebound_by_state": {
        "broad_rally": 0.8,
        "repair": 1.2,
        "risk_release": 2.0,
    },
    "smart_t_min_available_base": 100,
    "smart_t_allowed_market_states": ["broad_rally", "repair"],
    "smart_t_add_volume_ratio_max": 0.4,
    "smart_t_require_low_rising": True,
    "smart_t_buy_below_vwap_pct": 0.3,
    "smart_t_open_avoid_minutes": 30,
    "smart_t_close_avoid_minutes": 30,
    "smart_t_profitable_position_only": True,
    "smart_t_max_symbols_per_cycle": 1,
    "smart_t_exit_stop_loss_pct": -0.6,
    "smart_t_exit_time_minutes": 60,
    "smart_t_high_pullback_exit_ratio": 0.5,
    "weak_hold_exit_days": 3,
    "weak_hold_exit_pct": 0.0,
    "time_exit_min_return_pct": 2.0,
}

ML_SIGNAL_TRAINING_DEFAULTS: dict[str, Any] = DEFAULT_TRAINING_PARAMS
