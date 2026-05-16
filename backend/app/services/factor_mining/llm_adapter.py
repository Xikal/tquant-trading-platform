from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.services.ai_service import AiService
from app.services.settings_service import SettingsService


class FactorMiningLLMAdapter:
    """DeepSeek-first OpenAI-compatible adapter with local fallback."""

    default_model = "deepseek-v4-flash"
    default_base_url = "https://api.deepseek.com/v1"

    def __init__(self, db: Session) -> None:
        payload = SettingsService(db).get_payload().model_dump()
        self.api_key = str(payload.get("llm_api_key") or "").strip()
        self.model = self.default_model
        self.base_url = self._resolve_base_url(payload)
        self.provider = "deepseek"

    def available(self) -> bool:
        return bool(self.api_key)

    def json_task(self, *, system_prompt: str, payload: dict[str, Any], max_tokens: int = 3000) -> dict[str, Any]:
        if not self.available():
            return {}
        endpoint = AiService._resolve_endpoint(self.base_url, "openai")
        body = AiService._build_request_body("openai", self.model, payload, system_prompt, max_tokens=max_tokens)
        try:
            data = AiService._request_with_retry(
                endpoint=endpoint,
                headers=AiService._build_headers("openai", self.api_key),
                body=body,
            )
        except Exception:
            return {}
        content = AiService._extract_response_content("openai", data)
        return _parse_json(content)

    def _resolve_base_url(self, payload: dict[str, Any]) -> str:
        configured = str(payload.get("llm_base_url") or "").strip().rstrip("/")
        provider = str(payload.get("llm_provider") or "").strip().lower()
        model = str(payload.get("llm_model") or "").strip().lower()
        if "deepseek" in provider or "deepseek" in model or "deepseek" in configured.lower():
            return configured or self.default_base_url
        return self.default_base_url


def _parse_json(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(content[start : end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}
