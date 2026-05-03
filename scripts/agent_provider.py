#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
RUNTIME_ENV_PATH = Path(os.getenv("RUNTIME_ENV_PATH", BACKEND_DIR / "data" / "runtime.env"))
VALID_PROVIDERS = {
    "none",
    "mcp",
    "custom_http",
    "langgraph",
    "openai_agents",
    "hermes",
    "openclaw",
    "crewai",
    "pydantic_ai",
}

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
for site_packages in sorted((BACKEND_DIR / ".venv" / "lib").glob("python*/site-packages")):
    if str(site_packages) not in sys.path:
        sys.path.insert(0, str(site_packages))

from app.agent_tools.registry import list_tool_definitions  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Provider 管理工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    switch_parser = subparsers.add_parser("switch")
    switch_parser.add_argument("provider", choices=sorted(VALID_PROVIDERS))
    subparsers.add_parser("validate")
    subparsers.add_parser("list-tools")
    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "switch":
        switch_provider(args.provider)
    elif args.command == "validate":
        validate_provider()
    elif args.command == "list-tools":
        list_tools()


def show_status() -> None:
    values = _read_runtime_env()
    print(f"配置文件: {RUNTIME_ENV_PATH}")
    print(f"当前 Provider: {_setting(values, 'AGENT_PROVIDER', 'none')}")
    print(f"Agent API Base: {_setting(values, 'AGENT_API_BASE', 'http://127.0.0.1:18090/api')}")
    print(f"写工具: {_setting(values, 'AGENT_ENABLE_WRITE_TOOLS', 'false')}")
    print(f"通知工具: {_setting(values, 'AGENT_ENABLE_NOTIFY_TOOLS', 'false')}")
    print(f"审计日志: {_setting(values, 'AGENT_AUDIT_ENABLED', 'true')}")
    print(f"工具数量: {len(list_tool_definitions())}")


def switch_provider(provider: str) -> None:
    if provider not in VALID_PROVIDERS:
        raise SystemExit(f"不支持的 Provider: {provider}")
    values = _read_runtime_env()
    values["AGENT_PROVIDER"] = provider
    _write_runtime_env(values)
    print(f"已切换 AGENT_PROVIDER={provider}")
    print("提示：如果后端已在运行，需要重启后端进程或容器后配置才会生效。")


def validate_provider() -> None:
    values = _read_runtime_env()
    base = _setting(values, "AGENT_API_BASE", "http://127.0.0.1:18090/api").rstrip("/")
    print("正在验证 Agent Safe API...")
    for path in ("/agent/health", "/agent/provider/status"):
        url = base + path
        try:
            payload = _http_json(url)
            print(f"OK {url}")
            print(json.dumps(payload, ensure_ascii=False, indent=2)[:1000])
        except Exception as exc:
            print(f"失败 {url}: {exc}")


def list_tools() -> None:
    for tool in list_tool_definitions():
        print(f"{tool.name}\t{tool.permission}\t{tool.enabled}\t{tool.method} {tool.path}")


def _read_runtime_env() -> dict[str, str]:
    if not RUNTIME_ENV_PATH.exists():
        return {}
    values: dict[str, str] = {}
    for line in RUNTIME_ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_runtime_env(values: dict[str, str]) -> None:
    RUNTIME_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in sorted(values.items())]
    RUNTIME_ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _setting(values: dict[str, str], key: str, default: str) -> str:
    return os.getenv(key) or values.get(key) or default


def _http_json(url: str, params: dict[str, str] | None = None) -> dict:
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params)}"
    token = _setting(_read_runtime_env(), "AGENT_API_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = Request(full_url, headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(str(exc)) from exc


if __name__ == "__main__":
    main()
