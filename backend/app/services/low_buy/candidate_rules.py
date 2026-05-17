from __future__ import annotations

from app.services.low_buy.candidate_distribution_gate import has_limit_up_distribution_exit
from app.services.low_buy.candidate_types import CandidateMetrics, StrategySetup
from app.services.low_buy.candidate_rule_params import (
    execution_params as _execution_params,
    prefilter_params as _prefilter_params,
)
from app.services.low_buy.candidate_prefilters import passes_strategy_prefilter
from app.services.low_buy.candidate_rules_n_pattern import (
    n_pattern_long_wash_setup,
    n_pattern_short_wash_setup,
)
from app.services.low_buy.candidate_rules_mainline import (
    _core_midcap_vwap_ma5_retrace_setup,
    _late_session_strong_support_setup,
    _mainline_limitup_shrink_retrace_reclaim_setup,
    _sector_mainline_first_divergence_low_buy_setup,
)
from app.services.low_buy.candidate_scoring import compute_score, score_candidate
from app.services.low_buy.shared import BoardCandidate


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
        "mainline_limitup_shrink_retrace_reclaim": _mainline_limitup_shrink_retrace_reclaim_setup,
        "ma_channel_band": _ma_channel_band_setup,
        "leader_pullback_band": _leader_pullback_band_setup,
        "n_pattern_long_wash": n_pattern_long_wash_setup,
        "n_pattern_short_wash": n_pattern_short_wash_setup,
        "breakout_support": _breakout_support_setup,
        "limit_up_breakout_retrace": _limit_up_breakout_retrace_setup,
        "divergence_consensus": _divergence_consensus_setup,
        "deep_pullback": _deep_pullback_setup,
        "trend_rebound": _trend_rebound_setup,
    }
    builder = setup_map.get(strategy, _classic_retrace_setup)
    return builder(item=item, metrics=metrics, score=score)


def _ma_support_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("ma_support")
    anchor = (
        metrics.ma5
        if metrics.close_to_ma5 <= execution["ma5_anchor_max_pct"]
        else metrics.ma10
        if metrics.close_to_ma10 <= execution["ma10_anchor_max_pct"]
        else metrics.ma20
    )
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor * execution["entry_high_multiplier"], 3),
        execution_ready=(
            (metrics.strong_trend or metrics.trend_ok)
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and (metrics.shrink_basic_ok or metrics.momentum_exhaustion)
            and (
                metrics.momentum_exhaustion
                or metrics.latest_change_pct >= execution["min_latest_change_pct"]
                or metrics.close_to_ma20 <= execution["max_close_to_ma20_pct"]
            )
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
    execution = _execution_params("first_board")
    prefilter = _prefilter_params("first_board")
    anchor_low = max(min(metrics.board_mid_price, metrics.ma5), metrics.board_low)
    anchor_high = max(metrics.ma5, metrics.board_open)
    return StrategySetup(
        entry_zone_low=round(anchor_low * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor_high * execution["entry_high_multiplier"], 3),
        execution_ready=(
            item.board_count == 1
            and metrics.retracement_days <= execution["max_retracement_days"]
            and metrics.board_low_held
            and (metrics.board_open_held or metrics.latest_close >= metrics.board_open * execution["min_board_open_hold_ratio"])
            and metrics.shrink_basic_ok
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
            and not has_limit_up_distribution_exit(metrics, prefilter)
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
    execution = _execution_params("volume_shrink")
    prefilter = _prefilter_params("volume_shrink")
    anchor = min(metrics.ma5, metrics.ma10)
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor * execution["entry_high_multiplier"], 3),
        execution_ready=(
            metrics.volume_burst_ratio >= execution["min_volume_burst_ratio"]
            and metrics.shrink_basic_ok
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.latest_close >= metrics.ma20 * execution["min_close_to_ma20_ratio"]
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
            and not has_limit_up_distribution_exit(metrics, prefilter)
            and (metrics.momentum_exhaustion or metrics.latest_change_pct >= execution["min_latest_change_pct"])
        ),
        execution_note="启动量能明确，等价格进入缩量承接区。",
        summary_reason="启动放量明显，回调量能持续递减。",
        reasons=[
            f"启动日量能达到前 5 日均量的 {metrics.volume_burst_ratio:.2f} 倍，存在主力异动信号。",
            f"回调阶段量能缩至启动日的 {metrics.post_volume_ratio:.2f} 倍，且呈阶梯式下降。",
            "当前价已回到均线支撑带附近，适合盯承接。",
        ],
    )


def _ma_channel_band_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("ma_channel_band")
    anchor = metrics.ma20
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor * execution["entry_high_multiplier"], 3),
        execution_ready=(
            score >= execution["min_score"]
            and metrics.latest_close >= metrics.ma20 * execution["min_close_to_ma20_ratio"]
            and metrics.close_to_ma20 <= execution["max_close_to_ma20_pct"]
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
        ),
        execution_note="均线通道波段仍处研究层，只用于回测和观察，不进入生产强买。",
        summary_reason="价格沿 20 日均线通道运行，回踩中轨附近但趋势骨架未破。",
        reasons=[
            f"股价距离 20 日均线约 {metrics.close_to_ma20:.2f}%，仍在通道承接区。",
            f"平台/趋势观察窗口约 {metrics.platform_window_days} 天，未明显跌破 60 日线。",
            f"近期量能约为启动日的 {metrics.post_volume_ratio:.2f} 倍，未出现异常放量破位。",
        ],
    )


