from __future__ import annotations

from app.services.low_buy.candidate_types import CandidateMetrics, StrategySetup
from app.services.low_buy.research_layers import passes_research_prefilter
from app.services.low_buy.shared import BoardCandidate, LOW_BUY_THRESHOLDS
from app.services.low_buy.strategy_policy import StrategyTier, get_strategy_tier
LIMIT_UP_BREAKOUT_PREFILTER = {
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
}

LIMIT_UP_BREAKOUT_EXECUTION = {
    "min_score": 88.0,
    "min_volume_burst_ratio": 2.0,
    "min_breakout_pct": 1.2,
    "min_drawdown_pct": -8.5,
    "max_drawdown_pct": -3.5,
    "max_post_volume_ratio": 0.72,
    "max_latest_volume_ratio": 0.78,
    "max_support_distance_pct": 2.5,
    "min_board_amount": 200_000_000.0,
}

DIVERGENCE_CONSENSUS_PREFILTER = {
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
}

DIVERGENCE_CONSENSUS_EXECUTION = {
    "min_score": 90.0,
    "min_consensus_volume_ratio": 1.55,
    "max_consolidation_volume_ratio": 0.66,
    "min_close_strength": 0.58,
}

LATE_SESSION_SUPPORT_PREFILTER = {
    "min_amount": 200_000_000.0,
    "min_retracement_days": 1,
    "max_retracement_days": 8,
    "max_support_distance_pct": 3.2,
    "max_latest_volume_ratio": 1.25,
    "max_post_volume_ratio": 1.15,
    "min_close_position_ratio": 0.55,
    "max_distribution_risk_score": 5.5,
}

CORE_MIDCAP_RETRACE_PREFILTER = {
    "min_amount": 500_000_000.0,
    "min_retracement_days": 1,
    "max_retracement_days": 6,
    "max_ma_distance_pct": 1.8,
    "max_support_distance_pct": 2.2,
    "max_latest_volume_ratio": 1.15,
    "max_post_volume_ratio": 1.20,
    "max_distribution_risk_score": 5.5,
}

MAINLINE_FIRST_DIVERGENCE_PREFILTER = {
    "min_amount": 200_000_000.0,
    "min_retracement_days": 1,
    "max_retracement_days": 5,
    "min_volume_burst_ratio": 1.40,
    "max_support_distance_pct": 3.0,
    "max_latest_volume_ratio": 1.25,
    "max_post_volume_ratio": 1.25,
    "max_distribution_risk_score": 5.8,
}

