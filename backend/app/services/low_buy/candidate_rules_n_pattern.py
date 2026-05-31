from __future__ import annotations

from app.services.low_buy.candidate_rule_params import execution_params as _execution_params
from app.services.low_buy.candidate_rule_params import float_param
from app.services.low_buy.candidate_types import CandidateMetrics, StrategySetup
from app.services.low_buy.shared import BoardCandidate


def n_pattern_long_wash_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("n_pattern_long_wash")
    anchor = max(metrics.board_low, min(metrics.ma10, metrics.ma20, metrics.recent_low_guard))
    setup_ready = _long_wash_setup_ready(metrics=metrics, score=score, execution=execution)
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(max(anchor, metrics.ma10) * execution["entry_high_multiplier"], 3),
        execution_ready=setup_ready,
        execution_note="长洗 N 字已降为研究层，只记录严格确认样本，盈利以 3-5 日冲高观察为主。",
        summary_reason="大阳启动后 7-15 日缩量洗盘，未跌破启动低点，最新出现放量修复。",
        reasons=[
            f"启动日低点 {metrics.board_low:.3f} 未被有效跌破，主力成本区仍被守住。",
            f"洗盘 {metrics.retracement_days} 天，回调均量约为启动日的 {metrics.post_volume_ratio:.2f} 倍。",
            f"最新 K 线收盘位置 {metrics.close_position_ratio:.0%}，若继续放量中阳，才视为 N 字右侧确认。",
        ],
    )


def n_pattern_short_wash_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("n_pattern_short_wash")
    anchor = max(metrics.board_low, min(metrics.recent_low_guard, metrics.ma5, metrics.ma10))
    setup_ready = _short_wash_setup_ready(metrics=metrics, score=score, execution=execution)
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(max(anchor, metrics.ma5) * execution["entry_high_multiplier"], 3),
        execution_ready=setup_ready,
        execution_note="短洗 N 字为研究归档/删除候选，只记录 T+1/T+2 冲高验证，失败样本快速归因。",
        summary_reason="启动后 2-5 日快速分歧，红十字/锤头线守住启动低点，观察尾盘试错机会。",
        reasons=[
            f"启动后快速分歧 {metrics.retracement_days} 天，仍守住启动低点 {metrics.board_low:.3f}。",
            "最新 K 线呈红十字、锤头或探底回升特征，说明短线抛压有钝化迹象。",
            "该策略只适合小仓试错，次日若不能弱转强，应按 T+1 纪律退出。",
        ],
    )


def _long_wash_setup_ready(*, metrics: CandidateMetrics, score: float, execution: dict[str, object]) -> bool:
    return (
        score >= float_param(execution, "min_score", 84.0)
        and float_param(execution, "min_retracement_days", 7) <= metrics.retracement_days <= float_param(execution, "max_retracement_days", 15)
        and metrics.board_low_held
        and metrics.post_volume_ratio <= float_param(execution, "setup_max_post_volume_ratio", 0.90)
        and metrics.latest_volume_ratio <= float_param(execution, "setup_max_latest_volume_ratio", 1.45)
        and metrics.latest_change_pct >= float_param(execution, "setup_min_latest_change_pct", -0.5)
        and metrics.close_position_ratio >= float_param(execution, "setup_min_close_position_ratio", 0.45)
        and metrics.distribution_risk_score < float_param(execution, "setup_max_distribution_risk_score", 5.2)
        and not metrics.false_breakout_flag
        and not metrics.stall_after_volume_flag
        and not metrics.intraday_reversal_flag
    )


def _short_wash_setup_ready(*, metrics: CandidateMetrics, score: float, execution: dict[str, object]) -> bool:
    if metrics.long_upper_shadow and metrics.latest_volume_ratio >= float_param(execution, "setup_upper_shadow_volume_ratio", 0.9):
        return False
    return (
        score >= float_param(execution, "min_score", 84.0)
        and float_param(execution, "min_retracement_days", 2) <= metrics.retracement_days <= float_param(execution, "max_retracement_days", 5)
        and metrics.board_low_held
        and metrics.latest_volume_ratio <= float_param(execution, "setup_max_latest_volume_ratio", 1.15)
        and metrics.support_distance_pct <= float_param(execution, "setup_max_support_distance_pct", 4.5)
        and metrics.close_position_ratio >= float_param(execution, "setup_min_close_position_ratio", 0.45)
        and (metrics.doji_like or metrics.long_lower_shadow)
        and metrics.distribution_risk_score < float_param(execution, "setup_max_distribution_risk_score", 5.2)
        and not metrics.false_breakout_flag
        and not metrics.stall_after_volume_flag
        and not metrics.intraday_reversal_flag
    )
