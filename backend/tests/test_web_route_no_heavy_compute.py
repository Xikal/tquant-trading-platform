from __future__ import annotations

from pathlib import Path

from app.services.tasks.registry import RUNTIME_TASK_REGISTRY


ROOT = Path(__file__).resolve().parents[2]
ROUTES_DIR = ROOT / "backend" / "app" / "api" / "routes"
FORBIDDEN_DIRECT_CALLS = (
    "execute_heavy_research_task(",
    "BacktestWorker(",
    "RuntimeWorker(",
    "export_daily_bars_parquet(",
    "build_strategy_24m_duckdb_report(",
    "run_duckdb_strategy_report",
)


def test_web_routes_do_not_call_worker_handlers_directly() -> None:
    offenders: list[str] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if path.name == "heavy_task_helpers.py":
            continue
        for marker in FORBIDDEN_DIRECT_CALLS:
            if marker in text:
                offenders.append(f"{path.relative_to(ROOT)}:{marker}")

    assert offenders == []


def test_web_routes_submit_registered_worker_tasks_only() -> None:
    route_text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(ROUTES_DIR.glob("*.py")))
    registered = set(RUNTIME_TASK_REGISTRY)
    missing: list[str] = []
    for line in route_text.splitlines():
        stripped = line.strip()
        if "task_type=" not in stripped:
            continue
        task_type = _string_after_task_type(stripped)
        if task_type and task_type not in registered:
            missing.append(task_type)

    assert sorted(set(missing)) == []


def _string_after_task_type(line: str) -> str:
    marker = "task_type="
    index = line.find(marker)
    if index < 0:
        return ""
    tail = line[index + len(marker):].lstrip()
    if not tail or tail[0] not in {"'", '"'}:
        return ""
    quote = tail[0]
    end = tail.find(quote, 1)
    return tail[1:end] if end > 1 else ""
