from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.timezone import beijing_today
from app.models.entities import BacktestRun, PaperAccount, PaperBacktestComparison
from app.models.schema_defs.phase4 import PaperBacktestComparisonResponse
from app.services.paper.performance import PaperPerformanceService


class PaperBacktestComparisonService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def compare(
        self,
        *,
        account_id: int,
        backtest_run_id: int,
        deviation_threshold_pct: float = 20.0,
        target_date: date | None = None,
    ) -> PaperBacktestComparisonResponse:
        account = self.db.get(PaperAccount, account_id)
        if account is None:
            raise LookupError("模拟账户不存在")
        run = self.db.get(BacktestRun, backtest_run_id)
        if run is None:
            raise LookupError("回测记录不存在")
        comparison_date = target_date or beijing_today()
        expected_return = _expected_return_pct(run)
        actual_return = float(PaperPerformanceService(self.db).compute_overall(account_id)["total_return_pct"])
        deviation = _deviation_pct(expected_return, actual_return)
        alert = abs(deviation) >= deviation_threshold_pct
        reason = _reason(expected_return, actual_return, deviation, alert)
        detail = {
            "threshold_pct": deviation_threshold_pct,
            "backtest_status": run.status,
            "backtest_strategy_keys": run.strategy_keys,
            "account_total_assets": float(account.total_assets or 0),
        }
        row = PaperBacktestComparison(
            account_id=account_id,
            backtest_run_id=backtest_run_id,
            comparison_date=comparison_date,
            expected_return_pct=expected_return,
            actual_return_pct=actual_return,
            deviation_pct=deviation,
            alert=alert,
            reason=reason,
            detail_json=json.dumps(detail, ensure_ascii=False, default=str),
        )
        self.db.add(row)
        self.db.commit()
        return PaperBacktestComparisonResponse(
            account_id=account_id,
            backtest_run_id=backtest_run_id,
            comparison_date=comparison_date.isoformat(),
            expected_return_pct=expected_return,
            actual_return_pct=actual_return,
            deviation_pct=deviation,
            alert=alert,
            reason=reason,
            detail=detail,
        )


def _expected_return_pct(run: BacktestRun) -> float:
    if float(run.initial_cash or 0) > 0 and float(run.final_equity or 0) > 0:
        return round((float(run.final_equity) / float(run.initial_cash) - 1) * 100, 3)
    try:
        payload = json.loads(run.result_json or "{}")
    except Exception:
        payload = {}
    metrics = payload.get("metrics") if isinstance(payload, dict) else {}
    if isinstance(metrics, dict):
        for key in ("total_return_pct", "return_pct", "cumulative_return_pct"):
            if key in metrics:
                return round(float(metrics.get(key) or 0), 3)
    return 0.0


def _deviation_pct(expected: float, actual: float) -> float:
    denominator = max(abs(expected), 1.0)
    return round((actual - expected) / denominator * 100, 3)


def _reason(expected: float, actual: float, deviation: float, alert: bool) -> str:
    if not alert:
        return "模拟盘与回测偏差在阈值内。"
    direction = "低于" if actual < expected else "高于"
    return f"模拟盘收益{direction}回测预期，偏差 {deviation:.2f}%，需要检查滑点、成交假设、样本过拟合或数据质量。"
