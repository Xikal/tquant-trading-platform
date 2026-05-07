from __future__ import annotations

from app.models.schemas import LowBuyNextDayEventPlanOut
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.shared import BoardCandidate


EVENT_MODEL_STRATEGIES = frozenset(
    {
        "limit_up_breakout_retrace",
        "divergence_consensus",
        "late_session_strong_support",
        "core_midcap_vwap_ma5_retrace",
        "sector_mainline_first_divergence_low_buy",
        "mainline_limitup_shrink_retrace_reclaim",
    }
)


def build_next_day_event_plan(
    *,
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
    research_stage: str,
) -> LowBuyNextDayEventPlanOut:
    if strategy == "limit_up_breakout_retrace":
        return _limit_up_retrace_plan(item=item, metrics=metrics, research_stage=research_stage)
    if strategy == "divergence_consensus":
        return _divergence_consensus_plan(item=item, metrics=metrics, research_stage=research_stage)
    if strategy == "late_session_strong_support":
        return _late_session_support_plan(metrics=metrics)
    if strategy == "core_midcap_vwap_ma5_retrace":
        return _core_midcap_retrace_plan(metrics=metrics)
    if strategy == "sector_mainline_first_divergence_low_buy":
        return _mainline_first_divergence_plan(metrics=metrics)
    if strategy == "mainline_limitup_shrink_retrace_reclaim":
        return _mainline_limitup_retrace_plan(metrics=metrics)
    return LowBuyNextDayEventPlanOut()


def _late_session_support_plan(*, metrics: CandidateMetrics) -> LowBuyNextDayEventPlanOut:
    return LowBuyNextDayEventPlanOut(
        state="take_profit_watch",
        state_text="次日冲高兑现",
        next_day_action="只看次日情绪惯性冲高，冲高 1.5%-3% 先兑现；不追高、不做趋势持有。",
        t2_action="T+2 前仍不能继续转强就退出，避免事件交易变成被动持仓。",
        first_take_profit_pct=1.5,
        second_take_profit_pct=3.0,
        max_holding_days=2,
        position_pct=8.0 if metrics.distribution_risk_score < 4.5 else 0.0,
        confirmation_rules=[
            "次日不能明显低开后走弱。",
            "开盘后重新站稳分时均线，回踩不破。",
            "不能出现放量冲高回落。",
        ],
        exit_rules=[
            "冲高 1.5%-3% 分批兑现。",
            "10:30 前不能站稳分时均线，降级退出。",
            "跌破收盘承接区，不再等待反抽。",
        ],
        risk_notes=_common_risk_notes(metrics),
    )


def _core_midcap_retrace_plan(*, metrics: CandidateMetrics) -> LowBuyNextDayEventPlanOut:
    return LowBuyNextDayEventPlanOut(
        state="weak_to_strong_candidate",
        state_text="短线修复候选",
        next_day_action="等回踩 5 日线或分时均线不破后再看修复，不能直接追涨。",
        t2_action="T+2 不强于板块或跌回 5 日线，退出等待下一次承接。",
        first_take_profit_pct=2.0,
        second_take_profit_pct=4.0,
        max_holding_days=2,
        position_pct=10.0 if metrics.distribution_risk_score < 4.8 else 0.0,
        confirmation_rules=[
            "站回分时均线，5/10 日线不破。",
            "分时低点抬高，反弹不是无量虚拉。",
            "板块中军或核心权重同步修复。",
        ],
        exit_rules=[
            "冲高 2%-4% 先处理一半风险。",
            "跌破 5 日线或分时均线后不回收，退出。",
            "弱于板块平均表现，不继续加仓。",
        ],
        risk_notes=_common_risk_notes(metrics),
    )


def _mainline_first_divergence_plan(*, metrics: CandidateMetrics) -> LowBuyNextDayEventPlanOut:
    return LowBuyNextDayEventPlanOut(
        state="weak_to_strong_candidate",
        state_text="主线回流候选",
        next_day_action="只等主线资金回流和个股弱转强确认；后排不追，板块不回流不买。",
        t2_action="T+2 没有继续强于板块，或跌破首板低点/5 日线，直接退出。",
        first_take_profit_pct=3.0,
        second_take_profit_pct=5.0,
        max_holding_days=3,
        position_pct=8.0 if metrics.distribution_risk_score < 5.0 else 0.0,
        confirmation_rules=[
            "板块热度回流，核心票不集体走弱。",
            "个股回踩不破首板低点和 5 日线。",
            "放量回升但不能长上影冲高回落。",
        ],
        exit_rules=[
            "次日冲高 3%-5% 先兑现。",
            "板块不回流，不做加仓。",
            "第 3 天仍不能转强，退出。",
        ],
        risk_notes=_common_risk_notes(metrics),
    )


