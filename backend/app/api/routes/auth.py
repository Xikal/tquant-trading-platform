from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rate_limit import require_auth_login_rate_limit, require_auth_register_rate_limit
from app.models.entities import User
from app.models.schemas import (
    AuthLoginRequest,
    AuthLogoutRequest,
    AuthMeResponse,
    AuthMfaSetupResponse,
    AuthMfaUpdateRequest,
    AuthRefreshRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
)
from app.services.auth_service import AuthError, AuthService
from app.services.operation_audit import record_operation_audit

router = APIRouter(prefix="/auth")
auth_service = AuthService()
REFRESH_COOKIE_NAME = "tquant_refresh_token"


def _raise_auth_error(exc: AuthError) -> None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def _public_tokens(tokens: AuthTokenResponse) -> AuthTokenResponse:
    """Refresh tokens live in httpOnly cookies and are never echoed to JS clients."""
    return tokens.model_copy(update={"refresh_token": ""})


@router.post("/register", response_model=AuthTokenResponse)
def register(
    payload: AuthRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    require_auth_register_rate_limit(request)
    try:
        tokens = auth_service.register(
            db,
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            device_name=payload.device_name,
        )
        record_operation_audit(
            db,
            operation="auth_register",
            resource_type="user",
            resource_id=payload.username,
            operator_ip=_client_ip(request),
        )
        db.commit()
        _set_refresh_cookie(response, tokens.refresh_token)
        return _public_tokens(tokens)
    except AuthError as exc:
        _raise_auth_error(exc)


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: AuthLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    require_auth_login_rate_limit(request, payload.username)
    try:
        tokens = auth_service.login(
            db,
            username=payload.username,
            password=payload.password,
            device_name=payload.device_name,
            mfa_code=payload.mfa_code,
        )
        record_operation_audit(
            db,
            operation="auth_login",
            resource_type="user",
            resource_id=payload.username,
            operator_ip=_client_ip(request),
        )
        db.commit()
        _set_refresh_cookie(response, tokens.refresh_token)
        return _public_tokens(tokens)
    except AuthError as exc:
        _raise_auth_error(exc)


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh(
    payload: AuthRefreshRequest,
    response: Response,
    refresh_cookie: str = Cookie(default="", alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    try:
        tokens = auth_service.refresh(db, payload.refresh_token or refresh_cookie)
        _set_refresh_cookie(response, tokens.refresh_token)
        return _public_tokens(tokens)
    except AuthError as exc:
        _raise_auth_error(exc)


@router.post("/logout")
def logout(
    payload: AuthLogoutRequest,
    response: Response,
    refresh_cookie: str = Cookie(default="", alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    auth_service.logout(db, payload.refresh_token or refresh_cookie)
    record_operation_audit(db, operation="auth_logout", resource_type="session")
    db.commit()
    _clear_refresh_cookie(response)
    return {"message": "已退出登录"}


@router.get("/me", response_model=AuthMeResponse)
def me(current_user: User = Depends(get_current_user)):
    return AuthMeResponse(user=auth_service.to_user_out(current_user))


@router.post("/mfa/totp/setup", response_model=AuthMfaSetupResponse)
def setup_totp_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthMfaSetupResponse:
    secret, uri = auth_service.prepare_totp_setup(db, user=current_user)
    record_operation_audit(db, operation="auth_mfa_setup", user=current_user, resource_type="user", resource_id=current_user.id)
    db.commit()
    return AuthMfaSetupResponse(
        secret=secret,
        otpauth_uri=uri,
        issuer=get_settings().app_name,
        account_name=current_user.username,
    )


@router.post("/mfa/totp/enable", response_model=AuthMeResponse)
def enable_totp_mfa(
    payload: AuthMfaUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthMeResponse:
    try:
        auth_service.enable_totp(db, user=current_user, code=payload.code)
        record_operation_audit(db, operation="auth_mfa_enable", user=current_user, resource_type="user", resource_id=current_user.id)
        db.commit()
        db.refresh(current_user)
        return AuthMeResponse(user=auth_service.to_user_out(current_user))
    except AuthError as exc:
        _raise_auth_error(exc)


@router.post("/mfa/totp/disable", response_model=AuthMeResponse)
def disable_totp_mfa(
    payload: AuthMfaUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthMeResponse:
    try:
        auth_service.disable_totp(db, user=current_user, code=payload.code)
        record_operation_audit(db, operation="auth_mfa_disable", user=current_user, resource_type="user", resource_id=current_user.id)
        db.commit()
        db.refresh(current_user)
        return AuthMeResponse(user=auth_service.to_user_out(current_user))
    except AuthError as exc:
        _raise_auth_error(exc)


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    max_age = settings.auth_refresh_token_days * 24 * 60 * 60
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=get_settings().auth_cookie_secure,
        samesite=get_settings().auth_cookie_samesite,
        path="/api/auth",
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else ""
