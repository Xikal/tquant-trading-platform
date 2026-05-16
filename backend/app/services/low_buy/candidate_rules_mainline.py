from __future__ import annotations

from app.services.low_buy.candidate_distribution_gate import has_limit_up_distribution_exit
from app.services.low_buy.candidate_rule_params import (
    execution_params as _execution_params,
    ma5_ma10_ma20_confluence_pct as _ma5_ma10_ma20_confluence_pct,
    prefilter_params as _prefilter_params,
)
from app.services.low_buy.candidate_types import CandidateMetrics, StrategySetup
from app.services.low_buy.shared import BoardCandidate


def _late_session_strong_support_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("late_session_strong_support")
    anchor = max(
        min(metrics.latest_close, metrics.ma5 * execution["ma5_anchor_multiplier"]),
        metrics.ma10 * execution["ma10_anchor_multiplier"],
    )
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(max(metrics.latest_close, anchor) * execution["entry_high_multiplier"], 3),
        execution_ready=(
            score >= execution["min_score"]
            and metrics.close_position_ratio >= execution["min_close_position_ratio"]
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.long_upper_shadow
            and not metrics.weak_close
            and not metrics.intraday_reversal_flag
        ),
        execution_note="收盘强势承接结构只看次日惯性冲高，不做 3-5 日持有。",
        summary_reason="收盘强势承接，收盘位置高，适合次日冲高兑现模型。",
        reasons=[
            f"收盘位置处在全天区间的 {metrics.close_position_ratio:.0%} 附近，收盘承接不弱。",
            f"价格距离支撑约 {metrics.support_distance_pct:.2f}%，未明显脱离承接区。",
            f"最近量能约为启动日的 {metrics.post_volume_ratio:.2f} 倍，没有失控放大。",
        ],
    )


def _core_midcap_vwap_ma5_retrace_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("core_midcap_vwap_ma5_retrace")
    anchor = metrics.ma5 if metrics.close_to_ma5 <= metrics.close_to_ma10 else metrics.ma10
    params = _prefilter_params("core_midcap_vwap_ma5_retrace")
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor * execution["entry_high_multiplier"], 3),
        execution_ready=(
            score >= execution["min_score"]
            and item.amount >= params["min_amount"]
            and (metrics.strong_trend or metrics.trend_ok)
            and min(metrics.close_to_ma5, metrics.close_to_ma10) <= execution["max_ma_distance_pct"]
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
        ),
        execution_note="主线中军回踩 5/10 日线，只做 1-2 日修复，不破支撑才执行。",
        summary_reason="板块核心中军回踩关键均线，量能收敛，等待短线修复。",
        reasons=[
            f"成交额约 {item.amount / 100_000_000:.1f} 亿，具备中军容量和流动性。",
            f"当前贴近 5/10 日关键均线，最近偏离约 {min(metrics.close_to_ma5, metrics.close_to_ma10):.2f}%。",
            f"回踩量能约为启动日的 {metrics.post_volume_ratio:.2f} 倍，未出现放量破位。",
        ],
    )


def _sector_mainline_first_divergence_low_buy_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("sector_mainline_first_divergence_low_buy")
    anchor = max(metrics.board_low, min(metrics.ma5, metrics.board_mid_price))
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(max(metrics.ma5, metrics.board_open) * execution["entry_high_multiplier"], 3),
        execution_ready=(
            score >= execution["min_score"]
            and metrics.retracement_days <= execution["max_retracement_days"]
            and metrics.board_low_held
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
        ),
        execution_note="主线首分歧只做核心前排，收盘承接或次日弱转强确认。",
        summary_reason="主线首分歧低吸，启动强度仍在，第一次分歧后等待资金回流。",
        reasons=[
            f"启动放量达到前 5 日均量的 {metrics.volume_burst_ratio:.2f} 倍，主线分歧前有资金参与。",
            f"当前为第 {metrics.retracement_days} 天分歧回踩，仍守住首板低点。",
            f"回踩量能约为启动日的 {metrics.post_volume_ratio:.2f} 倍，尚未演变成放量阴跌。",
        ],
    )


def _mainline_limitup_shrink_retrace_reclaim_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    prefilter = _prefilter_params("mainline_limitup_shrink_retrace_reclaim")
    execution = _execution_params("mainline_limitup_shrink_retrace_reclaim")
    ma_confluence_pct = _ma5_ma10_ma20_confluence_pct(metrics)
    structure_ready = (
        ma_confluence_pct <= execution["max_ma_confluence_pct"]
        or metrics.support_touch_count >= execution["min_support_touch_count"]
    )
    ma_anchor = (metrics.ma5 + metrics.ma10 + metrics.ma20) / 3.0
    support_anchor = max(metrics.recent_low_guard, min(ma_anchor, metrics.latest_close))
    entry_high = min(
        ma_anchor * execution["ma_anchor_entry_high_multiplier"],
        metrics.ma5 * (1 + prefilter["max_close_above_ma5_pct"] / 100.0),
    )
    return StrategySetup(
        entry_zone_low=round(support_anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(max(entry_high, support_anchor * execution["entry_high_min_multiplier"]), 3),
        execution_ready=(
            score >= execution["min_score"]
            and metrics.board_low_held
            and metrics.latest_close >= metrics.ma5 * execution["min_close_to_ma5_ratio"]
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and structure_ready
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.long_upper_shadow
            and not metrics.weak_close
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
            and not has_limit_up_distribution_exit(metrics, prefilter)
        ),
        execution_note="主线涨停后只等缩量回调确认，不追高；重新站回 5 日线才执行。",
        summary_reason="主线涨停启动后 3-8 日缩量回调，均线合一附近重新站回 5 日线。",
        reasons=[
            f"{item.board_date} 涨停启动后已回调 {metrics.retracement_days} 天，处在 3-8 天观察窗口。",
            f"5/10/20 日线合一宽度约 {ma_confluence_pct:.2f}%，支撑触达 {metrics.support_touch_count} 次，当前距离支撑约 {metrics.support_distance_pct:.2f}%。",
            f"回调量能缩到启动日的 {metrics.post_volume_ratio:.2f} 倍，且收盘重新贴近/站回 5 日线。",
        ],
    )
