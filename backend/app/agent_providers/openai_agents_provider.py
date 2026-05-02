from __future__ import annotations

from app.agent_providers.reserved_provider import ReservedRemoteProvider


class OpenAIAgentsProvider(ReservedRemoteProvider):
    name = "openai_agents"
    api_url_setting = "openai_agents_api_url"
    api_key_setting = "openai_agents_api_key"
