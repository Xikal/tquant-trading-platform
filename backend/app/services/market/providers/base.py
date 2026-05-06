from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class DataSourceQuality:
    source: str
    ok: bool
    quality: str = "failed"
    latency_ms: int = 0
    is_stale: bool = False
    warning: str = ""


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    value: T | None
    quality: DataSourceQuality
    warnings: list[str] = field(default_factory=list)


class ProviderTimer:
    def __init__(self, source: str) -> None:
        self.source = source
        self.started = time.perf_counter()

    def quality(self, *, ok: bool, quality: str | None = None, is_stale: bool = False, warning: str = "") -> DataSourceQuality:
        latency_ms = int((time.perf_counter() - self.started) * 1000)
        return DataSourceQuality(
            source=self.source,
            ok=ok,
            quality=quality or ("ok" if ok else "failed"),
            latency_ms=latency_ms,
            is_stale=is_stale,
            warning=warning,
        )
