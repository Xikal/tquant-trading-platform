from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from app.repositories.low_buy import DailyBarRow
from app.services.finance.performance_math import sequence_max_drawdown_pct
from app.services.strategy_tracking_helpers import pct, round_or_none, round_value, text

ABNORMAL_GAIN_PCT = 35.0
ABNORMAL_DRAWDOWN_PCT = 15.0
EXTENSION_MIN_RETURN_PCT = 8.0
EXTENSION_MAX_DRAWDOWN_PCT = -6.0
GIVEBACK_WARN_RATIO = 0.35
TREND_MIN_BARS = 10
MIDLONG_MIN_BARS = 30


@dataclass(frozen=True)
class HoldingAnalysis:
    best_holding_days: int = 0
    best_exit_date: str | None = None
    best_exit_return_pct: float | None = None
    best_exit_drawdown_pct: float | None = None
    return_drawdown_ratio: float | None = None
    giveback_from_peak_pct: float | None = None
    holding_bucket: str = "unavailable"
    exit_quality: str = "unavailable"
    exit_reason: str = "后续行情不足"
    hold_extension_state: str = "unavailable"
    hold_extension_text: str = "数据不足"
    hold_extension_score: int = 0
    hold_extension_reasons: list[str] = field(default_factory=list)
    hold_extension_risks: list[str] = field(default_factory=list)
    suggested_holding_plan: str = "unavailable"


@dataclass(frozen=True)
class AttributionAnalysis:
    failure_tags: list[str] = field(default_factory=list)
    failure_reason_text: str = ""
    abnormal_return: bool = False
    needs_review: bool = False
    review_priority: str = "normal"
    audit_flags: list[str] = field(default_factory=list)


def analyze_holding(
    *,
    bars: list[DailyBarRow],
    first_signal_date: str,
    reference_price: float | None,
    stop_loss: float | None,
) -> HoldingAnalysis:
    if not reference_price or reference_price <= 0:
        return HoldingAnalysis(exit_reason="推荐价缺失")
    ordered = sorted(bars, key=lambda row: row.trade_date)
    posterior = [bar for bar in ordered if bar.trade_date > first_signal_date]
    if not posterior:
        return HoldingAnalysis(exit_reason="推荐日后行情不足")

    best_index = _best_exit_index(posterior, reference_price)
    best_bar = posterior[best_index]
    best_days = best_index + 1
    closes_to_best = [reference_price] + [bar.close_price for bar in posterior[: best_index + 1]]
    best_return = pct(best_bar.close_price, reference_price)
    best_drawdown = sequence_max_drawdown_pct(closes_to_best)
    peak_return = max(pct(bar.high_price, reference_price) for bar in posterior)
    current_return = pct(posterior[-1].close_price, reference_price)
    giveback = max(0.0, peak_return - current_return)
    extension = _extension_state(
        history=[bar for bar in ordered if bar.trade_date <= posterior[-1].trade_date],
        posterior=posterior,
        reference_price=reference_price,
        stop_loss=stop_loss,
        peak_return_pct=peak_return,
        current_return_pct=current_return,
    )
    return HoldingAnalysis(
        best_holding_days=best_days,
        best_exit_date=best_bar.trade_date,
        best_exit_return_pct=round_or_none(best_return),
        best_exit_drawdown_pct=round_or_none(best_drawdown),
        return_drawdown_ratio=round_or_none(_return_drawdown_ratio(best_return, best_drawdown)),
        giveback_from_peak_pct=round_or_none(giveback),
        holding_bucket=_holding_bucket(best_days),
        exit_quality=_exit_quality(best_return, best_drawdown, giveback),
        exit_reason=_exit_reason(best_days, best_return, best_drawdown, giveback),
        hold_extension_state=extension.hold_extension_state,
        hold_extension_text=extension.hold_extension_text,
        hold_extension_score=extension.hold_extension_score,
        hold_extension_reasons=extension.hold_extension_reasons,
        hold_extension_risks=extension.hold_extension_risks,
        suggested_holding_plan=extension.suggested_holding_plan,
    )