def passes_strategy_prefilter(
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
) -> bool:
    strategy_tier = get_strategy_tier(strategy)
    if strategy_tier == StrategyTier.CORE and item.amount < LOW_BUY_THRESHOLDS.MIN_DAILY_AMOUNT_CORE:
        return False
    if strategy_tier == StrategyTier.AUXILIARY and item.amount < LOW_BUY_THRESHOLDS.MIN_DAILY_AMOUNT_AUXILIARY:
        return False
    if strategy == "ma_support":
        return (
            item.board_count <= 3
            and 1 <= metrics.retracement_days <= 8
            and (metrics.trend_ok or metrics.latest_close >= metrics.ma20 * 0.988)
            and metrics.latest_close >= metrics.ma20 * 0.988
            and (min(metrics.close_to_ma5, metrics.close_to_ma10) <= 2.8 or metrics.close_to_ma20 <= 2.2)
            and metrics.support_distance_pct <= 2.8
        )
    if strategy == "first_board":
        return (
            item.board_count == 1
            and 1 <= metrics.retracement_days <= 6
            and metrics.board_low_held
            and metrics.volume_burst_ratio >= 1.25
            and metrics.latest_close <= metrics.board_high * 1.045
            and metrics.distribution_risk_score < 5.8
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
        )
    if strategy == "volume_shrink":
        return (
            1 <= metrics.retracement_days <= 8
            and metrics.volume_burst_ratio >= 1.65
            and (metrics.shrink_staircase or metrics.shrink_basic_ok)
            and metrics.latest_volume_ratio <= 1.12
            and metrics.post_volume_ratio <= 1.15
            and metrics.support_distance_pct <= 2.8
            and metrics.latest_close >= metrics.ma20 * 0.995
            and metrics.distribution_risk_score < 5.6
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
        )
    if strategy == "late_session_strong_support":
        return _passes_late_session_support_prefilter(item, metrics)
    if strategy == "core_midcap_vwap_ma5_retrace":
        return _passes_core_midcap_retrace_prefilter(item, metrics)
    if strategy == "sector_mainline_first_divergence_low_buy":
        return _passes_mainline_first_divergence_prefilter(item, metrics)
    if strategy == "breakout_support":
        return (
            1 <= metrics.retracement_days <= 8
            and metrics.breakout_level > 0
            and metrics.breakout_distance_pct <= 3.8
            and metrics.latest_close >= metrics.breakout_level * 0.978
            and metrics.latest_change_pct <= 4.2
        )
    if strategy == "limit_up_breakout_retrace":
        return passes_research_prefilter(strategy, item, metrics)
    if strategy == "divergence_consensus":
        return _passes_divergence_consensus_prefilter(item, metrics)
    if strategy == "deep_pullback":
        return (
            item.board_count <= 2
            and metrics.strong_trend
            and 2 <= metrics.retracement_days <= 10
            and -10.5 <= metrics.drawdown_from_board_pct <= -1.8
            and metrics.support_distance_ma20_pct <= 5.2
            and metrics.latest_close >= metrics.recent_low_guard
        )
    if strategy == "trend_rebound":
        return (
            1 <= metrics.retracement_days <= 8
            and (metrics.strong_trend or (metrics.trend_ok and metrics.latest_close >= metrics.ma20 * 0.992))
            and metrics.latest_close >= metrics.ma10 * 0.982
            and metrics.drawdown_from_board_pct >= -10.5
        )
    return (
        item.board_count <= 2
        and 1 <= metrics.retracement_days <= 6
        and metrics.volume_burst_ratio >= 1.05
        and metrics.support_distance_pct <= 3.0
        and metrics.latest_close >= metrics.ma10 * 0.98
        and (metrics.shrink_basic_ok or metrics.momentum_exhaustion or metrics.post_volume_ratio <= 1.22)
    )


def compute_score(
    board_count: int,
    retracement_days: int,
    volume_burst_ratio: float,
    volume_shrink_ratio: float,
    support_distance_pct: float,
    latest_change_pct: float,
) -> float:
    score = 70.0
    score += min(max(volume_burst_ratio - 1.2, 0.0), 2.0) * 8
    score += min(max(0.85 - volume_shrink_ratio, 0.0), 0.5) * 24
    score += max(0.0, 2.4 - support_distance_pct) * 4.5
    score += max(0.0, 1.8 - abs(latest_change_pct)) * 3.2
    retracement_bonus = {1: 3.0, 2: 7.2, 3: 8.0, 4: 6.2, 5: 3.8, 6: 1.6, 7: 0.2, 8: -0.6, 9: -1.6, 10: -2.4}
    score += retracement_bonus.get(retracement_days, 0.0)
    if board_count == 1:
        score += 6.0
    elif board_count >= 3:
        score -= 4.0
    return round(max(0.0, min(99.0, score)), 1)


def _passes_divergence_consensus_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    return passes_research_prefilter("divergence_consensus", item, metrics)


def _passes_late_session_support_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    return (
        item.amount >= LATE_SESSION_SUPPORT_PREFILTER["min_amount"]
        and LATE_SESSION_SUPPORT_PREFILTER["min_retracement_days"]
        <= metrics.retracement_days
        <= LATE_SESSION_SUPPORT_PREFILTER["max_retracement_days"]
        and -2.0 <= metrics.latest_change_pct <= 6.5
        and metrics.close_position_ratio >= LATE_SESSION_SUPPORT_PREFILTER["min_close_position_ratio"]
        and metrics.support_distance_pct <= LATE_SESSION_SUPPORT_PREFILTER["max_support_distance_pct"]
        and metrics.latest_volume_ratio <= LATE_SESSION_SUPPORT_PREFILTER["max_latest_volume_ratio"]
        and metrics.post_volume_ratio <= LATE_SESSION_SUPPORT_PREFILTER["max_post_volume_ratio"]
        and metrics.distribution_risk_score < LATE_SESSION_SUPPORT_PREFILTER["max_distribution_risk_score"]
        and (metrics.trend_ok or metrics.strong_trend)
        and not metrics.long_upper_shadow
        and not metrics.weak_close
        and not metrics.false_breakout_flag
    )