def _mainline_limitup_retrace_plan(*, metrics: CandidateMetrics) -> LowBuyNextDayEventPlanOut:
    return LowBuyNextDayEventPlanOut(
        state="weak_to_strong_candidate",
        state_text="二次确认候选",
        next_day_action="只看低开不破支撑后重新站稳 5 日线/VWAP；高开急拉不追，回踩确认后再小仓。",
        t2_action="T+2 不能脱离买点区或重新跌回 5 日线，直接降级；最多验证到第 5 天。",
        first_take_profit_pct=3.0,
        second_take_profit_pct=5.0,
        max_holding_days=5,
        position_pct=8.0 if metrics.distribution_risk_score < 4.6 else 0.0,
        confirmation_rules=[
            "开盘后不能放量跌破 5 日线和支撑带。",
            "重新站稳 VWAP，分时低点抬高。",
            "回调量继续收缩，不能出现放量阴线。",
        ],
        exit_rules=[
            "冲高 3%-5% 先处理一半风险。",
            "跌回 5 日线、VWAP 或支撑带，直接退出。",
            "第 5 天仍不能形成修复，不继续占用资金。",
        ],
        risk_notes=_common_risk_notes(metrics),
    )


def _limit_up_retrace_plan(
    *,
    item: BoardCandidate,
    metrics: CandidateMetrics,
    research_stage: str,
) -> LowBuyNextDayEventPlanOut:
    risk_notes = _common_risk_notes(metrics)
    if research_stage == "blocked":
        return _failed_plan("确认失败", "假突破或派发风险过高，次日不参与。", risk_notes)
    if research_stage == "buy_ready":
        return LowBuyNextDayEventPlanOut(
            state="weak_to_strong_candidate",
            state_text="弱转强候选",
            next_day_action="明日只看低开后快速收回平台高点、站稳 VWAP 的弱转强，小仓确认，不追高。",
            t2_action="T+2 若不能继续强于板块，冲高先降仓；跌回平台高点直接退出。",
            first_take_profit_pct=3.0,
            second_take_profit_pct=5.0,
            max_holding_days=2,
            position_pct=_weak_to_strong_position(item=item, leader_rank="strong_follow"),
            confirmation_rules=[
                "开盘后 15-30 分钟不跌破平台高点。",
                "回踩 VWAP 不破，5/15 分钟低点抬高。",
                "强于板块平均表现，且不是急拉急跌。",
            ],
            exit_rules=_take_profit_exit_rules(anchor_name="平台高点"),
            risk_notes=risk_notes,
        )
    if research_stage == "near_entry":
        return LowBuyNextDayEventPlanOut(
            state="take_profit_watch",
            state_text="次日冲高兑现",
            next_day_action="若已有试仓，明日冲高 3%-5% 优先兑现；若无仓位，只等收回平台高点并站稳 VWAP。",
            t2_action="T+2 不允许无条件持有，不能转强就退出或继续观察。",
            first_take_profit_pct=3.0,
            second_take_profit_pct=5.0,
            max_holding_days=2,
            position_pct=0.0,
            confirmation_rules=[
                "距平台高点足够近，不能高开 6% 以上追。",
                "低开后快速翻红并站上 VWAP 才看弱转强。",
            ],
            exit_rules=_take_profit_exit_rules(anchor_name="平台高点"),
            risk_notes=risk_notes,
        )
    return LowBuyNextDayEventPlanOut(
        state="watch",
        state_text="明日观察",
        next_day_action="当前只是涨停突破回踩观察，明日先看是否靠近平台高点并出现承接。",
        t2_action="未进入接近买点层前，不做 T+2 执行计划。",
        first_take_profit_pct=3.0,
        second_take_profit_pct=5.0,
        max_holding_days=2,
        confirmation_rules=["平台高点不破。", "回踩量继续收缩。"],
        exit_rules=_take_profit_exit_rules(anchor_name="平台高点"),
        risk_notes=risk_notes,
    )


