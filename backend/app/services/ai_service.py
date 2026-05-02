from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse, urlunparse
from typing import Any

import httpx
from fastapi.encoders import jsonable_encoder

from app.models.schemas import AiInsight


class AiService:
    def build_insight(
        self,
        settings: dict[str, Any],
        payload: dict[str, Any],
        include_ai: bool = True,
    ) -> AiInsight:
        system_prompt = (
            "你是A股短线做T分析助手。你只能在量化引擎基础上补充解释，"
            "不能放松风险控制。请只返回 JSON，字段为 summary, confidence, "
            "suggestions, warnings。"
        )
        return self.build_task_insight(
            settings=settings,
            payload=payload,
            system_prompt=system_prompt,
            include_ai=include_ai,
        )

    def build_task_insight(
        self,
        settings: dict[str, Any],
        payload: dict[str, Any],
        system_prompt: str,
        include_ai: bool = True,
        max_tokens: int = 1600,
    ) -> AiInsight:
        api_key = (settings.get("llm_api_key") or "").strip()
        model = (settings.get("llm_model") or "").strip()
        if not include_ai or not api_key or not model:
            return AiInsight(
                enabled=False,
                summary="未配置大模型，当前返回量化引擎结论。",
                confidence=0.0,
                suggestions=["在配置页填写 API Key、接口地址和模型名后可启用 AI 补充分析。"],
                warnings=[],
                raw=None,
            )

        base_url = (settings.get("llm_base_url") or "https://api.openai.com/v1").rstrip("/")
        provider = (settings.get("llm_provider") or "auto").strip()
        request_mode = self._resolve_request_mode(base_url, provider)
        endpoint = self._resolve_endpoint(base_url, request_mode)
        safe_payload = jsonable_encoder(payload, sqlalchemy_safe=True)
        body = self._build_request_body(
            request_mode,
            model,
            safe_payload,
            system_prompt,
            max_tokens=max_tokens,
        )

        try:
            data = self._request_with_retry(
                endpoint=endpoint,
                headers=self._build_headers(request_mode, api_key),
                body=body,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            return AiInsight(
                enabled=False,
                summary="AI 请求失败，已回退到纯量化建议。",
                confidence=0.0,
                suggestions=[],
                warnings=[self._format_request_error(exc)],
                raw=None,
            )

        content = self._extract_response_content(request_mode, data)
        parsed = self._parse_json(content)
        if not parsed and content.strip() in {"", "{}"}:
            return AiInsight(
                enabled=False,
                summary="AI 返回空内容，已回退到纯量化建议。",
                confidence=0.0,
                suggestions=[],
                warnings=["模型接口本次没有返回可解读文本，建议稍后重试或更换响应更快的模型。"],
                raw=None,
            )
        return AiInsight(
            enabled=True,
            summary=self._normalize_summary(parsed.get("summary"), content),
            confidence=self._normalize_confidence(parsed.get("confidence")),
            suggestions=self._normalize_text_list(parsed.get("suggestions"), limit=10),
            warnings=self._normalize_text_list(parsed.get("warnings"), limit=8),
            raw=parsed or {"text": content[:2000]},
        )

    @staticmethod
    def _request_with_retry(
        endpoint: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=35.0) as client:
                    response = client.post(endpoint, headers=headers, json=body)
                    response.raise_for_status()
                    return response.json()
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPStatusError) as exc:
                last_error = exc
                if not AiService._should_retry(exc) or attempt == 2:
                    raise
                time.sleep(0.8 * (attempt + 1))
        if last_error is not None:
            raise last_error
        raise RuntimeError("模型请求失败。")

    @staticmethod
    def _should_retry(exc: Exception) -> bool:
        if isinstance(exc, (httpx.ReadTimeout, httpx.ConnectTimeout)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code >= 500
        return False

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    pass
        return {}

    @staticmethod
    def _normalize_summary(value: Any, fallback_content: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, "", [], {}):
            return AiService._format_text_value(value)
        fallback = fallback_content.strip()
        if fallback and fallback != "{}":
            return fallback[:800]
        return "AI 已生成补充说明。"

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        if isinstance(value, str):
            mapped = {
                "低": 0.35,
                "较低": 0.35,
                "中": 0.55,
                "中等": 0.55,
                "高": 0.75,
                "较高": 0.75,
            }.get(value.strip())
            if mapped is not None:
                return mapped
        try:
            confidence = float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
        if confidence > 1:
            confidence = confidence / 100
        return max(0.0, min(confidence, 1.0))

    @staticmethod
    def _normalize_text_list(value: Any, limit: int) -> list[str]:
        if value in (None, "", [], {}):
            return []
        if isinstance(value, list):
            return [AiService._format_text_value(item) for item in value if item not in (None, "", [], {})][:limit]
        if isinstance(value, dict):
            return [
                f"{key}：{AiService._format_text_value(item)}"
                for key, item in value.items()
                if item not in (None, "", [], {})
            ][:limit]
        text = str(value)
        lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
        if not lines:
            return []
        return lines[:limit]

    @staticmethod
    def _format_text_value(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            parts = [
                f"{key}：{AiService._format_text_value(item)}"
                for key, item in value.items()
                if item not in (None, "", [], {})
            ]
            return "；".join(parts)
        if isinstance(value, list):
            return "；".join(AiService._format_text_value(item) for item in value if item not in (None, "", [], {}))
        return str(value)

    @staticmethod
    def _resolve_request_mode(base_url: str, provider: str = "auto") -> str:
        if provider in {"anthropic", "claude"}:
            return "anthropic"
        if provider in {"openai", "openai_compatible", "compatible"}:
            return "openai"
        normalized = base_url.rstrip("/")
        parsed = urlparse(normalized)
        path = parsed.path.rstrip("/")
        if path.endswith("/anthropic") or "/anthropic/" in f"{path}/":
            return "anthropic"
        return "openai"

    @staticmethod
    def _resolve_endpoint(base_url: str, request_mode: str) -> str:
        normalized = base_url.rstrip("/")
        if request_mode == "anthropic":
            if normalized.endswith("/v1/messages"):
                return normalized
            if normalized.endswith("/anthropic"):
                return f"{normalized}/v1/messages"
            if normalized.endswith("/anthropic/v1"):
                return f"{normalized}/messages"
            return f"{normalized}/v1/messages"

        if normalized.endswith("/chat/completions"):
            return normalized
        if normalized.endswith("/v1"):
            return f"{normalized}/chat/completions"

        parsed = urlparse(normalized)
        host = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        if host in {"api.minimaxi.com", "api.minimax.io"}:
            if path.endswith("/anthropic"):
                path = path[: -len("/anthropic")]
            path = f"{path}/v1".replace("//", "/")
            return urlunparse(parsed._replace(path=f"{path}/chat/completions", params="", query="", fragment=""))

        return f"{normalized}/chat/completions"

    @staticmethod
    def _build_request_body(
        request_mode: str,
        model: str,
        safe_payload: dict[str, Any],
        system_prompt: str,
        *,
        max_tokens: int,
    ) -> dict[str, Any]:
        user_payload = json.dumps(safe_payload, ensure_ascii=False)

        if request_mode == "anthropic":
            return {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": 0.2,
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_payload,
                            }
                        ],
                    }
                ],
            }

        return {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
            **AiService._json_response_format(model),
        }

    @staticmethod
    def _json_response_format(model: str) -> dict[str, Any]:
        normalized = model.lower()
        if "deepseek" in normalized:
            return {}
        return {"response_format": {"type": "json_object"}}

    @staticmethod
    def _build_headers(request_mode: str, api_key: str) -> dict[str, str]:
        if request_mode == "anthropic":
            return {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _extract_response_content(request_mode: str, data: dict[str, Any]) -> str:
        if request_mode == "anthropic":
            blocks = data.get("content") or []
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    return str(block.get("text") or "{}")
            return "{}"

        return (
            (((data.get("choices") or [{}])[0]).get("message") or {}).get("content")
            or "{}"
        )

    @staticmethod
    def _format_request_error(exc: Exception) -> str:
        if isinstance(exc, httpx.ReadTimeout):
            return "模型接口响应超时，AI 已自动回退到纯量化建议。"
        if isinstance(exc, httpx.HTTPStatusError):
            detail = ""
            try:
                payload = exc.response.json()
                detail = (
                    payload.get("error", {}).get("message")
                    or payload.get("message")
                    or json.dumps(payload, ensure_ascii=False)
                )
            except Exception:
                detail = exc.response.text

            detail = (detail or str(exc)).strip()
            if "insufficient balance" in detail.lower():
                return "MiniMax 账户余额或配额不足，AI 已自动回退到纯量化建议。"
            if exc.response.status_code >= 500:
                return "模型接口临时波动，AI 已自动回退到纯量化建议。"
            if exc.response.status_code == 404:
                return "模型接口地址不可用，请检查 Base URL 与模型协议是否匹配。"
            if exc.response.status_code == 401:
                return "API Key 无效或账号区域不匹配，请检查当前 Key 与接口域名是否对应。"
            return f"模型接口返回 {exc.response.status_code}：{detail}"
        return str(exc)
