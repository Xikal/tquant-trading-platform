from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rate_limit import require_auth_login_rate_limit, require_auth_register_rate_limit
from app.core.user_permissions import paper_trade_enabled
from app.models.entities import User
from app.models.schemas import (
    AuthLoginRequest,
    AuthLogoutRequest,
    AuthMeResponse,
    PaperAccessResponse,
    AuthRefreshRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
)
from app.services.auth_service import AuthError, AuthService

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
        )
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
    _clear_refresh_cookie(response)
    return {"message": "已退出登录"}


@router.get("/me", response_model=AuthMeResponse)
def me(current_user: User = Depends(get_current_user)):
    return AuthMeResponse(user=auth_service.to_user_out(current_user))


@router.get("/paper-access", response_model=PaperAccessResponse)
def paper_access(current_user: User = Depends(get_current_user)):
    can_access = paper_trade_enabled(current_user.can_paper_trade)
    return PaperAccessResponse(
        can_paper_trade=can_access,
        reason="" if can_access else "账号未开通模拟盘权限，请联系管理员加入白名单",
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    max_age = settings.auth_refresh_token_days * 24 * 60 * 60
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=get_settings().auth_cookie_secure,
        samesite="lax",
        path="/api/auth",
    )
