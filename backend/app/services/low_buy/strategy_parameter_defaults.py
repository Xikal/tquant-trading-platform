from __future__ import annotations

from typing import Any


LOW_BUY_STRATEGY_PREFILTER_DEFAULTS: dict[str, dict[str, Any]] = {
    "classic_retrace": {
        "max_board_count": 2,
        "min_retracement_days": 1,
        "max_retracement_days": 6,
        "min_volume_burst_ratio": 1.05,
        "max_support_distance_pct": 3.0,
        "min_close_to_ma10_ratio": 0.98,
        "max_distribution_risk_score": 6.0,
        "max_post_volume_ratio_relaxed": 1.22,
    },
    "ma_support": {
        "max_board_count": 2,
        "min_retracement_days": 1,
        "max_retracement_days": 8,
        "min_close_to_ma20_ratio": 0.988,
        "max_close_to_ma5_ma10_pct": 2.8,
        "max_close_to_ma20_pct": 2.2,
        "max_support_distance_pct": 2.8,
    },
    "first_board": {
        "required_board_count": 1,
        "min_retracement_days": 1,
        "max_retracement_days": 6,
        "min_volume_burst_ratio": 1.25,
        "max_close_above_board_high_pct": 4.5,
        "max_distribution_risk_score": 5.8,
    },
    "volume_shrink": {
        "max_board_count": 2,
        "min_retracement_days": 1,
        "max_retracement_days": 8,
        "min_volume_burst_ratio": 1.65,
        "max_latest_volume_ratio": 1.12,
        "max_post_volume_ratio": 1.15,
        "max_support_distance_pct": 2.8,
        "min_close_to_ma20_ratio": 0.995,
        "max_distribution_risk_score": 5.6,
    },
    "breakout_support": {
        "min_retracement_days": 1,
        "max_retracement_days": 8,
        "max_breakout_distance_pct": 3.8,
        "min_close_to_breakout_ratio": 0.978,
        "max_latest_change_pct": 4.2,
    },
    "deep_pullback": {
        "max_board_count": 2,
        "min_retracement_days": 2,
        "max_retracement_days": 10,
        "min_drawdown_from_board_pct": -10.5,
        "max_drawdown_from_board_pct": -1.8,
        "max_support_distance_ma20_pct": 5.2,
    },
    "trend_rebound": {
        "min_retracement_days": 1,
        "max_retracement_days": 8,
        "min_close_to_ma20_ratio": 0.992,
        "min_close_to_ma10_ratio": 0.982,
        "min_drawdown_from_board_pct": -10.5,
    },
    "limit_up_breakout_retrace": {
        "min_platform_days": 20,
        "min_retracement_days": 2,
        "max_retracement_days": 5,
        "min_volume_burst_ratio": 1.9,
        "min_breakout_pct": 1.0,
        "max_platform_range_pct": 35.0,
        "min_drawdown_pct": -10.0,
        "max_drawdown_pct": -3.0,
        "max_post_volume_ratio": 0.78,
        "max_latest_volume_ratio": 0.82,
        "max_support_distance_pct": 3.0,
        "min_board_amount": 150_000_000.0,
        "min_platform_hold_ratio": 0.995,
        "min_board_open_hold_ratio": 0.985,
    },
    "divergence_consensus": {
        "min_platform_days": 20,
        "min_retracement_days": 4,
        "max_retracement_days": 12,
        "min_board_amount": 180_000_000.0,
        "min_volume_burst_ratio": 1.8,
        "min_platform_breakout_pct": 0.8,
        "max_platform_range_pct": 38.0,
        "min_divergence_volume_ratio": 0.55,
        "min_consolidation_days": 2,
        "max_consolidation_days": 8,
        "max_consolidation_volume_ratio": 0.72,
        "min_consensus_volume_ratio": 1.45,
        "max_breakout_extension_pct": 8.5,
    },
    "late_session_strong_support": {
        "min_amount": 200_000_000.0,
        "min_retracement_days": 1,
        "max_retracement_days": 8,
        "max_support_distance_pct": 3.2,
        "max_latest_volume_ratio": 1.25,
        "max_post_volume_ratio": 1.15,
        "min_close_position_ratio": 0.55,
        "max_distribution_risk_score": 5.5,
    },
    "core_midcap_vwap_ma5_retrace": {
        "min_amount": 500_000_000.0,
        "min_retracement_days": 1,
        "max_retracement_days": 6,
        "max_ma_distance_pct": 1.8,
        "max_support_distance_pct": 2.2,
        "max_latest_volume_ratio": 1.15,
        "max_post_volume_ratio": 1.2,
        "max_distribution_risk_score": 5.5,
    },
    "sector_mainline_first_divergence_low_buy": {
        "min_amount": 200_000_000.0,
        "min_retracement_days": 1,
        "max_retracement_days": 5,
        "min_volume_burst_ratio": 1.4,
        "max_support_distance_pct": 3.0,
        "max_latest_volume_ratio": 1.25,
        "max_post_volume_ratio": 1.25,
        "max_distribution_risk_score": 5.8,
    },
    "mainline_limitup_shrink_retrace_reclaim": {
        "max_board_count": 2,
        "min_amount": 180_000_000.0,
        "min_retracement_days": 3,
        "max_retracement_days": 8,
        "min_volume_burst_ratio": 1.6,
        "max_latest_volume_ratio": 1.05,
        "max_post_volume_ratio": 0.95,
        "max_support_distance_pct": 2.4,
        "max_ma_confluence_pct": 2.2,
        "min_support_touch_count": 2,
        "min_close_to_ma5_ratio": 0.998,
        "max_close_above_ma5_pct": 2.5,
        "max_distribution_risk_score": 5.0,
    },
    "ma_channel_band": {
        "min_amount": 50_000_000.0,
        "min_platform_days": 20,
        "min_retracement_days": 2,
        "max_retracement_days": 14,
        "max_ma20_distance_pct": 3.2,
        "max_latest_volume_ratio": 1.2,
        "max_post_volume_ratio": 1.25,
        "max_distribution_risk_score": 6.5,
    },
    "leader_pullback_band": {
        "min_amount": 50_000_000.0,
        "min_retracement_days": 1,
        "max_retracement_days": 8,
        "min_volume_burst_ratio": 1.6,
        "max_support_distance_pct": 3.5,
        "max_latest_volume_ratio": 1.25,
        "max_post_volume_ratio": 1.25,
        "max_distribution_risk_score": 5.8,
    },
}