def _passes_core_midcap_retrace_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    ma_distance = min(metrics.close_to_ma5, metrics.close_to_ma10)
    return (
        item.amount >= CORE_MIDCAP_RETRACE_PREFILTER["min_amount"]
        and CORE_MIDCAP_RETRACE_PREFILTER["min_retracement_days"]
        <= metrics.retracement_days
        <= CORE_MIDCAP_RETRACE_PREFILTER["max_retracement_days"]
        and (metrics.strong_trend or metrics.trend_ok)
        and ma_distance <= CORE_MIDCAP_RETRACE_PREFILTER["max_ma_distance_pct"]
        and metrics.support_distance_pct <= CORE_MIDCAP_RETRACE_PREFILTER["max_support_distance_pct"]
        and -4.0 <= metrics.latest_change_pct <= 2.8
        and metrics.latest_volume_ratio <= CORE_MIDCAP_RETRACE_PREFILTER["max_latest_volume_ratio"]
        and metrics.post_volume_ratio <= CORE_MIDCAP_RETRACE_PREFILTER["max_post_volume_ratio"]
        and metrics.distribution_risk_score < CORE_MIDCAP_RETRACE_PREFILTER["max_distribution_risk_score"]
        and not metrics.false_breakout_flag
        and not metrics.intraday_reversal_flag
    )


def _passes_mainline_first_divergence_prefilter(item: BoardCandidate, metrics: CandidateMetrics) -> bool:
    return (
        item.board_count <= 2
        and item.amount >= MAINLINE_FIRST_DIVERGENCE_PREFILTER["min_amount"]
        and MAINLINE_FIRST_DIVERGENCE_PREFILTER["min_retracement_days"]
        <= metrics.retracement_days
        <= MAINLINE_FIRST_DIVERGENCE_PREFILTER["max_retracement_days"]
        and metrics.volume_burst_ratio >= MAINLINE_FIRST_DIVERGENCE_PREFILTER["min_volume_burst_ratio"]
        and -6.0 <= metrics.latest_change_pct <= 2.8
        and metrics.support_distance_pct <= MAINLINE_FIRST_DIVERGENCE_PREFILTER["max_support_distance_pct"]
        and metrics.latest_volume_ratio <= MAINLINE_FIRST_DIVERGENCE_PREFILTER["max_latest_volume_ratio"]
        and metrics.post_volume_ratio <= MAINLINE_FIRST_DIVERGENCE_PREFILTER["max_post_volume_ratio"]
        and metrics.board_low_held
        and metrics.distribution_risk_score < MAINLINE_FIRST_DIVERGENCE_PREFILTER["max_distribution_risk_score"]
        and not metrics.long_upper_shadow
        and not metrics.weak_close
        and not metrics.false_breakout_flag
    )


def _within(value: float, low: float, high: float) -> bool:
    return low <= value <= high


