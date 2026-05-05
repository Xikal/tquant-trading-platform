from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.backtest_worker import BacktestWorker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the persistent backtest DB worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one available job and exit.")
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument("--max-duration-seconds", type=float, default=3600.0)
    args = parser.parse_args()

    worker = BacktestWorker(max_duration_seconds=args.max_duration_seconds)
    if args.once:
        outcome = worker.run_once()
        if outcome is None:
            print("no queued backtest jobs")
        else:
            print(f"run_id={outcome.run_id} status={outcome.status} message={outcome.message}")
        return 0

    worker.run_forever(poll_interval_seconds=args.poll_interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
