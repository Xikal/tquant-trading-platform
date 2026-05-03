from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
for site_packages in sorted((BACKEND_DIR / ".venv" / "lib").glob("python*/site-packages")):
    if str(site_packages) not in sys.path:
        sys.path.insert(0, str(site_packages))

from app.agent_tools.registry import list_tool_definitions  # noqa: E402
from app.agent_tools.policy import AgentPolicy  # noqa: E402
from app.agent_tools.schemas import ToolDefinition  # noqa: E402


SERVER_INFO = {"name": "weis-quant-agent", "version": "1.0.0"}
PROTOCOL_VERSION = "2025-03-26"


def main() -> None:
    for line in sys.stdin:
        request = _parse_line(line)
        if request is None:
            continue
        if _is_jsonrpc(request):
            response = _handle_jsonrpc(request)
            if response is not None:
                _write(response)
            continue
        _write(_handle_legacy_request(request))


def _handle_jsonrpc(request: dict[str, Any]) -> dict[str, Any] | None:
    method = str(request.get("method") or "")
    request_id = request.get("id")
    try:
        if method == "initialize":
            return _jsonrpc_result(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": SERVER_INFO,
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return _jsonrpc_result(request_id, {})
        if method == "tools/list":
            return _jsonrpc_result(request_id, {"tools": _mcp_tools()})
        if method == "tools/call":
            params = request.get("params") if isinstance(request.get("params"), dict) else {}
            name = str(params.get("name") or "")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            return _jsonrpc_result(request_id, _mcp_call_tool(name, arguments))
        return _jsonrpc_error(request_id, -32601, f"Unknown method: {method}")
    except Exception as exc:
        return _jsonrpc_error(request_id, -32603, _safe_error_message(exc))


def _handle_legacy_request(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("method") == "tools/list":
        return {"ok": True, "tools": [tool.model_dump() for tool in list_tool_definitions()]}
    tool_name = str(request.get("tool_name") or request.get("name") or "")
    arguments = request.get("arguments") if isinstance(request.get("arguments"), dict) else {}
    return _legacy_call_tool(tool_name, arguments)


def _mcp_tools() -> list[dict[str, Any]]:
    policy = AgentPolicy()
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema or {"type": "object", "properties": {}},
        }
        for tool in list_tool_definitions()
        if tool.enabled and policy.check_tool_allowed(tool) is None
    ]


def _mcp_call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    payload = _legacy_call_tool(tool_name, arguments)
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False),
            }
        ],
        "isError": not bool(payload.get("ok")),
    }


def _legacy_call_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    tool = _tool_by_name(tool_name)
    if tool is None:
        return _error("TOOL_NOT_FOUND", f"Unknown tool: {tool_name}", retryable=False)
    policy_error = AgentPolicy().check_tool_allowed(tool)
    if policy_error is not None:
        return _error(policy_error.code, policy_error.message, retryable=policy_error.retryable)
    try:
        return {"ok": True, "data": _request_safe_api(tool, arguments or {}), "error": None}
    except TimeoutError as exc:
        return _error("TOOL_TIMEOUT", str(exc), retryable=True)
    except httpx.HTTPStatusError as exc:
        return _error("TOOL_EXECUTION_FAILED", _http_error_message(exc), retryable=exc.response.status_code >= 500)
    except httpx.HTTPError as exc:
        return _error("TOOL_EXECUTION_FAILED", _safe_error_message(exc), retryable=True)
    except Exception as exc:
        return _error("TOOL_EXECUTION_FAILED", _safe_error_message(exc), retryable=True)


def _request_safe_api(tool: ToolDefinition, arguments: dict[str, Any]) -> Any:
    base = os.getenv("AGENT_API_BASE", "http://127.0.0.1:18090/api").rstrip("/") + "/"
    path = tool.path.lstrip("/")
    if path.startswith("api/") and base.endswith("/api/"):
        path = path[4:]
    url = urljoin(base, path)
    timeout = max(int(os.getenv("AGENT_TIMEOUT_SECONDS", "10") or "10"), 1)
    headers = _headers()
    try:
        with httpx.Client(timeout=timeout) as client:
            if tool.method.upper() == "GET":
                response = client.get(url, params=arguments, headers=headers)
            else:
                response = client.request(tool.method.upper(), url, json=arguments, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException as exc:
        raise TimeoutError(f"Tool {tool.name} timed out after {timeout}s") from exc


def _headers() -> dict[str, str]:
    token = os.getenv("AGENT_API_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _tool_by_name(tool_name: str) -> ToolDefinition | None:
    return next((tool for tool in list_tool_definitions() if tool.name == tool_name), None)


def _parse_line(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        _write(_jsonrpc_error(None, -32700, "Request must be valid JSON."))
        return None
    if not isinstance(value, dict):
        _write(_jsonrpc_error(None, -32600, "Request must be a JSON object."))
        return None
    return value


def _is_jsonrpc(request: dict[str, Any]) -> bool:
    return request.get("jsonrpc") == "2.0" or "id" in request


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _error(code: str, message: str, *, retryable: bool) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message, "retryable": retryable}}


def _http_error_message(exc: httpx.HTTPStatusError) -> str:
    status_code = exc.response.status_code
    try:
        body = exc.response.json()
    except Exception:
        body = exc.response.text[:200]
    return f"HTTP {status_code}: {body}"


def _safe_error_message(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:500] if text else exc.__class__.__name__


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
