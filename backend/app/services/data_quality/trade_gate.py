from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DataQualitySnapshot
from app.models.schema_defs.phase4 import DataSourceProbeResponse
from app.services.data_quality.schemas import TradeDataGateCheckOut, TradeDataGateResponse
from app.services.market.providers import DataSourceProbeService


CRITICAL_STATUSES = {"fail", "unavailable", "blocked_by_data"}
REQUIRED_DATASETS = ("daily_bars", "minute_bars", "tick_trades")


def build_trade_data_gate(
    db: Session,
    *,
    source_probe: DataSourceProbeResponse | None = None,
) -> TradeDataGateResponse:
    snapshots = _latest_snapshots(db)
    probe = source_probe or DataSourceProbeService().probe()
    checks = [
        _freshness_check(snapshots),
        _coverage_check(snapshots),
        _adjustment_check(snapshots),
        _sla_check(snapshots),
        _source_check(probe),
    ]
    return TradeDataGateResponse(ok=not any(item.severity == "red" for item in checks), checks=checks)


def _latest_snapshots(db: Session) -> list[DataQualitySnapshot]:
    rows = db.execute(
        select(DataQualitySnapshot)
        .where(DataQualitySnapshot.scope == "production_universe")
        .where(DataQualitySnapshot.dataset_key.in_(REQUIRED_DATASETS))
        .order_by(DataQualitySnapshot.dataset_key.asc(), DataQualitySnapshot.as_of_date.desc(), DataQualitySnapshot.id.desc())
    ).scalars().all()
    latest: dict[str, DataQualitySnapshot] = {}
    for row in rows:
        latest.setdefault(row.dataset_key, row)
    return [latest[key] for key in REQUIRED_DATASETS if key in latest]


def _freshness_check(rows: list[DataQualitySnapshot]) -> TradeDataGateCheckOut:
    if not rows:
        return _check("freshness", "行情新鲜度", False, "red", "缺少数据质量快照")
    stale = [item.dataset_key for item in rows if bool(item.stale)]
    if stale:
        return _check("freshness", "行情新鲜度", True, "yellow", f"部分数据偏旧：{'、'.join(stale)}")
    return _check("freshness", "行情新鲜度", True, "green", "关键数据集新鲜度正常")


def _coverage_check(rows: list[DataQualitySnapshot]) -> TradeDataGateCheckOut:
    missing = [f"{item.dataset_key} 缺 {int(item.missing_days or 0)} 天" for item in rows if int(item.missing_days or 0) > 0]
    if missing:
        return _check("coverage", "覆盖率缺口", False, "red", "；".join(missing))
    return _check("coverage", "覆盖率缺口", True, "green", "未发现关键覆盖缺口")


def _adjustment_check(rows: list[DataQualitySnapshot]) -> TradeDataGateCheckOut:
    invalid = [f"{item.dataset_key} invalid={int(item.invalid_rows or 0)} duplicate={int(item.duplicate_rows or 0)}" for item in rows if int(item.invalid_rows or 0) or int(item.duplicate_rows or 0)]
    if invalid:
        return _check("adjustment", "复权一致", False, "red", "；".join(invalid))
    return _check("adjustment", "复权一致", True, "green", "未发现 invalid 或重复行")


def _sla_check(rows: list[DataQualitySnapshot]) -> TradeDataGateCheckOut:
    missing_datasets = [item for item in REQUIRED_DATASETS if item not in {row.dataset_key for row in rows}]
    reasons = []
    if missing_datasets:
        reasons.append(f"缺少 SLA：{'、'.join(missing_datasets)}")
    for item in rows:
        blockers = _json_list(item.blockers_json)
        if item.status in CRITICAL_STATUSES or blockers:
            reasons.append(f"{item.dataset_key}[{item.status}] {'、'.join(blockers)}".strip())
    if reasons:
        return _check("sla", "关键 SLA", False, "red", "；".join(reasons))
    return _check("sla", "关键 SLA", True, "green", "关键 SLA 已通过")


def _source_check(probe: DataSourceProbeResponse) -> TradeDataGateCheckOut:
    items = probe.items or []
    if not items:
        return _check("source", "主数据源状态", False, "red", "数据源探测无返回")
    preferred = probe.provider_order[0] if probe.provider_order else items[0].source
    by_source = {item.source: item for item in items}
    main = by_source.get(preferred) or items[0]
    if not main.ok or main.quality == "failed":
        detail = main.warning or "主数据源暂时不可用"
        return _check("source", "主数据源状态", False, "red", detail)
    if main.quality in {"degraded", "stale"} or main.is_stale:
        return _check("source", "主数据源状态", True, "yellow", main.warning or "主数据源偏旧或降级")
    return _check("source", "主数据源状态", True, "green", "主数据源在线")


def _check(key: str, label: str, ok: bool, severity: str, detail: str) -> TradeDataGateCheckOut:
    return TradeDataGateCheckOut(key=key, label=label, ok=ok, severity=severity, detail=detail)


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded if str(item)]
