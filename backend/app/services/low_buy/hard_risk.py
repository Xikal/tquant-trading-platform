from __future__ import annotations

from app.models.schemas import LowBuyHardRiskOut
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.strategy_parameter_defaults import LOW_BUY_HARD_RISK_DEFAULTS
from app.services.low_buy.shared import BoardCandidate
from app.services.quant.runtime_parameters import get_low_buy_hard_risk

_ST_MARKERS = ("ST", "*ST", "退")


def build_hard_risk_assessment(
    *,
    item: BoardCandidate,
    metrics: CandidateMetrics,
) -> LowBuyHardRiskOut:
    params = _hard_risk_params()
    reasons: list[str] = []
    tags: list[str] = []
    level = "clear"
    score_penalty = 0.0

    untradable_reason, untradable_tag = hard_untradable_reason(item=item, metrics=metrics)
    if untradable_reason:
        reasons.append(untradable_reason)
        tags.append(untradable_tag)
        return _assessment("block", 99.0, True, reasons, tags)

    amount_level, amount_penalty, amount_reason = _amount_risk(item.amount)
    if amount_reason:
        level = _max_level(level, amount_level)
        score_penalty += amount_penalty
        reasons.append(amount_reason)
        tags.append("硬风控:流动性")

    if metrics.distribution_risk_score >= params["distribution_block_score"]:
        level = _max_level(level, "block")
        score_penalty += params["distribution_block_penalty"]
        reasons.append("派发风险过高，技术买点不再具备执行价值。")
        tags.append("硬风控:派发")
    elif metrics.distribution_risk_score >= params["distribution_degrade_score"]:
        level = _max_level(level, "degrade")
        score_penalty += params["distribution_degrade_penalty"]
        reasons.append("派发风险偏高，需要降级观察。")
        tags.append("硬风控:派发关注")

    if (
        metrics.latest_volume_ratio >= params["volume_selloff_latest_volume_ratio"]
        and metrics.latest_change_pct <= params["volume_selloff_latest_change_pct"]
    ):
        level = _max_level(level, "degrade")
        score_penalty += params["volume_selloff_penalty"]
        reasons.append("最新交易日放量下跌，疑似资金主动撤退。")
        tags.append("硬风控:放量下跌")

    if metrics.latest_close < metrics.ma60 * params["trend_break_ma60_ratio"]:
        level = _max_level(level, "degrade")
        score_penalty += params["trend_break_penalty"]
        reasons.append("价格跌回 60 日线下方，趋势保护不足。")
        tags.append("硬风控:趋势破坏")

    return _assessment(level, score_penalty, level == "block", reasons, tags)


def hard_untradable_reason(*, item: BoardCandidate, metrics: CandidateMetrics) -> tuple[str, str]:
    """Return a hard block reason for symbols that should not enter low-buy scoring."""

    params = _hard_risk_params()
    if _has_name_risk(item.name):
        return "名称触发 ST/退市风险标记，低吸策略不参与。", "硬风控:名称风险"
    if metrics.latest_close <= 0:
        return "价格无效，无法确认真实买点。", "硬风控:价格无效"
    if item.amount <= 0:
        return "成交额缺失或疑似停牌，暂不进入低吸候选。", "硬风控:疑似停牌"
    if (
        metrics.latest_change_pct >= params["limit_up_change_pct"]
        and metrics.close_position_ratio >= params["limit_up_close_position_ratio"]
    ):
        return "价格接近涨停强封区域，低吸策略不追高。", "硬风控:涨停追高"
    if (
        metrics.latest_change_pct <= params["limit_down_change_pct"]
        and metrics.close_position_ratio <= params["limit_down_close_position_ratio"]
    ):
        return "价格接近跌停弱封区域，流动性和止损执行风险过高。", "硬风控:跌停流动性"
    return "", ""


def _has_name_risk(name: str) -> bool:
    upper_name = name.upper()
    return any(marker in upper_name for marker in _ST_MARKERS)


def _amount_risk(amount: float) -> tuple[str, float, str]:
    params = _hard_risk_params()
    if amount <= 0:
        return "degrade", params["amount_missing_penalty"], "成交额缺失，无法确认真实流动性。"
    if amount < params["amount_block_threshold"]:
        return "block", params["amount_block_penalty"], "成交额低于阻断阈值，流动性不足，低吸不参与。"
    if amount < params["amount_degrade_threshold"]:
        return "degrade", params["amount_degrade_penalty"], "成交额低于降级阈值，仓位和优先级需要下调。"
    return "clear", 0.0, ""


def _hard_risk_params() -> dict[str, float]:
    values = {**LOW_BUY_HARD_RISK_DEFAULTS, **get_low_buy_hard_risk()}
    return {str(key): float(value) for key, value in values.items()}


def _assessment(
    level: str,
    score_penalty: float,
    execution_blocked: bool,
    reasons: list[str],
    tags: list[str],
) -> LowBuyHardRiskOut:
    return LowBuyHardRiskOut(
        level=level,  # type: ignore[arg-type]
        score_penalty=round(score_penalty, 2),
        execution_blocked=execution_blocked,
        reasons=reasons,
        tags=tags,
    )


def _max_level(current: str, candidate: str) -> str:
    order = {"clear": 0, "note": 1, "degrade": 2, "block": 3}
    return candidate if order[candidate] > order[current] else current
