from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Instrument, InstrumentRule
from app.services.etf.universe import EtfProfile, list_etf_profiles
from app.services.market.shared import guess_market


@dataclass(frozen=True)
class EtfRuleSyncItem:
    symbol: str
    name: str
    category: str
    action: str
    same_day_sell_allowed: bool
    previous_same_day_sell_allowed: bool | None


def sync_etf_t0_rules(db: Session) -> dict[str, object]:
    items: list[EtfRuleSyncItem] = []
    for profile in [item for item in list_etf_profiles() if item.same_day_sell_allowed]:
        previous = db.execute(select(InstrumentRule).where(InstrumentRule.symbol == profile.symbol)).scalar_one_or_none()
        previous_same_day = None if previous is None else bool(previous.same_day_sell_allowed)
        _upsert_instrument(db, profile)
        rule, action = _upsert_rule(db, profile, previous)
        items.append(
            EtfRuleSyncItem(
                symbol=profile.symbol,
                name=profile.name,
                category=profile.category.value,
                action=action,
                same_day_sell_allowed=rule.same_day_sell_allowed,
                previous_same_day_sell_allowed=previous_same_day,
            )
        )
    db.commit()
    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "status": "completed",
        "source": "app.services.etf.universe",
        "t0_enabled_count": len(items),
        "updated_or_created_count": sum(1 for item in items if item.action in {"created", "updated"}),
        "items": [asdict(item) for item in sorted(items, key=lambda item: item.symbol)],
        "notes": [
            "仅同步 ETF universe 中 same_day_sell_allowed=true 的白名单。",
            "股票规则和未放行 ETF 不会被提升为 T+0。",
            "该脚本只持久化交易规则，不代表 ETF 分钟线和折溢价数据已满足验收。",
        ],
    }


def _upsert_instrument(db: Session, profile: EtfProfile) -> None:
    row = db.execute(select(Instrument).where(Instrument.symbol == profile.symbol)).scalar_one_or_none()
    if row is None:
        db.add(
            Instrument(
                symbol=profile.symbol,
                name=profile.name,
                market=guess_market(profile.symbol),
                instrument_type="fund",
                sector_name=profile.tracking_index or profile.category.value,
                status="active",
            )
        )
        return
    row.name = row.name or profile.name
    row.instrument_type = row.instrument_type or "fund"
    row.sector_name = row.sector_name or profile.tracking_index or profile.category.value
    row.status = row.status or "active"


def _upsert_rule(db: Session, profile: EtfProfile, row: InstrumentRule | None) -> tuple[InstrumentRule, str]:
    payload = {
        "turnaround_mode": "t0",
        "supports_positive_t": True,
        "supports_negative_t": True,
        "same_day_sell_allowed": True,
        "requires_base_position": False,
        "notes": (
            f"ETF universe 持久化 T+0 白名单；分类 {profile.category.value}；"
            f"跟踪 {profile.tracking_index or 'unknown'}；{profile.notes}"
        ),
    }
    if row is None:
        row = InstrumentRule(symbol=profile.symbol, **payload)
        db.add(row)
        return row, "created"
    changed = False
    for key, value in payload.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    return row, "updated" if changed else "unchanged"
