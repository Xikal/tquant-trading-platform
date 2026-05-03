from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent_tools.audit import audit_raw_tool_call, audit_tool_call
from app.agent_tools.policy import AgentPolicy
from app.agent_tools.rate_limit import agent_tool_rate_limiter
from app.agent_tools.registry import get_tool_definition, list_tool_definitions
from app.agent_tools.schemas import ToolDefinition
from app.models.schema_defs.agent import AgentErrorOut, AgentProviderHealth, AgentToolResult

logger = logging.getLogger(__name__)


class AgentProvider(ABC):
    name = "base"
    external_agent = False

    def __init__(self, db: Session | None = None) -> None:
        self.db = db
        self.policy = AgentPolicy()

    @abstractmethod
    def is_available(self) -> bool:
        ...

    def list_tools(self) -> list[ToolDefinition]:
        return [tool for tool in list_tool_definitions() if tool.enabled]

    @abstractmethod
    def health(self) -> AgentProviderHealth:
        ...

    def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> AgentToolResult:
        trace_id = _trace_id()
        started = time.perf_counter()
        tool = get_tool_definition(tool_name)
        if tool is None:
            result = self._error_result(
                trace_id=trace_id,
                tool_name=tool_name,
                started=started,
                error=AgentErrorOut(
                    code="TOOL_NOT_FOUND",
                    message=f"Unknown tool: {tool_name}",
                    retryable=False,
                ),
            )
            audit_raw_tool_call(
                trace_id=trace_id,
                provider=self.name,
                tool_name=tool_name,
                permission="unknown",
                arguments=arguments,
                ok=False,
                duration_ms=result.duration_ms,
                error_code="TOOL_NOT_FOUND",
                db=self.db,
            )
            return result

        policy_error = self.policy.check_tool_allowed(tool)
        if policy_error is not None:
            return self._finalize_error(trace_id, tool_name, started, tool, arguments, policy_error)

        allowed, retry_after = agent_tool_rate_limiter.allow(self.name, tool)
        if not allowed:
            return self._finalize_error(
                trace_id,
                tool_name,
                started,
                tool,
                arguments,
                AgentErrorOut(
                    code="TOOL_RATE_LIMITED",
                    message=f"Tool {tool_name} is rate limited. Retry after {retry_after}s.",
                    retryable=True,
                ),
            )

        try:
            data = self._invoke_allowed_tool(tool, arguments)
            result = self._success_result(trace_id, started, tool, data)
            self._audit(tool=tool, arguments=arguments, result=result)
            return result
        except Exception as exc:
            error = self._error_from_exception(exc=exc, trace_id=trace_id, tool_name=tool_name)
        return self._finalize_error(trace_id, tool_name, started, tool, arguments, error)

    @abstractmethod
    def _invoke_allowed_tool(self, tool: ToolDefinition, arguments: dict[str, Any]) -> Any:
        ...

    def _success_result(
        self,
        trace_id: str,
        started: float,
        tool: ToolDefinition,
        data: Any,
    ) -> AgentToolResult:
        return AgentToolResult(
            ok=True,
            provider=self.name,
            tool_name=tool.name,
            data=data,
            duration_ms=_duration_ms(started),
            trace_id=trace_id,
        )

    def _finalize_error(
        self,
        trace_id: str,
        tool_name: str,
        started: float,
        tool: ToolDefinition,
        arguments: dict[str, Any],
        error: AgentErrorOut,
    ) -> AgentToolResult:
        result = self._error_result(trace_id=trace_id, tool_name=tool_name, started=started, error=error)
        self._audit(tool=tool, arguments=arguments, result=result)
        return result

    def _audit(
        self,
        *,
        tool: ToolDefinition,
        arguments: dict[str, Any],
        result: AgentToolResult,
    ) -> None:
        audit_tool_call(
            trace_id=result.trace_id,
            provider=self.name,
            tool=tool,
            arguments=arguments,
            ok=result.ok,
            duration_ms=result.duration_ms,
            error_code=result.error.code if result.error else None,
            db=self.db,
        )

    @staticmethod
    def _error_from_exception(*, exc: Exception, trace_id: str, tool_name: str) -> AgentErrorOut:
        if isinstance(exc, TimeoutError):
            return AgentErrorOut(code="TOOL_TIMEOUT", message=str(exc), retryable=True)
        if isinstance(exc, ProviderNotConfigured):
            return AgentErrorOut(code="PROVIDER_NOT_CONFIGURED", message=str(exc), retryable=False)
        if isinstance(exc, ProviderUnavailable):
            return AgentErrorOut(code="PROVIDER_UNAVAILABLE", message=str(exc), retryable=True)
        if isinstance(exc, (InvalidToolArguments, ValidationError)):
            return AgentErrorOut(code="INVALID_ARGUMENTS", message=str(exc), retryable=False)
        logger.exception("agent tool execution failed: tool=%s trace_id=%s", tool_name, trace_id)
        return AgentErrorOut(
            code="TOOL_EXECUTION_FAILED",
            message=f"Tool {tool_name} execution failed.",
            retryable=True,
        )

    def _error_result(
        self,
        *,
        trace_id: str,
        tool_name: str,
        started: float,
        error: AgentErrorOut,
    ) -> AgentToolResult:
        return AgentToolResult(
            ok=False,
            provider=self.name,
            tool_name=tool_name,
            data=None,
            error=error,
            duration_ms=_duration_ms(started),
            trace_id=trace_id,
        )


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderUnavailable(RuntimeError):
    pass


class InvalidToolArguments(ValueError):
    pass


def _trace_id() -> str:
    return f"agent_{uuid.uuid4().hex[:16]}"


def _duration_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
