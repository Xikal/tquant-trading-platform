from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import FactorDefinitionEntity
from app.services.factor_mining.json_utils import json_dict, json_list
from app.services.factor_mining.runtime_values import is_factor_active, read_factor_value
from app.services.low_buy.factor_types import FactorContext
from app.services.low_buy.factor_functions import FactorSpec


def dynamic_factor_specs() -> list[FactorSpec]:
    """Expose approved factors to the existing factor registry.

    Generated factors remain inert until an admin explicitly activates the
    factor. Active production factors read the latest evaluated point-in-time
    values from the factor value store, keeping scoring controlled and auditable.
    """

    try:
        with SessionLocal() as db:
            rows = db.execute(
                select(FactorDefinitionEntity)
                .where(FactorDefinitionEntity.status == "production")
                .order_by(FactorDefinitionEntity.factor_key.asc())
            ).scalars().all()
    except Exception:
        return []
    specs: list[FactorSpec] = []
    for row in rows:
        result = json_dict(row.eval_result_json)
        weight = 0.5 if result.get("passed_production_gate") else 0.0
        specs.append(
            FactorSpec(
                name=f"llm_{row.factor_key}",
                weight=weight,
                data_dependencies=tuple(str(item) for item in json_list(row.data_deps_json)),
                applicable_strategies=(),
                activation_condition="production_factor_library",
                status="active",
                status_text="因子实验室已晋级",
                evaluator=_dynamic_factor_evaluator(row.factor_key),
            )
        )
    return specs


def _dynamic_factor_evaluator(factor_key: str):
    def evaluator(_metrics, context: FactorContext | None) -> float:
        if context is None or not context.current_symbol:
            return 0.0
        if not is_factor_active(factor_key):
            return 0.0
        trade_date = context.current_date or context.confirmed_trade_date
        return read_factor_value(factor_key, context.current_symbol, trade_date)

    return evaluator
