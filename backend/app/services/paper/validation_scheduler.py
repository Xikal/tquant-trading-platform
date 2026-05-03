from __future__ import annotations

import json
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import BacktestRun
from app.models.schema_defs.research import StrategyValidationRequest
from app.services.low_buy.strategy_policy import PRODUCTION_PRIORITY_STRATEGIES
from app.services.paper.validation import StrategyValidationPipeline

logger = logging.getLogger(__name__)

MONTHLY_VALIDATION_RUN_NAME = "strategy-validation-monthly"


class MonthlyStrategyValidationJob:
    """Run one production-strategy validation report per calendar month."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def run_if_due(self, today: date | None = None):
        target_day = today or date.today()
        month_key = target_day.strftime("%Y-%m")
        if self._has_monthly_report(month_key):
            return None
        payload = StrategyValidationRequest(
            strategies=sorted(PRODUCTION_PRIORITY_STRATEGIES),
            lookback_days=self.settings.strategy_validation_monthly_lookback_days,
            max_signals_per_day=self.settings.strategy_validation_monthly_max_signals_per_day,
        )
        logger.info("运行月度策略样本外验证: %s", month_key)
        return StrategyValidationPipeline(self.db).validate(
            payload,
            run_name=MONTHLY_VALIDATION_RUN_NAME,
            extra_params={"month_key": month_key, "generated_by": "monthly_scheduler"},
        )

    def _has_monthly_report(self, month_key: str) -> bool:
        rows = self.db.execute(
            select(BacktestRun)
            .where(BacktestRun.name == MONTHLY_VALIDATION_RUN_NAME)
            .order_by(BacktestRun.id.desc())
            .limit(24)
        ).scalars()
        for row in rows:
            if _json_dict(row.params_json).get("month_key") == month_key:
                return True
        return False


def _json_dict(raw_value: str | None) -> dict:
    try:
        value = json.loads(raw_value or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
