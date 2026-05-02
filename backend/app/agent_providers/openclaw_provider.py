from __future__ import annotations

from app.agent_providers.reserved_provider import ReservedRemoteProvider


class OpenClawProvider(ReservedRemoteProvider):
    name = "openclaw"
    api_url_setting = "openclaw_api_url"
    api_key_setting = "openclaw_api_key"
