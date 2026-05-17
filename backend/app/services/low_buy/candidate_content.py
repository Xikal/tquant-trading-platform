from __future__ import annotations

from typing import Any

from app.services.low_buy.candidate_types import CandidateContextAdjustment, CandidateMetrics
from app.services.low_buy.shared import BoardCandidate, LowBuyCandidateOut


def entry_tolerance_pct(strategy: str) -> float:
    tolerance_map = {
        "classic_retrace": 0.8,
        "ma_support": 0.8,
        "first_board": 0.6,
        "volume_shrink": 0.6,
        "late_session_strong_support": 0.4,
        "core_midcap_vwap_ma5_retrace": 0.6,
        "sector_mainline_first_divergence_low_buy": 0.6,
        "mainline_limitup_shrink_retrace_reclaim": 0.5,
        "breakout_support": 0.5,
        "limit_up_breakout_retrace": 0.35,
        "divergence_consensus": 0.25,
        "n_pattern_long_wash": 0.45,
        "n_pattern_short_wash": 0.35,
        "deep_pullback": 0.0,
        "trend_rebound": 0.6,
    }
    return tolerance_map.get(strategy, 0.5)


def execution_quality(candidate: LowBuyCandidateOut) -> tuple[float, str]:
    state_score = {
        "buy_now": 34.0,
        "soft_buy_now": 27.0,
        "observe_confirmed": 22.0,
        "near_entry": 20.0,
        "watch": 8.0,
        "avoid": -22.0,
    }.get(candidate.buy_signal_state, 0.0)
    distance = max(candidate.entry_distance_pct, 0.0)
    if distance <= 0:
        distance_score = 18.0
    elif distance <= 0.5:
        distance_score = 12.0
    elif distance <= 1.0:
        distance_score = 7.0
    elif distance <= 2.0:
        distance_score = 2.0
    else:
        distance_score = -min(18.0, distance * 3.0)
    stop_gap = (
        (candidate.latest_price - candidate.stop_loss) / max(candidate.latest_price, 0.01) * 100
        if candidate.latest_price > 0
        else 0.0
    )
    if candidate.stop_loss >= candidate.latest_price:
        risk_score = -24.0
    elif 2.0 <= stop_gap <= 9.0:
        risk_score = 10.0
    elif stop_gap > 14.0:
        risk_score = -5.0
    else:
        risk_score = 3.0
    tier_score = {"block": -28.0, "degrade": -10.0, "note": 3.0}.get(candidate.risk_tier, 0.0)
    distribution_penalty = min(max(candidate.distribution_risk_score - 3.5, 0.0) * 2.6, 12.0)
    raw_score = 42.0 + state_score + distance_score + risk_score + tier_score - distribution_penalty
    score = round(max(0.0, min(raw_score, 100.0)), 1)
    if candidate.risk_tier == "block" or candidate.buy_signal_state == "avoid":
        label = "禁入"
    elif score >= 78:
        label = "高"
    elif score >= 58:
        label = "中"
    else:
        label = "低"
    return score, f"执行质量：{label}，到价/止跌/风控综合评分 {score:.1f}"


def initial_signal_state(
    *,
    execution_blocked: bool,
    execution_ready: bool,
    score: float,
    research_stage: str,
) -> str:
    if research_stage == "blocked":
        return "avoid"
    if research_stage in {"watch", "near_entry", "buy_ready"}:
        return "watch"
    if execution_blocked:
        return "avoid"
    return "watch" if execution_ready or score >= 80 else "avoid"


def build_candidate_reasons(base_reasons: list[str], research_layer: Any) -> list[str]:
    reasons = list(base_reasons)
    if research_layer.stage in {"watch", "near_entry", "buy_ready"} and research_layer.stage_text:
        reasons.append(f"研究分层：{research_layer.stage_text}。")
    if research_layer.near_miss_rules:
        reasons.extend(research_layer.near_miss_rules[:2])
    if research_layer.failed_rules:
        reasons.append("仍缺确认：" + "；".join(research_layer.failed_rules[:3]) + "。")
    if research_layer.blocked_reason:
        reasons.append(research_layer.blocked_reason)
    return reasons


