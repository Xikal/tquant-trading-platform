from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "backend" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.models.schemas import LowBuyHardRiskOut
from app.services.low_buy.candidate_observation_confirmation import observation_confirmation_ready
from app.services.low_buy.candidate_types import CandidateContextAdjustment, CandidateMetrics
from low_buy_market_backtest import _resolve_evaluated_states, _states_stem
from low_buy_market_backtest_reporting import StrategyBacktestStats
from low_buy_market_backtest_signal_stats import signal_group_stats


def test_long_wash_observe_confirmed_uses_shape_not_sector_gate() -> None:
    metrics = _metrics()
    context = _context()

    assert observation_confirmation_ready(
        strategy="n_pattern_long_wash",
        setup_ready=True,
        metrics=metrics,
        context=context,
    )
    assert observation_confirmation_ready(
        strategy="n_pattern_long_wash",
        setup_ready=True,
        metrics=metrics,
        context=replace(context, industry_tier="cold"),
    )
    assert not observation_confirmation_ready(
        strategy="n_pattern_long_wash",
        setup_ready=True,
        metrics=replace(metrics, long_upper_shadow=True, latest_volume_ratio=0.95),
        context=context,
    )


def test_short_wash_observe_confirmed_keeps_distribution_filter() -> None:
    metrics = replace(_metrics(), latest_volume_ratio=0.82, doji_like=True, long_lower_shadow=True)
    context = _context()

    assert observation_confirmation_ready(
        strategy="n_pattern_short_wash",
        setup_ready=True,
        metrics=metrics,
        context=context,
    )
    assert not observation_confirmation_ready(
        strategy="n_pattern_short_wash",
        setup_ready=True,
        metrics=replace(metrics, false_breakout_flag=True),
        context=context,
    )


def test_signal_group_stats_reports_best_holding_day() -> None:
    outcomes = [
        _outcome(0.5, 1.2, 2.0, 1.4, 0.8),
        _outcome(-0.2, 0.1, 0.8, 0.4, -0.4),
    ]

    result = signal_group_stats(
        outcomes=outcomes,
        states={"observe_confirmed"},
        target_profit_pct=3.0,
    )

    assert result["evaluated_count"] == 2
    assert result["win_rate_3d"] == 100.0
    assert result["avg_return_3d"] == 1.4
    assert result["spike_win_rate_5d"] == 100.0
    assert result["avg_spike_return_5d"] == 2.0
    assert result["best_holding_day"]["day"] == 3


def test_signal_group_stats_reports_execution_performance_metrics() -> None:
    outcomes = [
        _outcome_with_execution("2026-01-02", "2026-01-03", "2026-01-06", 2.0),
        _outcome_with_execution("2026-01-07", "2026-01-08", "2026-01-10", -1.0),
        _outcome_with_execution("2026-01-13", "2026-01-14", "2026-01-15", 3.0),
    ]

    result = signal_group_stats(
        outcomes=outcomes,
        states={"observe_confirmed"},
        target_profit_pct=3.0,
    )

    assert result["trade_count"] == 3
    assert result["total_return_pct"] > 0
    assert result["max_drawdown_pct"] < 0
    assert result["sharpe_ratio"] != 0
    assert result["profit_loss_ratio"] == 2.5
    assert result["avg_holding_days"] == 2.0
    assert "回撤" in result["drawdown_recovery_status"]


def test_backtest_state_filter_parser_supports_confirmed_alias() -> None:
    states = _resolve_evaluated_states("confirmed")

    assert states == {"buy_now", "soft_buy_now"}
    assert _states_stem(states) == "confirmed"


def test_strategy_backtest_stats_reports_state_filter_diagnostics() -> None:
    stat = StrategyBacktestStats(
        strategy_key="first_board",
        strategy_title="首板回调",
        strategy_family="event",
        strategy_family_text="事件策略",
    )
    stat.record_signal_state("buy_now")
    stat.record_signal_state("near_entry")
    stat.record_skipped_state("near_entry")
    stat.record_pending_reason("forward_window_incomplete_or_missing_bars")
    stat.outcomes = [
        _outcome_with_execution("2026-01-02", "2026-01-03", "2026-01-06", 2.0),
        _outcome_with_execution(
            "2026-01-07",
            "",
            "",
            0.0,
            execution_status="not_filled",
            execution_exit_reason="信号后 2 日未出现可成交买点。",
        ),
    ]
    stat.evaluated_count = len(stat.outcomes)
    stat.pending_count = 1

    payload = stat.as_dict(target_profit_pct=3.0, selected_states={"buy_now", "soft_buy_now"})

    assert payload["selected_signal_states"] == ["buy_now", "soft_buy_now"]
    assert payload["signal_state_counts"] == {"buy_now": 1, "near_entry": 1}
    diagnostics = payload["evaluation_diagnostics"]
    assert diagnostics["skipped_by_state_count"] == 1
    assert diagnostics["skipped_by_state_counts"] == {"near_entry": 1}
    assert diagnostics["pending_reason_counts"] == {"forward_window_incomplete_or_missing_bars": 1}
    assert diagnostics["not_filled_reason_counts"] == {"信号后 2 日未出现可成交买点。": 1}


