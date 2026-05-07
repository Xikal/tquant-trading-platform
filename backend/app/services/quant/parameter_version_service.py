from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import QuantParameterAuditLog, QuantParameterSet
from app.services.low_buy.strategy_parameter_defaults import (
    LOW_BUY_AUTO_GOVERNANCE_DEFAULTS,
    LOW_BUY_DYNAMIC_ADJUSTMENT_DEFAULTS,
    LOW_BUY_HARD_RISK_DEFAULTS,
    LOW_BUY_RESEARCH_LAYER_DEFAULTS,
    LOW_BUY_SCORING_DEFAULTS,
    LOW_BUY_STRATEGY_EXECUTION_DEFAULTS,
    LOW_BUY_STRATEGY_PREFILTER_DEFAULTS,
    LOW_BUY_THRESHOLD_DEFAULTS,
    POSITION_T_SCORING_DEFAULTS,
    quant_parameter_schema,
)
from app.models.schema_defs.phase4 import (
    QuantParameterAuditListResponse,
    QuantParameterAuditOut,
    QuantParameterExportResponse,
    QuantParameterRollbackRequest,
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
        "thresholds": {
            **LOW_BUY_THRESHOLD_DEFAULTS,
        },
        "strategy_prefilters": {
            **LOW_BUY_STRATEGY_PREFILTER_DEFAULTS,
        },
        "strategy_execution": {
            **LOW_BUY_STRATEGY_EXECUTION_DEFAULTS,
        },
        "scoring": {
            **LOW_BUY_SCORING_DEFAULTS,
        },
        "auto_governance": {
            **LOW_BUY_AUTO_GOVERNANCE_DEFAULTS,
        },
        "research_layers": {
            **LOW_BUY_RESEARCH_LAYER_DEFAULTS,
        },
        "hard_risk": {
            **LOW_BUY_HARD_RISK_DEFAULTS,
        },
        "dynamic_adjustment": {
            **LOW_BUY_DYNAMIC_ADJUSTMENT_DEFAULTS,
        },
        "market_state_rules": {},
        "signal_thresholds": {
            "hard_buy_min_scores": {
                "default": 80.0,
                "mainline_limitup_shrink_retrace_reclaim": 86.0,
                "limit_up_breakout_retrace": 88.0,
                "divergence_consensus": 90.0,
            },
            "soft_buy_min_scores": {
                "classic_retrace": {"in_zone": 84.0, "near_above_zone": 88.0},
                "ma_support": {"in_zone": 84.0, "near_above_zone": 87.0},
                "first_board": {"in_zone": 86.0, "near_above_zone": 90.0},
                "volume_shrink": {"in_zone": 85.0, "near_above_zone": 89.0},
                "late_session_strong_support": {"in_zone": 86.0, "near_above_zone": 90.0},
                "core_midcap_vwap_ma5_retrace": {"in_zone": 84.0, "near_above_zone": 88.0},
                "sector_mainline_first_divergence_low_buy": {"in_zone": 84.0, "near_above_zone": 88.0},
                "mainline_limitup_shrink_retrace_reclaim": {"in_zone": 86.0, "near_above_zone": 90.0},
                "breakout_support": {"in_zone": 84.0, "near_above_zone": 88.0},
                "limit_up_breakout_retrace": {"in_zone": 90.0, "near_above_zone": 94.0},
                "divergence_consensus": {"in_zone": 92.0},
                "deep_pullback": {"in_zone": 88.0, "near_above_zone": 92.0},
                "trend_rebound": {"in_zone": 84.0, "near_above_zone": 87.0},
            },
        },
    },
    "position_t": {
        "positive_t_min_edge_pct": 1.2,
        "negative_t_min_risk_pct": 1.0,
        "min_available_lot": 100,
        "scoring": {
            **POSITION_T_SCORING_DEFAULTS,
        },
    },
    "ml": {
        "production_enabled": False,
        "min_oos_days": 60,
        "min_samples": 1000,
    },
}


def default_quant_parameters() -> dict[str, Any]:
    params = deepcopy(DEFAULT_QUANT_PARAMETERS)
    if not params.get("low_buy", {}).get("market_state_rules"):
        from app.services.low_buy.market_state_rules import default_market_state_rule_parameters

        params.setdefault("low_buy", {})["market_state_rules"] = default_market_state_rule_parameters()
    return params


class QuantParameterVersionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_default(self) -> QuantParameterSet:
        version = get_settings().quant_parameter_default_version
        existing = self.db.execute(
            select(QuantParameterSet).where(QuantParameterSet.version == version)
        ).scalar_one_or_none()
        if existing is not None:
            merged = _deep_merge(default_quant_parameters(), _json_dict(existing.params_json))
            if merged != _json_dict(existing.params_json):
                existing.params_json = _json_dumps(merged)
                self.db.commit()
                _clear_runtime_quant_cache()
                self.db.refresh(existing)
            return existing
        row = QuantParameterSet(
            version=version,
            name="默认生产参数",
            scope="global",
            status="active",
            params_json=_json_dumps(default_quant_parameters()),
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
            .where(QuantParameterSet.scope.in_(_scope_values(scope)))
            .order_by(_scope_priority(scope), QuantParameterSet.id.desc())
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
        before = self.current(scope=payload.scope).params if payload.activate else {}
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
        self.db.flush()
        self._audit(
            action="create_activate" if payload.activate else "create_draft",
            version=row.version,
            scope=row.scope,
            operator=created_by,
            before=before,
            after=_deep_merge(default_quant_parameters(), payload.params),
        )
        self.db.commit()
        _clear_runtime_quant_cache()
        self.db.refresh(row)
        return _out(row)

    def export_current(self, scope: str = "global") -> QuantParameterExportResponse:
        current = self.current(scope=scope)
        return QuantParameterExportResponse(
            current_version=current.version,
            exported_at=datetime.utcnow(),
            params=current.params,
            parameter_schema=quant_parameter_schema(),
        )

    def schema(self) -> dict[str, Any]:
        return quant_parameter_schema()

    def rollback(self, payload: QuantParameterRollbackRequest, *, operator: str = "admin") -> QuantParameterSetOut:
        target = self.db.execute(
            select(QuantParameterSet)
            .where(QuantParameterSet.version == payload.version)
            .where(QuantParameterSet.scope.in_(_scope_values(payload.scope)))
            .order_by(_scope_priority(payload.scope), QuantParameterSet.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if target is None:
            raise ValueError(f"quant parameter version not found: {payload.version}")
        before = self.current(scope=target.scope).params
        self.db.execute(
            QuantParameterSet.__table__.update()
            .where(QuantParameterSet.scope == target.scope)
            .values(status="archived")
        )
        target.status = "active"
        target.activated_at = datetime.utcnow()
        after = _deep_merge(default_quant_parameters(), _json_dict(target.params_json))
        self._audit(
            action="rollback_activate",
            version=target.version,
            scope=target.scope,
            operator=operator,
            before=before,
            after=after,
        )
        self.db.commit()
        _clear_runtime_quant_cache()
        self.db.refresh(target)
        return _out(target)

    def audit_logs(self, limit: int = 50) -> QuantParameterAuditListResponse:
        rows = self.db.execute(
            select(QuantParameterAuditLog).order_by(QuantParameterAuditLog.id.desc()).limit(max(1, min(limit, 200)))
        ).scalars().all()
        return QuantParameterAuditListResponse(items=[_audit_out(row) for row in rows])

    def _audit(
        self,
        *,
        action: str,
        version: str,
        scope: str,
        operator: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        self.db.add(
            QuantParameterAuditLog(
                action=action,
                version=version,
                scope=scope,
                operator=operator,
                before_json=_json_dumps(before),
                after_json=_json_dumps(after),
            )
        )


def _out(row: QuantParameterSet) -> QuantParameterSetOut:
    return QuantParameterSetOut(
        id=row.id,
        version=row.version,
        name=row.name,
        scope=row.scope,
        status=row.status,
        params=_deep_merge(default_quant_parameters(), _json_dict(row.params_json)),
        description=row.description,
        created_by=row.created_by,
        created_at=row.created_at,
        activated_at=row.activated_at,
    )


def _audit_out(row: QuantParameterAuditLog) -> QuantParameterAuditOut:
    return QuantParameterAuditOut(
        id=row.id,
        action=row.action,
        version=row.version,
        scope=row.scope,
        operator=row.operator,
        before=_json_dict(row.before_json),
        after=_json_dict(row.after_json),
        created_at=row.created_at,
    )


def _scope_values(scope: str) -> list[str]:
    values = [scope]
    if scope != "global":
        values.append("global")
    return values


def _scope_priority(scope: str):
    return case((QuantParameterSet.scope == scope, 0), else_=1)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, default_value in defaults.items():
        override_value = overrides.get(key)
        if isinstance(default_value, dict) and isinstance(override_value, dict):
            result[key] = _deep_merge(default_value, override_value)
        elif key in overrides:
            result[key] = override_value
        else:
            result[key] = default_value
    for key, value in overrides.items():
        if key not in result:
            result[key] = value
    return result


def _clear_runtime_quant_cache() -> None:
    try:
        from app.services.quant.runtime_parameters import clear_quant_parameter_cache

        clear_quant_parameter_cache()
    except Exception:
        pass
