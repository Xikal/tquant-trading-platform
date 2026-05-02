from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
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
            try:
                target()
            except Exception as exc:
                logger.exception("managed background task failed: %s", name)
                with self._lock:
                    task = self._tasks.get(name)
                    if task is not None:
                        task.last_error = str(exc)
            elapsed = time.perf_counter() - started
            wait_seconds = max(interval_seconds - elapsed, 0.0)
            if stop_event.wait(wait_seconds):
                return


task_manager = TaskManager()