def analyze_attribution(
    *,
    payload: dict[str, Any],
    lifecycle_status: str,
    stats: dict[str, Any],
    holding: HoldingAnalysis,
    data_quality: str,
) -> AttributionAnalysis:
    tags: list[str] = []
    audit_flags: list[str] = []
    if not stats.get("entry_touched"):
        tags.append("no_entry_touch")
    if lifecycle_status == "stopped" and stats.get("entry_touched"):
        tags.append("fast_support_break")
    if lifecycle_status == "stopped":
        tags.append("stop_loss_triggered")
    if (holding.giveback_from_peak_pct or 0.0) >= 4.0:
        tags.append("spike_without_take_profit")
    if text(payload, "sector_state") == "sector_retreat" or "板块退潮" in text(payload, "sector_state_text", "market_state_text"):
        tags.append("sector_retreat")
    if text(payload, "market_state") in {"weak_market", "weak"} or "弱" in text(payload, "market_state_text", "market_state_category_text"):
        tags.append("market_mismatch")
    if data_quality in {"partial", "unavailable"}:
        tags.append("data_insufficient")
        audit_flags.append("data_quality_incomplete")
    if lifecycle_status == "invalidated":
        tags.append("signal_invalidated")
    max_gain = stats.get("max_gain_pct")
    max_drawdown = stats.get("max_drawdown_pct")
    excessive_drawdown = bool(max_drawdown is not None and abs(float(max_drawdown)) >= ABNORMAL_DRAWDOWN_PCT)
    abnormal = bool(
        (max_gain is not None and float(max_gain) >= ABNORMAL_GAIN_PCT)
        or (max_drawdown is not None and float(max_drawdown) > 0)
    )
    if abnormal:
        tags.append("abnormal_return")
        audit_flags.append("abnormal_return")
    if excessive_drawdown:
        audit_flags.append("excessive_drawdown")
    unique_tags = list(dict.fromkeys(tags))
    needs_review = abnormal or excessive_drawdown or bool({"data_insufficient", "market_mismatch"} & set(unique_tags))
    return AttributionAnalysis(
        failure_tags=unique_tags,
        failure_reason_text=_failure_text(unique_tags),
        abnormal_return=abnormal,
        needs_review=needs_review,
        review_priority="high" if abnormal else ("normal" if needs_review else "low"),
        audit_flags=audit_flags,
    )


def market_context(payload: dict[str, Any]) -> dict[str, str]:
    market_state = text(payload, "market_state") or _market_state_from_text(text(payload, "market_state_text", "market_state_category_text"))
    market_text = text(payload, "market_state_text", "market_state_category_text") or _market_state_label(market_state)
    sector_state = text(payload, "sector_state") or _sector_state_from_text(text(payload, "sector_state_text", "mainline_tier_text", "leader_strength_text"))
    sector_text = text(payload, "sector_state_text", "mainline_tier_text", "leader_strength_text") or _sector_state_label(sector_state)
    return {
        "market_state": market_state or "unknown",
        "market_state_text": market_text or "市场状态不足",
        "sector_state": sector_state or "sector_unknown",
        "sector_state_text": sector_text or "板块状态不足",
    }


def audit_context(
    *,
    payload: dict[str, Any],
    bars: list[DailyBarRow],
    first_signal_date: str,
    latest_trade_date: str,
    audit_flags: list[str],
) -> dict[str, Any]:
    ordered = sorted(bars, key=lambda row: row.trade_date)
    posterior = [bar for bar in ordered if bar.trade_date > first_signal_date]
    first_bar = next((bar for bar in ordered if bar.trade_date >= first_signal_date), None)
    last_bar = posterior[-1] if posterior else None
    return {
        "signal_generated_at": text(payload, "signal_generated_at", "generated_at") or first_signal_date,
        "data_cutoff_at": text(payload, "data_cutoff_at", "data_cutoff") or first_signal_date,
        "lookback_start_date": text(payload, "lookback_start_date") or (ordered[0].trade_date if ordered else ""),
        "lookback_end_date": text(payload, "lookback_end_date") or first_signal_date,
        "posterior_start_date": posterior[0].trade_date if posterior else "",
        "posterior_end_date": last_bar.trade_date if last_bar else "",
        "market_data_source": first_bar.source if first_bar else "",
        "market_data_updated_at": first_bar.fetch_time if first_bar else "",
        "future_leak_check": "needs_review" if audit_flags else "passed",
        "audit_flags": audit_flags,
    }


