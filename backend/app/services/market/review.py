from __future__ import annotations

import json
from datetime import date, datetime, time as dt_time
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now, beijing_today
from app.models.entities import MarketHourlySnapshotHistory, MarketPulseEvent, MarketReviewReport
from app.models.schema_defs.market import (
    MarketBreadthResponse,
    MarketReviewReportOut,
    MarketReviewStatusOut,
    SectorRelativeStrengthItem,
    SectorRelativeStrengthResponse,
)
from app.services.market.autofill import MarketDataAutofillService
from app.services.market.hourly_snapshot import latest_hourly_all_market_snapshot


class MarketReviewService:
    """Generate midday/close reviews for the whole A-share market."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_review_report(
        self,
        *,
        report_slot: str,
        target_date: date | None = None,
    ) -> MarketReviewReport:
        slot = _normalize_report_slot(report_slot)
        report_date = target_date or beijing_today()
        metrics = self._metrics_snapshot(report_date, slot=slot)
        summary, highlights, alerts, suggestion = _build_market_rule_report(slot, metrics)

        report = self._find_report(report_date, slot)
        if report is None:
            report = MarketReviewReport(report_date=report_date, report_slot=slot)
            self.db.add(report)
        report.overall_summary = summary
        report.strategy_highlights = _json_dumps(highlights)
        report.risk_alerts = _json_dumps(alerts)
        report.suggestion = suggestion
        report.raw_metrics_snapshot = _json_dumps({**metrics, "report_slot": slot})
        report.generated_at = beijing_now().replace(tzinfo=None)
        report.llm_model = "market-rule"
        self.db.flush()
        return report

    def _find_report(self, report_date: date, report_slot: str) -> MarketReviewReport | None:
        return self.db.execute(
            select(MarketReviewReport).where(
                MarketReviewReport.report_date == report_date,
                MarketReviewReport.report_slot == report_slot,
            )
        ).scalar_one_or_none()

    def _metrics_snapshot(self, report_date: date, *, slot: str) -> dict[str, Any]:
        trade_date = report_date.isoformat()
        cutoff = _slot_cutoff_time(slot)
        hourly_rows = self.db.execute(
            select(MarketHourlySnapshotHistory)
            .where(MarketHourlySnapshotHistory.trade_date == trade_date)
            .order_by(MarketHourlySnapshotHistory.snapshot_bucket.asc())
        ).scalars().all()
        pulse_rows = self.db.execute(
            select(MarketPulseEvent)
            .where(MarketPulseEvent.trade_date == trade_date)
            .order_by(MarketPulseEvent.created_at.asc(), MarketPulseEvent.id.asc())
        ).scalars().all()

        hourly_payloads = [
            payload
            for payload in (_json_dict(row.payload_json) for row in hourly_rows)
            if _payload_within_cutoff(payload, cutoff)
        ]
        if not hourly_payloads and report_date == beijing_today():
            latest_hourly = latest_hourly_all_market_snapshot(self.db)
            if latest_hourly and _payload_within_cutoff(latest_hourly, cutoff):
                hourly_payloads.append(latest_hourly)

        filtered_pulse_pairs = [
            (row, payload)
            for row, payload in ((row, _json_dict(row.payload_json)) for row in pulse_rows)
            if _pulse_within_cutoff(row, payload, cutoff)
        ]
        pulse_rows = [row for row, _payload in filtered_pulse_pairs]
        pulse_payloads = [payload for _row, payload in filtered_pulse_pairs]
        latest_hourly = _select_latest_usable_hourly(hourly_payloads, pulse_payloads)
        latest_pulse_row, latest_pulse = _select_latest_usable_pulse(pulse_rows, pulse_payloads)
        canonical_hourly = _select_latest_canonical_hourly(hourly_payloads)
        autofill = MarketDataAutofillService(self.db).fill_for_pulse(
            market_breadth=_market_breadth_for_review_autofill(canonical_hourly),
            sector_relative_strength=_sector_strength_from_metrics(latest_pulse),
            trade_date=trade_date,
            cutoff_time=_slot_cutoff_time(slot).strftime("%H:%M:%S") if _slot_cutoff_time(slot) else "",
        )
        if autofill.market_breadth is not None:
            latest_hourly = {
                **latest_hourly,
                "hourly_all_market_snapshot": autofill.market_breadth.hourly_all_market_snapshot,
                "emotion_temperature": autofill.market_breadth.emotion_temperature,
                "emotion_temperature_text": autofill.market_breadth.emotion_temperature_text,
                "emotion_temperature_score": autofill.market_breadth.emotion_temperature_score,
                "data_quality": autofill.market_breadth.data_quality,
                "data_quality_text": autofill.market_breadth.data_quality_text,
                "autofill_details": autofill.details,
            }
            latest_hourly = _merge_hourly_snapshot_metrics(latest_hourly, autofill.market_breadth.hourly_all_market_snapshot)
        if autofill.sector_relative_strength is not None:
            latest_pulse = {
                **latest_pulse,
                "leader_strength_text": _leader_strength_text_from_sector(autofill.sector_relative_strength),
                "leader_strength_summary": _leader_summary_from_sector(autofill.sector_relative_strength),
                "autofill_details": autofill.details,
            }
        if autofill.details:
            latest_pulse = {
                **latest_pulse,
                "partial_errors": _filtered_partial_errors(latest_pulse.get("partial_errors") or [], autofill.details),
                "data_quality_text": _append_quality_note(
                    str(latest_pulse.get("data_quality_text") or ""),
                    "自动补全已填入部分缺失字段",
                ),
            }
        score_series = [
            _float(item.get("market_strength_score"))
            for item in hourly_payloads
            if item and _payload_snapshot_count(item) > 0
        ]
        hourly_quality = str(latest_hourly.get("data_quality") or ("fresh" if latest_hourly.get("ok") else "unavailable"))
        pulse_quality = str(getattr(latest_pulse_row, "data_quality", "") or latest_pulse.get("data_quality") or "unavailable")
        data_quality = _combined_quality([hourly_quality, pulse_quality], latest_hourly)
        if autofill.details and data_quality == "unavailable":
            data_quality = "partial"
        data_quality_text = str(
            latest_pulse.get("data_quality_text")
            or latest_hourly.get("data_quality_text")
            or "市场复盘数据等待刷新。"
        )
        missing_data = _missing_data_items(latest_hourly, latest_pulse)
        if autofill.details:
            missing_data = _filtered_missing_data(missing_data, autofill.details)

        return {
            "trade_date": trade_date,
            "hourly_snapshot_count": len(hourly_payloads),
            "pulse_event_count": len(pulse_rows),
            "latest_hourly": latest_hourly,
            "latest_pulse": latest_pulse,
            "score_series": score_series,
            "market_strength_score": _float(latest_hourly.get("market_strength_score")),
            "market_strength_text": str(
                latest_pulse.get("market_strength_text")
                or latest_hourly.get("market_strength_text")
                or "市场强弱待确认"
            ),
            "snapshot_count": int(_float(latest_hourly.get("snapshot_count"))),
            "stock_up_ratio": _float(latest_hourly.get("stock_up_ratio")),
            "stock_down_ratio": _float(latest_hourly.get("stock_down_ratio")),
            "stock_median_change": _float(latest_hourly.get("stock_median_change")),
            "strong_count": int(_float(latest_hourly.get("strong_count"))),
            "weak_count": int(_float(latest_hourly.get("weak_count"))),
            "pulse_level": str(getattr(latest_pulse_row, "pulse_level", "") or latest_pulse.get("pulse_level") or "unknown"),
            "pulse_text": str(getattr(latest_pulse_row, "pulse_text", "") or latest_pulse.get("pulse_text") or "等待盘中数据刷新。"),
            "pulse_action": str(
                getattr(latest_pulse_row, "suggested_action", "")
                or latest_pulse.get("suggested_action")
                or "只读观察，不触发交易。"
            ),
            "leader_strength_text": str(latest_pulse.get("leader_strength_text") or "龙头强度待确认"),
            "emotion_text": str(latest_pulse.get("emotion_text") or "情绪温度待确认"),
            "data_quality": data_quality,
            "data_quality_text": data_quality_text,
            "missing_data": missing_data,
            "autofill_details": list(autofill.details),
        }


def build_market_review_summary(
    db: Session,
    *,
    target_date: date | None = None,
) -> tuple[MarketReviewStatusOut, list[MarketReviewReportOut]]:
    review_date = target_date or beijing_today()
    rows = db.execute(
        select(MarketReviewReport)
        .where(MarketReviewReport.report_date == review_date)
        .order_by(MarketReviewReport.report_slot.asc(), MarketReviewReport.generated_at.asc())
    ).scalars().all()
    reports = [_review_report_out(row) for row in rows]
    slots = {item.report_slot for item in reports}
    has_midday = "midday" in slots
    has_close = "close" in slots
    status = "complete" if has_midday and has_close else "midday_ready" if has_midday else "close_ready" if has_close else "empty"
    risk_count = sum(len(item.risk_alerts) for item in reports)
    return (
        MarketReviewStatusOut(
            trade_date=review_date.isoformat(),
            status=status,
            status_text=_status_text(status),
            has_midday=has_midday,
            has_close=has_close,
            next_trigger_at=_next_trigger_text(review_date, has_midday=has_midday, has_close=has_close),
            risk_alert_count=risk_count,
            suggested_action=_suggested_action(reports),
        ),
        reports,
    )


def list_market_review_history(db: Session, *, limit: int = 20) -> list[MarketReviewReportOut]:
    rows = db.execute(
        select(MarketReviewReport)
        .order_by(desc(MarketReviewReport.report_date), desc(MarketReviewReport.generated_at))
        .limit(max(1, min(limit, 200)))
    ).scalars().all()
    return [_review_report_out(row) for row in rows]


def _build_market_rule_report(
    slot: str,
    metrics: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], list[dict[str, str]], str]:
    slot_text = "午盘市场复盘" if slot == "midday" else "收盘市场复盘"
    slot_prefix = "中午看盘" if slot == "midday" else "收盘看盘"
    sample_count = int(metrics.get("snapshot_count") or 0)
    score = _float(metrics.get("market_strength_score"))
    up_ratio = _float(metrics.get("stock_up_ratio"))
    down_ratio = _float(metrics.get("stock_down_ratio"))
    median_change = _float(metrics.get("stock_median_change"))
    strong_count = int(metrics.get("strong_count") or 0)
    weak_count = int(metrics.get("weak_count") or 0)
    hourly_count = int(metrics.get("hourly_snapshot_count") or 0)
    if sample_count <= 0:
        summary = f"{slot_text}：现在还没有拿到足够的全市场行情样本，先不要根据这份复盘做加仓决定。"
    else:
        summary = (
            f"{slot_text}：{slot_prefix}整体偏{_plain_market_side(score)}。"
            f"这次统计了 {sample_count} 只股票，只有 {up_ratio * 100:.1f}% 在涨，"
            f"{down_ratio * 100:.1f}% 在跌，中位数涨跌幅是 {median_change:.2f}%。"
            f"大涨的有 {strong_count} 只，大跌的有 {weak_count} 只。"
            f"{_plain_market_conclusion(score, up_ratio, weak_count, strong_count)}"
        )

    highlights = [
        {
            "strategy": "市场涨跌面",
            "comment": (
                f"已看过 {hourly_count} 次小时快照。简单说，涨的股票约 {up_ratio * 100:.1f}%，"
                f"跌的股票约 {down_ratio * 100:.1f}%。"
                f"{'跌的明显更多，下午先把风险放前面。' if down_ratio > up_ratio else '涨的更多，但也要看主线能不能持续。'}"
            ),
            "trend": _trend_label(metrics.get("score_series") or []),
        },
        {
            "strategy": "带头股票",
            "comment": _plain_optional_text(str(metrics.get("leader_strength_text") or ""), "带头的强势股还不够清楚，暂时不要只靠个别股票判断全市场转强。"),
            "trend": "stable",
        },
        {
            "strategy": "市场情绪",
            "comment": _plain_optional_text(str(metrics.get("emotion_text") or ""), "情绪数据还不完整，先按保守口径处理。"),
            "trend": "stable",
        },
    ]
    alerts: list[dict[str, str]] = []
    if sample_count <= 0:
        alerts.append({"level": "warning", "content": "全市场行情样本不足，这次复盘只能当作提醒，不能当作交易依据。"})
    if metrics.get("data_quality") in {"partial", "stale", "unavailable"}:
        alerts.append({"level": "warning", "content": f"有些数据还不完整：{_plain_data_quality_text(metrics)}"})
    if metrics.get("missing_data"):
        alerts.append({"level": "warning", "content": f"缺少数据：{_plain_missing_data_text(metrics.get('missing_data'))}"})
    if score <= -10:
        alerts.append({"level": "warning", "content": "市场整体偏弱，不要因为少数股票反弹就判断行情已经转好。"})
    if weak_count > max(strong_count, 1) * 1.2:
        alerts.append({"level": "warning", "content": "大跌股票明显多于大涨股票，下午或明天开盘前先控制新开仓。"})
    if str(metrics.get("pulse_level") or "").lower() in {"weak", "defensive", "unavailable", "unknown"}:
        alerts.append({"level": "info", "content": f"盘中提示：{_plain_pulse_text(str(metrics.get('pulse_text') or ''))}"})

    suggestion = _market_suggestion(slot, score, metrics)
    return summary, highlights, alerts, suggestion


def _market_suggestion(slot: str, score: float, metrics: dict[str, Any]) -> str:
    pulse_action = str(metrics.get("pulse_action") or "")
    if slot == "midday":
        if score <= -10:
            return "下午先防守：少交易、少加仓，只看已经确认很强的方向；如果市场继续走弱，不追涨新标的。"
        if score >= 10:
            return "下午可以继续看主线，但只做计划内机会；不要因为盘面变好就放宽买点和止损。"
        return _plain_action_text(pulse_action) or "下午先观察，等涨跌面或带头股票再确认一次，再决定是否出手。"
    if score <= -10:
        return "今晚复盘先按弱市处理：明天先看风险，等开盘后涨的股票明显变多，再提高参与度。"
    if score >= 10:
        return "今晚把强势主线和风险点记清楚；明天只有在涨跌面继续支持时，才执行计划内标的。"
    return "今晚先按中性行情准备：明天等市场方向确认，再按计划控制仓位执行。"


def _plain_market_side(score: float) -> str:
    if score >= 25:
        return "强"
    if score >= 8:
        return "暖"
    if score <= -25:
        return "弱"
    if score <= -8:
        return "弱"
    return "中性"


def _plain_market_conclusion(score: float, up_ratio: float, weak_count: int, strong_count: int) -> str:
    if score <= -10 or weak_count > max(strong_count, 1) * 1.2:
        return "跌的面更大，说明市场还没有真正稳住，下午重点是少犯错。"
    if score >= 10 and up_ratio >= 0.55:
        return "涨的面占优，说明市场有修复，但仍要看龙头和成交能不能继续跟上。"
    return "多空还没有明显胜负，最好等下午再确认一次方向。"


def _plain_optional_text(value: str, fallback: str) -> str:
    text = value.strip()
    if not text or "待确认" in text or "数据不足" in text:
        return fallback
    return text


def _plain_data_quality_text(metrics: dict[str, Any]) -> str:
    raw = str(metrics.get("data_quality_text") or "").strip()
    if not raw:
        return "部分行情、情绪或龙头数据暂时缺失。"
    text = raw.replace("data_quality", "数据完整度").replace("pulse", "盘中提示")
    text = text.replace("partial", "部分可用").replace("unavailable", "暂不可用")
    text = text.replace("emotion_temperature", "情绪温度")
    text = text.replace("盘中 盘中提示", "盘中提示")
    if "缺失：" in text:
        text = text.replace("缺失：", "缺少")
        if not text.endswith("数据"):
            text = f"{text}数据"
    return text


def _plain_missing_data_text(items: Any) -> str:
    if not isinstance(items, list):
        return "部分行情、情绪或龙头数据暂时缺失。"
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("source") or "").strip()
        detail = str(item.get("detail") or "").strip()
        if name and detail:
            parts.append(f"{name}（{detail}）")
        elif name:
            parts.append(name)
    return "；".join(parts) or "部分行情、情绪或龙头数据暂时缺失。"


def _plain_pulse_text(value: str) -> str:
    text = value.strip()
    if not text:
        return "盘中提示还不完整，先按保守口径执行。"
    return text.replace("pulse", "盘中提示").replace("全市场", "市场整体")


def _plain_action_text(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return text.replace("只读观察", "先观察").replace("不触发交易", "暂时不主动开新仓")


def _review_report_out(row: MarketReviewReport) -> MarketReviewReportOut:
    metrics = _json_dict(row.raw_metrics_snapshot or "{}")
    return MarketReviewReportOut(
        id=int(row.id or 0),
        report_date=row.report_date.isoformat() if row.report_date else "",
        report_slot=row.report_slot or "",
        overall_summary=row.overall_summary or "",
        strategy_highlights=_json_list(row.strategy_highlights),
        risk_alerts=_json_list(row.risk_alerts),
        suggestion=row.suggestion or "",
        generated_at=row.generated_at.isoformat() if row.generated_at else "",
        llm_model=row.llm_model or "market-rule",
        missing_data=list(metrics.get("missing_data") or []),
        autofill_details=list(metrics.get("autofill_details") or []),
    )


def _normalize_report_slot(value: str) -> str:
    slot = str(value or "").strip().lower()
    return slot if slot in {"midday", "close"} else "close"


def _status_text(status: str) -> str:
    if status == "complete":
        return "今日市场午盘和收盘复盘已生成"
    if status == "midday_ready":
        return "今日市场午盘复盘已生成，等待收盘复盘"
    if status == "close_ready":
        return "今日市场收盘复盘已生成"
    return "今日暂无市场复盘"


def _next_trigger_text(review_date: date, *, has_midday: bool, has_close: bool) -> str:
    if not has_midday:
        return datetime.combine(review_date, dt_time(hour=11, minute=35)).strftime("%Y-%m-%d %H:%M")
    if not has_close:
        return datetime.combine(review_date, dt_time(hour=15, minute=5)).strftime("%Y-%m-%d %H:%M")
    return "下一交易日 11:35"


def _suggested_action(reports: list[MarketReviewReportOut]) -> str:
    if not reports:
        return "等待午盘或收盘市场复盘生成；盘中先看市场方向、风控和仓位，不急着开新仓。"
    close = next((item for item in reports if item.report_slot == "close"), None)
    midday = next((item for item in reports if item.report_slot == "midday"), None)
    return (close or midday or reports[-1]).suggestion or "按市场复盘执行，不放宽仓位和买点。"


def _combined_quality(values: list[str], latest_hourly: dict[str, Any]) -> str:
    quality = [str(item or "").lower() for item in values if item]
    raw_hourly = str(latest_hourly.get("data_quality") or "").lower()
    if raw_hourly in {"fresh", "stale", "partial", "unavailable"}:
        quality.append(raw_hourly)
    if not quality:
        return "unavailable"
    if "unavailable" in quality:
        return "unavailable"
    if "partial" in quality:
        return "partial"
    if "stale" in quality:
        return "stale"
    return "fresh"


def _slot_cutoff_time(slot: str) -> dt_time | None:
    if slot == "midday":
        return dt_time(hour=13, minute=30)
    return None


def _payload_within_cutoff(payload: dict[str, Any], cutoff: dt_time | None) -> bool:
    if cutoff is None:
        return True
    payload_time = _payload_time(payload)
    return payload_time is None or payload_time <= cutoff


def _pulse_within_cutoff(row: MarketPulseEvent, payload: dict[str, Any], cutoff: dt_time | None) -> bool:
    if cutoff is None:
        return True
    payload_time = _payload_time(payload)
    if payload_time is not None:
        return payload_time <= cutoff
    if row.created_at is not None:
        return row.created_at.time() <= cutoff
    return True


def _payload_time(payload: dict[str, Any]) -> dt_time | None:
    raw = str(payload.get("updated_at") or "")
    if not raw:
        hourly = payload.get("hourly_snapshot_summary")
        if isinstance(hourly, dict):
            raw = str(hourly.get("updated_at") or "")
    try:
        return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").time()
    except ValueError:
        return None


def _select_latest_usable_hourly(
    hourly_payloads: list[dict[str, Any]],
    pulse_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    pulse_hourly_payloads = [
        item.get("hourly_snapshot_summary")
        for item in pulse_payloads
        if isinstance(item.get("hourly_snapshot_summary"), dict)
    ]
    candidates = [item for item in [*hourly_payloads, *pulse_hourly_payloads] if isinstance(item, dict) and item]
    for item in reversed(candidates):
        if item.get("ok") and _payload_snapshot_count(item) > 0:
            return item
    return hourly_payloads[-1] if hourly_payloads else {}


def _select_latest_usable_pulse(
    pulse_rows: list[MarketPulseEvent],
    pulse_payloads: list[dict[str, Any]],
) -> tuple[MarketPulseEvent | None, dict[str, Any]]:
    paired = list(zip(pulse_rows, pulse_payloads))
    for row, payload in reversed(paired):
        quality = str(row.data_quality or payload.get("data_quality") or "").lower()
        hourly = payload.get("hourly_snapshot_summary") if isinstance(payload, dict) else None
        if quality != "unavailable" and isinstance(hourly, dict) and _payload_snapshot_count(hourly) > 0:
            return row, payload
    return paired[-1][:2] if paired else (None, {})


def _select_latest_canonical_hourly(hourly_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    for item in reversed(hourly_payloads):
        if not isinstance(item, dict):
            continue
        if bool(item.get("ok")) and _payload_snapshot_count(item) > 0:
            return item
    return {}


def _missing_data_items(latest_hourly: dict[str, Any], latest_pulse: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not latest_hourly or not latest_hourly.get("ok") or _payload_snapshot_count(latest_hourly) <= 0:
        items.append(
            {
                "source": "hourly_all_market_snapshot",
                "name": "全市场小时快照",
                "detail": "没有可用股票样本，涨跌家数、中位涨跌幅和强弱数量无法计算",
            }
        )
    for error in latest_pulse.get("partial_errors") or []:
        if not isinstance(error, dict):
            continue
        source = str(error.get("source") or "").strip()
        detail = str(error.get("detail") or "").strip()
        if source == "emotion_temperature":
            items.append({"source": source, "name": "情绪温度", "detail": detail or "样本不足"})
        elif source:
            items.append({"source": source, "name": _missing_source_name(source), "detail": detail or "暂不可用"})
    leader_summary = latest_pulse.get("leader_strength_summary")
    leader_text = str(latest_pulse.get("leader_strength_text") or "")
    if "待确认" in leader_text or (
        isinstance(leader_summary, dict)
        and int(_float(leader_summary.get("sector_count"))) <= 0
        and not leader_summary.get("top")
    ):
        items.append(
            {
                "source": "sector_relative_strength",
                "name": "板块/龙头强度",
                "detail": "没有可用板块龙头排行，不能判断谁在带头",
            }
        )
    return _dedupe_missing_items(items)


def _dedupe_missing_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in items:
        source = item.get("source") or item.get("name") or ""
        if not source or source in seen:
            continue
        seen.add(source)
        result.append(item)
    return result


def _missing_source_name(source: str) -> str:
    return {
        "market_breadth": "市场宽度",
        "sector_relative_strength": "板块/龙头强度",
        "hourly_all_market_snapshot": "全市场小时快照",
        "emotion_temperature": "情绪温度",
    }.get(source, source)


def _payload_snapshot_count(payload: dict[str, Any]) -> int:
    return int(_float(payload.get("snapshot_count")))


def _merge_hourly_snapshot_metrics(metrics: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or not snapshot:
        return metrics
    merged = dict(metrics)
    for key in (
        "ok",
        "snapshot_count",
        "stock_up_ratio",
        "stock_down_ratio",
        "stock_flat_count",
        "stock_median_change",
        "strong_count",
        "weak_count",
        "market_strength_score",
        "market_strength_text",
        "data_quality_text",
        "updated_at",
        "reason",
        "source",
    ):
        if key in snapshot and snapshot.get(key) is not None:
            merged[key] = snapshot[key]
    return merged


def _filtered_partial_errors(errors: list[dict[str, Any]], autofill_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filled_sources = {str(item.get("source") or "") for item in autofill_details if isinstance(item, dict)}
    filtered: list[dict[str, Any]] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        if str(item.get("source") or "") in filled_sources:
            continue
        filtered.append(item)
    return filtered


def _append_quality_note(text: str, note: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return note
    return clean if note in clean else f"{clean}；{note}"


def _filtered_missing_data(items: list[dict[str, str]], autofill_details: list[dict[str, Any]]) -> list[dict[str, str]]:
    filled_sources = {str(item.get("source") or "") for item in autofill_details if isinstance(item, dict)}
    return [item for item in items if str(item.get("source") or "") not in filled_sources]


def _market_breadth_from_metrics(metrics: dict[str, Any]) -> MarketBreadthResponse | None:
    if not metrics:
        return None
    return MarketBreadthResponse(
        updated_at=str(metrics.get("updated_at") or ""),
        state=str(metrics.get("state") or ""),
        state_text=str(metrics.get("state_text") or metrics.get("market_strength_text") or ""),
        breadth_ready=int(_float(metrics.get("snapshot_count"))) > 0,
        emotion_ready=str(metrics.get("emotion_temperature") or "").strip().lower() not in {"", "unknown"},
        stock_up_ratio=_float(metrics.get("stock_up_ratio")),
        stock_median_change=_float(metrics.get("stock_median_change")),
        largecap_change=_float(metrics.get("largecap_change")),
        smallcap_change=_float(metrics.get("smallcap_change")),
        style_divergence=_float(metrics.get("style_divergence")),
        limit_up_count=int(_float(metrics.get("strong_count"))),
        limit_down_count=int(_float(metrics.get("weak_count"))),
        broken_board_ratio=0.0,
        promotion_ratio=0.0,
        board_height=0,
        emotion_temperature=str(metrics.get("emotion_temperature") or "unknown"),
        emotion_temperature_text=str(metrics.get("emotion_temperature_text") or "情绪温度待确认"),
        emotion_temperature_score=_float(metrics.get("emotion_temperature_score")),
        hot_industries=list(metrics.get("hot_industries") or []),
        hot_turnover=_float(metrics.get("hot_turnover")),
        hot_overlap_ratio=_float(metrics.get("hot_overlap_ratio")),
        data_quality=str(metrics.get("data_quality") or "unavailable"),
        data_quality_text=str(metrics.get("data_quality_text") or ""),
        hourly_all_market_snapshot=dict(metrics.get("hourly_all_market_snapshot") or metrics.get("latest_hourly") or {}),
    )


def _market_breadth_for_review_autofill(metrics: dict[str, Any]) -> MarketBreadthResponse | None:
    breadth = _market_breadth_from_metrics(metrics)
    if breadth is None:
        return None
    snapshot = dict(metrics or {})
    if bool(snapshot.get("ok")) and int(_float(snapshot.get("snapshot_count"))) > 0:
        return breadth.model_copy(update={"hourly_all_market_snapshot": snapshot})
    return None


def _sector_strength_from_metrics(metrics: dict[str, Any]) -> SectorRelativeStrengthResponse | None:
    leader_summary = metrics.get("leader_strength_summary") if isinstance(metrics, dict) else None
    if not isinstance(leader_summary, dict):
        return None
    top_items = leader_summary.get("top")
    if not isinstance(top_items, list) or not top_items:
        return None
    items: list[SectorRelativeStrengthItem] = []
    for index, item in enumerate(top_items, start=1):
        if not isinstance(item, dict):
            continue
        items.append(
            SectorRelativeStrengthItem(
                sector_name=str(item.get("sector_name") or "未分类"),
                symbol=str(item.get("symbol") or ""),
                name=str(item.get("name") or ""),
                latest_price=_float(item.get("latest_price")),
                change_pct=_float(item.get("change_pct")),
                sector_median_change_pct=_float(item.get("sector_median_change_pct")),
                relative_strength_ratio=item.get("relative_strength_ratio"),
                volume_ratio=_float(item.get("volume_ratio")),
                turnover_proxy=_float(item.get("turnover_proxy")),
                leader_score=_float(item.get("leader_score")),
                rank=index,
                data_quality_text="复盘自动补全的龙头强度代理",
            )
        )
    if not items:
        return None
    return SectorRelativeStrengthResponse(
        updated_at=str(metrics.get("updated_at") or ""),
        trade_date=str(metrics.get("trade_date") or ""),
        sector_count=int(leader_summary.get("sector_count") or len(items)),
        items=items,
        notes=["复盘自动补全的龙头强度代理"],
    )


def _leader_strength_text_from_sector(payload: SectorRelativeStrengthResponse) -> str:
    if not payload.items:
        return "龙头强度待确认"
    top = payload.items[0]
    sector = str(getattr(top, "sector_name", "") or "未分类")
    name = str(getattr(top, "name", "") or getattr(top, "symbol", "") or "未知标的")
    score = _float(getattr(top, "leader_score", 0.0))
    return f"{sector}龙头 {name}，强度 {score:.0f}"


def _leader_summary_from_sector(payload: SectorRelativeStrengthResponse) -> dict[str, Any]:
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


def _trend_label(values: list[Any]) -> str:
    numbers = [_float(item) for item in values]
    if len(numbers) < 2:
        return "stable"
    delta = numbers[-1] - numbers[0]
    if delta >= 5:
        return "improving"
    if delta <= -5:
        return "declining"
    return "stable"


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(raw: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw or "[]")
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _float(value: object, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
