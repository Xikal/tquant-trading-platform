from __future__ import annotations

from typing import Any

from app.services.trading_experience.config import FORBIDDEN_TRADING_COPY


def assert_no_forbidden_trading_copy(payload: Any) -> None:
    text = _flatten_text(payload)
    blocked = [word for word in FORBIDDEN_TRADING_COPY if word in text]
    if blocked:
        raise ValueError(f"forbidden_trading_copy:{','.join(blocked)}")


def assert_no_production_score(payload: Any) -> None:
    if _contains_key(payload, "production_score"):
        raise ValueError("trading_experience_must_not_emit_production_score")


def validate_observation_payload(payload: Any) -> Any:
    assert_no_forbidden_trading_copy(payload)
    assert_no_production_score(payload)
    return payload


def _flatten_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return " ".join(_flatten_text(value) for value in payload.values())
    if isinstance(payload, (list, tuple, set)):
        return " ".join(_flatten_text(value) for value in payload)
    return ""


def _contains_key(payload: Any, key: str) -> bool:
    if isinstance(payload, dict):
        return key in payload or any(_contains_key(value, key) for value in payload.values())
    if isinstance(payload, (list, tuple, set)):
        return any(_contains_key(value, key) for value in payload)
    return False
