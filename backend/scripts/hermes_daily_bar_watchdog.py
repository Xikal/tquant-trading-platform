#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.services.latest_data_watchdog import LatestDailyBarWatchdog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the post-close daily bar watchdog and send Hermes/Feishu notification.")
    parser.add_argument("--trade-date", default="", help="Expected trade date, YYYY-MM-DD. Defaults to latest expected A-share trade date.")
    parser.add_argument("--no-notify", action="store_true", help="Only check data; do not send notification.")
    parser.add_argument("--force-notify", action="store_true", help="Send again even if this trade date was already notified.")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = LatestDailyBarWatchdog().run(
            db,
            trade_date=args.trade_date or None,
            notify=not args.no_notify,
            force_notify=bool(args.force_notify),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") not in {"notification_failed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
