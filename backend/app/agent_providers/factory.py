from __future__ import annotations

from sqlalchemy.orm import Session

from app.agent_providers.base import AgentProvider
from app.agent_providers.crewai_provider import CrewAIProvider
from app.agent_providers.custom_http_provider import CustomHttpProvider
from app.agent_providers.hermes_provider import HermesProvider
from app.agent_providers.langgraph_provider import LangGraphProvider
from app.agent_providers.mcp_provider import MCPProvider
from app.agent_providers.none_provider import NoneProvider
from app.agent_providers.openai_agents_provider import OpenAIAgentsProvider
from app.agent_providers.openclaw_provider import OpenClawProvider
from app.agent_providers.pydantic_ai_provider import PydanticAIProvider
from app.core.config import get_settings


PROVIDER_TYPES: dict[str, type[AgentProvider]] = {
    "none": NoneProvider,
    "mcp": MCPProvider,
    "custom_http": CustomHttpProvider,
    "langgraph": LangGraphProvider,
    "openai_agents": OpenAIAgentsProvider,
    "hermes": HermesProvider,
    "openclaw": OpenClawProvider,
    "crewai": CrewAIProvider,
    "pydantic_ai": PydanticAIProvider,
}


def create_agent_provider(db: Session | None = None) -> AgentProvider:
    provider_name = str(get_settings().agent_provider or "none").strip().lower()
    provider_type = PROVIDER_TYPES.get(provider_name, NoneProvider)
    return provider_type(db=db)
