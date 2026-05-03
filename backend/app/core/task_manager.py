from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class ManagedTask:
    name: str
    thread: threading.Thread
    stop_event: threading.Event
    interval_seconds: float
    initial_delay_seconds: float = 0.0
    last_error: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    duration_ms: int = 0
    rows_processed: int = 0
    run_count: int = 0
    enabled: bool = True


class TaskManager:
    """Small in-process scheduler for bounded background maintenance tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, ManagedTask] = {}
        self._lock = threading.Lock()

    def register_loop(
        self,
        *,
        name: str,
        target: Callable[[], None],
        interval_seconds: float,
        initial_delay_seconds: float = 0.0,
    ) -> None:
        with self._lock:
            if name in self._tasks:
                return
            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._run_loop,
                args=(name, target, interval_seconds, initial_delay_seconds, stop_event),
                name=f"runtime-{name}",
                daemon=True,
            )
            self._tasks[name] = ManagedTask(
                name=name,
                thread=thread,
                stop_event=stop_event,
                interval_seconds=interval_seconds,
                initial_delay_seconds=initial_delay_seconds,
            )
            thread.start()

    def shutdown(self, timeout: float = 10.0) -> None:
        with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            task.stop_event.set()
        for task in tasks:
            task.thread.join(timeout=timeout)

    def snapshot(self) -> list[dict]:
        with self._lock:
            tasks = list(self._tasks.values())
        return [_task_snapshot(task) for task in tasks]

    def _run_loop(
        self,
        name: str,
        target: Callable[[], None],
        interval_seconds: float,
        initial_delay_seconds: float,
        stop_event: threading.Event,
    ) -> None:
        if initial_delay_seconds > 0 and stop_event.wait(initial_delay_seconds):
            return
        while not stop_event.is_set():
            started = time.perf_counter()
            started_at = datetime.now()
            with self._lock:
                task = self._tasks.get(name)
                if task is not None:
                    task.last_started_at = started_at
                    task.run_count += 1
            try:
                target()
                with self._lock:
                    task = self._tasks.get(name)
                    if task is not None:
                        task.last_error = None
                        task.last_success_at = datetime.now()
            except Exception as exc:
                logger.exception("managed background task failed: %s", name)
                with self._lock:
                    task = self._tasks.get(name)
                    if task is not None:
                        task.last_error = str(exc)
            elapsed = time.perf_counter() - started
            finished_at = datetime.now()
            with self._lock:
                task = self._tasks.get(name)
                if task is not None:
                    task.last_finished_at = finished_at
                    task.duration_ms = int(elapsed * 1000)
            wait_seconds = max(interval_seconds - elapsed, 0.0)
            if stop_event.wait(wait_seconds):
                return


task_manager = TaskManager()


def _task_snapshot(task: ManagedTask) -> dict:
    next_run_at = None
    if task.last_finished_at is not None:
        next_run_at = task.last_finished_at + timedelta(seconds=task.interval_seconds)
    return {
        "task_name": task.name,
        "last_started_at": _dt(task.last_started_at),
        "last_finished_at": _dt(task.last_finished_at),
        "last_success_at": _dt(task.last_success_at),
        "last_error": task.last_error,
        "duration_ms": task.duration_ms,
        "rows_processed": task.rows_processed,
        "next_run_at": _dt(next_run_at),
        "enabled": task.enabled and not task.stop_event.is_set(),
        "interval_seconds": task.interval_seconds,
        "run_count": task.run_count,
        "thread_alive": task.thread.is_alive(),
    }


def _dt(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None