def build_candidate_risks(
    strategy: str,
    metrics: CandidateMetrics,
    context_adjustment: CandidateContextAdjustment,
) -> list[str]:
    if strategy == "limit_up_breakout_retrace":
        risks = [
            "跌回平台高点、涨停开盘价或涨停低点，说明突破回踩失败。",
            "这类策略只适合低位平台突破后的首轮回踩，不适合追高加速段。",
        ]
        if metrics.false_breakout_flag:
            risks.append("突破后重新跌回关键位，疑似假突破，本轮不执行。")
        if metrics.intraday_reversal_flag:
            risks.append("回踩后冲高回落，说明承接不足，需要重新确认。")
        if metrics.distribution_risk_score >= 5.0:
            risks.append("派发风险偏高，回踩确认需要降级观察。")
        if context_adjustment.execution_blocked:
            risks.append("市场或风险分层阻断强买，只保留观察提醒。")
        return risks + context_adjustment.extra_risks
    if strategy == "divergence_consensus":
        risks = [
            "跌回分歧高点或横盘下沿，说明突破失败，应直接放弃。",
            "这类策略是右侧确认，不适合在缩量弱市或高位退潮期追击。",
        ]
        if metrics.false_breakout_flag:
            risks.append("突破后重新跌回关键位，疑似假突破，本轮不执行。")
        if metrics.stall_after_volume_flag:
            risks.append("放量后价格扩张变差，可能是边拉边派发。")
        if metrics.intraday_reversal_flag:
            risks.append("突破日冲高回落，收盘承接不足，需要重新站稳。")
        if metrics.distribution_risk_score >= 5.0:
            risks.append("派发风险偏高，突破确认需要降级观察。")
        if context_adjustment.execution_blocked:
            risks.append("风险分层已触发执行阻断，本轮不允许进入确定买入。")
        return risks + context_adjustment.extra_risks
    if strategy in {"n_pattern_long_wash", "n_pattern_short_wash"}:
        risks = [
            "跌破启动日低点，说明主力成本区失守，N 字结构直接失败。",
            "当前是核心生产策略，只能按小仓冲高止盈纪律执行。",
        ]
        if strategy == "n_pattern_short_wash":
            risks.append("短洗试错必须次日验证，不能把失败试仓拿成被动持仓。")
        if metrics.long_upper_shadow or metrics.intraday_reversal_flag:
            risks.append("出现长上影或冲高回落，说明承接不稳定，需要降级观察。")
        if metrics.distribution_risk_score >= 5.0:
            risks.append("派发风险偏高，N 字修复可能是假反抽。")
        return risks + context_adjustment.extra_risks
    risks = [
        "跌破止损位说明本次低吸逻辑失效，应直接离场。",
        "只适合上升趋势或震荡偏强市场，跌停潮里应整体降级处理。",
    ]
    if not metrics.shrink_basic_ok:
        risks.append("回调量能还没基本缩到位，若继续放量下跌，应从名单中剔除。")
    elif not metrics.shrink_ok:
        risks.append("当前缩量只是基本成立，还没到最理想的干净洗盘状态。")
    if not metrics.momentum_exhaustion:
        risks.append("下跌动能尚未钝化，当前仍不能硬接。")
    if metrics.distribution_risk_score >= 6.0:
        risks.append("近期派发风险偏高，哪怕价格到位也要等更强确认。")
    if metrics.trend_fatigue_score >= 6.0:
        risks.append("近 3 日出现趋势疲劳迹象，不能只按均线多头判断强势。")
    if context_adjustment.execution_blocked:
        risks.append("风险分层已触发执行阻断，本轮不允许进入确定买入。")
    return risks + context_adjustment.extra_risks


