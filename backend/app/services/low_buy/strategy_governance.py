from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
    PRODUCTION_PRIORITY_STRATEGIES,
    get_strategy_tier,
    participates_in_priority_board,
    requires_mainline_industry,
    strategy_layer,
    strong_buy_paused,
)
from app.services.low_buy.strategy_pool_config import strategy_pool_profile


def build_low_buy_strategy_governance(db: Session | None = None) -> LowBuyStrategyGovernanceResponse:
    """Return the current low-buy strategy governance map.

    This is intentionally metadata-only. It does not calculate signals or mutate
    strategy state, so Web/App/Agent clients can use it as a stable migration
    contract while old endpoints remain compatible.
    """

    performances = latest_strategy_performance_map(db) if db is not None else {}
    auto_overrides = _load_auto_governance_overrides(db) if db is not None else {}
    items = [
        _strategy_item(
            strategy_key,
            performances.get(strategy_key),
            auto_override=auto_overrides.get(strategy_key),
        )
        for strategy_key in PLAYBOOKS.keys()
    ]
    return LowBuyStrategyGovernanceResponse(
        default_strategy=DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        production_strategies=sorted(PRODUCTION_PRIORITY_STRATEGIES),
        items=items,
    )


def _strategy_item(
    strategy_key: str,
    performance: LowBuyStrategyPerformanceOut | None = None,
    auto_override: dict[str, Any] | None = None,
) -> LowBuyStrategyGovernanceItemOut:
    playbook = PLAYBOOKS.get(strategy_key, {})
    tier = get_strategy_tier(strategy_key)
    pool = strategy_pool_profile(strategy_key)
    holding = strategy_holding_policy(strategy_key)
    health_score, health_text = _strategy_health(performance)
    status, status_text = _status_for_strategy(
        strategy_key,
        performance=performance,
        health_score=health_score,
        auto_override=auto_override,
    )
    auto_status = str((auto_override or {}).get("status") or "")
    auto_reason = str((auto_override or {}).get("reason") or "")
    auto_updated_at = str((auto_override or {}).get("updated_at") or "")
    return LowBuyStrategyGovernanceItemOut(
        strategy_key=strategy_key,
        strategy_title=str(playbook.get("title") or strategy_key),
        subtitle=str(playbook.get("subtitle") or ""),
        tier=tier.value,
        layer=strategy_layer(strategy_key),
        status=status,
        status_text=status_text,
        enabled=pool.enabled,
        participates_priority_board=participates_in_priority_board(strategy_key),
        strong_buy_paused=strong_buy_paused(strategy_key),
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
        performance_sample_count=performance.filled_signals if performance is not None else 0,
        notes=list(playbook.get("notes") or []),
    )


def _status_for_strategy(
    strategy_key: str,
    *,
    performance: LowBuyStrategyPerformanceOut | None = None,
    health_score: float = 0.0,
    auto_override: dict[str, Any] | None = None,
) -> tuple[str, str]:
    tier = get_strategy_tier(strategy_key)
    pool = strategy_pool_profile(strategy_key)
    if not pool.enabled:
        return "paused", "暂停执行，仅保留历史研究"
    if auto_override:
        override_status = str(auto_override.get("status") or "")
        override_reason = str(auto_override.get("reason") or "")
        if override_status in {"paused", "watch"}:
            return override_status, override_reason or "策略健康度自动治理生效"
    if performance is not None and performance.filled_signals >= 20:
        if health_score < 35:
            return "paused", "绩效健康度较弱，自动暂停强信号"
        if health_score < 55:
            return "watch", "绩效健康度偏弱，自动降级观察"
    if tier.value == "core":
        return "active", "核心生产策略"
    if tier.value == "auxiliary":
        return "watch", "生产观察策略，轻仓验证"
    if tier.value == "factor":
        return "research", "辅助因子，不单独触发买入"
    return "research", "研究层，不进入强买"


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


def _strategy_health(performance: LowBuyStrategyPerformanceOut | None) -> tuple[float, str]:
    if performance is None or performance.filled_signals <= 0:
        return 0.0, "暂无绩效样本"
    score = 0.0
    score += _range_score(performance.avg_net_return_pct, low=-2.0, high=4.0) * 23.0
    score += _range_score(performance.profit_factor, low=0.6, high=2.0) * 18.0
    score += (1.0 - min(abs(min(performance.avg_max_drawdown_5d, 0.0)) / 8.0, 1.0)) * 16.0
    score += min(performance.filled_signals / 50.0, 1.0) * 16.0
    score += _range_score(performance.net_win_rate, low=-20.0, high=35.0) * 12.0
    score += _market_regime_adaptation_score(performance) * 15.0
    score -= min(max(performance.stop_loss_rate - 18.0, 0.0), 30.0) * 0.45
    score -= min(max(performance.not_filled_rate - 40.0, 0.0), 40.0) * 0.18
    normalized = round(max(min(score, 100.0), 0.0), 1)
    return normalized, _health_text(normalized, performance.filled_signals)


def _range_score(value: float, *, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(min((value - low) / (high - low), 1.0), 0.0)


def _market_regime_adaptation_score(performance: LowBuyStrategyPerformanceOut) -> float:
    """Score whether a strategy still works outside its easiest market buckets."""

    buckets = performance.market_state_attribution
    usable = [bucket for bucket in buckets if bucket.sample_count >= 5]
    if not usable:
        return 0.45

    weighted = 0.0
    total = 0
    for bucket in usable:
        bucket_score = (
            _range_score(bucket.avg_return_3d, low=-2.0, high=3.0) * 0.45
            + _range_score(bucket.avg_return_5d, low=-3.0, high=4.0) * 0.25
            + _range_score(bucket.hit_rate, low=35.0, high=68.0) * 0.30
        )
        if any(keyword in bucket.label for keyword in ("退潮", "风险释放", "轮动过快")):
            bucket_score *= 0.85
        weighted += bucket_score * bucket.sample_count
        total += bucket.sample_count
    return max(min(weighted / max(total, 1), 1.0), 0.0)


def _health_text(score: float, filled_signals: int) -> str:
    if filled_signals < 20:
        return "样本不足，仅供参考"
    if score >= 75:
        return "健康，可生产验证"
    if score >= 55:
        return "一般，建议降权观察"
    if score >= 35:
        return "偏弱，限制强信号"
    return "较弱，建议研究层"


AUTO_GOVERNANCE_SETTING_KEY = "low_buy.strategy_auto_governance"
_AUTO_GOVERNANCE_CACHE_TTL_SECONDS = 60
_AUTO_GOVERNANCE_CACHE: tuple[float, dict[str, dict[str, Any]]] = (0.0, {})


def _load_auto_governance_overrides(db: Session) -> dict[str, dict[str, Any]]:
    row = SystemSettingRepository(db).fetch(AUTO_GOVERNANCE_SETTING_KEY)
    if row is None or not row.value:
        return {}
    try:
        payload = json.loads(row.value)
    except json.JSONDecodeError:
        return {}
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
