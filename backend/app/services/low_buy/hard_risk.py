from __future__ import annotations

from app.models.schemas import LowBuyHardRiskOut
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.shared import BoardCandidate

_ST_MARKERS = ("ST", "*ST", "退")


def build_hard_risk_assessment(
    *,
    item: BoardCandidate,
    metrics: CandidateMetrics,
) -> LowBuyHardRiskOut:
    reasons: list[str] = []
    tags: list[str] = []
    level = "clear"
    score_penalty = 0.0

    if _has_name_risk(item.name):
        reasons.append("名称触发 ST/退市风险标记，低吸策略不参与。")
        tags.append("硬风控:名称风险")
        return _assessment("block", 99.0, True, reasons, tags)

    amount_level, amount_penalty, amount_reason = _amount_risk(item.amount)
    if amount_reason:
        level = _max_level(level, amount_level)
        score_penalty += amount_penalty
        reasons.append(amount_reason)
        tags.append("硬风控:流动性")

    if metrics.distribution_risk_score >= 7.0:
        level = _max_level(level, "block")
        score_penalty += 10.0
        reasons.append("派发风险过高，技术买点不再具备执行价值。")
        tags.append("硬风控:派发")
    elif metrics.distribution_risk_score >= 5.6:
        level = _max_level(level, "degrade")
        score_penalty += 5.0
        reasons.append("派发风险偏高，需要降级观察。")
        tags.append("硬风控:派发关注")

    if metrics.latest_volume_ratio >= 2.4 and metrics.latest_change_pct <= -2.5:
        level = _max_level(level, "degrade")
        score_penalty += 4.5
        reasons.append("最新交易日放量下跌，疑似资金主动撤退。")
        tags.append("硬风控:放量下跌")

    if metrics.latest_close < metrics.ma60 * 0.985:
        level = _max_level(level, "degrade")
        score_penalty += 4.0
        reasons.append("价格跌回 60 日线下方，趋势保护不足。")
        tags.append("硬风控:趋势破坏")

    return _assessment(level, score_penalty, level == "block", reasons, tags)


def _has_name_risk(name: str) -> bool:
    upper_name = name.upper()
    return any(marker in upper_name for marker in _ST_MARKERS)


def _amount_risk(amount: float) -> tuple[str, float, str]:
    if amount <= 0:
        return "degrade", 5.0, "成交额缺失，无法确认真实流动性。"
    if amount < 80_000_000:
        return "block", 12.0, "成交额低于 8000 万，流动性不足，低吸不参与。"
    if amount < 150_000_000:
        return "degrade", 4.0, "成交额低于 1.5 亿，仓位和优先级需要下调。"
    return "clear", 0.0, ""


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
