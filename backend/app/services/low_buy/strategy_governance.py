from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now_string
from app.core.database import SessionLocal
from app.models.entities import (
    LowBuyStrategyPerformanceSnapshot,
    LowBuyStrategyPerformanceWindowSnapshot,
)
from app.models.schema_defs.screener import (
    LowBuyStrategyGovernanceItemOut,
    LowBuyStrategyGovernanceResponse,
    LowBuyStrategyPerformanceOut,
)
from app.repositories.low_buy import SystemSettingRepository
from app.services.low_buy.holding_policy import strategy_holding_policy
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY, PERFORMANCE_LOOKBACK_DAYS, PLAYBOOKS
from app.services.low_buy.strategy_policy import (
    StrategyTier,
    get_strategy_tier,
    requires_mainline_industry,
)
from app.services.low_buy.strategy_governance_health import (
    auto_governance_params as _auto_governance_params,
    evidence_gate_decision as _evidence_gate_decision,
    float_param as _float_param,
    int_param as _int_param,
    strategy_health as _strategy_health,
)
from app.services.low_buy.strategy_validation_phase import resolve_strategy_validation_phase
from app.services.low_buy.strategy_pool_config import strategy_pool_profile
from app.services.low_buy.strategy_tier_resolver import StrategyTierResolver


def build_low_buy_strategy_governance(db: Session | None = None) -> LowBuyStrategyGovernanceResponse:
    """Return the current low-buy strategy governance map.

    This is intentionally metadata-only. It does not calculate signals or mutate
    strategy state, so Web/App/Agent clients can use it as a stable migration
    contract while old endpoints remain compatible.
    """

    performances = latest_strategy_performance_map(db) if db is not None else {}
    auto_overrides = _load_auto_governance_overrides(db) if db is not None else {}
    tier_resolver = StrategyTierResolver(db) if db is not None else None
    governance_params = _auto_governance_params()
    items = [
        _strategy_item(
            strategy_key,
            performances.get(strategy_key),
            auto_override=auto_overrides.get(strategy_key),
            tier_resolver=tier_resolver,
            governance_params=governance_params,
        )
        for strategy_key in PLAYBOOKS.keys()
    ]
    production_strategies = [
        item.strategy_key
        for item in items
        if item.tier in {StrategyTier.CORE.value, StrategyTier.AUXILIARY.value}
    ]
    return LowBuyStrategyGovernanceResponse(
        default_strategy=DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        production_strategies=sorted(production_strategies),
        items=items,
    )


def _strategy_item(
    strategy_key: str,
    performance: LowBuyStrategyPerformanceOut | None = None,
    auto_override: dict[str, Any] | None = None,
    tier_resolver: StrategyTierResolver | None = None,
    governance_params: dict[str, Any] | None = None,
) -> LowBuyStrategyGovernanceItemOut:
    playbook = PLAYBOOKS.get(strategy_key, {})
    tier = tier_resolver.resolve(strategy_key) if tier_resolver is not None else get_strategy_tier(strategy_key)
    pool = strategy_pool_profile(strategy_key)
    holding = strategy_holding_policy(strategy_key)
    params = governance_params or _auto_governance_params()
    health_score, health_text = _strategy_health(performance, params)
    status, status_text = _status_for_strategy(
        strategy_key,
        tier=tier,
        performance=performance,
        health_score=health_score,
        auto_override=auto_override,
        governance_params=params,
    )
    auto_status = str((auto_override or {}).get("status") or "")
    auto_reason = str((auto_override or {}).get("reason") or "")
    auto_updated_at = str((auto_override or {}).get("updated_at") or "")
    phase = resolve_strategy_validation_phase(performance, health_score)
    return LowBuyStrategyGovernanceItemOut(
        strategy_key=strategy_key,
        strategy_title=str(playbook.get("title") or strategy_key),
        subtitle=str(playbook.get("subtitle") or ""),
        tier=tier.value,
        layer=_layer_for_tier(tier),
        status=status,
        status_text=status_text,
        enabled=pool.enabled,
        participates_priority_board=tier in {StrategyTier.CORE, StrategyTier.AUXILIARY},
        strong_buy_paused=tier in {StrategyTier.RESEARCH, StrategyTier.FACTOR},
        requires_mainline_industry=requires_mainline_industry(strategy_key),
        pool_key=pool.pool_key,
        pool_title=pool.title,
        pool_source=pool.source,
        pool_max_size=pool.max_size,
        uses_daily_scan_pool=pool.uses_daily_scan,
        max_holding_days=holding.max_holding_days,
        holding_brief=holding.brief,
        strategy_health_score=health_score,
        strategy_health_text=health_text,
        auto_governance_status=auto_status,
        auto_governance_reason=auto_reason,
        auto_governance_updated_at=auto_updated_at,
        validation_phase=phase.phase,
        validation_phase_text=phase.phase_text,
        validation_phase_reason=phase.reason,
        validation_position_scale=phase.position_scale,
        performance_sample_count=performance.filled_signals if performance is not None else 0,
        notes=list(playbook.get("notes") or []),
    )


