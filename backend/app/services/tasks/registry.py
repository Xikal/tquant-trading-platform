from __future__ import annotations

from typing import Any

from app.services.tasks.handlers import RegisteredHandler


class TaskHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, RegisteredHandler] = {}

    def register(self, task_type: str, handler: RegisteredHandler) -> None:
        key = str(task_type).strip()
        if not key:
            raise ValueError("task_type is required")
        self._handlers[key] = handler

    def get(self, task_type: str) -> RegisteredHandler:
        try:
            return self._handlers[task_type]
        except KeyError as exc:
            raise ValueError(f"未知任务类型: {task_type}") from exc

    def task_types(self) -> list[str]:
        return sorted(self._handlers)


def analytics_task_registry() -> TaskHandlerRegistry:
    from app.services.tasks.analytics_handlers import register_analytics_handlers

    registry = TaskHandlerRegistry()
    register_analytics_handlers(registry)
    return registry
