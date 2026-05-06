from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timezone import utc_now, utc_now_naive
from app.core.user_permissions import paper_trade_enabled
from app.models.entities import User, UserSession
from app.models.schemas import AuthTokenResponse, AuthUserOut

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000
ACCESS_TOKEN_ALGORITHM = "HS256"
ACCESS_TOKEN_ISSUER = "tquant"


class AuthError(ValueError):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    username: str
    expires_at: int


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _auth_secret() -> bytes:
    settings = get_settings()
    configured = settings.auth_secret_key.strip()
    if not configured:
        raise AuthError("AUTH_SECRET_KEY 未配置，认证服务拒绝签发或校验令牌")
    return hashlib.sha256(configured.encode("utf-8")).digest()


def ensure_auth_secret_configured() -> None:
    _auth_secret()


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _allowed_usernames() -> set[str]:
    return {_normalize_username(item) for item in get_settings().auth_allowed_usernames if item.strip()}


def _ensure_username_allowed(username: str) -> None:
    allowed = _allowed_usernames()
    if allowed and _normalize_username(username) not in allowed:
        raise AuthError("账号未开通，请联系管理员加入模拟盘白名单")


def _hash_password(password: str, salt: bytes | None = None) -> str:
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        actual_salt,
        PASSWORD_ITERATIONS,
    )
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${_b64encode(actual_salt)}${_b64encode(digest)}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = stored_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM or int(iterations) != PASSWORD_ITERATIONS:
            return False
        candidate = _hash_password(password, _b64decode(salt_text)).rsplit("$", 1)[-1]
        return hmac.compare_digest(candidate, digest_text)
    except Exception:
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _sign_payload(payload_text: str) -> str:
    signature = hmac.new(_auth_secret(), payload_text.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(signature)


class AuthService:
    def register(
        self,
        db: Session,
        *,
        username: str,
        password: str,
        display_name: str = "",
        device_name: str = "",
    ) -> AuthTokenResponse:
        normalized = _normalize_username(username)
        _ensure_username_allowed(normalized)
        if self._get_user_by_username(db, normalized) is not None:
            raise AuthError("账号已存在")
        user = User(
            username=normalized,
            display_name=display_name.strip() or normalized,
            password_hash=_hash_password(password),
            can_paper_trade=True,
            roles="",
        )
        db.add(user)
        db.flush()
        response = self._issue_token_pair(db, user=user, device_name=device_name)
        db.commit()
        return response

    def login(
        self,
        db: Session,
        *,
        username: str,
        password: str,
        device_name: str = "",
    ) -> AuthTokenResponse:
        normalized = _normalize_username(username)
        _ensure_username_allowed(normalized)
        user = self._get_user_by_username(db, normalized)
        if user is None or not user.is_active or not _verify_password(password, user.password_hash):
            raise AuthError("账号或密码错误")
        response = self._issue_token_pair(db, user=user, device_name=device_name)
        db.commit()
        return response

    def refresh(self, db: Session, refresh_token: str) -> AuthTokenResponse:
        session = self._get_active_session(db, refresh_token)
        if session is None:
            raise AuthError("登录已失效，请重新登录")
        user = db.get(User, session.user_id)
        if user is None or not user.is_active:
            raise AuthError("账号不可用")
        settings = get_settings()
        access_expires_at = utc_now() + timedelta(minutes=settings.auth_access_token_minutes)
        session.expires_at = utc_now_naive() + timedelta(days=settings.auth_refresh_token_days)
        db.commit()
        return AuthTokenResponse(
            access_token=self._build_access_token(user, access_expires_at),
            refresh_token=refresh_token,
            expires_in=settings.auth_access_token_minutes * 60,
            user=self.to_user_out(user),
        )

    def logout(self, db: Session, refresh_token: str) -> None:
        if not refresh_token:
            return
        session = self._get_active_session(db, refresh_token)
        if session is not None:
            session.revoked_at = utc_now_naive()
            db.commit()

    def user_from_access_token(self, db: Session, token: str) -> User:
        claims = self.parse_access_token(token)
        user = db.get(User, claims.user_id)
        if user is None or not user.is_active or user.username != claims.username:
            raise AuthError("登录已失效，请重新登录")
        return user

    def parse_access_token(self, token: str) -> TokenClaims:
        try:
            return self._parse_jwt_access_token(token)
        except AuthError:
            if token.count(".") != 1:
                raise
            return self._parse_legacy_access_token(token)

    @staticmethod
    def _parse_jwt_access_token(token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                _auth_secret(),
                algorithms=[ACCESS_TOKEN_ALGORITHM],
                issuer=ACCESS_TOKEN_ISSUER,
            )
            return TokenClaims(
                user_id=int(payload["sub"]),
                username=str(payload["username"]),
                expires_at=int(payload["exp"]),
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("登录已过期") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthError("无效登录凭证") from exc
        except Exception as exc:
            raise AuthError("无效登录凭证") from exc

    @staticmethod
    def _parse_legacy_access_token(token: str) -> TokenClaims:
        try:
            payload_text, signature = token.split(".", 1)
            expected = _sign_payload(payload_text)
            if not hmac.compare_digest(signature, expected):
                raise AuthError("无效登录凭证")
            payload = json.loads(_b64decode(payload_text))
            expires_at = int(payload.get("exp", 0))
            if expires_at < int(utc_now().timestamp()):
                raise AuthError("登录已过期")
            return TokenClaims(
                user_id=int(payload["sub"]),
                username=str(payload["username"]),
                expires_at=expires_at,
            )
        except AuthError:
            raise
        except Exception as exc:
            raise AuthError("无效登录凭证") from exc

    def to_user_out(self, user: User) -> AuthUserOut:
        roles = [item.strip() for item in (user.roles or "").split(",") if item.strip()]
        return AuthUserOut(
            id=user.id,
            username=user.username,
            display_name=user.display_name or user.username,
            can_paper_trade=paper_trade_enabled(user.can_paper_trade),
            roles=roles,
            created_at=user.created_at,
        )

    def _issue_token_pair(self, db: Session, *, user: User, device_name: str = "") -> AuthTokenResponse:
        settings = get_settings()
        access_expires_at = utc_now() + timedelta(minutes=settings.auth_access_token_minutes)
        refresh_expires_at = utc_now_naive() + timedelta(days=settings.auth_refresh_token_days)
        refresh_token = secrets.token_urlsafe(40)
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=_hash_token(refresh_token),
            device_name=device_name.strip()[:80],
            expires_at=refresh_expires_at,
        )
        db.add(session)
        access_token = self._build_access_token(user, access_expires_at)
        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.auth_access_token_minutes * 60,
            user=self.to_user_out(user),
        )

    @staticmethod
    def _build_access_token(user: User, expires_at: datetime) -> str:
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "exp": int(expires_at.timestamp()),
            "iat": int(utc_now().timestamp()),
            "iss": ACCESS_TOKEN_ISSUER,
        }
        return jwt.encode(payload, _auth_secret(), algorithm=ACCESS_TOKEN_ALGORITHM)

    @staticmethod
    def _get_user_by_username(db: Session, username: str) -> User | None:
        return db.execute(select(User).where(User.username == username)).scalar_one_or_none()

    @staticmethod
    def _get_active_session(db: Session, refresh_token: str) -> UserSession | None:
        return db.execute(
            select(UserSession).where(
                UserSession.refresh_token_hash == _hash_token(refresh_token),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > utc_now_naive(),
            )
        ).scalar_one_or_none()
