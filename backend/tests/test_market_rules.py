from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import Instrument, InstrumentRule
from app.services.etf.universe import EtfCategory, etf_profile_for, is_t0_eligible_etf, list_etf_profiles
from app.services.etf.rule_sync import sync_etf_t0_rules
from app.services.market_rules import T0_KEYWORDS
from app.services.paper.symbols import can_sell_same_day, is_etf


def test_t0_keywords_are_deduplicated() -> None:
    assert len(T0_KEYWORDS) == len(set(T0_KEYWORDS))


def test_etf_universe_keeps_known_broad_base_etf_t0_enabled() -> None:
    profile = etf_profile_for("510300", name="沪深300ETF", instrument_type="fund")

    assert profile is not None
    assert profile.category == EtfCategory.BROAD_BASE
    assert profile.same_day_sell_allowed is True
    assert is_etf("510300") is True
    assert can_sell_same_day("510300") is True


def test_etf_universe_does_not_promote_unknown_sector_etf_to_t0() -> None:
    profile = etf_profile_for("512999", name="测试行业ETF", instrument_type="fund")

    assert profile is not None
    assert profile.category == EtfCategory.SECTOR
    assert profile.same_day_sell_allowed is False
    assert is_etf("512999") is True
    assert can_sell_same_day("512999") is False
    assert is_t0_eligible_etf("512999", name="测试行业ETF", instrument_type="fund") is False


def test_market_rule_service_uses_etf_universe_for_t0_gate() -> None:
    from app.services.market_rules import MarketRuleService

    service = MarketRuleService()

    known = service._derive_rule("510300", "沪深300ETF", "fund")
    unknown = service._derive_rule("512999", "测试行业ETF", "fund")
    stock = service._derive_rule("600000", "浦发银行", "stock")

    assert known["turnaround_mode"] == "t0"
    assert known["same_day_sell_allowed"] is True
    assert unknown["turnaround_mode"] == "t1"
    assert unknown["same_day_sell_allowed"] is False
    assert stock["turnaround_mode"] == "t1"
    assert stock["same_day_sell_allowed"] is False
    assert service.looks_like_etf("512999", "测试行业ETF") is True
    assert service.looks_like_etf("600000", "浦发银行") is False


def test_etf_universe_runtime_override_is_explicit_and_auditable() -> None:
    profile = etf_profile_for(
        "512999",
        name="测试行业ETF",
        instrument_type="fund",
        params={
            "universe_overrides": {
                "512999": {
                    "name": "测试行业ETF",
                    "category": "sector",
                    "t0_eligible": True,
                    "settlement_rule": "t0",
                    "enabled_for_t0": True,
                    "tracking_index": "测试行业",
                    "min_amount": 88000000,
                    "notes": "测试覆盖",
                }
            }
        },
    )

    assert profile is not None
    assert profile.same_day_sell_allowed is True
    assert profile.tracking_index == "测试行业"
    assert profile.min_amount == 88000000
    assert profile.notes == "测试覆盖"


def test_list_etf_profiles_merges_runtime_overrides_without_promoting_unknowns() -> None:
    profiles = list_etf_profiles(params={"universe_overrides": {"512999": {"name": "测试行业ETF", "category": "sector", "t0_eligible": False}}})
    by_symbol = {item.symbol: item for item in profiles}

    assert by_symbol["510300"].same_day_sell_allowed is True
    assert by_symbol["512999"].category == EtfCategory.SECTOR
    assert by_symbol["512999"].same_day_sell_allowed is False


def test_sync_etf_t0_rules_persists_whitelist_without_promoting_unknowns() -> None:
    db = _session()
    db.add(Instrument(symbol="512999", name="测试行业ETF", market="SH", instrument_type="fund"))
    db.add(
        InstrumentRule(
            symbol="510300",
            turnaround_mode="t1",
            supports_positive_t=True,
            supports_negative_t=True,
            same_day_sell_allowed=False,
            requires_base_position=True,
            notes="old",
        )
    )
    db.commit()

    report = sync_etf_t0_rules(db)
    known = db.query(InstrumentRule).filter_by(symbol="510300").one()
    unknown = db.query(InstrumentRule).filter_by(symbol="512999").one_or_none()

    assert report["t0_enabled_count"] >= 1
    item_by_symbol = {item["symbol"]: item for item in report["items"]}
    assert item_by_symbol["510300"]["previous_same_day_sell_allowed"] is False
    assert known.turnaround_mode == "t0"
    assert known.same_day_sell_allowed is True
    assert known.requires_base_position is False
    assert unknown is None


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