def _status_for_strategy(
    strategy_key: str,
    *,
    tier: StrategyTier | None = None,
    performance: LowBuyStrategyPerformanceOut | None = None,
    health_score: float = 0.0,
    auto_override: dict[str, Any] | None = None,
    governance_params: dict[str, Any] | None = None,
) -> tuple[str, str]:
    tier = tier or get_strategy_tier(strategy_key)
    params = governance_params or _auto_governance_params()
    pool = strategy_pool_profile(strategy_key)
    if not pool.enabled:
        return "paused", "暂停执行，仅保留历史研究"
    if auto_override:
        override_status = str(auto_override.get("status") or "")
        override_reason = str(auto_override.get("reason") or "")
        if override_status in {"paused", "watch"}:
            return override_status, override_reason or "策略健康度自动治理生效"
    if performance is not None and performance.filled_signals >= _int_param(params, "min_filled_signals"):
        if health_score < _float_param(params, "pause_health_threshold"):
            return "paused", "绩效健康度较弱，自动暂停强信号"
        if health_score < _float_param(params, "watch_health_threshold"):
            return "watch", "绩效健康度偏弱，自动降级观察"
    evidence_gate = _evidence_gate_decision(strategy_key, performance, params)
    if evidence_gate is not None:
        return evidence_gate["status"], evidence_gate["reason"]
    if tier.value == "core":
        return "active", "核心生产策略"
    if tier.value == "auxiliary":
        return "watch", "生产观察策略，轻仓验证"
    if tier.value == "factor":
        return "research", "辅助因子，不单独触发买入"
    return "research", "研究层，不进入强买"


def _layer_for_tier(tier: StrategyTier) -> str:
    if tier in {StrategyTier.CORE, StrategyTier.AUXILIARY}:
        return "production"
    if tier == StrategyTier.FACTOR:
        return "research"
    return tier.value


