from __future__ import annotations

from app.agent_providers.reserved_provider import ReservedRemoteProvider


class LangGraphProvider(ReservedRemoteProvider):
    name = "langgraph"
    api_url_setting = "langgraph_api_url"
    api_key_setting = "langgraph_api_key"
