from __future__ import annotations

from typing import Any

from app.core.timezone import beijing_now_string
from app.services.market.autofill import MarketDataAutofillService
from app.models.schema_defs.market import IntradayMarketPulse, MarketBreadthResponse, SectorRelativeStrengthResponse

_QUALITY_RANK = {"fresh": 0, "stale": 1, "partial": 2, "unavailable": 3}


def build_intraday_market_pulse(
    *,
    market_breadth: MarketBreadthResponse | None,
    sector_relative_strength: SectorRelativeStrengthResponse | None,
    autofill_service: MarketDataAutofillService | None = None,
    trade_date: str = "",
    cutoff_time: str = "",
    partial_errors: list[dict[str, str]] | None = None,
) -> IntradayMarketPulse:
    errors = list(partial_errors or [])
    if market_breadth is None:
        errors.append({"source": "market_breadth", "detail": "市场宽度不可用"})
    if sector_relative_strength is None:
        errors.append({"source": "sector_relative_strength", "detail": "龙头强度不可用"})

    hourly = dict(market_breadth.hourly_all_market_snapshot or {}) if market_breadth else {}
    if not hourly:
        errors.append({"source": "hourly_all_market_snapshot", "detail": "小时全市场快照尚未生成"})
    if market_breadth and not market_breadth.emotion_ready:
        errors.append({"source": "emotion_temperature", "detail": "情绪温度样本不足"})

    autofill_details: list[dict[str, Any]] = []
    if autofill_service is not None:
        filled = autofill_service.fill_for_pulse(
            market_breadth=market_breadth,
            sector_relative_strength=sector_relative_strength,
            trade_date=trade_date,
            cutoff_time=cutoff_time,
        )
        market_breadth = filled.market_breadth or market_breadth
        sector_relative_strength = filled.sector_relative_strength or sector_relative_strength
        autofill_details = filled.details
        if autofill_details:
            errors = [item for item in errors if item.get("source") not in {detail.get("source") for detail in autofill_details}]

    hourly = dict(market_breadth.hourly_all_market_snapshot or {}) if market_breadth else {}
    quality = _aggregate_quality(market_breadth=market_breadth, hourly=hourly, errors=errors)
    market_score = _float(hourly.get("market_strength_score"), 0.0)
    emotion_score = _float(getattr(market_breadth, "emotion_temperature_score", 0.0) if market_breadth else 0.0, 0.0)
    leader_score = _leader_score(sector_relative_strength)
    pulse_score = market_score * 0.45 + emotion_score * 0.30 + leader_score * 0.25
    pulse_level, pulse_text, action = _pulse_decision(
        pulse_score=pulse_score,
        quality=quality,
        market_text=str(hourly.get("market_strength_text") or getattr(market_breadth, "state_text", "") or ""),
    )

    return IntradayMarketPulse(
        updated_at=beijing_now_string(),
        data_quality=quality,
        data_quality_text=_quality_text(quality, errors),
        market_strength_text=str(hourly.get("market_strength_text") or (market_breadth.state_text if market_breadth else "市场强弱待确认")),
        leader_strength_text=_leader_strength_text(sector_relative_strength),
        emotion_text=str(
            (market_breadth.emotion_temperature_text if market_breadth else "")
            or "情绪温度待确认"
        ),
        hourly_snapshot_text=str(hourly.get("data_quality_text") or hourly.get("market_strength_text") or "小时快照待确认"),
        pulse_level=pulse_level,
        pulse_text=pulse_text,
        suggested_action=action,
        partial_errors=errors,
        market_breadth_summary=_market_summary(market_breadth),
        leader_strength_summary=_leader_summary(sector_relative_strength),
        emotion_summary=_emotion_summary(market_breadth),
        hourly_snapshot_summary=hourly,
        autofill_details=autofill_details,
    )


def _aggregate_quality(
    *,
    market_breadth: MarketBreadthResponse | None,
    hourly: dict[str, Any],
    errors: list[dict[str, str]],
) -> str:
    states = []
    if market_breadth is None:
        states.append("unavailable")
    else:
        raw = str(getattr(market_breadth, "data_quality", "") or "").strip().lower()
        if raw in _QUALITY_RANK:
            states.append(raw)
        elif not market_breadth.breadth_ready or not market_breadth.emotion_ready:
            states.append("partial")
        else:
            states.append("fresh")
    if not hourly:
        states.append("partial" if market_breadth is not None else "unavailable")
    elif str(hourly.get("data_quality") or "").strip().lower() in _QUALITY_RANK:
        states.append(str(hourly.get("data_quality")).strip().lower())
    elif not hourly.get("ok", True):
        states.append("unavailable")
    if errors and not states:
        states.append("partial")
    if errors and "unavailable" not in states:
        states.append("partial")
    return max(states or ["unavailable"], key=lambda item: _QUALITY_RANK.get(item, 3))