def latest_strategy_performance_map(db: Session) -> dict[str, LowBuyStrategyPerformanceOut]:
    latest_trade_date = _latest_performance_trade_date(db)
    if not latest_trade_date:
        return {}
    rows = (
        db.execute(
            select(LowBuyStrategyPerformanceWindowSnapshot).where(
                LowBuyStrategyPerformanceWindowSnapshot.latest_trade_date == latest_trade_date,
                LowBuyStrategyPerformanceWindowSnapshot.lookback_days == PERFORMANCE_LOOKBACK_DAYS,
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        rows = (
            db.execute(
                select(LowBuyStrategyPerformanceSnapshot).where(
                    LowBuyStrategyPerformanceSnapshot.latest_trade_date == latest_trade_date,
                )
            )
            .scalars()
            .all()
        )
    result: dict[str, LowBuyStrategyPerformanceOut] = {}
    for row in rows:
        payload = _parse_performance_payload(row.payload_json)
        if payload is not None:
            result[row.strategy_key] = payload
    return result


def _latest_performance_trade_date(db: Session) -> str:
    latest = db.execute(select(func.max(LowBuyStrategyPerformanceWindowSnapshot.latest_trade_date))).scalar()
    if latest:
        return str(latest)
    legacy_latest = db.execute(select(func.max(LowBuyStrategyPerformanceSnapshot.latest_trade_date))).scalar()
    return str(legacy_latest or "")


def _parse_performance_payload(raw: str) -> LowBuyStrategyPerformanceOut | None:
    if not raw:
        return None
    try:
        return LowBuyStrategyPerformanceOut.model_validate_json(raw)
    except Exception:
        return None


AUTO_GOVERNANCE_SETTING_KEY = "low_buy.strategy_auto_governance"
_AUTO_GOVERNANCE_CACHE_TTL_SECONDS = 60
_AUTO_GOVERNANCE_CACHE: tuple[float, dict[str, dict[str, Any]]] = (0.0, {})


def set_strategy_governance_override(
    db: Session,
    *,
    strategy_key: str,
    status: str,
    reason: str = "",
) -> LowBuyStrategyGovernanceResponse:
    if strategy_key not in PLAYBOOKS:
        raise ValueError(f"未知策略：{strategy_key}")
    if status not in {"active", "watch", "paused"}:
        raise ValueError("策略状态只能是 active、watch 或 paused")

    payload = _load_governance_payload(db)
    items = payload.setdefault("items", {})
    if status == "active":
        items.pop(strategy_key, None)
    else:
        items[strategy_key] = {
            "status": status,
            "reason": reason.strip() or _manual_governance_reason(status),
            "updated_at": beijing_now_string(),
            "source": "manual_admin",
        }
    payload["updated_at"] = beijing_now_string()
    SystemSettingRepository(db).upsert(AUTO_GOVERNANCE_SETTING_KEY, json.dumps(payload, ensure_ascii=False))
    db.commit()
    _clear_auto_governance_cache()
    return build_low_buy_strategy_governance(db)


def _load_governance_payload(db: Session) -> dict[str, Any]:
    row = SystemSettingRepository(db).fetch(AUTO_GOVERNANCE_SETTING_KEY)
    if row is None or not row.value:
        return {"items": {}}
    try:
        payload = json.loads(row.value)
    except json.JSONDecodeError:
        return {"items": {}}
    return payload if isinstance(payload, dict) else {"items": {}}


def _manual_governance_reason(status: str) -> str:
    if status == "paused":
        return "管理员手动暂停强信号"
    if status == "watch":
        return "管理员手动降级为观察"
    return ""


def _clear_auto_governance_cache() -> None:
    global _AUTO_GOVERNANCE_CACHE
    _AUTO_GOVERNANCE_CACHE = (0.0, {})


def _load_auto_governance_overrides(db: Session) -> dict[str, dict[str, Any]]:
    payload = _load_governance_payload(db)
    items = payload.get("items") if isinstance(payload, dict) else {}
    return items if isinstance(items, dict) else {}


def cached_auto_governance_override(strategy_key: str) -> dict[str, Any] | None:
    """Return cached auto-governance status for hot signal paths."""

    global _AUTO_GOVERNANCE_CACHE
    now = time.time()
    expires_at, payload = _AUTO_GOVERNANCE_CACHE
    if now < expires_at:
        return payload.get(strategy_key)
    try:
        with SessionLocal() as db:
            payload = _load_auto_governance_overrides(db)
    except Exception:
        payload = {}
    _AUTO_GOVERNANCE_CACHE = (now + _AUTO_GOVERNANCE_CACHE_TTL_SECONDS, payload)
    return payload.get(strategy_key)
