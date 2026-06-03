from __future__ import annotations

import pytest

from app.core.config import AppSettings
from app.models.entities import SystemSetting
from app.services.shared.feature_flags import clear_feature_flag_cache
from app.services.trading_experience.guards import assert_no_forbidden_trading_copy, assert_no_production_score
from app.services.trading_experience.service import TradingExperienceService
from backend.tests.trading_experience_fixtures import session_factory


def test_feature_flags_default_false() -> None:
    settings = AppSettings()

    assert settings.trading_experience_suite_enabled is False
    assert settings.trade_review_suite_enabled is False
    assert settings.vp_position_tags_enabled is False
    assert settings.relative_strength_board_enabled is False
    assert settings.holding_discipline_assistant_enabled is False
    assert settings.limit_up_followthrough_enabled is False
    assert settings.t_trade_discipline_enabled is False


def test_forbidden_copy_guard_blocks_trading_instruction_words() -> None:
    with pytest.raises(ValueError):
        assert_no_forbidden_trading_copy({"text": "这里不能出现买入指令"})


def test_production_score_guard_blocks_output_key() -> None:
    with pytest.raises(ValueError):
        assert_no_production_score({"items": [{"production_score": 88}]})


def test_trading_experience_readiness_uses_db_feature_flags() -> None:
    Session = session_factory()
    db = Session()
    db.add(SystemSetting(key="ff_trading_experience_suite_enabled", value="true"))
    db.add(SystemSetting(key="ff_trade_review_suite_enabled", value="true"))
    db.commit()
    clear_feature_flag_cache()

    readiness = TradingExperienceService(db).readiness()

    assert readiness.enabled is True
    assert readiness.flags["trade_review_suite_enabled"] is True
