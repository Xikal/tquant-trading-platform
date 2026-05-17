from __future__ import annotations

from app.services.low_buy.candidate_rule_params import execution_params as _execution_params
from app.services.low_buy.candidate_types import CandidateMetrics, StrategySetup
from app.services.low_buy.shared import BoardCandidate


def n_pattern_long_wash_setup(item: BoardCandidate, metrics: CandidateMetrics, score: float) -> StrategySetup:
    execution = _execution_params("n_pattern_long_wash")
    anchor = max(metrics.board_low, min(metrics.ma10, metrics.ma20, metrics.recent_low_guard))
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(max(anchor, metrics.ma10) * execution["entry_high_multiplier"], 3),
        execution_ready=(
            score >= execution["min_score"]
            and execution["min_retracement_days"] <= metrics.retracement_days <= execution["max_retracement_days"]
            and metrics.board_low_held
            and metrics.post_volume_ratio <= execution["max_post_volume_ratio"]
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.latest_change_pct >= execution["min_latest_change_pct"]
            and metrics.close_position_ratio >= execution["min_close_position_ratio"]
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
            and not metrics.intraday_reversal_flag
        ),
        execution_note="长洗 N 字仍处研究层，只记录守住启动低点后的放量修复，不进入生产强买。",
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
    return StrategySetup(
        entry_zone_low=round(anchor * execution["entry_low_multiplier"], 3),
        entry_zone_high=round(max(anchor, metrics.ma5) * execution["entry_high_multiplier"], 3),
        execution_ready=(
            score >= execution["min_score"]
            and execution["min_retracement_days"] <= metrics.retracement_days <= execution["max_retracement_days"]
            and metrics.board_low_held
            and metrics.latest_volume_ratio <= execution["max_latest_volume_ratio"]
            and metrics.support_distance_pct <= execution["max_support_distance_pct"]
            and metrics.close_position_ratio >= execution["min_close_position_ratio"]
            and (metrics.doji_like or metrics.long_lower_shadow)
            and metrics.distribution_risk_score < execution["max_distribution_risk_score"]
            and not metrics.false_breakout_flag
            and not metrics.long_upper_shadow
        ),
        execution_note="短洗 N 字为尾盘试错研究策略，失败必须次日快速 T 出。",
        summary_reason="启动后 2-5 日快速分歧，红十字/锤头线守住启动低点，观察尾盘试错机会。",
        reasons=[
            f"启动后快速分歧 {metrics.retracement_days} 天，仍守住启动低点 {metrics.board_low:.3f}。",
            "最新 K 线呈红十字、锤头或探底回升特征，说明短线抛压有钝化迹象。",
            "该策略只适合小仓试错，次日若不能弱转强，应按 T+1 纪律退出。",
        ],
    )
