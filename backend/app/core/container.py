from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar


T = TypeVar("T")


class ServiceContainer:
    """Minimal DI container for tests and provider replacement.

    The project does not need a heavy framework. This registry gives us a
    stable seam to replace market data, Agent, notification, and ML services in
    tests or future Agent architectures.
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., Any]] = {}

    def register(self, key: str, factory: Callable[..., T]) -> None:
        if not key:
            raise ValueError("service key is required")
        self._factories[key] = factory

    def resolve(self, key: str, *args: Any, **kwargs: Any) -> Any:
        factory = self._factories.get(key)
        if factory is None:
            raise KeyError(f"service not registered: {key}")
        return factory(*args, **kwargs)

    def clear(self) -> None:
        self._factories.clear()


container = ServiceContainer()
