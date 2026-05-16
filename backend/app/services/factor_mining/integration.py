from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import FactorDefinitionEntity
from app.services.factor_mining.json_utils import json_dict, json_list
from app.services.low_buy.factor_functions import FactorSpec


def dynamic_factor_specs() -> list[FactorSpec]:
    """Expose approved factors to the existing factor registry.

    Generated factors are registered as metadata first. Their scoring evaluator
    intentionally returns 0 until a strategy explicitly consumes the factor
    values from the factor store, preventing unverified code from silently
    changing production recommendations.
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
                evaluator=lambda _metrics, _context: 0.0,
            )
        )
    return specs
