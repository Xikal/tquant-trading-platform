from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timezone import utc_now, utc_now_naive
from app.core.user_permissions import paper_trade_enabled
from app.models.entities import User, UserSession
from app.models.schemas import AuthTokenResponse, AuthUserOut
from app.services.auth_security_alerts import notify_login_lockout
from app.services.totp import build_otpauth_uri, generate_totp_secret, verify_totp
from app.services.totp_secret_crypto import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    is_encrypted_totp_secret,
)

PASSWORD_ALGORITHM = "scrypt_sha256"
LEGACY_PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
ACCESS_TOKEN_ALGORITHM = "HS256"
ACCESS_TOKEN_ISSUER = "tquant"
ACCESS_TOKEN_AUDIENCE = "tquant-client"
MIN_AUTH_SECRET_LENGTH = 64
WEAK_AUTH_SECRETS = {"default_secret", "tquant_secret_2024", "test-secret", "test-auth-secret"}
REFRESH_RETRY_GRACE_SECONDS = 10


class AuthError(ValueError):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    username: str
    expires_at: int
    session_id: int = 0
    token_version: int = 0


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
    if _secret_is_weak(configured) and not _allow_weak_secret_for_tests():
        raise AuthError("AUTH_SECRET_KEY 长度不足或属于已知弱密钥，认证服务拒绝启动")
    return hashlib.sha256(configured.encode("utf-8")).digest()


def _secret_is_weak(value: str) -> bool:
    return len(value) < MIN_AUTH_SECRET_LENGTH or value in WEAK_AUTH_SECRETS


