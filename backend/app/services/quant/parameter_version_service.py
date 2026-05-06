from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import QuantParameterSet
from app.models.schema_defs.phase4 import (
    QuantParameterSetCreate,
    QuantParameterSetListResponse,
    QuantParameterSetOut,
)


DEFAULT_QUANT_PARAMETERS: dict[str, Any] = {
    "risk": {
        "max_single_position_pct": 0.3,
        "max_total_exposure_pct": 0.8,
        "default_stop_loss_pct": -3.0,
        "default_take_profit_pct": 4.5,
    },
    "low_buy": {
        "min_priority_score": 75,
        "max_candidates_per_day": 12,
        "entry_zone_buffer_pct": 0.8,
        "stale_quote_seconds": 90,
    },
    "position_t": {
        "positive_t_min_edge_pct": 1.2,
        "negative_t_min_risk_pct": 1.0,
        "min_available_lot": 100,
    },
    "ml": {
        "production_enabled": False,
        "min_oos_days": 60,
        "min_samples": 1000,
    },
}


class QuantParameterVersionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_default(self) -> QuantParameterSet:
        version = get_settings().quant_parameter_default_version
        existing = self.db.execute(
            select(QuantParameterSet).where(QuantParameterSet.version == version)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        row = QuantParameterSet(
            version=version,
            name="默认生产参数",
            scope="global",
            status="active",
            params_json=_json_dumps(DEFAULT_QUANT_PARAMETERS),
            description="Phase 4 参数版本化基线。历史回测应绑定该版本以保证可复现。",
            created_by="system",
            activated_at=datetime.utcnow(),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def current(self, scope: str = "global") -> QuantParameterSetOut:
        row = self.db.execute(
            select(QuantParameterSet)
            .where(QuantParameterSet.status == "active")
            .where(QuantParameterSet.scope.in_([scope, "global"]))
            .order_by(QuantParameterSet.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        row = row or self.ensure_default()
        return _out(row)

    def list(self, limit: int = 50) -> QuantParameterSetListResponse:
        self.ensure_default()
        rows = self.db.execute(
            select(QuantParameterSet).order_by(QuantParameterSet.id.desc()).limit(limit)
        ).scalars().all()
        current = self.current()
        return QuantParameterSetListResponse(current_version=current.version, items=[_out(row) for row in rows])

    def create(self, payload: QuantParameterSetCreate, *, created_by: str = "admin") -> QuantParameterSetOut:
        if payload.activate:
            self.db.execute(
                QuantParameterSet.__table__.update()
                .where(QuantParameterSet.scope == payload.scope)
                .values(status="archived")
            )
        row = QuantParameterSet(
            version=payload.version,
            name=payload.name or payload.version,
            scope=payload.scope,
            status="active" if payload.activate else "draft",
            params_json=_json_dumps(payload.params),
            description=payload.description,
            created_by=created_by,
            activated_at=datetime.utcnow() if payload.activate else None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _out(row)


def _out(row: QuantParameterSet) -> QuantParameterSetOut:
    return QuantParameterSetOut(
        id=row.id,
        version=row.version,
        name=row.name,
        scope=row.scope,
        status=row.status,
        params=_json_dict(row.params_json),
        description=row.description,
        created_by=row.created_by,
        created_at=row.created_at,
        activated_at=row.activated_at,
    )


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
