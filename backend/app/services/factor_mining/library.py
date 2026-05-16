from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import FactorApprovalEntity, FactorDefinitionEntity, FactorEvalRunEntity, User
from app.models.schema_defs.factor_mining import (
    FactorCreateRequest,
    FactorDefinitionOut,
    FactorEvalResultOut,
    FactorListResponse,
)
from app.services.factor_mining.compute_engine import FactorComputeEngine
from app.services.factor_mining.json_utils import json_dict, json_dumps, json_list

ALLOWED_STATUS_TRANSITIONS = {
    "candidate": {"validated", "rejected", "archived"},
    "validated": {"production", "rejected", "archived"},
    "production": {"archived"},
    "rejected": {"candidate", "archived"},
    "archived": {"candidate"},
}


class FactorLibrary:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, *, status: str = "", limit: int = 50, offset: int = 0) -> FactorListResponse:
        statement = select(FactorDefinitionEntity)
        count_statement = select(func.count(FactorDefinitionEntity.id))
        if status:
            statement = statement.where(FactorDefinitionEntity.status == status)
            count_statement = count_statement.where(FactorDefinitionEntity.status == status)
        rows = self.db.execute(
            statement.order_by(FactorDefinitionEntity.updated_at.desc()).offset(offset).limit(limit)
        ).scalars().all()
        total = int(self.db.execute(count_statement).scalar() or 0)
        return FactorListResponse(items=[factor_out(row) for row in rows], total=total)

    def get(self, factor_key: str) -> FactorDefinitionEntity:
        row = self.db.execute(
            select(FactorDefinitionEntity).where(FactorDefinitionEntity.factor_key == factor_key)
        ).scalar_one_or_none()
        if row is None:
            raise LookupError(f"因子不存在: {factor_key}")
        return row

    def create(self, payload: FactorCreateRequest, *, user: User | None = None) -> FactorDefinitionOut:
        FactorComputeEngine().validate(payload.formula_code)
        existing = self.db.execute(
            select(FactorDefinitionEntity).where(FactorDefinitionEntity.factor_key == payload.factor_key)
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError(f"因子 key 已存在: {payload.factor_key}")
        row = FactorDefinitionEntity(
            factor_key=payload.factor_key,
            name=payload.name,
            hypothesis=payload.hypothesis,
            formula_code=payload.formula_code,
            data_deps_json=json_dumps(payload.data_deps),
            direction=payload.direction,
            category=payload.category,
            source=payload.source,
            created_by=getattr(user, "username", None) or "system",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return factor_out(row)

    def promote(
        self,
        factor_key: str,
        *,
        target_status: str,
        reason: str,
        user: User | None = None,
    ) -> FactorDefinitionOut:
        row = self.get(factor_key)
        if target_status not in ALLOWED_STATUS_TRANSITIONS.get(row.status, set()):
            raise ValueError(f"不允许从 {row.status} 切换到 {target_status}")
        if target_status == "production":
            result = _eval_result(row)
            if not result or not result.passed_production_gate:
                raise ValueError("因子未通过生产门槛，不能晋级 production")
        previous = row.status
        row.status = target_status
        self.db.add(
            FactorApprovalEntity(
                factor_key=factor_key,
                action="status_change",
                from_status=previous,
                to_status=target_status,
                operator_user_id=getattr(user, "id", None),
                detail_json=json_dumps({"reason": reason}),
            )
        )
        self.db.commit()
        self.db.refresh(row)
        return factor_out(row)

    def save_evaluation(
        self,
        row: FactorDefinitionEntity,
        *,
        result: FactorEvalResultOut,
        interpretation: dict[str, Any],
        request: Any,
        elapsed_seconds: float,
    ) -> FactorEvalRunEntity:
        row.eval_result_json = result.model_dump_json()
        if row.status == "candidate" and result.passed_candidate_gate:
            row.status = "validated"
        run = FactorEvalRunEntity(
            factor_key=row.factor_key,
            status="succeeded",
            start_date=getattr(request, "start_date", "") or "",
            end_date=getattr(request, "end_date", "") or "",
            symbol_count=result.symbol_count,
            observation_count=result.observation_count,
            metrics_json=result.model_dump_json(),
            interpretation_json=json_dumps(interpretation),
            elapsed_seconds=elapsed_seconds,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        self.db.refresh(row)
        return run


def factor_out(row: FactorDefinitionEntity) -> FactorDefinitionOut:
    return FactorDefinitionOut(
        id=row.id,
        factor_key=row.factor_key,
        name=row.name,
        hypothesis=row.hypothesis,
        formula_code=row.formula_code,
        data_deps=[str(item) for item in json_list(row.data_deps_json)],
        direction=row.direction,  # type: ignore[arg-type]
        category=row.category,
        status=row.status,  # type: ignore[arg-type]
        source=row.source,  # type: ignore[arg-type]
        version=row.version,
        eval_result=_eval_result(row),
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _eval_result(row: FactorDefinitionEntity) -> FactorEvalResultOut | None:
    payload = json_dict(row.eval_result_json)
    if not payload:
        return None
    try:
        return FactorEvalResultOut.model_validate(payload)
    except Exception:
        return None