def _allow_weak_secret_for_tests() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TQUANT_ALLOW_WEAK_AUTH_SECRET_FOR_TESTS"))


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
    digest = _scrypt_digest(password, actual_salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"{PASSWORD_ALGORITHM}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64encode(actual_salt)}${_b64encode(digest)}"


def _hash_legacy_pbkdf2_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return _b64encode(digest)


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        parts = stored_hash.split("$")
        algorithm = parts[0]
        if algorithm == PASSWORD_ALGORITHM and len(parts) == 6:
            _, n_text, r_text, p_text, salt_text, digest_text = parts
            digest = _scrypt_digest(password, _b64decode(salt_text), n=int(n_text), r=int(r_text), p=int(p_text))
            return hmac.compare_digest(_b64encode(digest), digest_text)
        if algorithm != LEGACY_PASSWORD_ALGORITHM or len(parts) != 4:
            return False
        _, iterations, salt_text, digest_text = parts
        if int(iterations) != PASSWORD_ITERATIONS:
            return False
        candidate = _hash_legacy_pbkdf2_password(password, _b64decode(salt_text))
        return hmac.compare_digest(candidate, digest_text)
    except Exception:
        return False


def _password_needs_rehash(stored_hash: str) -> bool:
    return not stored_hash.startswith(f"{PASSWORD_ALGORITHM}$")


def _scrypt_digest(password: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(password.encode("utf-8"))


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
        mfa_code: str = "",
    ) -> AuthTokenResponse:
        normalized = _normalize_username(username)
        _ensure_username_allowed(normalized)
        user = self._get_user_by_username(db, normalized)
        if user is not None:
            self._ensure_not_locked(user)
        if user is None or not user.is_active or not _verify_password(password, user.password_hash):
            if user is not None and user.is_active:
                self._record_failed_login(db, user)
            raise AuthError("账号或密码错误")
        if _password_needs_rehash(user.password_hash):
            user.password_hash = _hash_password(password)
        if user.mfa_totp_enabled and get_settings().auth_require_mfa_for_login:
            secret = self._totp_secret_for_verification(user)
            if not verify_totp(mfa_code, secret):
                self._record_failed_login(db, user)
                raise AuthError("请输入有效动态验证码")
            self._encrypt_plain_totp_secret_if_needed(user, secret)
        self._clear_failed_login(user)
        response = self._issue_token_pair(db, user=user, device_name=device_name)
        db.commit()
        return response

    def refresh(self, db: Session, refresh_token: str) -> AuthTokenResponse:
        session = self._get_session_by_token(db, refresh_token)
        if session is None:
            raise AuthError("登录已失效，请重新登录")
        if session.revoked_at is not None:
            if self._is_recent_refresh_retry(session):
                raise AuthError("登录凭证已轮换，请使用最新会话")
            self._revoke_all_user_sessions(db, session.user_id)
            db.commit()
            raise AuthError("登录凭证疑似被重放，已吊销该账号所有会话，请重新登录")
        if session.expires_at <= utc_now_naive():
            session.revoked_at = utc_now_naive()
            db.commit()
            raise AuthError("登录已失效，请重新登录")
        user = db.get(User, session.user_id)
        if user is None or not user.is_active:
            raise AuthError("账号不可用")
        device_name = session.device_name or ""
        session.revoked_at = utc_now_naive()
        response = self._issue_token_pair(db, user=user, device_name=device_name)
        db.commit()
        return response

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
        if int(getattr(user, "token_version", 0) or 0) != claims.token_version:
            raise AuthError("登录状态已变更，请重新登录")
        if claims.session_id > 0:
            session = db.get(UserSession, claims.session_id)
            if (
                session is None
                or session.user_id != user.id
                or session.revoked_at is not None
                or session.expires_at <= utc_now_naive()
            ):
                raise AuthError("登录已失效，请重新登录")
        elif not get_settings().auth_allow_legacy_tokens:
            raise AuthError("登录凭证缺少会话标识，请重新登录")
        return user

    def parse_access_token(self, token: str) -> TokenClaims:
        try:
            return self._parse_jwt_access_token(token)
        except AuthError:
            if not get_settings().auth_allow_legacy_tokens or token.count(".") != 1:
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
                audience=ACCESS_TOKEN_AUDIENCE,
            )
            return TokenClaims(
                user_id=int(payload["sub"]),
                username=str(payload["username"]),
                expires_at=int(payload["exp"]),
                session_id=int(payload.get("sid", 0) or 0),
                token_version=int(payload.get("tv", 0) or 0),
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
            mfa_totp_enabled=bool(getattr(user, "mfa_totp_enabled", False)),
            created_at=user.created_at,
        )

    def prepare_totp_setup(self, db: Session, *, user: User) -> tuple[str, str]:
        secret = self._totp_secret_for_verification(user) if user.mfa_totp_secret else generate_totp_secret()
        user.mfa_totp_secret = encrypt_totp_secret(secret)
        db.commit()
        return secret, build_otpauth_uri(issuer=get_settings().app_name, username=user.username, secret=secret)

    def enable_totp(self, db: Session, *, user: User, code: str) -> None:
        if not user.mfa_totp_secret:
            user.mfa_totp_secret = encrypt_totp_secret(generate_totp_secret())
        secret = self._totp_secret_for_verification(user)
        if not verify_totp(code, secret):
            raise AuthError("动态验证码无效")
        user.mfa_totp_secret = encrypt_totp_secret(secret)
        user.mfa_totp_enabled = True
        db.commit()

    def disable_totp(self, db: Session, *, user: User, code: str) -> None:
        if user.mfa_totp_enabled:
            secret = self._totp_secret_for_verification(user)
            if not verify_totp(code, secret):
                raise AuthError("动态验证码无效")
        user.mfa_totp_enabled = False
        user.mfa_totp_secret = ""
        db.commit()

    @staticmethod
    def _totp_secret_for_verification(user: User) -> str:
        try:
            return decrypt_totp_secret(user.mfa_totp_secret)
        except ValueError as exc:
            raise AuthError(str(exc)) from exc

    @staticmethod
    def _encrypt_plain_totp_secret_if_needed(user: User, secret: str) -> None:
        if user.mfa_totp_secret and not is_encrypted_totp_secret(user.mfa_totp_secret):
            user.mfa_totp_secret = encrypt_totp_secret(secret)

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
        db.flush()
        access_token = self._build_access_token(user, access_expires_at, session_id=session.id)
        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.auth_access_token_minutes * 60,
            user=self.to_user_out(user),
        )

    @staticmethod
    def _ensure_not_locked(user: User) -> None:
        locked_until = getattr(user, "locked_until", None)
        if locked_until is not None and locked_until > utc_now_naive():
            raise AuthError("账号登录失败次数过多，已临时锁定，请稍后再试")

    @staticmethod
    def _record_failed_login(db: Session, user: User) -> None:
        settings = get_settings()
        threshold = max(int(settings.auth_login_lockout_threshold or 5), 1)
        lock_minutes = max(int(settings.auth_login_lockout_minutes or 15), 1)
        user.failed_login_count = int(getattr(user, "failed_login_count", 0) or 0) + 1
        user.last_failed_login_at = utc_now_naive()
        if user.failed_login_count >= threshold:
            user.locked_until = utc_now_naive() + timedelta(minutes=lock_minutes)
            notify_login_lockout(username=user.username, locked_until=user.locked_until)
        db.commit()

    @staticmethod
    def _clear_failed_login(user: User) -> None:
        user.failed_login_count = 0
        user.locked_until = None
        user.last_failed_login_at = None

    @staticmethod
    def _build_access_token(user: User, expires_at: datetime, *, session_id: int) -> str:
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "sid": int(session_id),
            "tv": int(getattr(user, "token_version", 0) or 0),
            "jti": secrets.token_urlsafe(16),
            "exp": int(expires_at.timestamp()),
            "iat": int(utc_now().timestamp()),
            "iss": ACCESS_TOKEN_ISSUER,
            "aud": ACCESS_TOKEN_AUDIENCE,
        }
        return jwt.encode(payload, _auth_secret(), algorithm=ACCESS_TOKEN_ALGORITHM)

    @staticmethod
    def _get_user_by_username(db: Session, username: str) -> User | None:
        return db.execute(select(User).where(User.username == username)).scalar_one_or_none()

    @staticmethod
    def _get_active_session(db: Session, refresh_token: str) -> UserSession | None:
        session = AuthService._get_session_by_token(db, refresh_token)
        if session is None:
            return None
        if session.revoked_at is not None or session.expires_at <= utc_now_naive():
            return None
        return session

    @staticmethod
    def _get_session_by_token(db: Session, refresh_token: str) -> UserSession | None:
        return db.execute(
            select(UserSession).where(
                UserSession.refresh_token_hash == _hash_token(refresh_token),
            )
        ).scalar_one_or_none()

    @staticmethod
    def _is_recent_refresh_retry(session: UserSession) -> bool:
        if session.revoked_at is None:
            return False
        return session.revoked_at >= utc_now_naive() - timedelta(seconds=REFRESH_RETRY_GRACE_SECONDS)

    @staticmethod
    def _revoke_all_user_sessions(db: Session, user_id: int) -> None:
        db.execute(
            UserSession.__table__.update()
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=utc_now_naive())
        )
