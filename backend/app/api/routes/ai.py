from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.core.rate_limit import require_ai_decision_rate_limit
from app.models.schemas import AiDecisionSupportRequest, AiDecisionSupportResponse
from app.services.ai_decision_support import AiDecisionSupportService

router = APIRouter(prefix="/ai")
ai_decision_support = AiDecisionSupportService()


@router.post("/decision-support", response_model=AiDecisionSupportResponse)
def build_decision_support(
    payload: AiDecisionSupportRequest,
    _auth: None = Depends(require_admin_auth),
    _rate_limit: None = Depends(require_ai_decision_rate_limit),
    db: Session = Depends(get_db),
):
    return ai_decision_support.explain(db=db, request=payload)
