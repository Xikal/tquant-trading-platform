from __future__ import annotations

from dataclasses import dataclass
import logging

from fastapi import Request

from app.core.database import SessionLocal
from app.models.entities import User
from app.services.auth_service import AuthError, AuthService
from app.services.operation_audit import record_operation_audit


logger = logging.getLogger(__name__)

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_AUDITED_PREFIXES = (
    "/api/settings",
    "/api/backtests",
    "/api/research",
    "/api/analyze",
    "/api/watchlist",
    "/api/paper",
    "/api/agent",
    "/api/ml",
    "/api/strategies",
    "/api/quant",
    "/api/market/paired-hedge",
    "/api/market/sector-etf",
)
_SKIP_SUFFIXES = ("/healthz", "/readyz", "/metrics")


@dataclass(frozen=True)
class AuditCandidate:
    operation: str
    resource_type: str
    user: User | None
    operator_ip: str


class OperationAuditMiddleware:
    """Append a lightweight audit event for high-risk mutating API requests."""

    def __init__(self, auth_service: AuthService | None = None) -> None:
        self.auth_service = auth_service or AuthService()

    def candidate(self, request: Request) -> AuditCandidate | None:
        if request.method.upper() not in _MUTATING_METHODS:
            return None
        path = request.url.path
        if path.endswith(_SKIP_SUFFIXES) or not path.startswith(_AUDITED_PREFIXES):
            return None
        with SessionLocal() as db:
            user = self._current_user(request, db)
            return AuditCandidate(
                operation=f"http_{request.method.lower()}",
                resource_type=_resource_type(path),
                user=user,
                operator_ip=_client_ip(request),
            )

    def record(self, candidate: AuditCandidate | None, *, status_code: int, path: str) -> None:
        if candidate is None:
            return
        try:
            with SessionLocal() as db:
                user = db.merge(candidate.user) if candidate.user is not None else None
                record_operation_audit(
                    db,
                    operation=candidate.operation,
                    user=user,
                    resource_type=candidate.resource_type,
                    resource_id=path[:80],
                    status="ok" if status_code < 400 else "failed",
                    operator_ip=candidate.operator_ip,
                    detail={"status_code": status_code},
                )
                db.commit()
        except Exception as exc:  # pragma: no cover - audit must never break business routes.
            logger.warning("operation audit write failed: %s", exc)

    def _current_user(self, request: Request, db) -> User | None:
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return None
        try:
            return self.auth_service.user_from_access_token(db, header.split(" ", 1)[1].strip())
        except AuthError:
            return None
        except Exception as exc:  # pragma: no cover - best-effort user resolution.
            logger.warning("operation audit user resolution failed: %s", exc)
            return None


def _resource_type(path: str) -> str:
    parts = [item for item in path.split("/") if item]
    if len(parts) >= 2 and parts[0] == "api":
        return parts[1][:80]
    return (parts[0] if parts else "api")[:80]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or request.headers.get("x-real-ip", "").strip() or (request.client.host if request.client else "")
