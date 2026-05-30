from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from sqlalchemy.orm import Session

from app.services.tasks.queue import RuntimeTaskQueue


class TaskHandler(Protocol):
    def __call__(self, context: "TaskContext") -> dict[str, Any]:
        ...


@dataclass
class TaskContext:
    task_id: int
    task_type: str
    payload: dict[str, Any]
    db: Session
    queue: RuntimeTaskQueue
    worker_id: str
    artifacts: list[str] = field(default_factory=list)

    def progress(self, progress_pct: float, message: str, payload: dict[str, Any] | None = None) -> None:
        self.queue.update_progress(
            self.task_id,
            progress_pct=progress_pct,
            message=message,
            payload=payload or {},
        )

    def heartbeat(self) -> None:
        self.queue.heartbeat(self.task_id, worker_id=self.worker_id)

    def add_artifact(self, path: str) -> None:
        if path and path not in self.artifacts:
            self.artifacts.append(path)
        self.queue.add_event(self.task_id, "artifact", "任务产物已生成", {"path": path})
        self.db.commit()


RegisteredHandler = Callable[[TaskContext], dict[str, Any]]
