from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ORCHESTRATION_PATH = PROJECT_ROOT / "docs" / "hermes_orchestration.yaml"
WORKFLOW_NAME = "tquant_daily_research"


@dataclass(frozen=True)
class HermesWorkflowRunResult:
    ok: bool
    status: str
    message: str
    markdown: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class HermesWorkflowRunner:
    """Execute the configured Hermes daily research workflow.

    This runner only talks to the configured Hermes workflow endpoint/CLI.
    Trading rules and data remain inside Agent Safe API tools.
    """

    def __init__(self, *, orchestration_path: Path | None = None) -> None:
        self.settings = get_settings()
        self.orchestration_path = orchestration_path or DEFAULT_ORCHESTRATION_PATH

    def is_configured(self) -> bool:
        return bool(str(self.settings.hermes_api_url or "").strip())

    def run_daily_research(self, *, symbols: list[str] | None = None) -> HermesWorkflowRunResult:
        if not self.is_configured():
            return HermesWorkflowRunResult(
                ok=False,
                status="not_configured",
                message="Hermes 未配置 HERMES_API_URL，无法启动研究工作流。",
            )
        orchestration = _load_orchestration(self.orchestration_path)
        target_symbols = _normalize_symbols(symbols)
        base_url = str(self.settings.hermes_api_url or "").strip().rstrip("/")
        if base_url.startswith("hermes-cli://"):
            return self._run_cli(base_url=base_url, symbols=target_symbols, orchestration=orchestration)
        return self._run_http(base_url=base_url, symbols=target_symbols, orchestration=orchestration)

    def _run_cli(
        self,
        *,
        base_url: str,
        symbols: list[str],
        orchestration: dict[str, Any],
    ) -> HermesWorkflowRunResult:
        executable = base_url.replace("hermes-cli://", "", 1).strip() or "/Users/j/.local/bin/hermes"
        hermes_path = Path(executable).expanduser()
        if not hermes_path.exists():
            return HermesWorkflowRunResult(
                ok=False,
                status="failed",
                message=f"Hermes CLI 不存在：{hermes_path}",
                data={"executable": str(hermes_path)},
            )

        prompt = _workflow_prompt(symbols=symbols, orchestration=orchestration)
        timeout = max(240, int(self.settings.agent_timeout_seconds or 10) * 30)
        env = os.environ.copy()
        env.setdefault("HERMES_ACCEPT_HOOKS", "1")
        try:
            result = subprocess.run(
                [str(hermes_path), "-z", prompt],
                cwd=str(PROJECT_ROOT),
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return HermesWorkflowRunResult(
                ok=False,
                status="timeout",
                message="Hermes workflow 执行超时。",
                data={
                    "symbols": symbols,
                    "timeout_seconds": timeout,
                    "stdout": (exc.stdout or "")[-2000:],
                    "stderr": (exc.stderr or "")[-2000:],
                },
            )
        except OSError as exc:
            return HermesWorkflowRunResult(
                ok=False,
                status="failed",
                message=f"Hermes workflow 启动失败：{exc}",
                data={"symbols": symbols},
            )

        data = {
            "symbols": symbols,
            "returncode": result.returncode,
            "stdout": result.stdout[-6000:],
            "stderr": result.stderr[-2000:],
        }
        if result.returncode != 0:
            return HermesWorkflowRunResult(
                ok=False,
                status="failed",
                message=f"Hermes workflow 退出码 {result.returncode}",
                data=data,
            )
        parsed = _parse_json_object(result.stdout)
        validation = _validate_workflow_result(orchestration, parsed)
        data["parsed"] = parsed
        data["validation"] = validation
        if not validation["ok"]:
            return HermesWorkflowRunResult(
                ok=False,
                status="failed",
                message="Hermes workflow 未通过逐 phase 硬验收。",
                data=data,
            )
        return HermesWorkflowRunResult(
            ok=True,
            status="succeeded",
            message="Hermes workflow 已完成。",
            markdown=str(parsed.get("final_markdown") or ""),
            data=data,
        )

    def _run_http(
        self,
        *,
        base_url: str,
        symbols: list[str],
        orchestration: dict[str, Any],
    ) -> HermesWorkflowRunResult:
        endpoint = f"{base_url}/workflows/{WORKFLOW_NAME}/run"
        payload = {
            "workflow_name": _workflow_name(orchestration),
            "symbols": symbols,
            "orchestration": orchestration.get("research_workflow") or {},
        }
        headers = {"Content-Type": "application/json"}
        api_key = str(self.settings.hermes_api_key or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        timeout = max(int(self.settings.agent_timeout_seconds or 10) * 30, 120)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status_code = response.getcode()
                body_text = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return HermesWorkflowRunResult(
                ok=False,
                status="failed",
                message=f"Hermes workflow HTTP {exc.code}",
                data={"endpoint": endpoint, "response": exc.read().decode("utf-8", errors="replace")[:2000]},
            )
        except urllib.error.URLError as exc:
            return HermesWorkflowRunResult(
                ok=False,
                status="failed",
                message=f"Hermes workflow 请求失败：{exc.reason}",
                data={"endpoint": endpoint},
            )
        if not (200 <= status_code < 300):
            return HermesWorkflowRunResult(
                ok=False,
                status="failed",
                message=f"Hermes workflow HTTP {status_code}",
                data={"endpoint": endpoint, "response": body_text[:2000]},
            )
        parsed = _parse_json_object(body_text)
        validation = _validate_workflow_result(orchestration, parsed)
        if not validation["ok"]:
            return HermesWorkflowRunResult(
                ok=False,
                status="failed",
                message="Hermes workflow 未通过逐 phase 硬验收。",
                data={"endpoint": endpoint, "response": parsed, "validation": validation},
            )
        return HermesWorkflowRunResult(
            ok=True,
            status="succeeded",
            message="Hermes workflow 已完成。",
            markdown=str(parsed.get("final_markdown") or ""),
            data={"endpoint": endpoint, "response": parsed, "validation": validation},
        )


def _normalize_symbols(symbols: list[str] | None) -> list[str]:
    output: list[str] = []
    for symbol in symbols or []:
        cleaned = "".join(ch for ch in str(symbol).strip() if ch.isalnum())
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output[:10]


def _load_orchestration(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(loaded, dict) or not isinstance(loaded.get("research_workflow"), dict):
        raise ValueError(f"Hermes orchestration config invalid: {path}")
    return loaded


def _workflow_prompt(*, symbols: list[str], orchestration: dict[str, Any]) -> str:
    contract = _orchestration_contract(orchestration)
    return (
        "你是 TQuant Hermes Workflow Skill 执行器。必须严格执行 workflow tquant_daily_research。"
        "只能调用 weis-quant Agent Safe API/MCP 工具；禁止修改策略参数，禁止执行实盘下单。"
        "请逐 phase 执行所有角色，并生成最终 Markdown 研究报告。"
        "只输出一个 JSON 对象，不要输出 Markdown 代码块。JSON schema："
        "{"
        "\"ok\": true|false,"
        "\"workflow_name\": string,"
        "\"phase_results\": ["
        "{\"phase\": string, \"agents\": ["
        "{\"name\": string, \"executed\": true|false, \"tool_calls\": ["
        "{\"tool_name\": string, \"ok\": true|false, \"error_code\": string|null, \"permission_denied\": true|false}"
        "], \"output_summary\": string}"
        "]}"
        "],"
        "\"final_markdown\": string,"
        "\"errors\": [string]"
        "}。"
        f"标的参考：{', '.join(symbols) if symbols else '全策略榜 TOP 10'}。"
        f"orchestration_contract={json.dumps(contract, ensure_ascii=False)}"
    )


def _orchestration_contract(orchestration: dict[str, Any]) -> dict[str, Any]:
    workflow = orchestration.get("research_workflow") or {}
    return {
        "workflow_name": _workflow_name(orchestration),
        "phases": workflow.get("phases") or [],
        "required_sections": (workflow.get("output") or {}).get("required_sections") or [],
    }


def _workflow_name(orchestration: dict[str, Any]) -> str:
    workflow = orchestration.get("research_workflow") or {}
    return str(workflow.get("name") or WORKFLOW_NAME)


def _validate_workflow_result(orchestration: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not result.get("ok"):
        errors.append("workflow 返回 ok=false")
    if result.get("workflow_name") not in {_workflow_name(orchestration), None, ""}:
        errors.append("workflow_name 不匹配")
    phases = result.get("phase_results")
    if not isinstance(phases, list):
        errors.append("缺少 phase_results")
        phases = []
    phase_agents = {
        str(agent.get("name"))
        for phase in phases
        if isinstance(phase, dict)
        for agent in (phase.get("agents") or [])
        if isinstance(agent, dict) and agent.get("executed")
    }
    expected_agents = _expected_agent_names(orchestration)
    expected_tools = _expected_agent_tools(orchestration)
    missing_agents = sorted(expected_agents - phase_agents)
    if missing_agents:
        errors.append(f"未执行角色：{', '.join(missing_agents)}")
    for agent_name, tool_names in expected_tools.items():
        agent_payload = _find_agent_payload(phases, agent_name)
        if not agent_payload:
            continue
        calls = agent_payload.get("tool_calls") or []
        for tool_name in tool_names:
            if not _tool_was_called(calls, tool_name):
                errors.append(f"{agent_name} 未调用工具：{tool_name}")
    markdown = str(result.get("final_markdown") or "")
    if not markdown.strip():
        errors.append("缺少 final_markdown")
    for section in _required_sections(orchestration):
        if section not in markdown:
            errors.append(f"报告缺少章节：{section}")
    return {
        "ok": not errors,
        "errors": errors,
        "expected_agents": sorted(expected_agents),
        "expected_tools": expected_tools,
    }


def _expected_agent_names(orchestration: dict[str, Any]) -> set[str]:
    output: set[str] = set()
    workflow = orchestration.get("research_workflow") or {}
    for phase in workflow.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        agents = phase.get("agents")
        if isinstance(agents, list):
            output.update(str(agent.get("name")) for agent in agents if isinstance(agent, dict) and agent.get("name"))
        agent = phase.get("agent")
        if isinstance(agent, dict) and agent.get("name"):
            output.add(str(agent.get("name")))
    return output


def _expected_agent_tools(orchestration: dict[str, Any]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    workflow = orchestration.get("research_workflow") or {}
    for phase in workflow.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        for agent in _phase_agents(phase):
            name = str(agent.get("name") or "")
            tools = [
                str(tool.get("tool_name") or "")
                for tool in (agent.get("tools") or [])
                if isinstance(tool, dict) and str(tool.get("tool_name") or "").strip()
            ]
            if name:
                output[name] = tools
    return output


def _phase_agents(phase: dict[str, Any]) -> list[dict[str, Any]]:
    agents = phase.get("agents")
    if isinstance(agents, list):
        return [agent for agent in agents if isinstance(agent, dict)]
    agent = phase.get("agent")
    return [agent] if isinstance(agent, dict) else []


def _find_agent_payload(phases: list[Any], agent_name: str) -> dict[str, Any] | None:
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        for agent in phase.get("agents") or []:
            if isinstance(agent, dict) and agent.get("name") == agent_name:
                return agent
    return None


def _tool_was_called(calls: list[Any], expected_tool: str) -> bool:
    for call in calls:
        if not isinstance(call, dict):
            continue
        actual = str(call.get("tool_name") or "")
        if actual == expected_tool:
            return True
        if expected_tool == "analyze_stock" and (actual.startswith("analyze_stock_") or actual == "analyze_stock x10"):
            return True
    return False


def _required_sections(orchestration: dict[str, Any]) -> list[str]:
    workflow = orchestration.get("research_workflow") or {}
    output = workflow.get("output") if isinstance(workflow.get("output"), dict) else {}
    return [str(item) for item in output.get("required_sections") or [] if str(item).strip()]


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = (text or "").strip()
    if not stripped:
        return {}
    try:
        decoded = json.loads(stripped)
        return decoded if isinstance(decoded, dict) else {}
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                decoded = json.loads(stripped[start : end + 1])
                return decoded if isinstance(decoded, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}
