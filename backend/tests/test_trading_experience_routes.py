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


def _enable_flags(db, *keys: str) -> None:  # noqa: ANN001
    db.add(SystemSetting(key="ff_trading_experience_suite_enabled", value="true"))
    for key in keys:
        db.add(SystemSetting(key=f"ff_{key}", value="true"))
    db.commit()
    clear_feature_flag_cache()
