from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import threading
from typing import Iterator

_LOCAL = threading.local()


@dataclass(frozen=True)
class MarketStateScopeToken:
    previous_scope: str


def current_market_state_scope() -> str:
    return str(getattr(_LOCAL, "scope", "") or "").strip()


def set_market_state_scope(scope: str | None) -> MarketStateScopeToken:
    token = MarketStateScopeToken(previous_scope=current_market_state_scope())
    _LOCAL.scope = (scope or "").strip()
    return token


def reset_market_state_scope(token: MarketStateScopeToken) -> None:
    _LOCAL.scope = token.previous_scope


@contextmanager
def use_market_state_scope(scope: str | None) -> Iterator[None]:
    token = set_market_state_scope(scope)
    try:
        yield
    finally:
        reset_market_state_scope(token)