LOW_BUY_STRATEGY_EXECUTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "mainline_limitup_shrink_retrace_reclaim": {
        "min_score": 86.0,
        "max_latest_volume_ratio": 0.98,
        "max_post_volume_ratio": 0.88,
        "max_support_distance_pct": 1.9,
        "max_ma_confluence_pct": 2.0,
        "min_support_touch_count": 2,
        "min_close_to_ma5_ratio": 1.0,
        "max_distribution_risk_score": 4.6,
    },
    "limit_up_breakout_retrace": {
        "min_score": 88.0,
        "min_volume_burst_ratio": 2.0,
        "min_breakout_pct": 1.2,
        "min_drawdown_pct": -8.5,
        "max_drawdown_pct": -3.5,
        "max_post_volume_ratio": 0.72,
        "max_latest_volume_ratio": 0.78,
        "max_support_distance_pct": 2.5,
        "min_board_amount": 200_000_000.0,
    },
    "divergence_consensus": {
        "min_score": 90.0,
        "min_consensus_volume_ratio": 1.55,
        "max_consolidation_volume_ratio": 0.66,
        "min_close_strength": 0.58,
    },
}


def quant_parameter_schema() -> dict[str, Any]:
    """Return a lightweight machine-readable schema for editable parameters."""

    return {
        "low_buy.strategy_prefilters": {
            strategy: {key: _field_schema(value) for key, value in params.items()}
            for strategy, params in LOW_BUY_STRATEGY_PREFILTER_DEFAULTS.items()
        },
        "low_buy.strategy_execution": {
            strategy: {key: _field_schema(value) for key, value in params.items()}
            for strategy, params in LOW_BUY_STRATEGY_EXECUTION_DEFAULTS.items()
        },
    }


def _field_schema(value: Any) -> dict[str, Any]:
    kind = "number" if isinstance(value, float) else "integer" if isinstance(value, int) else "string"
    return {
        "type": kind,
        "default": value,
        "min": 0 if isinstance(value, (int, float)) and value >= 0 else None,
        "max": None,
        "description": "策略运行参数，修改后下一次扫描生效。",
        "risk_level": "medium",
    }
