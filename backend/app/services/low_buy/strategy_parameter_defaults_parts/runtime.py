from __future__ import annotations

from typing import Any

BACKTEST_EXECUTION_DEFAULTS: dict[str, Any] = {
    "max_concurrent_backtests": 2,
    "queue_depth_warning_threshold": 10,
    "market_impact_no_turnover_rate": 0.008,
    "market_impact_participation_thresholds": [0.02, 0.05, 0.10],
    "market_impact_rates": [0.0008, 0.0015, 0.003, 0.008],
    "paper_slippage_stock_bps": 5.0,
    "paper_slippage_etf_bps": 2.0,
    "paper_slippage_mid_liquidity_bps": 8.0,
    "paper_slippage_low_liquidity_bps": 15.0,
    "paper_slippage_mid_liquidity_amount": 100_000_000.0,
    "paper_slippage_low_liquidity_amount": 30_000_000.0,
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
