from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from ipaddress import ip_address
from threading import Lock
from typing import Any
from urllib.parse import urlparse

import requests

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_FORWARDED_HEADERS = {"authorization", "x-admin-token"}
_CIRCUIT_OPEN_UNTIL: dict[str, float] = {}
_CIRCUIT_LOCK = Lock()


class RemoteBffError(RuntimeError):
    """Raised when an upstream BFF/service adapter cannot return usable JSON."""


def forwarded_request_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    return {
        key: value
        for key, value in headers.items()
        if key.lower() in _FORWARDED_HEADERS and value
    }


def remote_bff_get(
    base_url: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    forward_headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    cleaned_base = base_url.strip().rstrip("/")
    if not cleaned_base:
        raise RemoteBffError("remote base_url is empty")
    if _is_circuit_open(cleaned_base):
        raise RemoteBffError("remote circuit is open")

    settings = get_settings()
    timeout = max(float(settings.tquant_service_call_timeout_seconds or 5.0), 1.0)
    trusted = _trusted_credential_target(cleaned_base)
    headers = forwarded_request_headers(forward_headers) if trusted else {}
    headers["X-TQuant-Bff-Hop"] = "1"
    if settings.tquant_internal_service_token and trusted:
        headers["X-Internal-Service-Token"] = settings.tquant_internal_service_token
    if not trusted and forward_headers:
        logger.warning("remote bff credentials suppressed for untrusted target base=%s", cleaned_base)

    try:
        response = requests.get(
            f"{cleaned_base}{path}",
            params=params,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        open_remote_bff_circuit(cleaned_base)
        logger.warning("remote bff request failed base=%s path=%s", cleaned_base, path)
        raise RemoteBffError(str(exc)) from exc
    except ValueError as exc:
        open_remote_bff_circuit(cleaned_base)
        raise RemoteBffError("remote response is not valid JSON") from exc

    if not isinstance(payload, dict):
        open_remote_bff_circuit(cleaned_base)
        raise RemoteBffError("remote response must be a JSON object")
    with _CIRCUIT_LOCK:
        _CIRCUIT_OPEN_UNTIL.pop(cleaned_base, None)
    return payload


def open_remote_bff_circuit(base_url: str) -> None:
    cleaned_base = base_url.strip().rstrip("/")
    if not cleaned_base:
        return
    ttl = max(float(get_settings().tquant_service_circuit_breaker_seconds or 30.0), 1.0)
    with _CIRCUIT_LOCK:
        _CIRCUIT_OPEN_UNTIL[cleaned_base] = time.monotonic() + ttl


def _is_circuit_open(cleaned_base: str) -> bool:
    with _CIRCUIT_LOCK:
        open_until = _CIRCUIT_OPEN_UNTIL.get(cleaned_base)
    if open_until is None:
        return False
    if open_until > time.monotonic():
        return True
    with _CIRCUIT_LOCK:
        _CIRCUIT_OPEN_UNTIL.pop(cleaned_base, None)
    return False


def _trusted_credential_target(base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    if parsed.scheme == "https":
        return True
    if parsed.scheme != "http":
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    if "." not in host:
        return True
    try:
        addr = ip_address(host)
    except ValueError:
        return host.endswith((".internal", ".local"))
    return addr.is_private or addr.is_loopback
