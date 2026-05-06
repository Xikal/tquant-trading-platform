from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import FeatureFlagAuditLog, SystemSetting, User


_PREFIX = "ff_"

@dataclass(frozen=True)
class FeatureFlag:
    key: str
    enabled: bool
    default: bool
    type: str
    description: str
    source: str = "default"


_FLAG_DESCRIPTIONS: dict[str, str] = {
    "t_engine_fee_aware_enabled": "做T分析展示手续费、净收益和小单拖累提示。",
    "t_engine_elasticity_enabled": "做T分析读取弹性缓存，用于提示近期冲高空间。",
    "strategy_ma_channel_band_enabled": "开放均线通道波段研究策略。",
    "strategy_leader_pullback_band_enabled": "开放龙头回踩波段研究策略。",
    "strategy_governance_enabled": "启用策略层级 promote/demote 治理覆盖。",
    "smart_mode_enabled": "策略工作台启用傻瓜模式摘要。",
    "playbook_lazy_load_enabled": "策略宝典按页面分段加载，减少首屏请求。",
}


_DEFAULT_FLAGS = {
    "t_engine_fee_aware_enabled": True,
    "t_engine_elasticity_enabled": True,
    "strategy_ma_channel_band_enabled": True,
    "strategy_leader_pullback_band_enabled": False,
    "strategy_governance_enabled": True,
    "smart_mode_enabled": True,
    "playbook_lazy_load_enabled": True,
}


def list_feature_flags(db: Session) -> list[FeatureFlag]:
    rows = {
        str(row.key)[len(_PREFIX) :]: str(row.value or "").strip().lower()
        for row in db.execute(select(SystemSetting).where(SystemSetting.key.like(f"{_PREFIX}%"))).scalars().all()
    }
    result: list[FeatureFlag] = []
    for key, default in _DEFAULT_FLAGS.items():
        if key in rows:
            result.append(_flag(key, enabled=rows[key] in {"1", "true", "yes", "on"}, source="db"))
        else:
            result.append(_flag(key, enabled=default, source="default"))
    return result


def feature_enabled(db: Session, key: str, default: bool = False) -> bool:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == f"{_PREFIX}{key}")).scalar_one_or_none()
    if row is None:
        return _DEFAULT_FLAGS.get(key, default)
    return str(row.value or "").strip().lower() in {"1", "true", "yes", "on"}


def update_feature_flag(db: Session, *, key: str, enabled: bool, current_user: User) -> FeatureFlag:
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
        )
    )
    db.commit()
    return _flag(key, enabled=enabled, source="db")


def flag_to_dict(flag: FeatureFlag) -> dict[str, Any]:
    return {
        "key": flag.key,
        "enabled": flag.enabled,
        "default": flag.default,
        "type": flag.type,
        "description": flag.description,
        "source": flag.source,
    }


def _flag(key: str, *, enabled: bool, source: str) -> FeatureFlag:
    return FeatureFlag(
        key=key,
        enabled=enabled,
        default=_DEFAULT_FLAGS.get(key, False),
        type="boolean",
        description=_FLAG_DESCRIPTIONS.get(key, ""),
        source=source,
    )
