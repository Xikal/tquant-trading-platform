from __future__ import annotations

from typing import Any

from app.services.decision_context.portfolio_executor import run_portfolio_execution_preview


def run_max5_max10_preview(outcomes: list[Any], **kwargs: Any) -> dict[str, Any]:
    """Single thin adapter for real portfolio max5/max10 semantics."""

    result = run_portfolio_execution_preview(outcomes, **kwargs)
    result["execution_model_version"] = "execution-model-boundary-v1"
    result.setdefault(
        "notes",
        [
            "max5/max10 preview delegates to portfolio_backtest_metrics through decision_context.portfolio_executor.",
        ],
    )
    return result
