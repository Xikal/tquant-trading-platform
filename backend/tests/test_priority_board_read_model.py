from __future__ import annotations

from app.services.low_buy import priority_board_read_model as read_model


def test_read_model_cache_key_includes_variant_date_and_user_filter_hash() -> None:
    key = read_model.priority_board_read_model_key(
        trade_date="2026-06-04",
        strategy_variant="default",
        cache_key="low-buy:priority:2026-06-04",
        user_filter_hash="abc123",
    )

    assert "2026-06-04" in key
    assert "default" in key
    assert "low-buy:priority:2026-06-04" in key
    assert "abc123" in key


def test_read_model_stores_and_loads_payload(monkeypatch) -> None:
    stored: dict[str, str] = {}

    monkeypatch.setattr(
        read_model,
        "set_text_cache",
        lambda key, value, ttl_seconds: stored.setdefault(key, value) is not None,
    )
    monkeypatch.setattr(read_model, "get_text_cache", lambda key: stored.get(key))

    payload = {
        "items": [{"symbol": "600000", "priority_score": 88.0, "buy_signal_state": "observe"}],
        "data_quality": "fresh",
    }
    key = "priority-board:test"

    assert read_model.store_priority_board_read_model(key, payload, ttl_seconds=45) is True
    loaded = read_model.load_priority_board_read_model(key)

    assert loaded == payload


def test_read_model_rejects_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(read_model, "get_text_cache", lambda key: "{bad json")

    assert read_model.load_priority_board_read_model("priority-board:test") is None