def _best_exit_index(posterior: list[DailyBarRow], reference_price: float) -> int:
    best_score = -10_000.0
    best_index = 0
    closes = [reference_price]
    running_high = reference_price
    for index, bar in enumerate(posterior):
        closes.append(bar.close_price)
        running_high = max(running_high, bar.high_price)
        return_pct = pct(bar.close_price, reference_price)
        drawdown_pct = sequence_max_drawdown_pct(closes)
        giveback_penalty = max(0.0, pct(running_high, reference_price) - return_pct) * 0.35
        score = return_pct - abs(min(drawdown_pct, 0.0)) * 0.75 - giveback_penalty
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def _extension_state(
    *,
    history: list[DailyBarRow],
    posterior: list[DailyBarRow],
    reference_price: float,
    stop_loss: float | None,
    peak_return_pct: float,
    current_return_pct: float,
) -> HoldingAnalysis:
    latest = posterior[-1]
    closes = [bar.close_price for bar in history]
    drawdown = sequence_max_drawdown_pct([reference_price] + [bar.close_price for bar in posterior])
    reasons: list[str] = []
    risks: list[str] = []
    score = 0
    if current_return_pct >= EXTENSION_MIN_RETURN_PCT:
        score += 25
        reasons.append("已有足够利润垫")
    else:
        risks.append("利润垫不足")
    if drawdown >= EXTENSION_MAX_DRAWDOWN_PCT:
        score += 20
        reasons.append("持有期回撤受控")
    else:
        risks.append("持有期回撤过大")
    ma20 = _moving_average(closes, 20)
    ma20_prev = _moving_average(closes[:-5], 20) if len(closes) >= 25 else None
    if ma20 is not None and latest.close_price >= ma20 and (ma20_prev is None or ma20 >= ma20_prev):
        score += 25
        reasons.append("价格站上MA20且均线未走弱")
    else:
        risks.append("MA20趋势确认不足")
    ma60 = _moving_average(closes, 60)
    if ma60 is not None and latest.close_price >= ma60:
        score += 15
        reasons.append("价格站上MA60")
    giveback_ratio = ((peak_return_pct - current_return_pct) / peak_return_pct) if peak_return_pct > 0 else 0.0
    if giveback_ratio >= GIVEBACK_WARN_RATIO:
        risks.append("利润回吐过多")
        score = min(score, 55)
    if stop_loss and latest.low_price <= stop_loss:
        return HoldingAnalysis(
            hold_extension_state="risk_off",
            hold_extension_text="跌破止损，不适合延长持有",
            hold_extension_score=min(score, 30),
            hold_extension_reasons=reasons,
            hold_extension_risks=[*risks, "已触及止损"],
            suggested_holding_plan="exit_review",
        )
    if len(posterior) >= MIDLONG_MIN_BARS and score >= 80:
        state, text_value, plan = "qualified", "可转中长线观察", "midlong_hold"
    elif len(posterior) >= TREND_MIN_BARS and score >= 65:
        state, text_value, plan = "qualified", "可转波段趋势持有", "trend_hold"
    elif score >= 45:
        state, text_value, plan = "watch", "继续观察，暂不确认中长线", "swing_hold"
    else:
        state, text_value, plan = "not_qualified", "不适合延长持有", "short_take_profit" if current_return_pct > 0 else "exit_review"
    return HoldingAnalysis(
        hold_extension_state=state,
        hold_extension_text=text_value,
        hold_extension_score=score,
        hold_extension_reasons=reasons,
        hold_extension_risks=risks,
        suggested_holding_plan=plan,
    )


def _return_drawdown_ratio(return_pct: float, drawdown_pct: float) -> float:
    drawdown_abs = abs(min(drawdown_pct, 0.0))
    return round_value(return_pct if drawdown_abs <= 0.01 else return_pct / drawdown_abs)


def _holding_bucket(days: int) -> str:
    if days <= 0:
        return "unavailable"
    if days <= 3:
        return "short_1_3d"
    if days <= 10:
        return "swing_4_10d"
    if days <= 30:
        return "trend_11_30d"
    return "midlong_31_120d"


def _exit_quality(return_pct: float, drawdown_pct: float, giveback_pct: float) -> str:
    if return_pct <= 0:
        return "no_profit"
    if drawdown_pct <= -10:
        return "drawdown_excessive"
    if giveback_pct >= max(4.0, return_pct * 0.5):
        return "late_exit"
    if return_pct >= 8 and drawdown_pct >= -6:
        return "excellent"
    return "acceptable"


def _exit_reason(days: int, return_pct: float, drawdown_pct: float, giveback_pct: float) -> str:
    if return_pct <= 0:
        return "推荐后未形成正收益窗口"
    if drawdown_pct <= -10:
        return "收益窗口伴随过大回撤"
    if giveback_pct >= max(4.0, return_pct * 0.5):
        return "最佳收益后回吐明显"
    if days <= 3:
        return "短线冲高窗口明确"
    if days <= 10:
        return "波段持有收益更优"
    if days <= 30:
        return "趋势持有收益更优"
    return "中长线持有收益更优"


def _failure_text(tags: list[str]) -> str:
    labels = {
        "no_entry_touch": "未触达买点",
        "fast_support_break": "买入后快速跌破支撑",
        "spike_without_take_profit": "冲高未止盈",
        "sector_retreat": "板块退潮",
        "market_mismatch": "大盘环境不匹配",
        "data_insufficient": "数据不足",
        "abnormal_return": "异常收益，需要复核",
        "stop_loss_triggered": "跌破止损",
        "signal_invalidated": "策略信号失效",
    }
    return "；".join(labels.get(tag, tag) for tag in tags)


def _market_state_from_text(value: str) -> str:
    if "强" in value:
        return "strong_market"
    if "弱" in value or "退潮" in value:
        return "weak_market"
    if "震荡" in value:
        return "range_market"
    return "unknown"


def _sector_state_from_text(value: str) -> str:
    if "主升" in value or "强" in value:
        return "sector_main_rise"
    if "轮动" in value:
        return "sector_rotation"
    if "退潮" in value or "弱" in value:
        return "sector_retreat"
    return "sector_unknown"


def _market_state_label(value: str) -> str:
    return {
        "strong_market": "强势行情",
        "range_market": "震荡行情",
        "weak_market": "弱势行情",
    }.get(value, "市场状态不足")


def _sector_state_label(value: str) -> str:
    return {
        "sector_main_rise": "板块主升",
        "sector_rotation": "板块轮动",
        "sector_retreat": "板块退潮",
    }.get(value, "板块状态不足")


def _moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])
