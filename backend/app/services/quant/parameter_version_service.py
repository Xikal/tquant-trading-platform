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
        "thresholds": {
            "min_daily_amount_core": 50_000_000.0,
            "min_daily_amount_auxiliary": 30_000_000.0,
            "max_symbols_quote_refresh": 60,
            "min_signal_score_buy": 75,
            "min_tradability_score_buy": 70,
        },
        "strategy_prefilters": {
            "limit_up_breakout_retrace": {
                "min_platform_days": 20,
                "min_retracement_days": 2,
                "max_retracement_days": 5,
                "min_volume_burst_ratio": 1.9,
                "min_breakout_pct": 1.0,
                "max_platform_range_pct": 35.0,
                "min_drawdown_pct": -10.0,
                "max_drawdown_pct": -3.0,
                "max_post_volume_ratio": 0.78,
                "max_latest_volume_ratio": 0.82,
                "max_support_distance_pct": 3.0,
                "min_board_amount": 150_000_000.0,
                "min_platform_hold_ratio": 0.995,
                "min_board_open_hold_ratio": 0.985,
            },
            "divergence_consensus": {
                "min_platform_days": 20,
                "min_retracement_days": 4,
                "max_retracement_days": 12,
                "min_board_amount": 180_000_000.0,
                "min_volume_burst_ratio": 1.8,
                "min_platform_breakout_pct": 0.8,
                "max_platform_range_pct": 38.0,
                "min_divergence_volume_ratio": 0.55,
                "min_consolidation_days": 2,
                "max_consolidation_days": 8,
                "max_consolidation_volume_ratio": 0.72,
                "min_consensus_volume_ratio": 1.45,
                "max_breakout_extension_pct": 8.5,
            },
            "late_session_strong_support": {
                "min_amount": 200_000_000.0,
                "min_retracement_days": 1,
                "max_retracement_days": 8,
                "max_support_distance_pct": 3.2,
                "max_latest_volume_ratio": 1.25,
                "max_post_volume_ratio": 1.15,
                "min_close_position_ratio": 0.55,
                "max_distribution_risk_score": 5.5,
            },
            "core_midcap_vwap_ma5_retrace": {
                "min_amount": 500_000_000.0,
                "min_retracement_days": 1,
                "max_retracement_days": 6,
                "max_ma_distance_pct": 1.8,
                "max_support_distance_pct": 2.2,
                "max_latest_volume_ratio": 1.15,
                "max_post_volume_ratio": 1.2,
                "max_distribution_risk_score": 5.5,
            },
            "sector_mainline_first_divergence_low_buy": {
                "min_amount": 200_000_000.0,
                "min_retracement_days": 1,
                "max_retracement_days": 5,
                "min_volume_burst_ratio": 1.4,
                "max_support_distance_pct": 3.0,
                "max_latest_volume_ratio": 1.25,
                "max_post_volume_ratio": 1.25,
                "max_distribution_risk_score": 5.8,
            },
            "ma_channel_band": {
                "min_amount": 50_000_000.0,
                "min_platform_days": 20,
                "min_retracement_days": 2,
                "max_retracement_days": 14,
                "max_ma20_distance_pct": 3.2,
                "max_latest_volume_ratio": 1.2,
                "max_post_volume_ratio": 1.25,
                "max_distribution_risk_score": 6.5,
            },
            "leader_pullback_band": {
                "min_amount": 50_000_000.0,
                "min_retracement_days": 1,
                "max_retracement_days": 8,
                "min_volume_burst_ratio": 1.6,
                "max_support_distance_pct": 3.5,
                "max_latest_volume_ratio": 1.25,
                "max_post_volume_ratio": 1.25,
                "max_distribution_risk_score": 5.8,
            },
        },
        "strategy_execution": {
            "limit_up_breakout_retrace": {
                "min_score": 88.0,
                "min_volume_burst_ratio": 2.0,
                "min_breakout_pct": 1.2,
                "min_drawdown_pct": -8.5,
                "max_drawdown_pct": -3.5,
                "max_post_volume_ratio": 0.72,
                "max_latest_volume_ratio": 0.78,
                "max_support_distance_pct": 2.5,
                "min_board_amount": 200_000_000.0,
            },
            "divergence_consensus": {
                "min_score": 90.0,
                "min_consensus_volume_ratio": 1.55,
                "max_consolidation_volume_ratio": 0.66,
                "min_close_strength": 0.58,
            },
        },
        "signal_thresholds": {
            "hard_buy_min_scores": {
                "default": 80.0,
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
            merged = _deep_merge(DEFAULT_QUANT_PARAMETERS, _json_dict(existing.params_json))
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
        _clear_runtime_quant_cache()
        self.db.refresh(row)
        return _out(row)


def _out(row: QuantParameterSet) -> QuantParameterSetOut:
    return QuantParameterSetOut(
        id=row.id,
        version=row.version,
        name=row.name,
        scope=row.scope,
        status=row.status,
        params=_deep_merge(DEFAULT_QUANT_PARAMETERS, _json_dict(row.params_json)),
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
