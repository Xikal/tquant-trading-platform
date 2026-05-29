from __future__ import annotations

import json
from datetime import date, timedelta

from app.models.entities import MarketModelObservation
from app.models.schema_defs.strategy_tracking import (
    StrategyTrackingItemOut,
    StrategyTrackingShadowObservationOut,
    StrategyTrackingSummaryOut,
)


def calendar_lookback(trade_date: str, days: int) -> str:
    try:
        parsed = date.fromisoformat(str(trade_date)[:10])
    except ValueError:
        return trade_date
    return (parsed - timedelta(days=days)).isoformat()


def linked_tracking_count(observations: list[MarketModelObservation], items: list[StrategyTrackingItemOut]) -> int:
    keys = {(item.symbol, item.first_signal_date) for item in items}
    return sum(1 for row in observations if (row.symbol, row.trade_date) in keys)


def observation_payload(row: MarketModelObservation) -> dict[str, object]:
    try:
        payload = json.loads(row.payload_json or "{}")
    except Exception:
        return {"schema_mismatch": True}
    return payload if isinstance(payload, dict) else {"schema_mismatch": True}


def payload_flag(payload: dict[str, object], *keys: str) -> bool:
    return any(payload.get(key) is True for key in keys)


def payload_status(payload: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def shadow_no_sample_reason(
    observations: list[MarketModelObservation],
    items: list[StrategyTrackingItemOut],
    linked_count: int,
) -> str:
    if not observations:
        return "no_model_observation"
    payloads = [observation_payload(row) for row in observations]
    statuses = {
        str(row.outcome_status or "")
        for row in observations
    } | {
        payload_status(payload, "no_sample_reason", "shadow_status", "job_status", "error_code", "status")
        for payload in payloads
    }
    if "schema_mismatch" in statuses or any(payload_flag(payload, "schema_mismatch", "schema_error") for payload in payloads):
        return "schema_mismatch"
    if "write_failed" in statuses or any(payload_flag(payload, "write_failed", "write_error") for payload in payloads):
        return "write_failed"
    if "shadow_job_not_run" in statuses or "not_run" in statuses:
        return "shadow_job_not_run"
    if "window_not_reached" in statuses or "pending_window" in statuses or any(payload_flag(payload, "window_not_reached") for payload in payloads):
        return "window_not_reached"
    if "strategy_disabled" in statuses or any(
        payload.get("strategy_enabled") is False or payload_status(payload, "strategy_status") in {"disabled", "paused"}
        for payload in payloads
    ):
        return "strategy_disabled"
    if all(not row.symbol or not row.trade_date for row in observations):
        return "data_missing"
    if not items or linked_count == 0:
        return "no_qualified_signal"
    return ""


def shadow_no_sample_reason_text(reason: str) -> str:
    return {
        "no_model_observation": "观测表里目前没有该模型观测记录",
        "no_qualified_signal": "当前窗口没有符合条件信号",
        "data_missing": "观测记录缺少可关联标的或行情数据",
        "strategy_disabled": "策略未启用",
        "window_not_reached": "观测时间窗口尚未满足",
        "shadow_job_not_run": "Shadow 任务未运行",
        "write_failed": "观测写入失败",
        "schema_mismatch": "观测字段或模型版本不匹配",
    }.get(reason, "")


def model_version(payload_json: str | None) -> str:
    try:
        payload = json.loads(payload_json or "{}")
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("model_version") or payload.get("model_version_id") or "")


def build_shadow_row(
    *,
    model_key: str,
    observations: list[MarketModelObservation],
    tracking_items: list[StrategyTrackingItemOut],
) -> StrategyTrackingShadowObservationOut:
    linked_count = linked_tracking_count(observations, tracking_items)
    reason = shadow_no_sample_reason(observations, tracking_items, linked_count)
    return StrategyTrackingShadowObservationOut(
        model_key=model_key,
        model_version=model_version(observations[0].payload_json) if observations else "",
        observation_count=len(observations),
        latest_observed_at=observations[0].observed_at.isoformat(timespec="seconds") if observations else None,
        linked_tracking_count=linked_count,
        no_sample_reason=reason,
        no_sample_reason_text=shadow_no_sample_reason_text(reason),
        actionable_count=sum(1 for row in observations if row.confidence > 0 or row.score > 0 or row.signal_state),
        settled_count=sum(1 for row in observations if row.outcome_status == "settled"),
        success_rate_pct=0.0,
    )


def report_markdown(
    *,
    report_type: str,
    summary: StrategyTrackingSummaryOut,
    items: list[StrategyTrackingItemOut],
    shadow: list[StrategyTrackingShadowObservationOut],
) -> str:
    stopped = sum(1 for item in items if item.stop_triggered)
    abnormal = sum(1 for item in items if item.abnormal_return)
    shadow_zero = [item.model_key for item in shadow if item.observation_count == 0]
    return "\n".join(
        [
            f"# 策略跟踪{'日报' if report_type == 'daily' else '周报'}",
            "",
            f"- 当前跟踪：{summary.tracking_count}",
            f"- 买点触达：{summary.in_entry_zone_count}",
            f"- 跌破止损：{stopped}",
            f"- 异常收益：{abnormal}",
            f"- Shadow 无样本模型：{', '.join(shadow_zero) if shadow_zero else '无'}",
        ]
    )