def _metrics() -> CandidateMetrics:
    return CandidateMetrics(
        latest_trade_date="2026-05-15",
        retracement_days=8,
        latest_open=10.1,
        latest_close=10.8,
        latest_high=11.0,
        latest_low=10.1,
        latest_change_pct=1.2,
        ma5=10.5,
        ma10=10.4,
        ma20=10.0,
        ma60=9.6,
        board_open=9.8,
        board_close=10.5,
        board_low=10.0,
        board_high=10.8,
        board_mid_price=10.4,
        board_gain_ok=True,
        volume_burst_ratio=2.0,
        latest_volume_ratio=0.86,
        post_volume_ratio=0.62,
        shrink_staircase=True,
        close_to_ma5=2.0,
        close_to_ma10=3.0,
        close_to_ma20=8.0,
        support_distance_pct=2.2,
        support_distance_ma20_pct=4.0,
        breakout_level=10.8,
        breakout_distance_pct=0.0,
        platform_high=10.9,
        platform_low=10.0,
        platform_window_days=8,
        platform_range_pct=8.0,
        platform_breakout_pct=0.0,
        platform_support_distance_pct=2.2,
        divergence_high=11.0,
        divergence_volume_ratio=1.0,
        divergence_day_stall=False,
        consolidation_days=8,
        consolidation_low=10.0,
        consolidation_high=10.9,
        consolidation_volume_ratio=0.62,
        consensus_breakout=True,
        consensus_volume_ratio=1.0,
        consensus_close_strength=0.65,
        recent_low_guard=10.0,
        recent_swing_high=11.0,
        drawdown_from_board_pct=3.0,
        latest_body_pct=4.0,
        upper_shadow_ratio=0.15,
        lower_shadow_ratio=0.25,
        close_position_ratio=0.78,
        doji_like=False,
        long_lower_shadow=False,
        long_upper_shadow=False,
        weak_close=False,
        false_breakout_flag=False,
        stall_after_volume_flag=False,
        intraday_reversal_flag=False,
        distribution_risk_score=2.0,
        momentum_exhaustion=False,
        trend_ok=True,
        strong_trend=True,
        support_ok=True,
        shrink_ok=True,
        shrink_basic_ok=True,
        board_low_held=True,
        board_open_held=True,
        support_watch_ok=True,
        latest_change_ok=True,
    )


def _context() -> CandidateContextAdjustment:
    return CandidateContextAdjustment(
        score_penalty=0.0,
        score_floor_shift=0.0,
        soft_buy_threshold_shift=0.0,
        candidate_penalty_weight=0.0,
        market_position_multiplier=1.0,
        risk_position_multiplier=1.0,
        dynamic_position_multiplier=1.0,
        industry_tier="core_hot",
        industry_tier_text="核心热门",
        industry_position_multiplier=1.0,
        execution_blocked=False,
        risk_tier="clear",
        dynamic_adjustment_reason="",
        market_state="repair",
        market_state_text="修复",
        market_state_strength=0.7,
        hard_risk=LowBuyHardRiskOut(),
        extra_risks=[],
        extra_tags=[],
    )


@dataclass
class _Outcome:
    return_1d: float
    return_2d: float
    return_3d: float
    return_4d: float
    return_5d: float
    spike_return_1d: float = 0.5
    spike_return_2d: float = 1.2
    spike_return_3d: float = 2.0
    spike_return_4d: float = 2.0
    spike_return_5d: float = 2.0
    buy_signal_state: str = "observe_confirmed"
    execution_status: str = "filled"
    net_return_pct: float = 1.0
    execution_exit_reason: str = "止盈"
    max_gain_5d: float = 3.2
    max_drawdown_5d: float = -1.0
    t1_high_return_pct: float = 0.0
    t1_close_return_pct: float = 0.0
    t1_spike_fade_pct: float = 0.0
    t2_high_return_pct: float = 0.0
    t2_close_return_pct: float = 0.0
    t1_hit_3_pct: bool = False
    t1_hit_5_pct: bool = False
    t1_fade_to_entry: bool = False
    signal_date: str = "2026-01-02"
    entry_trade_date: str = "2026-01-03"
    exit_trade_date: str = "2026-01-06"


def _outcome(return_1d: float, return_2d: float, return_3d: float, return_4d: float, return_5d: float) -> _Outcome:
    return _Outcome(return_1d, return_2d, return_3d, return_4d, return_5d)


def _outcome_with_execution(
    signal_date: str,
    entry_date: str,
    exit_date: str,
    net_return_pct: float,
    *,
    execution_status: str = "filled",
    execution_exit_reason: str = "止盈",
) -> _Outcome:
    return _Outcome(
        return_1d=net_return_pct,
        return_2d=net_return_pct,
        return_3d=net_return_pct,
        return_4d=net_return_pct,
        return_5d=net_return_pct,
        net_return_pct=net_return_pct,
        execution_status=execution_status,
        execution_exit_reason=execution_exit_reason,
        signal_date=signal_date,
        entry_trade_date=entry_date,
        exit_trade_date=exit_date,
    )
