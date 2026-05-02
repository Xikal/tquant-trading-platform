from __future__ import annotations

from app.agent_providers.reserved_provider import ReservedRemoteProvider


class CrewAIProvider(ReservedRemoteProvider):
    name = "crewai"
    api_url_setting = "crewai_api_url"
    api_key_setting = "crewai_api_key"