def _leader_pullback_band_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("leader_pullback_band")
    anchor = max(min(metrics.ma10, metrics.board_mid_price), metrics.ma20)
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor * execution["entry_high_multiplier"], 3),
        execution_ready=(
            score >= execution["min_score"]
            and metrics.strong_trend
            and metrics.board_low_held
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
        ),
        execution_note="龙头回踩波段为研究策略，只记录二波可能性，不恢复生产强买。",
        summary_reason="热点龙头启动后回踩关键支撑，观察二波修复结构。",
        reasons=[
            f"启动量能达到均量的 {metrics.volume_burst_ratio:.2f} 倍，具备龙头事件基础。",
            f"当前回踩 {metrics.retracement_days} 天，仍守住启动低点和关键均线。",
            f"距离支撑约 {metrics.support_distance_pct:.2f}%，适合继续观察承接质量。",
        ],
    )


def _breakout_support_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("breakout_support")
    anchor = max(metrics.breakout_level, metrics.ma10)
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor * execution["entry_high_multiplier"], 3),
        execution_ready=(
            metrics.breakout_distance_pct <= execution["max_breakout_distance_pct"]
            and metrics.latest_close >= metrics.breakout_level * execution["min_close_to_breakout_ratio"]
            and (metrics.momentum_exhaustion or metrics.latest_change_pct >= execution["min_latest_change_pct"])
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
    prefilter = _prefilter_params("limit_up_breakout_retrace")
    execution = _execution_params("limit_up_breakout_retrace")
    return StrategySetup(
        entry_zone_low=round(support_anchor * execution.get("entry_low_multiplier", 0.996), 3),
        entry_zone_high=round(
            max(
                metrics.platform_high * execution.get("platform_entry_high_multiplier", 1.006),
                min(metrics.board_open, metrics.ma5) * execution.get("ma_entry_high_multiplier", 1.002),
            ),
            3,
        ),
        execution_ready=(
            score >= execution["min_score"]
            and item.board_count == 1
            and item.amount >= execution["min_board_amount"]
            and metrics.platform_window_days >= prefilter["min_platform_days"]
            and prefilter["min_retracement_days"] <= metrics.retracement_days <= prefilter["max_retracement_days"]
            and metrics.volume_burst_ratio >= execution["min_volume_burst_ratio"]
            and metrics.platform_breakout_pct >= execution["min_breakout_pct"]
            and metrics.platform_range_pct <= prefilter["max_platform_range_pct"]
            and execution["min_drawdown_pct"] <= metrics.drawdown_from_board_pct <= execution["max_drawdown_pct"]
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.platform_support_distance_pct <= execution["max_support_distance_pct"]
            and metrics.board_low_held
            and metrics.latest_close >= metrics.platform_high
            and metrics.latest_close >= metrics.board_open
            and metrics.momentum_exhaustion
            and (
                metrics.doji_like
                or metrics.long_lower_shadow
                or metrics.latest_close >= metrics.ma5 * execution.get("min_close_to_ma5_ratio", 0.998)
            )
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
    execution = _execution_params("divergence_consensus")
    entry_low = metrics.divergence_high * execution["entry_low_multiplier"]
    entry_high = metrics.divergence_high * execution["entry_high_multiplier"]
    return StrategySetup(
        entry_zone_low=round(entry_low, 3),
        entry_zone_high=round(entry_high, 3),
        execution_ready=(
            score >= execution["min_score"]
            and metrics.consensus_breakout
            and metrics.consensus_volume_ratio >= execution["min_consensus_volume_ratio"]
            and metrics.consolidation_volume_ratio <= execution["max_consolidation_volume_ratio"]
            and metrics.consensus_close_strength >= execution["min_close_strength"]
            and metrics.latest_close <= entry_high
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
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
    execution = _execution_params("deep_pullback")
    anchor = max(metrics.ma20, metrics.recent_low_guard)
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor * execution["entry_high_multiplier"], 3),
        execution_ready=(
            metrics.strong_trend
            and execution["min_drawdown_from_board_pct"] <= metrics.drawdown_from_board_pct <= execution["max_drawdown_from_board_pct"]
            and metrics.support_distance_ma20_pct <= execution["max_support_distance_ma20_pct"]
            and (metrics.momentum_exhaustion or metrics.latest_change_pct >= execution["min_latest_change_pct"])
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
    execution = _execution_params("trend_rebound")
    anchor = min(metrics.ma10, max(metrics.ma20, metrics.breakout_level))
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor * execution["entry_high_multiplier"], 3),
        execution_ready=(
            (metrics.strong_trend or metrics.latest_close >= metrics.ma20)
            and metrics.retracement_days >= execution["min_retracement_days"]
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and metrics.latest_close >= metrics.ma10 * execution["min_close_to_ma10_ratio"]
            and (metrics.momentum_exhaustion or metrics.latest_change_pct >= execution["min_latest_change_pct"])
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
    execution = _execution_params("classic_retrace")
    anchor = min(metrics.ma5, metrics.ma10)
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(anchor * execution["entry_high_multiplier"], 3),
        execution_ready=(
            score >= execution["min_score"]
            and execution["min_retracement_days"] <= metrics.retracement_days <= execution["max_retracement_days"]
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and execution["min_latest_change_pct"] <= metrics.latest_change_pct <= execution["max_latest_change_pct"]
            and (metrics.board_low_held or metrics.latest_close >= metrics.board_low * execution["min_board_low_reclaim_ratio"])
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
