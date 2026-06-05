from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import time
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import FeatureFlagAuditLog, SystemSetting, User


_PREFIX = "ff_"
_CACHE_TTL_SECONDS = 60.0
_CACHE_EXPIRES_AT = 0.0
_CACHE_ITEMS: list["FeatureFlag"] | None = None
_CACHE_RAW_VALUES: dict[str, str] = {}

@dataclass(frozen=True)
class FeatureFlag:
    key: str
    enabled: bool
    default: bool
    type: str
    description: str
    source: str = "default"
    value: bool = False
    updated_at: str = ""
    updated_by: str = ""


_FLAG_DESCRIPTIONS: dict[str, str] = {
    "t_engine_fee_aware_enabled": "做T分析展示手续费、净收益和小单拖累提示。",
    "t_engine_elasticity_enabled": "做T分析读取弹性缓存，用于提示近期冲高空间。",
    "strategy_ma_channel_band_enabled": "开放均线通道波段研究策略。",
    "strategy_leader_pullback_band_enabled": "开放龙头回踩波段研究策略。",
    "strategy_mainline_limitup_shrink_retrace_reclaim_enabled": "开放主线涨停缩量回调研究观察策略。",
    "strategy_governance_enabled": "启用策略层级 promote/demote 治理覆盖。",
    "smart_mode_enabled": "策略工作台启用傻瓜模式摘要。",
    "playbook_lazy_load_enabled": "策略宝典按页面分段加载，减少首屏请求。",
    "market_provider_router_enabled": "启用统一市场数据 provider router（默认开启，旧链路作为 fallback）。",
    "a_key_level_engine_enabled": "启用 AKeyLevel 关键位引擎展示与 API 入口；默认关闭，开启后 API 优先读取物化缓存。",
    "trading_experience_suite_enabled": "启用交易经验观察与复盘套件总入口；默认关闭。",
    "trade_review_suite_enabled": "启用每日复盘池和交易纪律日志；默认关闭。",
    "vp_position_tags_enabled": "启用量价-位置风险标签展示；默认关闭。",
    "relative_strength_board_enabled": "启用相对强度和抗跌榜展示；默认关闭。",
    "holding_discipline_assistant_enabled": "启用模拟盘持仓纪律助手；默认关闭。",
    "limit_up_followthrough_enabled": "启用涨停后形态研究列表；默认关闭。",
    "t_trade_discipline_enabled": "启用做 T 纪律与效果归因；默认关闭。",
    "frontend_worker_compute_enabled": "启用前端 TypeScript Worker 计算孤岛；失败自动回退同步路径。",
    "frontend_realtime_signals_island_enabled": "启用前端 signals 实时字段性能孤岛；服务端数据仍以 Query 为真源。",
    "frontend_canvas_chart_island_enabled": "启用前端 ChartIsland 密集图表降采样路径；普通图表保持 ECharts。",
    "frontend_wasm_compute_enabled": "启用前端 WASM 纯计算实验；默认关闭，必须保留 TypeScript fallback。",
    "frontend_solid_island_enabled": "启用 Solid 局部性能孤岛实验；默认关闭，禁止整站迁移。",
}


_DEFAULT_FLAGS = {
    "t_engine_fee_aware_enabled": True,
    "t_engine_elasticity_enabled": True,
    "strategy_ma_channel_band_enabled": True,
    "strategy_leader_pullback_band_enabled": False,
    "strategy_mainline_limitup_shrink_retrace_reclaim_enabled": True,
    "strategy_governance_enabled": True,
    "smart_mode_enabled": True,
    "playbook_lazy_load_enabled": True,
    "market_provider_router_enabled": True,
    "a_key_level_engine_enabled": False,
    "trading_experience_suite_enabled": False,
    "trade_review_suite_enabled": False,
    "vp_position_tags_enabled": False,
    "relative_strength_board_enabled": False,
    "holding_discipline_assistant_enabled": False,
    "limit_up_followthrough_enabled": False,
    "t_trade_discipline_enabled": False,
    "frontend_worker_compute_enabled": True,
    "frontend_realtime_signals_island_enabled": True,
    "frontend_canvas_chart_island_enabled": True,
    "frontend_wasm_compute_enabled": False,
    "frontend_solid_island_enabled": False,
}


