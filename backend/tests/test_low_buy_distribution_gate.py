from __future__ import annotations

from app.services.low_buy.candidate_distribution_gate import has_limit_up_distribution_exit
from app.services.low_buy.candidate_rule_params import prefilter_params
from app.services.low_buy.candidate_rules import passes_strategy_prefilter
from backend.tests.test_divergence_consensus_strategy import _item
from backend.tests.test_divergence_consensus_strategy import _metrics


def test_limit_up_distribution_exit_triggers_on_high_volume_weak_retrace() -> None:
    metrics = _metrics(
        retracement_days=2,
        post_volume_ratio=1.18,
        latest_volume_ratio=0.92,
        latest_change_pct=-2.4,
        close_position_ratio=0.34,
        consecutive_lower_lows=2,
        weak_close=True,
    )

    assert has_limit_up_distribution_exit(metrics, prefilter_params("first_board")) is True


def test_limit_up_distribution_exit_does_not_block_clean_shrink_retrace() -> None:
    metrics = _metrics(
        retracement_days=4,
        post_volume_ratio=0.64,
        latest_volume_ratio=0.72,
        latest_change_pct=-0.4,
        close_position_ratio=0.62,
        consecutive_lower_lows=0,
        weak_close=False,
    )

    assert has_limit_up_distribution_exit(metrics, prefilter_params("volume_shrink")) is False


def test_limit_up_distribution_exit_blocks_production_prefilter() -> None:
    metrics = _metrics(
        retracement_days=2,
        post_volume_ratio=1.18,
        latest_volume_ratio=0.92,
        latest_change_pct=-2.4,
        close_position_ratio=0.34,
        consecutive_lower_lows=2,
        weak_close=True,
        support_distance_pct=1.8,
        volume_burst_ratio=2.1,
        board_low_held=True,
    )

    assert passes_strategy_prefilter("first_board", _item(), metrics) is False
