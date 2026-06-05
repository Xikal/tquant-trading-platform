from __future__ import annotations

from datetime import date

from app.models.entities import SystemSetting
from app.services.shared.feature_flags import clear_feature_flag_cache
from app.services.trading_experience.config import DISCIPLINE_FLAG_KEYS
from app.services.trading_experience.schemas import TradeJournalEntryCreate
from app.services.trading_experience.service import TradingExperienceService
from backend.tests.trading_experience_fixtures import seed_daily_bars, session_factory


def test_review_workspace_is_disabled_when_flags_are_off() -> None:
    Session = session_factory()
    db = Session()

    response = TradingExperienceService(db).review_workspace(pool_date=date(2026, 5, 24), limit=10, user_id=1)

    assert response.enabled is False
    assert response.review_enabled is False
    assert response.relative_strength_enabled is False
    assert response.data_quality == "blocked"
    assert response.items == []
    assert response.summary.pending_review_count == 0
    assert response.reminder.status == "blocked"


def test_review_workspace_links_pool_items_to_journals_and_relative_strength() -> None:
    Session = session_factory()
    db = Session()
    _enable_flags(db, "trade_review_suite_enabled", "relative_strength_board_enabled")
    seed_daily_bars(db, symbol="600000", pct=8.8, sector="银行")

    TradingExperienceService(db).create_trade_journal(
        TradeJournalEntryCreate(
            symbol="600000",
            action="note",
            reason_text="盘后复盘记录",
            signal_source="manual_review",
            discipline_flags={
                "trend_follow": True,
                "stop_loss_set": True,
                "no_add_down": True,
                "no_chase_noliquidity": True,
                "not_against_mainline": True,
                "planned_position": True,
            },
            mistake_tags=[],
        ),
        user_id=1,
    )

    response = TradingExperienceService(db).review_workspace(pool_date=date(2026, 5, 24), limit=20, user_id=1)

    assert response.enabled is True
    assert response.review_enabled is True
    assert response.relative_strength_enabled is True
    assert response.research_only is True
    assert response.source == "review_workspace"
    assert response.summary.pending_review_count >= 0
    assert response.summary.missing_journal_count >= 0
    assert response.summary.completion_rate_pct >= 0
    assert response.summary.seven_day_journal_count >= 0
    assert response.summary.seven_day_discipline_pass_rate_pct == 100
    assert response.reminder.status in {"not_due", "queued", "refreshing", "ready", "insufficient", "blocked"}
    assert response.reminder.message
    assert {source.source for source in response.sources} == {"review_pool", "trade_journal", "relative_strength"}
    for item in response.items:
        assert item.review_key == f"{item.pool_item.pool_date}:{item.pool_item.symbol}"
        assert item.next_action_label in {"写复盘", "查看纪律", "查看剔除原因", "检查数据"}
        assert item.review_status in {"pending", "journaled", "retained", "dropped", "data_issue"}


def test_review_workspace_exposes_source_timing_budget() -> None:
    Session = session_factory()
    db = Session()
    _enable_flags(db, "trade_review_suite_enabled", "relative_strength_board_enabled")
    seed_daily_bars(db, symbol="600000", pct=8.8, sector="银行")

    response = TradingExperienceService(db).review_workspace(pool_date=None, limit=30, user_id=1)

    assert response.elapsed_ms >= 0
    assert response.elapsed_ms < 500
    assert response.cache_status in {"fresh", "stale", "miss"}
    assert {source.source for source in response.sources} == {"review_pool", "trade_journal", "relative_strength"}
    for source in response.sources:
        assert source.elapsed_ms >= 0
        assert source.status in {"ok", "disabled", "stale", "insufficient", "timeout", "error"}


def test_review_workspace_scopes_journal_entries_to_current_user() -> None:
    Session = session_factory()
    db = Session()
    _enable_flags(db, "trade_review_suite_enabled", "relative_strength_board_enabled")
    seed_daily_bars(db, symbol="600000", pct=8.8, sector="银行")

    TradingExperienceService(db).create_trade_journal(
        TradeJournalEntryCreate(
            symbol="600000",
            action="note",
            reason_text="用户一复盘",
            signal_source="manual_review",
            discipline_flags={key: True for key in DISCIPLINE_FLAG_KEYS},
        ),
        user_id=1,
    )
    TradingExperienceService(db).create_trade_journal(
        TradeJournalEntryCreate(
            symbol="600000",
            action="note",
            reason_text="用户二复盘",
            signal_source="manual_review",
            discipline_flags={key: False for key in DISCIPLINE_FLAG_KEYS},
        ),
        user_id=2,
    )

    response = TradingExperienceService(db).review_workspace(pool_date=date(2026, 5, 24), limit=20, user_id=1)

    linked_entries = [entry for item in response.items for entry in item.journal_entries]
    assert linked_entries
    assert {entry.reason_text for entry in linked_entries} == {"用户一复盘"}
    assert {entry.user_id for entry in linked_entries} == {1}
    assert response.summary.seven_day_journal_count == 1
    assert response.summary.seven_day_discipline_pass_rate_pct == 100


def _enable_flags(db, *keys: str) -> None:  # noqa: ANN001
    db.add(SystemSetting(key="ff_trading_experience_suite_enabled", value="true"))
    for key in keys:
        db.add(SystemSetting(key=f"ff_{key}", value="true"))
    db.commit()
    clear_feature_flag_cache()