def score_candidate(
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
    hot_industries: list[str],
) -> float:
    score = compute_score(
        board_count=item.board_count,
        retracement_days=metrics.retracement_days,
        volume_burst_ratio=metrics.volume_burst_ratio,
        volume_shrink_ratio=metrics.post_volume_ratio,
        support_distance_pct=metrics.support_distance_pct,
        latest_change_pct=metrics.latest_change_pct,
    )
    if metrics.strong_trend:
        score += 5.2
    if item.industry and hot_industries and item.industry in hot_industries:
        score += 3.5
    if metrics.shrink_staircase:
        score += 2.8
    if strategy == "ma_support" and metrics.support_distance_pct <= 1.6:
        score += 4.0
    if strategy == "first_board" and item.board_count == 1 and metrics.retracement_days <= 3:
        score += 5.0
    if strategy == "volume_shrink" and metrics.volume_burst_ratio >= 2.0 and metrics.shrink_staircase:
        score += 5.5
    if strategy == "late_session_strong_support":
        score += max(0.0, metrics.close_position_ratio - 0.55) * 12.0
        score += 3.0 if metrics.latest_change_pct >= 0 else 0.0
        score += 2.5 if metrics.latest_volume_ratio <= 0.95 else 0.0
    if strategy == "core_midcap_vwap_ma5_retrace":
        score += 4.0 if metrics.strong_trend else 2.0
        score += max(0.0, 1.8 - min(metrics.close_to_ma5, metrics.close_to_ma10)) * 2.5
        score += 2.5 if item.amount >= 800_000_000 else 0.0
    if strategy == "sector_mainline_first_divergence_low_buy":
        score += 4.0 if item.board_count == 1 else 1.5
        score += max(0.0, 1.2 - metrics.post_volume_ratio) * 4.0
        score += 2.5 if metrics.board_low_held else 0.0
    if strategy == "breakout_support" and metrics.breakout_distance_pct <= 2.0:
        score += 4.0
    if strategy == "limit_up_breakout_retrace":
        if metrics.platform_breakout_pct >= 2.0:
            score += 6.0
        if metrics.post_volume_ratio <= 0.68:
            score += 4.0
        if metrics.doji_like or metrics.long_lower_shadow:
            score += 4.0
    if strategy == "divergence_consensus":
        score += 5.0 if metrics.consensus_breakout else -8.0
        score += min(max(metrics.consensus_volume_ratio - 1.4, 0.0), 1.2) * 4.0
        score += max(0.0, 0.72 - metrics.consolidation_volume_ratio) * 12.0
        score += 3.0 if metrics.consensus_close_strength >= 0.68 else 0.0
        score += 2.0 if item.industry and hot_industries and item.industry in hot_industries else 0.0
    if strategy == "deep_pullback" and -8.5 <= metrics.drawdown_from_board_pct <= -3.0:
        score += 5.0
    if strategy == "trend_rebound" and metrics.latest_close >= metrics.ma10 and metrics.retracement_days >= 2:
        score += 4.0
    return round(max(0.0, min(99.0, score)), 1)


def build_strategy_setup(
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
    score: float,
) -> StrategySetup:
    setup_map = {
        "ma_support": _ma_support_setup,
        "first_board": _first_board_setup,
        "volume_shrink": _volume_shrink_setup,
        "late_session_strong_support": _late_session_strong_support_setup,
        "core_midcap_vwap_ma5_retrace": _core_midcap_vwap_ma5_retrace_setup,
        "sector_mainline_first_divergence_low_buy": _sector_mainline_first_divergence_low_buy_setup,
        "breakout_support": _breakout_support_setup,
        "limit_up_breakout_retrace": _limit_up_breakout_retrace_setup,
        "divergence_consensus": _divergence_consensus_setup,
        "deep_pullback": _deep_pullback_setup,
        "trend_rebound": _trend_rebound_setup,
    }
    builder = setup_map.get(strategy, _classic_retrace_setup)
    return builder(item=item, metrics=metrics, score=score)


def _ma_support_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    anchor = metrics.ma5 if metrics.close_to_ma5 <= 1.3 else metrics.ma10 if metrics.close_to_ma10 <= 1.8 else metrics.ma20
    return StrategySetup(
        entry_zone_low=round(anchor * 0.993, 3),
        entry_zone_high=round(anchor * 1.005, 3),
        execution_ready=(
            (metrics.strong_trend or metrics.trend_ok)
            and metrics.support_distance_pct <= 2.45
            and (metrics.shrink_basic_ok or metrics.momentum_exhaustion)
            and (metrics.momentum_exhaustion or metrics.latest_change_pct >= -1.6 or metrics.close_to_ma20 <= 1.2)
        ),
        execution_note="价格靠近关键均线，只等进入买点区。",
        summary_reason="均线多头排列，回踩关键均线后缩量。",
        reasons=[
            "股价仍站在 20 日和 60 日均线上方，5/10/20/60 日均线保持多头。",
            f"当前距离关键均线仅 {metrics.support_distance_pct:.2f}%，属于标准均线承接位置。",
            f"回调 {metrics.retracement_days} 天，近几日量能约为启动日的 {metrics.post_volume_ratio:.2f} 倍。",
        ],
    )


