from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    PaperAccount,
    PaperDailyReport,
    PaperMarketPerfDaily,
    PaperPerformanceSnapshot,
    PaperStrategyPerfDaily,
)
from app.services.paper.performance import PaperPerformanceService


class PaperPerformanceDashboardService:
    """读取模拟盘归档数据并组装前端看板响应。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, account: PaperAccount, days: int) -> dict:
        start_date = date.today() - timedelta(days=days - 1)
        snapshots = self._snapshots(account.id, start_date)
        strategies = self._strategies(account.id, start_date)
        markets = self._markets(account.id, start_date)
        report = self._latest_report(account.id)
        performance_service = PaperPerformanceService(self.db)
        performance = performance_service.compute_overall(account.id)
        return {
            "account": {
                "id": account.id,
                "total_assets": float(account.total_assets or 0),
                "total_return_pct": performance["total_return_pct"],
                "sharpe_ratio": performance.get("sharpe_ratio", 0.0),
            },
            "equity_curve": [_snapshot_point(row) for row in snapshots],
            "win_rate_trend": [_win_rate_point(row) for row in snapshots],
            "strategy_trend": _strategy_trend(strategies),
            "market_perf_heatmap": _market_heatmap(markets),
            "strategy_market_matrix": performance_service.compute_by_strategy_market_state(
                account.id,
                start_date=start_date,
            ),
            "today_report": _daily_report(report) if report else None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _snapshots(self, account_id: int, start_date: date) -> list[PaperPerformanceSnapshot]:
        return self.db.execute(
            select(PaperPerformanceSnapshot)
            .where(
                PaperPerformanceSnapshot.account_id == account_id,
                PaperPerformanceSnapshot.snapshot_date >= start_date,
            )
            .order_by(PaperPerformanceSnapshot.snapshot_date.asc())
        ).scalars().all()

    def _strategies(self, account_id: int, start_date: date) -> list[PaperStrategyPerfDaily]:
        return self.db.execute(
            select(PaperStrategyPerfDaily)
            .where(
                PaperStrategyPerfDaily.account_id == account_id,
                PaperStrategyPerfDaily.snapshot_date >= start_date,
            )
            .order_by(PaperStrategyPerfDaily.snapshot_date.asc())
        ).scalars().all()

    def _markets(self, account_id: int, start_date: date) -> list[PaperMarketPerfDaily]:
        return self.db.execute(
            select(PaperMarketPerfDaily)
            .where(
                PaperMarketPerfDaily.account_id == account_id,
                PaperMarketPerfDaily.snapshot_date >= start_date,
            )
            .order_by(PaperMarketPerfDaily.snapshot_date.asc())
        ).scalars().all()

    def _latest_report(self, account_id: int) -> PaperDailyReport | None:
        return self.db.execute(
            select(PaperDailyReport)
            .where(PaperDailyReport.account_id == account_id)
            .order_by(PaperDailyReport.report_date.desc())
            .limit(1)
        ).scalar_one_or_none()


def _snapshot_point(row: PaperPerformanceSnapshot) -> dict:
    return {
        "date": row.snapshot_date.isoformat(),
        "total_assets": float(row.total_assets or 0),
        "cumulative_return_pct": float(row.cumulative_return_pct or 0),
    }


def _win_rate_point(row: PaperPerformanceSnapshot) -> dict:
    return {
        "date": row.snapshot_date.isoformat(),
        "win_rate_pct": float(row.win_rate_pct or 0),
        "net_win_rate_pct": float(row.net_win_rate_pct or 0),
    }


def _strategy_trend(rows: list[PaperStrategyPerfDaily]) -> list[dict]:
    grouped: dict[str, list[PaperStrategyPerfDaily]] = {}
    for row in rows:
        grouped.setdefault(row.strategy_key or "未分类", []).append(row)
    return [
        {
            "strategy_key": strategy_key,
            "points": [
                {
                    "date": item.snapshot_date.isoformat(),
                    "win_rate_pct": float(item.win_rate_pct or 0),
                    "net_win_rate_pct": float(item.net_win_rate_pct or 0),
                    "avg_return_pct": float(item.avg_return_pct or 0),
                    "trade_count": int(item.trade_count or 0),
                }
                for item in items
            ],
        }
        for strategy_key, items in sorted(grouped.items())
    ]


def _market_heatmap(rows: list[PaperMarketPerfDaily]) -> list[dict]:
    grouped: dict[str, list[PaperMarketPerfDaily]] = {}
    for row in rows:
        grouped.setdefault(row.market_state or "未分类", []).append(row)
    result = []
    for market_state, items in grouped.items():
        trade_count = sum(int(item.trade_count or 0) for item in items)
        denominator = max(len(items), 1)
        result.append(
            {
                "market_state": market_state,
                "avg_win_rate_pct": round(sum(float(item.win_rate_pct or 0) for item in items) / denominator, 3),
                "avg_return_pct": round(sum(float(item.avg_return_pct or 0) for item in items) / denominator, 3),
                "trade_count": trade_count,
                "profit_factor": _avg_optional([float(item.profit_factor) for item in items if item.profit_factor is not None]),
            }
        )
    return sorted(result, key=lambda item: item["trade_count"], reverse=True)


def _daily_report(row: PaperDailyReport) -> dict:
    return {
        "id": row.id,
        "report_date": row.report_date.isoformat(),
        "overall_summary": row.overall_summary,
        "strategy_highlights": _json_dict_list(row.strategy_highlights),
        "risk_alerts": _json_dict_list(row.risk_alerts),
        "suggestion": row.suggestion,
        "generated_at": row.generated_at.isoformat() if row.generated_at else "",
        "llm_model": row.llm_model,
    }


def _json_dict_list(raw: str) -> list[dict]:
    try:
        values = json.loads(raw or "[]")
    except Exception:
        return []
    return [item for item in values if isinstance(item, dict)]


def _avg_optional(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)
