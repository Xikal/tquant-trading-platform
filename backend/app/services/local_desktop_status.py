from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import ping_database
from app.models.schema_defs.local_desktop import (
    LocalDesktopComponentStatus,
    LocalDesktopDirectoryStatus,
    LocalDesktopLaunchGuide,
    LocalDesktopStatusResponse,
)
from app.services.shared.distributed_cache_state import get_distributed_cache_client
from app.services.tasks import RuntimeTaskQueue

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SAFETY_FLAGS = {
    "deploy_allowed": False,
    "restart_production_allowed": False,
    "cleanup_allowed": False,
    "auto_trade_allowed": False,
    "strategy_mutation_allowed": False,
}


def build_local_desktop_status(db: Session, *, project_root: Optional[Union[str, Path]] = None) -> LocalDesktopStatusResponse:
    settings = get_settings()
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    components = [
        _backend_component(),
        _database_component(),
        _redis_component(),
        *_runtime_components(db),
    ]
    return LocalDesktopStatusResponse(
        generated_at=datetime.now(),
        app=str(getattr(settings, "app_name", "") or "TQuant"),
        environment=str(getattr(settings, "app_environment", "") or "local"),
        version=_git_version(root),
        components=components,
        directories=_directory_statuses(root),
        launch_guides=_launch_guides(),
        safety=dict(SAFETY_FLAGS),
    )


def _backend_component() -> LocalDesktopComponentStatus:
    return LocalDesktopComponentStatus(name="backend", status="ok", message="backend api reachable")


def _database_component() -> LocalDesktopComponentStatus:
    started = time.monotonic()
    try:
        ping_database()
    except Exception as exc:
        return LocalDesktopComponentStatus(
            name="mysql",
            status="error",
            latency_ms=_elapsed_ms(started),
            message=_safe_error(exc),
        )
    settings = get_settings()
    database_url = str(getattr(settings, "database_url", "") or "")
    message = "sqlite/local database ok" if database_url.startswith("sqlite") else "database ok"
    return LocalDesktopComponentStatus(name="mysql", status="ok", latency_ms=_elapsed_ms(started), message=message)


def _redis_component() -> LocalDesktopComponentStatus:
    settings = get_settings()
    if not str(getattr(settings, "redis_url", "") or "").strip():
        return LocalDesktopComponentStatus(name="redis", status="unknown", message="redis url not configured")
    started = time.monotonic()
    try:
        client = get_distributed_cache_client()
        if client is None:
            return LocalDesktopComponentStatus(name="redis", status="error", latency_ms=_elapsed_ms(started), message="redis unavailable")
        client.ping()
    except Exception as exc:
        return LocalDesktopComponentStatus(name="redis", status="error", latency_ms=_elapsed_ms(started), message=_safe_error(exc))
    return LocalDesktopComponentStatus(name="redis", status="ok", latency_ms=_elapsed_ms(started), message="redis ok")


def _runtime_components(db: Session) -> list[LocalDesktopComponentStatus]:
    try:
        workers = RuntimeTaskQueue(db).workers()
    except Exception as exc:
        message = _safe_error(exc)
        return [
            LocalDesktopComponentStatus(name="runtime_worker", status="unknown", message=message),
            LocalDesktopComponentStatus(name="runtime_scheduler", status="unknown", message=message),
        ]

    by_component: dict[str, list[Any]] = {}
    for item in getattr(workers, "items", []) or []:
        by_component.setdefault(str(getattr(item, "component", "") or ""), []).append(item)
    return [
        _component_from_workers("runtime_worker", by_component.get("runtime-worker", [])),
        _component_from_workers("runtime_scheduler", by_component.get("runtime-scheduler", [])),
    ]


def _component_from_workers(name: str, items: list[Any]) -> LocalDesktopComponentStatus:
    if not items:
        return LocalDesktopComponentStatus(name=name, status="unknown", message="heartbeat missing")
    running = [item for item in items if str(getattr(item, "status", "") or "") == "running"]
    target = running[0] if running else items[0]
    raw_status = str(getattr(target, "status", "") or "unknown")
    status = "ok" if raw_status == "running" else "unknown"
    return LocalDesktopComponentStatus(
        name=name,
        status=status,
        message=raw_status,
        details={
            "worker_id": str(getattr(target, "worker_id", "") or ""),
            "heartbeat_updated_at": str(getattr(target, "heartbeat_updated_at", "") or ""),
            "heartbeat_age_seconds": getattr(target, "heartbeat_age_seconds", None),
            "running_task_count": int(getattr(target, "running_task_count", 0) or 0),
        },
    )


def _directory_statuses(root: Path) -> list[LocalDesktopDirectoryStatus]:
    paths = {
        "project": root,
        "logs": root / "logs",
        "data": root / "backend" / "data",
        "reports": root / "docs" / "reports",
        "frontend_dist": root / "frontend-next" / "dist",
    }
    return [
        LocalDesktopDirectoryStatus(key=key, path=str(path), exists=path.exists())
        for key, path in paths.items()
    ]


def _launch_guides() -> list[LocalDesktopLaunchGuide]:
    return [
        LocalDesktopLaunchGuide(
            key="web",
            label="本机 Web/API",
            command="scripts/run_platform_component.sh web",
            description="启动 FastAPI 本机进程，默认监听 127.0.0.1:8000。",
        ),
        LocalDesktopLaunchGuide(
            key="runtime_worker",
            label="Runtime Worker",
            command="scripts/run_platform_component.sh runtime-worker",
            description="处理已入队的数据刷新、物化和修复任务；不会由桌面端自动启动。",
        ),
        LocalDesktopLaunchGuide(
            key="runtime_scheduler",
            label="Runtime Scheduler",
            command="scripts/run_platform_component.sh scheduler",
            description="按本地配置入队周期任务；启动前需确认不会与其他 scheduler 重复运行。",
        ),
        LocalDesktopLaunchGuide(
            key="analytics_worker",
            label="Analytics Worker",
            command="scripts/run_platform_component.sh analytics-worker",
            description="仅在维护窗口处理 DuckDB/Parquet/分析类任务；默认可不常驻。",
            optional=True,
        ),
    ]


def _git_version(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _safe_error(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    redacted = text
    for marker in ("password", "secret", "token"):
        redacted = redacted.replace(marker, "redacted")
        redacted = redacted.replace(marker.upper(), "REDACTED")
    if "://" in redacted and "@" in redacted:
        return exc.__class__.__name__
    return redacted[:160]
