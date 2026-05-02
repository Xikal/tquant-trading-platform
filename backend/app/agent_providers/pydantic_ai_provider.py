from __future__ import annotations

from app.agent_providers.reserved_provider import ReservedRemoteProvider


class PydanticAIProvider(ReservedRemoteProvider):
    name = "pydantic_ai"
    api_url_setting = "pydantic_ai_api_url"
    api_key_setting = "pydantic_ai_api_key"
