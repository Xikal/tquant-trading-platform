from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from contextvars import Token
from typing import Iterator

_MARKET_STATE_SCOPE: ContextVar[str] = ContextVar("market_state_scope", default="")


def current_market_state_scope() -> str:
    return _MARKET_STATE_SCOPE.get().strip()


def set_market_state_scope(scope: str | None) -> Token[str]:
    return _MARKET_STATE_SCOPE.set((scope or "").strip())


def reset_market_state_scope(token: Token[str]) -> None:
    _MARKET_STATE_SCOPE.reset(token)


@contextmanager
def use_market_state_scope(scope: str | None) -> Iterator[None]:
    token = set_market_state_scope(scope)
    try:
        yield
    finally:
        reset_market_state_scope(token)
