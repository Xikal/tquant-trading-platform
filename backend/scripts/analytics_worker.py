from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import init_db
from app.services.analytics.dependencies import require_analytics_dependencies
from app.services.tasks.registry import analytics_task_registry
from app.services.tasks.worker import RuntimeTaskWorker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 analytics RuntimeTask worker")
    parser.add_argument("--queue", default="analytics", help="兼容参数；当前按 analytics task_type claim")
    parser.add_argument("--worker-id", default="")
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true", help="只处理一个任务后退出")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO)
    require_analytics_dependencies()
    init_db()
    worker = RuntimeTaskWorker(
        registry=analytics_task_registry(),
        worker_id=args.worker_id or f"analytics-worker",
        poll_interval_seconds=args.poll_interval_seconds,
    )
    if args.once:
        return 0 if worker.run_once() else 3
    worker.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