def _first_board_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    anchor_low = max(min(metrics.board_mid_price, metrics.ma5), metrics.board_low)
    anchor_high = max(metrics.ma5, metrics.board_open)
    return StrategySetup(
        entry_zone_low=round(anchor_low * 0.995, 3),
        entry_zone_high=round(anchor_high * 1.004, 3),
        execution_ready=(
            item.board_count == 1
            and metrics.retracement_days <= 6
            and metrics.board_low_held
            and (metrics.board_open_held or metrics.latest_close >= metrics.board_open * 0.982)
            and metrics.shrink_basic_ok
            and metrics.distribution_risk_score < 5.2
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
        ),
        execution_note="首板关键价未破，等价格回到首板承接区。",
        summary_reason="首板后的第一次健康回踩，关键价仍然守住。",
        reasons=[
            f"{item.board_date} 为首板启动，当前回调 {metrics.retracement_days} 天。",
            f"股价仍守住首板低点 {metrics.board_low:.3f} 与开盘价 {metrics.board_open:.3f} 附近承接。",
            f"回调缩量到启动日的 {metrics.post_volume_ratio:.2f} 倍，尚未出现明显出货。",
        ],
    )


def _volume_shrink_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    anchor = min(metrics.ma5, metrics.ma10)
    return StrategySetup(
        entry_zone_low=round(anchor * 0.992, 3),
        entry_zone_high=round(anchor * 1.006, 3),
        execution_ready=(
            metrics.volume_burst_ratio >= 1.5
            and metrics.shrink_basic_ok
            and metrics.support_distance_pct <= 2.35
            and metrics.post_volume_ratio <= 1.08
            and metrics.latest_volume_ratio <= 1.05
            and metrics.latest_close >= metrics.ma20 * 0.998
            and metrics.distribution_risk_score < 5.0
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
            and (metrics.momentum_exhaustion or metrics.latest_change_pct >= -1.6)
        ),
        execution_note="启动量能明确，等价格进入缩量承接区。",
        summary_reason="启动放量明显，回调量能持续递减。",
        reasons=[
            f"启动日量能达到前 5 日均量的 {metrics.volume_burst_ratio:.2f} 倍，存在主力异动信号。",
            f"回调阶段量能缩至启动日的 {metrics.post_volume_ratio:.2f} 倍，且呈阶梯式下降。",
            "当前价已回到均线支撑带附近，适合盯承接。",
        ],
    )


