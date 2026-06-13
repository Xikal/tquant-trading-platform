from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.schema_defs.local_desktop import LocalDesktopStatusResponse
from app.services.local_desktop_status import build_local_desktop_status

router = APIRouter(prefix="/local")


@router.get("/status", response_model=LocalDesktopStatusResponse)
def local_desktop_status_view(db: Session = Depends(get_db)) -> LocalDesktopStatusResponse:
    return build_local_desktop_status(db)
