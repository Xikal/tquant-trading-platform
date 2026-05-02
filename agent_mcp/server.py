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
from app.agent_tools.schemas import ToolDefinition  # noqa: E402


def list_tools() -> list[dict[str, Any]]:
    return [tool.model_dump() for tool in list_tool_definitions()]


def call_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    tool = _tool_by_name(tool_name)
    if tool is None:
        return _error("TOOL_NOT_FOUND", f"Unknown tool: {tool_name}", retryable=False)
    try:
        return {"ok": True, "data": _request_safe_api(tool, arguments or {}), "error": None}
    except TimeoutError as exc:
        return _error("TOOL_TIMEOUT", str(exc), retryable=True)
    except httpx.HTTPError as exc:
        return _error("TOOL_EXECUTION_FAILED", str(exc), retryable=True)
    except Exception as exc:
        return _error("TOOL_EXECUTION_FAILED", str(exc), retryable=True)


def main() -> None:
    for line in sys.stdin:
        request = _parse_line(line)
        if request is None:
            continue
        if request.get("method") == "tools/list":
            _write({"ok": True, "tools": list_tools()})
            continue
        tool_name = str(request.get("tool_name") or request.get("name") or "")
        arguments = request.get("arguments") if isinstance(request.get("arguments"), dict) else {}
        _write(call_tool(tool_name, arguments))


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
        _write(_error("INVALID_ARGUMENTS", "Request must be a JSON object.", retryable=False))
        return None
    if not isinstance(value, dict):
        _write(_error("INVALID_ARGUMENTS", "Request must be a JSON object.", retryable=False))
        return None
    return value


def _error(code: str, message: str, *, retryable: bool) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message, "retryable": retryable}}


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
