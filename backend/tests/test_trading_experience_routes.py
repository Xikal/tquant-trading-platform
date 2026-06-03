from __future__ import annotations

from app.models.entities import SystemSetting
from app.services.shared.feature_flags import clear_feature_flag_cache
from backend.tests.trading_experience_fixtures import client_for, seed_daily_bars, seed_minutes, seed_paper, session_factory


def test_holding_discipline_route_does_not_expose_other_user_account() -> None:
    Session = session_factory()
    db = Session()
    _enable_flags(db, "holding_discipline_assistant_enabled")
    seed_daily_bars(db)
    other_account = seed_paper(db, user_id=2)
    other_account_id = other_account.id
    db.close()
    client = client_for(Session)

    response = client.get(f"/api/trading-experience/holding-discipline?account_id={other_account_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["account_id"] == other_account_id
    assert payload["items"] == []
    assert payload["data_quality"] == "insufficient"


def test_t_trade_attribution_route_does_not_expose_other_user_account() -> None:
    Session = session_factory()
    db = Session()
    _enable_flags(db, "t_trade_discipline_enabled")
    other_account = seed_paper(db, user_id=2)
    other_account_id = other_account.id
    seed_minutes(db)
    db.close()
    client = client_for(Session)

    response = client.get(f"/api/trading-experience/t-trade-attribution?account_id={other_account_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["account_id"] == other_account_id
    assert payload["items"] == []
    assert payload["data_quality"] == "no_data"


def test_trade_journal_route_rejects_other_user_account() -> None:
    Session = session_factory()
    db = Session()
    _enable_flags(db, "trade_review_suite_enabled")
    other_account = seed_paper(db, user_id=2)
    other_account_id = other_account.id
    db.close()
    client = client_for(Session)

    response = client.post(
        "/api/trading-experience/trade-journal",
        json={"account_id": other_account_id, "symbol": "600000", "action": "note"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "paper_account_not_found"


def test_review_pool_route_applies_main_board_filter_in_backend() -> None:
    Session = session_factory()
    db = Session()
    _enable_flags(db, "trade_review_suite_enabled")
    seed_daily_bars(db, symbol="300001", pct=20.0, sector="创业板样本")
    seed_daily_bars(db, symbol="600001", pct=10.0, sector="主板样本")
    db.close()
    client = client_for(Session)

    response = client.get("/api/trading-experience/review-pool?pool_date=2026-05-24&limit=2&board_filter=main_only")

    assert response.status_code == 200
    payload = response.json()
    assert payload["board_filter"] == "main_only"
    assert [item["symbol"] for item in payload["items"]] == ["600001"]
    assert payload["items"][0]["board_name"] == "主板"


def _enable_flags(db, *keys: str) -> None:  # noqa: ANN001
    db.add(SystemSetting(key="ff_trading_experience_suite_enabled", value="true"))
    for key in keys:
        db.add(SystemSetting(key=f"ff_{key}", value="true"))
    db.commit()
    clear_feature_flag_cache()
