from __future__ import annotations

from dataclasses import dataclass

from app.services.analytics.config import analytics_config


@dataclass(frozen=True)
class AnalyticsDependencyStatus:
    status: str
    ready: bool
    enabled: bool
    missing: tuple[str, ...] = ()
    error: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "ready": self.ready,
            "enabled": self.enabled,
            "missing": list(self.missing),
            "error": self.error,
        }


def analytics_dependency_status() -> AnalyticsDependencyStatus:
    config = analytics_config()
    missing: list[str] = []
    try:
        import duckdb  # noqa: F401
    except Exception:
        missing.append("duckdb")
    try:
        import pyarrow  # noqa: F401
    except Exception:
        missing.append("pyarrow")
    if missing:
        status = "degraded" if config.enabled else "disabled"
        return AnalyticsDependencyStatus(
            status=status,
            ready=False,
            enabled=config.enabled,
            missing=tuple(missing),
            error=f"missing analytics dependencies: {', '.join(missing)}",
        )
    return AnalyticsDependencyStatus(status="ok" if config.enabled else "disabled", ready=True, enabled=config.enabled)


def require_analytics_dependencies() -> None:
    status = analytics_dependency_status()
    if not status.ready:
        raise RuntimeError(status.error or "analytics dependencies unavailable")
