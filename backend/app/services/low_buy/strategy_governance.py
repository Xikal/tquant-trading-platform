from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    LowBuyStrategyPerformanceSnapshot,
    LowBuyStrategyPerformanceWindowSnapshot,
)
from app.models.schema_defs.screener import (
    LowBuyStrategyGovernanceItemOut,
    LowBuyStrategyGovernanceResponse,
    LowBuyStrategyPerformanceOut,
)
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

    performances = _latest_strategy_performance(db) if db is not None else {}
    items = [_strategy_item(strategy_key, performances.get(strategy_key)) for strategy_key in PLAYBOOKS.keys()]
    return LowBuyStrategyGovernanceResponse(
        default_strategy=DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        production_strategies=sorted(PRODUCTION_PRIORITY_STRATEGIES),
        items=items,
    )


def _strategy_item(
    strategy_key: str,
    performance: LowBuyStrategyPerformanceOut | None = None,
) -> LowBuyStrategyGovernanceItemOut:
    playbook = PLAYBOOKS.get(strategy_key, {})
    tier = get_strategy_tier(strategy_key)
    pool = strategy_pool_profile(strategy_key)
    holding = strategy_holding_policy(strategy_key)
    health_score, health_text = _strategy_health(performance)
    status, status_text = _status_for_strategy(strategy_key, performance=performance, health_score=health_score)
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
        performance_sample_count=performance.filled_signals if performance is not None else 0,
        notes=list(playbook.get("notes") or []),
    )


def _status_for_strategy(
    strategy_key: str,
    *,
    performance: LowBuyStrategyPerformanceOut | None = None,
    health_score: float = 0.0,
) -> tuple[str, str]:
    tier = get_strategy_tier(strategy_key)
    pool = strategy_pool_profile(strategy_key)
    if not pool.enabled:
        return "paused", "暂停执行，仅保留历史研究"
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


def _latest_strategy_performance(db: Session) -> dict[str, LowBuyStrategyPerformanceOut]:
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
    score += _range_score(performance.avg_net_return_pct, low=-2.0, high=4.0) * 28.0
    score += _range_score(performance.profit_factor, low=0.6, high=2.0) * 22.0
    score += (1.0 - min(abs(min(performance.avg_max_drawdown_5d, 0.0)) / 8.0, 1.0)) * 18.0
    score += min(performance.filled_signals / 50.0, 1.0) * 18.0
    score += _range_score(performance.net_win_rate, low=-20.0, high=35.0) * 14.0
    score -= min(max(performance.stop_loss_rate - 18.0, 0.0), 30.0) * 0.45
    score -= min(max(performance.not_filled_rate - 40.0, 0.0), 40.0) * 0.18
    normalized = round(max(min(score, 100.0), 0.0), 1)
    return normalized, _health_text(normalized, performance.filled_signals)


def _range_score(value: float, *, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(min((value - low) / (high - low), 1.0), 0.0)


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