def list_feature_flags(db: Session) -> list[FeatureFlag]:
    global _CACHE_EXPIRES_AT, _CACHE_ITEMS, _CACHE_RAW_VALUES
    now = time.monotonic()
    if _CACHE_ITEMS is not None and now < _CACHE_EXPIRES_AT:
        return list(_CACHE_ITEMS)
    settings = {
        str(row.key)[len(_PREFIX) :]: row
        for row in db.execute(select(SystemSetting).where(SystemSetting.key.like(f"{_PREFIX}%"))).scalars().all()
    }
    _CACHE_RAW_VALUES = {key: str(row.value or "").strip().lower() for key, row in settings.items()}
    result: list[FeatureFlag] = []
    for key, default in _DEFAULT_FLAGS.items():
        if key in settings:
            row = settings[key]
            result.append(
                _flag(
                    key,
                    enabled=_truthy(row.value),
                    source="db",
                    updated_at=_iso(row.updated_at),
                )
            )
        else:
            result.append(_flag(key, enabled=default, source="default"))
    _CACHE_ITEMS = list(result)
    _CACHE_EXPIRES_AT = now + _CACHE_TTL_SECONDS
    return result


def feature_enabled(db: Session, key: str, default: bool = False) -> bool:
    for item in list_feature_flags(db):
        if item.key == key:
            return item.enabled
    now = time.monotonic()
    if now < _CACHE_EXPIRES_AT and key in _CACHE_RAW_VALUES:
        return _truthy(_CACHE_RAW_VALUES[key])
    row = db.execute(select(SystemSetting).where(SystemSetting.key == f"{_PREFIX}{key}")).scalar_one_or_none()
    if row is not None:
        return _truthy(row.value)
    return _DEFAULT_FLAGS.get(key, default)


def update_feature_flag(
    db: Session,
    *,
    key: str,
    enabled: bool,
    current_user: User,
    operator_ip: str = "",
) -> FeatureFlag:
    if key not in _DEFAULT_FLAGS:
        raise ValueError(f"未知功能开关: {key}")
    setting_key = f"{_PREFIX}{key}"
    row = db.execute(select(SystemSetting).where(SystemSetting.key == setting_key)).scalar_one_or_none()
    old_value = str(row.value if row is not None else _DEFAULT_FLAGS[key]).lower()
    new_value = "true" if enabled else "false"
    if row is None:
        row = SystemSetting(key=setting_key, value=new_value)
        db.add(row)
    else:
        row.value = new_value
    db.add(
        FeatureFlagAuditLog(
            flag_key=key,
            old_value=old_value,
            new_value=new_value,
            operator_user_id=current_user.id,
            operator_ip=operator_ip[:80],
        )
    )
    db.commit()
    clear_feature_flag_cache()
    return _flag(
        key,
        enabled=enabled,
        source="db",
        updated_at=_iso(getattr(row, "updated_at", None)),
        updated_by=str(current_user.id),
    )


def list_feature_flag_audit(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.execute(
        select(FeatureFlagAuditLog)
        .order_by(desc(FeatureFlagAuditLog.created_at), desc(FeatureFlagAuditLog.id))
        .limit(max(1, min(int(limit or 50), 200)))
    ).scalars().all()
    return [
        {
            "id": row.id,
            "flag_key": row.flag_key,
            "old_value": row.old_value,
            "new_value": row.new_value,
            "operator_user_id": row.operator_user_id,
            "operator_ip": getattr(row, "operator_ip", "") or "",
            "created_at": _iso(row.created_at),
        }
        for row in rows
    ]


def clear_feature_flag_cache() -> None:
    global _CACHE_EXPIRES_AT, _CACHE_ITEMS, _CACHE_RAW_VALUES
    _CACHE_ITEMS = None
    _CACHE_RAW_VALUES = {}
    _CACHE_EXPIRES_AT = 0.0
    try:
        from app.services.market.quotes import MarketQuoteMixin

        MarketQuoteMixin.clear_market_provider_router_flag_cache()
    except Exception:
        pass


def flag_to_dict(flag: FeatureFlag) -> dict[str, Any]:
    return {
        "key": flag.key,
        "enabled": flag.enabled,
        "value": flag.value,
        "default": flag.default,
        "type": flag.type,
        "description": flag.description,
        "source": flag.source,
        "updated_at": flag.updated_at,
        "updated_by": flag.updated_by,
    }


def _flag(
    key: str,
    *,
    enabled: bool,
    source: str,
    updated_at: str = "",
    updated_by: str = "",
) -> FeatureFlag:
    return FeatureFlag(
        key=key,
        enabled=enabled,
        default=_DEFAULT_FLAGS.get(key, False),
        type="boolean",
        description=_FLAG_DESCRIPTIONS.get(key, ""),
        source=source,
        value=enabled,
        updated_at=updated_at,
        updated_by=updated_by,
    )


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _iso(value: datetime | None) -> str:
    return value.isoformat(sep=" ", timespec="seconds") if value else ""
