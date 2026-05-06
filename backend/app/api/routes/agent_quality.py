from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.agent_auth import require_current_user_or_agent_token
from app.core.database import get_db
from app.models.schema_defs.phase4 import AgentQualityScoreRequest, AgentQualityScoreResponse
from app.services.agent_quality import score_agent_result

router = APIRouter(prefix="/agent/quality", dependencies=[Depends(require_current_user_or_agent_token)])


@router.post("/score", response_model=AgentQualityScoreResponse)
def score_agent_quality(
    payload: AgentQualityScoreRequest,
    db: Session = Depends(get_db),
) -> AgentQualityScoreResponse:
    return score_agent_result(payload, db=db, persist=True)
