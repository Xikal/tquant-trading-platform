from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.services.backtest.engine import BacktestResult


class BacktestReporter:
    def to_payload(self, result: BacktestResult) -> dict[str, Any]:
        return result.to_dict()

    def to_summary(self, result: BacktestResult) -> dict[str, Any]:
        metrics = result.metrics
        return {
            "version": result.version,
            "status": result.status,
            "dataset_manifest": result.dataset_manifest,
            "start_date": result.data_quality.start_date,
            "end_date": result.data_quality.end_date,
            "adjustment_method": result.data_quality.adjustment_method,
            "total_return_pct": metrics.get("total_return_pct", 0.0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
            "trade_count": metrics.get("trade_count", 0),
            "filled_order_count": metrics.get("filled_order_count", 0),
            "rejected_order_count": metrics.get("rejected_order_count", 0),
            "data_quality": asdict(result.data_quality),
        }

    def to_markdown(self, result: BacktestResult) -> str:
        metrics = result.metrics
        quality = result.data_quality
        lines = [
            f"# Backtest Report ({result.version})",
            "",
            f"- Period: {quality.start_date} to {quality.end_date}",
            f"- Final equity: {metrics.get('final_equity', 0.0)}",
            f"- Total return: {metrics.get('total_return_pct', 0.0)}%",
            f"- Max drawdown: {metrics.get('max_drawdown_pct', 0.0)}%",
            f"- Trades: {metrics.get('trade_count', 0)}",
            f"- Rejected orders: {metrics.get('rejected_order_count', 0)}",
        ]
        if quality.warnings:
            lines.extend(["", "## Data Quality", *[f"- {item}" for item in quality.warnings]])
        return "\n".join(lines)
