from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.repositories.low_buy import LowBuyResultRepository
from app.services.agent_notification_service import AgentNotificationService
from app.services.latest_data_status import latest_data_status, publish_latest_trade_date_if_ready
from app.services.low_buy.strategy_policy import PRODUCTION_PRIORITY_STRATEGIES
from app.services.low_buy_materialization import enqueue_low_buy_materialization


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="验收低吸最新数据闭环并在失败时告警")
    parser.add_argument("--strategies", default=",".join(sorted(PRODUCTION_PRIORITY_STRATEGIES)))
    parser.add_argument("--notify-on-fail", action="store_true", help="失败时发送飞书/Hermes 告警")
    parser.add_argument("--enqueue-missing", action="store_true", help="缺少最新物化时入队后台刷新任务")
    parser.add_argument("--publish-if-ready", action="store_true", help="验收前尝试发布已就绪日期")
    parser.add_argument("--repair", action="store_true", help="验收失败时同步刷新日线并重建生产策略快照")
    parser.add_argument("--channel", default="feishu")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    strategies = [item.strip() for item in args.strategies.split(",") if item.strip()]
    init_db()
    with SessionLocal() as db:
        if args.publish_if_ready:
            publish_latest_trade_date_if_ready(db, strategies=strategies)
            db.commit()
        status = latest_data_status(db, strategies=strategies)
        summaries = _strategy_summaries(db, status.get("expected_trade_date", ""), strategies)
        failures = _failures(status=status, summaries=summaries)
        warnings = _warnings(summaries=summaries)
        if failures and args.repair:
            _repair_latest_data(db, status=status, strategies=strategies)
            status = latest_data_status(db, strategies=strategies)
            summaries = _strategy_summaries(db, status.get("expected_trade_date", ""), strategies)
            failures = _failures(status=status, summaries=summaries)
            warnings = _warnings(summaries=summaries)
        if failures and args.enqueue_missing:
            enqueue_low_buy_materialization(db, reason="latest_data_acceptance_failed")
            db.commit()

    payload = {
        "ok": not failures,
        "status": status,
        "strategy_summaries": summaries,
        "failures": failures,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    if failures and args.notify_on_fail:
        _notify_failure(payload, channel=args.channel)
    return 0 if not failures else 2


def _strategy_summaries(db, trade_date: str, strategies: list[str]) -> list[dict[str, Any]]:
    repository = LowBuyResultRepository(db)
    rows: list[dict[str, Any]] = []
    for strategy in strategies:
        summary = repository.fetch_scan_summary(strategy_key=strategy, latest_trade_date=trade_date)
        rows.append(
            {
                "strategy": strategy,
                "latest_trade_date": trade_date,
                "present": summary is not None,
                "pool_size": int(summary.pool_size or 0) if summary else 0,
                "matched_count": int(summary.matched_count or 0) if summary else 0,
                "updated_at": str(summary.updated_at) if summary and summary.updated_at else "",
            }
        )
    return rows


def _repair_latest_data(db, *, status: dict[str, Any], strategies: list[str]) -> None:
    daily_count = int(status.get("daily_bar_count") or 0)
    min_count = int(status.get("min_daily_bar_count") or 0)
    if daily_count < min_count:
        from app.services.daily_bar_refresh import DailyBarRefreshService

        DailyBarRefreshService(db).refresh_latest(limit=6000)
        db.commit()
    if latest_data_status(db, strategies=strategies).get("missing_strategies"):
        from app.services.low_buy_materialization import refresh_latest_low_buy_materialization

        refresh_latest_low_buy_materialization(strategies=strategies)
    publish_latest_trade_date_if_ready(db, strategies=strategies)
    db.commit()


def _failures(*, status: dict[str, Any], summaries: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    expected = str(status.get("expected_trade_date") or "")
    published = str(status.get("published_trade_date") or "")
    daily_count = int(status.get("daily_bar_count") or 0)
    min_count = int(status.get("min_daily_bar_count") or 0)
    missing = list(status.get("missing_strategies") or [])
    if not expected:
        failures.append("无法识别预期最新交易日")
    if daily_count < min_count:
        failures.append(f"{expected} 日线覆盖不足：{daily_count}/{min_count}")
    if missing:
        failures.append(f"{expected} 缺少策略快照：{', '.join(missing)}")
    if published != expected or status.get("status") != "success":
        failures.append(f"最新数据未发布：expected={expected}, published={published}, status={status.get('status')}")
    return failures


def _warnings(*, summaries: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for row in summaries:
        if row["present"] and row["pool_size"] <= 0:
            warnings.append(f"{row['strategy']} 样本池为空")
    return warnings


def _notify_failure(payload: dict[str, Any], *, channel: str) -> None:
    failures = "\n".join(f"- {item}" for item in payload["failures"])
    status = payload["status"]
    message = (
        "TQuant 最新数据闭环验收失败\n"
        f"预期交易日：{status.get('expected_trade_date')}\n"
        f"已发布交易日：{status.get('published_trade_date') or '未发布'}\n"
        f"日线覆盖：{status.get('daily_bar_count')}/{status.get('min_daily_bar_count')}\n"
        f"问题：\n{failures}"
    )
    result = AgentNotificationService().send_test(AgentNotificationTestRequest(channel=channel, message=message))
    if not result.ok:
        print(
            json.dumps(
                {"notification_ok": False, "code": result.code, "message": result.message},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())