def _quality_text(quality: str, errors: list[dict[str, str]]) -> str:
    if quality == "fresh":
        return "盘中 pulse 数据完整且新鲜"
    if quality == "stale":
        return "盘中 pulse 含过期数据，请结合时间戳判断"
    if quality == "partial":
        missing = "、".join(sorted({item.get("source", "") for item in errors if item.get("source")})[:3])
        return f"盘中 pulse 部分可用{f'，缺失：{missing}' if missing else ''}"
    return "盘中 pulse 暂不可用"


def _pulse_decision(*, pulse_score: float, quality: str, market_text: str) -> tuple[str, str, str]:
    if quality == "unavailable":
        return "unavailable", "盘中数据不足，不能形成可靠结论。", "暂停新增动作，等待数据恢复。"
    prefix = "数据部分缺失，" if quality in {"partial", "stale"} else ""
    if pulse_score >= 30:
        return "strong", f"{prefix}市场偏强：{market_text or '强结构扩散'}。", "只延续已验证方向，严禁因强势放宽买点。"
    if pulse_score >= 8:
        return "repair", f"{prefix}市场修复但仍需确认：{market_text or '结构温和修复'}。", "下午动作以确认承接为主，小仓试错。"
    if pulse_score <= -25:
        return "weak", f"{prefix}市场偏弱：{market_text or '风险释放不足'}。", "降低频率和仓位，优先处理风险。"
    if pulse_score <= -8:
        return "defensive", f"{prefix}市场转弱：{market_text or '分歧扩大'}。", "仅保留高质量信号，等待尾盘确认。"
    return "neutral", f"{prefix}市场强弱中性，结构分歧仍在。", "按既有信号质量执行，不扩大试错。"


def _leader_score(payload: SectorRelativeStrengthResponse | None) -> float:
    if payload is None or not payload.items:
        return 0.0
    return max(
        -100.0,
        min(
            100.0,
            sum(_float(getattr(item, "leader_score", 0.0), 0.0) for item in payload.items[:5])
            / min(len(payload.items), 5),
        ),
    )


def _leader_strength_text(payload: SectorRelativeStrengthResponse | None) -> str:
    if payload is None or not payload.items:
        return "龙头强度待确认"
    top = payload.items[0]
    sector = getattr(top, "sector_name", "") or "未分类"
    symbol = getattr(top, "symbol", "") or ""
    name = getattr(top, "name", "") or symbol or "未知标的"
    leader_score = _float(getattr(top, "leader_score", 0.0), 0.0)
    return f"{sector}龙头 {name}，强度 {leader_score:.0f}"


def _market_summary(payload: MarketBreadthResponse | None) -> dict[str, Any]:
    if payload is None:
        return {}
    return {
        "state": payload.state,
        "state_text": payload.state_text,
        "stock_up_ratio": payload.stock_up_ratio,
        "stock_median_change": payload.stock_median_change,
        "limit_up_count": payload.limit_up_count,
        "limit_down_count": payload.limit_down_count,
    }


def _leader_summary(payload: SectorRelativeStrengthResponse | None) -> dict[str, Any]:
    if payload is None:
        return {}
    return {
        "sector_count": payload.sector_count,
        "top": [
            {
                "sector_name": getattr(item, "sector_name", ""),
                "symbol": getattr(item, "symbol", ""),
                "name": getattr(item, "name", ""),
                "leader_score": getattr(item, "leader_score", None),
                "change_pct": getattr(item, "change_pct", None),
            }
            for item in payload.items[:5]
        ],
    }


def _emotion_summary(payload: MarketBreadthResponse | None) -> dict[str, Any]:
    if payload is None:
        return {}
    return {
        "emotion_temperature": payload.emotion_temperature,
        "emotion_temperature_text": payload.emotion_temperature_text,
        "emotion_temperature_score": payload.emotion_temperature_score,
        "hot_industries": payload.hot_industries,
    }


def _float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