def _late_session_strong_support_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    anchor = max(min(metrics.latest_close, metrics.ma5 * 1.012), metrics.ma10 * 0.995)
    return StrategySetup(
        entry_zone_low=round(anchor * 0.994, 3),
        entry_zone_high=round(max(metrics.latest_close, anchor) * 1.004, 3),
        execution_ready=(
            score >= 84.0
            and metrics.close_position_ratio >= 0.60
            and metrics.support_distance_pct <= 2.4
            and metrics.latest_volume_ratio <= 1.05
            and metrics.post_volume_ratio <= 1.08
            and metrics.distribution_risk_score < 4.8
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
    anchor = metrics.ma5 if metrics.close_to_ma5 <= metrics.close_to_ma10 else metrics.ma10
    return StrategySetup(
        entry_zone_low=round(anchor * 0.994, 3),
        entry_zone_high=round(anchor * 1.006, 3),
        execution_ready=(
            score >= 84.0
            and item.amount >= CORE_MIDCAP_RETRACE_PREFILTER["min_amount"]
            and (metrics.strong_trend or metrics.trend_ok)
            and min(metrics.close_to_ma5, metrics.close_to_ma10) <= 1.5
            and metrics.support_distance_pct <= 1.8
            and metrics.latest_volume_ratio <= 1.05
            and metrics.post_volume_ratio <= 1.12
            and metrics.distribution_risk_score < 4.8
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
    anchor = max(metrics.board_low, min(metrics.ma5, metrics.board_mid_price))
    return StrategySetup(
        entry_zone_low=round(anchor * 0.994, 3),
        entry_zone_high=round(max(metrics.ma5, metrics.board_open) * 1.004, 3),
        execution_ready=(
            score >= 88.0
            and metrics.retracement_days <= 3
            and metrics.board_low_held
            and metrics.support_distance_pct <= 2.0
            and metrics.latest_volume_ratio <= 1.08
            and metrics.post_volume_ratio <= 1.10
            and metrics.distribution_risk_score < 4.8
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


def _breakout_support_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    anchor = max(metrics.breakout_level, metrics.ma10)
    return StrategySetup(
        entry_zone_low=round(anchor * 0.993, 3),
        entry_zone_high=round(anchor * 1.005, 3),
        execution_ready=(
            metrics.breakout_distance_pct <= 2.8
            and metrics.latest_close >= metrics.breakout_level * 0.99
            and (metrics.momentum_exhaustion or metrics.latest_change_pct >= -1.4)
        ),
        execution_note="突破支撑尚在，等回踩确认后再动手。",
        summary_reason="突破后的关键支撑位还在，位置盈亏比更清晰。",
        reasons=[
            f"前高/突破位在 {metrics.breakout_level:.3f} 附近，当前距离仅 {metrics.breakout_distance_pct:.2f}%。",
            "股价没有有效跌回突破位下方，位置支撑仍成立。",
            "更适合等回踩确认后的低吸，而不是追涨。",
        ],
    )


def _limit_up_breakout_retrace_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    support_anchor = max(
        metrics.platform_high,
        min(metrics.board_mid_price, metrics.ma10),
    )
    return StrategySetup(
        entry_zone_low=round(support_anchor * 0.996, 3),
        entry_zone_high=round(max(metrics.platform_high * 1.006, min(metrics.board_open, metrics.ma5) * 1.002), 3),
        execution_ready=(
            score >= LIMIT_UP_BREAKOUT_EXECUTION["min_score"]
            and item.board_count == 1
            and item.amount >= LIMIT_UP_BREAKOUT_EXECUTION["min_board_amount"]
            and metrics.platform_window_days >= LIMIT_UP_BREAKOUT_PREFILTER["min_platform_days"]
            and LIMIT_UP_BREAKOUT_PREFILTER["min_retracement_days"] <= metrics.retracement_days <= LIMIT_UP_BREAKOUT_PREFILTER["max_retracement_days"]
            and metrics.volume_burst_ratio >= LIMIT_UP_BREAKOUT_EXECUTION["min_volume_burst_ratio"]
            and metrics.platform_breakout_pct >= LIMIT_UP_BREAKOUT_EXECUTION["min_breakout_pct"]
            and metrics.platform_range_pct <= LIMIT_UP_BREAKOUT_PREFILTER["max_platform_range_pct"]
            and LIMIT_UP_BREAKOUT_EXECUTION["min_drawdown_pct"] <= metrics.drawdown_from_board_pct <= LIMIT_UP_BREAKOUT_EXECUTION["max_drawdown_pct"]
            and metrics.post_volume_ratio <= LIMIT_UP_BREAKOUT_EXECUTION["max_post_volume_ratio"]
            and metrics.latest_volume_ratio <= LIMIT_UP_BREAKOUT_EXECUTION["max_latest_volume_ratio"]
            and metrics.platform_support_distance_pct <= LIMIT_UP_BREAKOUT_EXECUTION["max_support_distance_pct"]
            and metrics.board_low_held
            and metrics.latest_close >= metrics.platform_high
            and metrics.latest_close >= metrics.board_open
            and metrics.momentum_exhaustion
            and (metrics.doji_like or metrics.long_lower_shadow or metrics.latest_close >= metrics.ma5 * 0.998)
        ),
        execution_note="平台突破后的洗盘回踩，只在关键位止跌并二次转强时处理。",
        summary_reason="低位平台放量涨停突破后，缩量回踩关键支撑位，等待二次启动。",
        reasons=[
            f"前面已有 {metrics.platform_window_days} 个交易日的平台整理，涨停日放量突破平台高点 {metrics.platform_high:.3f}。",
            f"回调 {metrics.retracement_days} 天，当前距平台突破位仅 {metrics.platform_support_distance_pct:.2f}%，且仍守住涨停开盘价与涨停低点。",
            f"回调均量缩到涨停日的 {metrics.post_volume_ratio:.2f} 倍，K 线呈现 {'十字/小实体' if metrics.doji_like else '下影承接'} 止跌特征。",
        ],
    )


def _divergence_consensus_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    entry_low = metrics.divergence_high * 1.002
    entry_high = metrics.divergence_high * 1.035
    return StrategySetup(
        entry_zone_low=round(entry_low, 3),
        entry_zone_high=round(entry_high, 3),
        execution_ready=(
            score >= DIVERGENCE_CONSENSUS_EXECUTION["min_score"]
            and metrics.consensus_breakout
            and metrics.consensus_volume_ratio >= DIVERGENCE_CONSENSUS_EXECUTION["min_consensus_volume_ratio"]
            and metrics.consolidation_volume_ratio <= DIVERGENCE_CONSENSUS_EXECUTION["max_consolidation_volume_ratio"]
            and metrics.consensus_close_strength >= DIVERGENCE_CONSENSUS_EXECUTION["min_close_strength"]
            and metrics.latest_close <= entry_high
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
            and metrics.distribution_risk_score < 5.5
        ),
        execution_note="已放量突破巨量分歧高点，属于右侧确认；只在不跌回突破位时执行。",
        summary_reason="底部涨停后经历分歧横盘，缩量沉淀后放量突破分歧高点。",
        reasons=[
            f"前面已有 {metrics.platform_window_days} 个交易日低位平台，涨停日放量达到前 5 日均量的 {metrics.volume_burst_ratio:.2f} 倍。",
            f"涨停后先出现放量分歧，再横盘沉淀 {metrics.consolidation_days} 天，量能缩到分歧日的 {metrics.consolidation_volume_ratio:.2f} 倍。",
            f"今日放量为近 5 日均量的 {metrics.consensus_volume_ratio:.2f} 倍，并突破分歧高点 {metrics.divergence_high:.3f}。",
        ],
    )


def _deep_pullback_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    anchor = max(metrics.ma20, metrics.recent_low_guard)
    return StrategySetup(
        entry_zone_low=round(anchor * 0.988, 3),
        entry_zone_high=round(anchor * 1.006, 3),
        execution_ready=(
            metrics.strong_trend
            and -9.2 <= metrics.drawdown_from_board_pct <= -2.8
            and metrics.support_distance_ma20_pct <= 3.6
            and (metrics.momentum_exhaustion or metrics.latest_change_pct >= -1.2)
        ),
        execution_note="这是高风险深回撤，只能在强趋势龙头上做。",
        summary_reason="龙头错杀回撤已较深，但趋势骨架未坏。",
        reasons=[
            f"相对启动位回撤 {metrics.drawdown_from_board_pct:.2f}%，已经进入深度低吸区。",
            f"股价距离 20 日线仅 {metrics.support_distance_ma20_pct:.2f}%，趋势骨架仍未破坏。",
            "当前位置更适合分批试仓，不能一次性重仓。",
        ],
    )


def _trend_rebound_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    anchor = min(metrics.ma10, max(metrics.ma20, metrics.breakout_level))
    return StrategySetup(
        entry_zone_low=round(anchor * 0.992, 3),
        entry_zone_high=round(anchor * 1.006, 3),
        execution_ready=(
            (metrics.strong_trend or metrics.latest_close >= metrics.ma20)
            and metrics.retracement_days >= 1
            and metrics.support_distance_pct <= 2.9
            and metrics.latest_close >= metrics.ma10 * 0.988
            and (metrics.momentum_exhaustion or metrics.latest_change_pct >= -1.4)
        ),
        execution_note="趋势未坏，等待二次上攻前的标准承接位。",
        summary_reason="趋势龙回头结构仍在，回调后没有破趋势。",
        reasons=[
            "前面已经有明显主升浪或大阳启动，当前属于二次上攻前的回踩段。",
            "股价仍在 10/20 日线之上，趋势没被破坏。",
            "更适合等价格回到承接位时低吸，不做高位追涨。",
        ],
    )


def _classic_retrace_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    anchor = min(metrics.ma5, metrics.ma10)
    return StrategySetup(
        entry_zone_low=round(anchor * 0.992, 3),
        entry_zone_high=round(anchor * 1.008, 3),
        execution_ready=(
            score >= 82
            and 1 <= metrics.retracement_days <= 6
            and metrics.support_distance_pct <= 2.8
            and metrics.post_volume_ratio <= 1.22
            and -3.8 <= metrics.latest_change_pct <= 3.6
            and (metrics.board_low_held or metrics.latest_close >= metrics.board_low * 0.985)
            and (metrics.shrink_basic_ok or metrics.momentum_exhaustion)
        ),
        execution_note="结构已经收敛，先等价格进入低吸区。",
        summary_reason="十日强势股回调到均线支撑位，结构已成熟。",
        reasons=[
            f"{item.board_date} 出现涨停，且启动量能约为前 5 日均量的 {metrics.volume_burst_ratio:.2f} 倍。",
            f"当前回调 {metrics.retracement_days} 天，已经回到 5/10 日均线附近，偏离仅 {metrics.support_distance_pct:.2f}%。",
            f"回调阶段量能约为涨停日的 {metrics.post_volume_ratio:.2f} 倍，短线抛压已经明显减弱。",
        ],
    )