def _divergence_consensus_plan(
    *,
    item: BoardCandidate,
    metrics: CandidateMetrics,
    research_stage: str,
) -> LowBuyNextDayEventPlanOut:
    risk_notes = _common_risk_notes(metrics)
    if research_stage == "blocked":
        return _failed_plan("确认失败", "冲高回落或派发风险偏高，分歧一致失败。", risk_notes)
    if research_stage == "buy_ready":
        return LowBuyNextDayEventPlanOut(
            state="weak_to_strong_candidate",
            state_text="弱转强候选",
            next_day_action="明日必须放量站稳分歧高点，回踩 VWAP 不破后才允许小仓确认。",
            t2_action="T+2 若不能继续强于板块，或跌回分歧高点，直接降级退出。",
            first_take_profit_pct=3.0,
            second_take_profit_pct=5.0,
            max_holding_days=3,
            position_pct=_weak_to_strong_position(item=item, leader_rank="leader"),
            confirmation_rules=[
                "竞价低开不超过 -2.5%，高开不超过 +5%。",
                "放量站稳分歧高点，突破幅度不过度延伸。",
                "回踩 VWAP 不破，不能长上影或急拉急跌。",
            ],
            exit_rules=_take_profit_exit_rules(anchor_name="分歧高点"),
            risk_notes=risk_notes,
        )
    if research_stage == "near_entry":
        return LowBuyNextDayEventPlanOut(
            state="near_entry",
            state_text="等次日确认",
            next_day_action="当前只表示资金可能回流，明日必须放量站稳分歧高点才看弱转强。",
            t2_action="若 T+1 确认后买入，T+2 冲高先处理，不能幻想 5 日主升。",
            first_take_profit_pct=3.0,
            second_take_profit_pct=5.0,
            max_holding_days=3,
            position_pct=0.0,
            confirmation_rules=[
                "接近分歧高点但不追高。",
                "放量回升要配合收盘强度，不能长上影。",
            ],
            exit_rules=_take_profit_exit_rules(anchor_name="分歧高点"),
            risk_notes=risk_notes,
        )
    return LowBuyNextDayEventPlanOut(
        state="watch",
        state_text="明日观察",
        next_day_action="当前只记录分歧后沉淀，不代表可买，明日观察是否主动转强。",
        t2_action="没有 T+1 弱转强确认前，不生成 T+2 执行计划。",
        first_take_profit_pct=3.0,
        second_take_profit_pct=5.0,
        max_holding_days=3,
        confirmation_rules=["缩量沉淀不破横盘下沿。", "资金重新放量靠近分歧高点。"],
        exit_rules=_take_profit_exit_rules(anchor_name="分歧高点"),
        risk_notes=risk_notes,
    )


def _take_profit_exit_rules(anchor_name: str) -> list[str]:
    return [
        "盘中冲高 3% 至少减半，冲高 5% 大部分止盈。",
        "冲高后跌破 VWAP，剩余仓位降级退出。",
        f"跌破{anchor_name}或关键支撑，不等反抽。",
        "10:30 前不能转强，取消当日执行计划。",
    ]


def _common_risk_notes(metrics: CandidateMetrics) -> list[str]:
    notes: list[str] = []
    if metrics.long_upper_shadow:
        notes.append("长上影说明上方兑现压力大。")
    if metrics.weak_close:
        notes.append("收盘偏弱，次日必须重新转强才有意义。")
    if metrics.distribution_risk_score >= 4.5:
        notes.append("派发风险偏高，只能观察，不能追。")
    if metrics.false_breakout_flag:
        notes.append("假突破已触发，放弃执行。")
    return notes


def _weak_to_strong_position(*, item: BoardCandidate, leader_rank: str) -> float:
    if item.amount < 180_000_000:
        return 0.0
    return 12.0 if leader_rank == "leader" else 8.0


def _failed_plan(state_text: str, action: str, risk_notes: list[str]) -> LowBuyNextDayEventPlanOut:
    return LowBuyNextDayEventPlanOut(
        state="failed_confirmation",
        state_text=state_text,
        next_day_action=action,
        t2_action="确认失败样本不进入 T+2 计划。",
        max_holding_days=0,
        risk_notes=risk_notes,
    )