def build_candidate_tags(
    *,
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
    hot_industries: list[str],
    context_adjustment: CandidateContextAdjustment,
    factor_scores: dict[str, float],
) -> list[str]:
    factor_tags = [f"{label}+{value:.1f}" for label, value in factor_score_labels(factor_scores)]
    if strategy == "limit_up_breakout_retrace":
        return [
            "热点行业" if item.industry and hot_industries and item.industry in hot_industries else "趋势筛选",
            "平台回踩",
            "缩量承接" if metrics.post_volume_ratio <= 1.05 else "缩量待确认",
            "关键位附近" if metrics.platform_support_distance_pct <= 5.0 else "未到关键位",
            "首板启动",
            "研究策略",
            distribution_tag(metrics.distribution_risk_score),
            f"风险层级:{context_adjustment.risk_tier}",
            *factor_tags,
            *context_adjustment.extra_tags,
        ]
    if strategy == "divergence_consensus":
        return [
            "热点行业" if item.industry and hot_industries and item.industry in hot_industries else "趋势筛选",
            "分歧突破" if metrics.consensus_breakout else "突破待确认",
            "横盘缩量" if metrics.consolidation_volume_ratio <= 0.72 else "缩量不足",
            "首板启动",
            "右侧确认",
            distribution_tag(metrics.distribution_risk_score),
            f"风险层级:{context_adjustment.risk_tier}",
            *factor_tags,
            *context_adjustment.extra_tags,
        ]
    if strategy in {"n_pattern_long_wash", "n_pattern_short_wash"}:
        confirmation_tag = (
            "放量修复"
            if (
                strategy == "n_pattern_long_wash"
                and metrics.latest_change_pct >= 0.6
                and metrics.close_position_ratio >= 0.50
            )
            else "锤头/十字"
            if strategy == "n_pattern_short_wash" and (metrics.doji_like or metrics.long_lower_shadow)
            else "修复待确认"
        )
        return [
            "热点行业" if item.industry and hot_industries and item.industry in hot_industries else "趋势筛选",
            "长洗N字" if strategy == "n_pattern_long_wash" else "短洗N字",
            "启动低点未破" if metrics.board_low_held else "启动低点失守",
            "缩量洗盘" if metrics.post_volume_ratio <= 0.9 else "缩量待确认",
            confirmation_tag,
            "核心生产",
            distribution_tag(metrics.distribution_risk_score),
            f"风险层级:{context_adjustment.risk_tier}",
            *factor_tags,
            *context_adjustment.extra_tags,
        ]
    return [
        "热点行业" if item.industry and hot_industries and item.industry in hot_industries else "趋势筛选",
        "缩量回调" if metrics.shrink_ok else ("缩量基本成立" if metrics.shrink_basic_ok else "缩量待确认"),
        "均线支撑" if metrics.support_ok else "靠近支撑",
        "首板优先" if item.board_count == 1 else f"{item.board_count} 连板",
        "强趋势" if metrics.strong_trend else "趋势未坏",
        "趋势疲劳" if metrics.trend_fatigue_score >= 6.0 else "趋势健康",
        distribution_tag(metrics.distribution_risk_score),
        f"风险层级:{context_adjustment.risk_tier}",
        *factor_tags,
        *context_adjustment.extra_tags,
    ]


def distribution_tag(distribution_risk_score: float) -> str:
    if distribution_risk_score >= 6.0:
        return "派发风险高"
    if distribution_risk_score >= 3.5:
        return "派发风险关注"
    return "派发风险低"


def factor_score_labels(factor_scores: dict[str, float]) -> list[tuple[str, float]]:
    labels = {
        "deep_pullback_factor": "深回踩因子",
        "trend_rebound_factor": "龙回头因子",
        "shrink_quality_factor": "缩量质量",
        "gap_risk_factor": "缺口风险低",
        "volatility_regime_factor": "波动收敛",
        "time_efficiency_factor": "回撤节奏",
        "price_structure_factor": "价格结构",
        "sector_density_factor": "板块共振",
        "sector_flow_factor": "板块资金",
        "big_order_flow_factor": "大单流向",
        "event_risk_factor": "公告风险低",
        "signal_freshness_factor": "信号新鲜",
        "absorption_quality_factor": "分时承接",
        "selection_quality_factor": "选股质量",
    }
    return [
        (labels.get(key, key), value)
        for key, value in factor_scores.items()
        if value > 0
    ]


def final_position_cap(
    *,
    suggested_position_pct: float,
    volatility_position_pct: float,
    existing_reason: str,
) -> tuple[float, str]:
    if suggested_position_pct <= 0:
        return 0.0, existing_reason
    if volatility_position_pct <= 0:
        return round(suggested_position_pct, 2), existing_reason
    final_cap = round(min(float(suggested_position_pct), float(volatility_position_pct)), 2)
    if final_cap < suggested_position_pct:
        return final_cap, f"{existing_reason}，低于策略建议仓位时按波动率上限执行"
    return final_cap, existing_reason
