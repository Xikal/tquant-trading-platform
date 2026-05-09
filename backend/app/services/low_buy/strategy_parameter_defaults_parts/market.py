from __future__ import annotations

from typing import Any

from app.services.market.parameter_defaults import MARKET_SECTOR_PROXY_DEFAULTS

MARKET_REGIME_SCORING_DEFAULTS: dict[str, Any] = {
    "normalizers": {
        "positive_ratio": [0.35, 0.75],
        "stock_up_ratio": [0.38, 0.72],
        "top3_avg_change": [0.15, 1.65],
        "median_change": [-0.20, 0.95],
        "stock_median_change": [-0.60, 1.40],
        "limit_down_value": [12.0, 50.0],
        "negative_median_change": [-0.2, 1.8],
        "negative_stock_median_change": [-0.3, 2.4],
        "weak_stock_up_gap": [-0.08, 0.30],
        "style_divergence": [0.40, 3.20],
        "largecap_change": [0.10, 2.20],
        "negative_smallcap_change": [-0.30, 2.40],
        "weight_stock_up_gap": [-0.05, 0.28],
        "concentration": [0.60, 2.30],
        "hot_turnover": [0.15, 1.0],
        "hot_overlap_gap": [0.0, 0.58],
        "rotation_top3_change": [0.50, 1.90],
        "rotation_positive_ratio": [0.28, 0.58],
        "limit_up_count": [8.0, 70.0],
        "board_height": [2.0, 7.0],
        "promotion_ratio": [0.08, 0.56],
        "promotion_break_gap": [-0.08, 0.22],
        "high_flyer_retreat_ratio": [0.06, 0.46],
        "broken_board_ratio": [0.10, 0.58],
        "retreat_limit_down_value": [10.0, 42.0],
        "promotion_break_pressure": [0.30, 0.86],
        "high_flyer_gap_speed": [0.10, 0.82],
        "distribution_stock_up_gap": [0.0, 0.32],
        "regime_score": [38.0, 78.0],
    },
    "mainline_lifecycle": {
        "retreat_high_flyer_ratio": 0.28,
        "retreat_distribution_pressure": 62.0,
        "rotation_hot_turnover": 0.55,
        "rotation_hot_overlap_max": 0.18,
        "accelerating_board_height": 4,
        "accelerating_promotion_ratio": 0.32,
        "accelerating_hot_overlap": 0.38,
        "stable_hot_overlap": 0.35,
    },
    "state_selection": {
        "repair_low_volume_max_gap": 3.0,
        "weight_support_active_max_gap": 4.0,
    },
    "confidence": {
        "breadth_ready_weight": 0.34,
        "emotion_ready_weight": 0.24,
        "base": 0.24,
        "score_weight": 0.34,
        "pressure_penalty_weight": 0.16,
    },
    "sector_proxy": MARKET_SECTOR_PROXY_DEFAULTS,
}
