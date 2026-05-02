from __future__ import annotations

from app.agent_providers.reserved_provider import ReservedRemoteProvider


class HermesProvider(ReservedRemoteProvider):
    name = "hermes"
    api_url_setting = "hermes_api_url"
    api_key_setting = "hermes_api_key"
