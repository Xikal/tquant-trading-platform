#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.agent_tools.registry import get_tool_definition  # noqa: E402
from app.models.entities import DailyBarSnapshot, LowBuyResultSnapshot  # noqa: E402
from app.services.agent_daily_workflow_service import AgentDailyWorkflowService  # noqa: E402
from app.services.market.openbb_adapter import OpenBBDataAdapter  # noqa: E402
from research.backtest.benchmark import write_benchmark_report  # noqa: E402
from research.backtest.strategy_validation import write_strategy_validation_report  # noqa: E402
from research.data_sync.tquant_to_qlib import qlib_status  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "research" / "reports" / "agent_os_acceptance.json"
DEFAULT_DATASET = PROJECT_ROOT / "research" / "reports" / "datasets" / "agent_strategy_samples.csv"
DEFAULT_STRATEGY_REPORT = PROJECT_ROOT / "research" / "reports" / "agent_strategy_validation.json"
DEFAULT_BENCHMARK_REPORT = PROJECT_ROOT / "research" / "reports" / "agent_benchmark.json"
DEFAULT_ORCHESTRATION = PROJECT_ROOT / "docs" / "hermes_orchestration.yaml"

EXPECTED_ORCHESTRATION_AGENTS = {
    "market_state_analyst",
    "sector_heat_analyst",
    "technical_analyst",
    "strategy_validator",
    "portfolio_manager",
}
WRITE_SAFE_ERROR_CODES = {"TOOL_PERMISSION_DENIED", "PROVIDER_NOT_CONFIGURED"}


@dataclass(frozen=True)
class StepResult:
    name: str
    status: str
    ok: bool
    message: str
    data: dict[str, Any]
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "ok": self.ok,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "data": self.data,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TQuant Agent OS real acceptance checks.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="验收总报告输出路径")
    parser.add_argument("--dataset-output", default=str(DEFAULT_DATASET), help="qlib 样本 CSV 输出路径")
    parser.add_argument("--orchestration", default=str(DEFAULT_ORCHESTRATION), help="Hermes 编排配置 YAML")
    parser.add_argument("--lookback-days", type=int, default=504, help="qlib 实盘样本回看交易日数量")
    parser.add_argument("--symbols", default="", help="Hermes workflow 标的，逗号分隔；默认取全策略榜前 10")
    parser.add_argument("--limit", type=int, default=10, help="Hermes workflow 标的数量")
    parser.add_argument("--strategy-key", action="append", dest="strategy_keys", help="限制 qlib 报告策略，可重复")
    parser.add_argument("--skip-hermes", action="store_true")
    parser.add_argument("--skip-feishu", action="store_true")
    parser.add_argument("--skip-qlib", action="store_true")
    parser.add_argument("--skip-openbb", action="store_true")
    args = parser.parse_args()

    report = run_acceptance(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"agent_os_acceptance_report={output_path}")
    print(json.dumps(_summary(report), ensure_ascii=False, indent=2))


def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    orchestration = _load_orchestration(Path(args.orchestration))
    with SessionLocal() as db:
        symbols = _symbols_from_args(args.symbols) or _load_priority_symbols(db, limit=args.limit)
        steps: list[StepResult] = []
        if not args.skip_hermes:
            steps.append(_timed("hermes_orchestration_contract", lambda: validate_orchestration_contract(orchestration)))
            steps.append(_timed("hermes_workflow", lambda: run_hermes_workflow(settings, symbols, orchestration)))
        if not args.skip_feishu:
            steps.append(_timed("feishu_daily_push", lambda: run_feishu_daily_push(db)))
        if not args.skip_qlib:
            steps.append(
                _timed(
                    "qlib_research_report",
                    lambda: run_qlib_report(
                        db,
                        dataset_path=Path(args.dataset_output),
                        lookback_days=args.lookback_days,
                        strategy_keys=args.strategy_keys,
                    ),
                )
            )
        if not args.skip_openbb:
            steps.append(_timed("openbb_degrade_check", run_openbb_check))

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": "TQuant 维斯量化平台",
        "symbols": symbols,
        "steps": [item.to_dict() for item in steps],
        "overall_status": _overall_status(steps),
        "notes": [
            "Hermes/飞书/OpenBB 依赖外部配置；缺配置会返回 not_configured，不影响核心 A 股链路。",
            "qlib 报告使用本地实盘物化信号和 daily_bar_snapshots 计算，不调用外部行情源。",
        ],
    }


def run_hermes_workflow(settings: Any, symbols: list[str], orchestration: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    base_url = str(getattr(settings, "hermes_api_url", "") or "").strip().rstrip("/")
    if not base_url:
        return "not_configured", "HERMES_API_URL 未配置，跳过真实 Hermes workflow。", {}
    if base_url.startswith("hermes-cli://"):
        return _run_hermes_cli_workflow(settings, base_url, symbols, orchestration)
    endpoint = f"{base_url}/workflows/tquant_daily_research/run"
    payload = {
        "workflow_name": _workflow_name(orchestration),
        "symbols": symbols[:10],
        "agent_api_base": getattr(settings, "agent_api_base", ""),
        "orchestration": _orchestration_contract_payload(orchestration),
        "requested_outputs": ["summary", "risk_notes", "next_actions"],
        "source": "scripts/agent_os_acceptance.py",
    }
    headers = {"Content-Type": "application/json"}
    api_key = str(getattr(settings, "hermes_api_key", "") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=max(3, int(getattr(settings, "agent_timeout_seconds", 10) or 10)),
        )
    except requests.Timeout:
        return "timeout", "Hermes workflow 请求超时。", {"endpoint": endpoint, "symbols": symbols[:10]}
    except requests.RequestException as exc:
        return "failed", f"Hermes workflow 请求失败：{exc}", {"endpoint": endpoint, "symbols": symbols[:10]}
    try:
        body: Any = response.json()
    except ValueError:
        body = {"raw_text": response.text[:2000]}
    if not 200 <= response.status_code < 300:
        return "failed", f"Hermes workflow HTTP {response.status_code}", {"endpoint": endpoint, "response": body}
    if isinstance(body, dict) and body.get("ok") is False:
        return "failed", "Hermes workflow 返回业务失败。", {"endpoint": endpoint, "response": body}
    validation = validate_hermes_workflow_result(orchestration, body if isinstance(body, dict) else {})
    if not validation["ok"]:
        return "failed", "Hermes workflow 未通过逐 phase 硬验收。", {
            "endpoint": endpoint,
            "response": body,
            "validation": validation,
            "symbols": symbols[:10],
        }
    return "ok", "Hermes workflow 已完成并通过逐 phase 验收。", {
        "endpoint": endpoint,
        "response": body,
        "validation": validation,
        "symbols": symbols[:10],
    }


def _run_hermes_cli_workflow(
    settings: Any,
    base_url: str,
    symbols: list[str],
    orchestration: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    executable = base_url.replace("hermes-cli://", "", 1).strip() or "/Users/j/.local/bin/hermes"
    hermes_path = Path(executable).expanduser()
    if not hermes_path.exists():
        return "failed", f"Hermes CLI 不存在：{hermes_path}", {"executable": str(hermes_path)}
    target_symbols = symbols[:10]
    prompt = _hermes_workflow_prompt(target_symbols, orchestration)
    timeout = max(240, int(getattr(settings, "agent_timeout_seconds", 10) or 10) * 30)
    env = os.environ.copy()
    env.setdefault("HERMES_ACCEPT_HOOKS", "1")
    try:
        result = subprocess.run(
            [str(hermes_path), "-z", prompt],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return "timeout", "Hermes CLI workflow 执行超时。", {
            "executable": str(hermes_path),
            "symbols": target_symbols,
            "timeout_seconds": timeout,
            "stdout": (exc.stdout or "")[:2000],
            "stderr": (exc.stderr or "")[:2000],
        }
    data = {
        "executable": str(hermes_path),
        "symbols": target_symbols,
        "stdout": result.stdout[-6000:],
        "stderr": result.stderr[-2000:],
        "returncode": result.returncode,
    }
    if result.returncode != 0:
        return "failed", f"Hermes CLI workflow 退出码 {result.returncode}", data
    parsed = _parse_json_object(result.stdout)
    validation = validate_hermes_workflow_result(orchestration, parsed)
    data["parsed"] = parsed
    data["validation"] = validation
    if not validation["ok"]:
        return "failed", "Hermes CLI workflow 未通过逐 phase 硬验收。", data
    return "ok", "Hermes CLI workflow 已完成并通过逐 phase 验收。", data


def _hermes_workflow_prompt(symbols: list[str], orchestration: dict[str, Any]) -> str:
    contract = _orchestration_contract_payload(orchestration)
    return (
        "你是 TQuant Hermes Agent OS 硬验收器。只允许使用 weis-quant MCP/Agent Safe API 工具；"
        "禁止执行 shell，禁止访问数据库，禁止修改策略，禁止实盘下单。"
        "必须严格按照下方 orchestration_contract 逐 phase 执行所有 agent。"
        "每个 agent 必须尝试调用其配置中的每个 tool；read 工具必须成功，write/notify 工具如果返回 TOOL_PERMISSION_DENIED，"
        "记录为已调用且 permission_denied=true，不得绕过权限。"
        "最终必须生成 markdown 报告，并包含 required_sections 的全部章节标题。"
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
        f"验收请求标的参考：{', '.join(symbols[:10])}。"
        f"orchestration_contract={json.dumps(contract, ensure_ascii=False)}"
    )


def _load_orchestration(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Hermes orchestration config not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Hermes orchestration config must be a mapping: {path}")
    workflow = loaded.get("research_workflow")
    if not isinstance(workflow, dict):
        raise ValueError(f"Hermes orchestration config missing research_workflow: {path}")
    return loaded


def validate_orchestration_contract(orchestration: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    errors: list[str] = []
    workflow = _workflow(orchestration)
    agents = _iter_agent_specs(orchestration)
    agent_names = {agent["name"] for agent in agents}
    missing_agents = sorted(EXPECTED_ORCHESTRATION_AGENTS - agent_names)
    if missing_agents:
        errors.append(f"缺少必须角色：{', '.join(missing_agents)}")
    if not workflow.get("phases"):
        errors.append("缺少 phases 配置。")
    if not _required_sections(orchestration):
        errors.append("缺少 output.required_sections 配置。")

    for agent in agents:
        prompt_template = str(agent.get("prompt_template") or "")
        if not _prompt_anchor_exists(prompt_template):
            errors.append(f"{agent['name']} prompt_template 不存在或锚点无效：{prompt_template}")
        for tool_name in agent["tools"]:
            if get_tool_definition(tool_name) is None:
                errors.append(f"{agent['name']} 声明了未注册工具：{tool_name}")

    data = {
        "workflow_name": _workflow_name(orchestration),
        "phase_count": len(workflow.get("phases") or []),
        "agent_count": len(agents),
        "agents": [agent["name"] for agent in agents],
        "required_sections": _required_sections(orchestration),
        "errors": errors,
    }
    if errors:
        return "failed", "Hermes 编排配置未通过合同校验。", data
    return "ok", "Hermes 编排配置合同校验通过。", data


def validate_hermes_workflow_result(orchestration: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    workflow_name = _workflow_name(orchestration)
    if not isinstance(result, dict) or not result:
        return {"ok": False, "errors": ["Hermes 未返回可解析 JSON 对象。"], "warnings": []}
    if result.get("workflow_name") not in {workflow_name, None, ""}:
        errors.append(f"workflow_name 不匹配：{result.get('workflow_name')} != {workflow_name}")
    phase_results = result.get("phase_results")
    if not isinstance(phase_results, list):
        errors.append("缺少 phase_results 数组。")
        phase_results = []

    for expected_phase in _workflow(orchestration).get("phases") or []:
        phase_name = str(expected_phase.get("phase") or "")
        actual_phase = _find_phase_result(phase_results, phase_name)
        if actual_phase is None:
            errors.append(f"缺少 phase 执行结果：{phase_name}")
            continue
        expected_agents = _phase_agents(expected_phase)
        actual_agents = actual_phase.get("agents") if isinstance(actual_phase, dict) else None
        if not isinstance(actual_agents, list):
            errors.append(f"{phase_name} 缺少 agents 执行结果。")
            continue
        for expected_agent in expected_agents:
            actual_agent = _find_agent_result(actual_agents, expected_agent["name"])
            if actual_agent is None:
                errors.append(f"{phase_name} 缺少 agent 执行结果：{expected_agent['name']}")
                continue
            if actual_agent.get("executed") is not True:
                errors.append(f"{expected_agent['name']} 未标记 executed=true。")
            tool_calls = actual_agent.get("tool_calls")
            if not isinstance(tool_calls, list):
                errors.append(f"{expected_agent['name']} 缺少 tool_calls 数组。")
                continue
            _validate_agent_tool_calls(expected_agent, tool_calls, errors, warnings)

    final_markdown = str(result.get("final_markdown") or "")
    if not final_markdown.strip():
        errors.append("缺少 final_markdown。")
    for section in _required_sections(orchestration):
        if section not in final_markdown:
            errors.append(f"final_markdown 缺少必需章节：{section}")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "workflow_name": workflow_name,
        "phase_count": len(_workflow(orchestration).get("phases") or []),
        "agent_count": len(_iter_agent_specs(orchestration)),
        "required_sections": _required_sections(orchestration),
    }


def _validate_agent_tool_calls(
    expected_agent: dict[str, Any],
    tool_calls: list[Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    for tool_name in expected_agent["tools"]:
        call = _find_tool_call(tool_calls, tool_name)
        if call is None:
            errors.append(f"{expected_agent['name']} 未调用工具：{tool_name}")
            continue
        definition = get_tool_definition(tool_name)
        ok = call.get("ok") is True if isinstance(call, dict) else False
        error_code = str(call.get("error_code") or "") if isinstance(call, dict) else ""
        permission_denied = bool(call.get("permission_denied")) if isinstance(call, dict) else False
        if definition is not None and definition.permission in {"write", "notify"}:
            if ok:
                warnings.append(f"{tool_name} 是 {definition.permission} 工具，本次验收返回 ok=true；请确认没有自动执行真实副作用。")
            elif error_code in WRITE_SAFE_ERROR_CODES or permission_denied:
                continue
            else:
                errors.append(f"{expected_agent['name']} 的 {tool_name} 写入/通知工具未安全拒绝：{error_code or 'unknown'}")
        elif not ok:
            errors.append(f"{expected_agent['name']} 的读工具 {tool_name} 未成功：{error_code or 'unknown'}")


def _orchestration_contract_payload(orchestration: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow_name": _workflow_name(orchestration),
        "phases": [
            {
                "phase": str(phase.get("phase") or ""),
                "parallel": bool(phase.get("parallel")),
                "depends_on": list(phase.get("depends_on") or []),
                "agents": _phase_agents(phase),
            }
            for phase in (_workflow(orchestration).get("phases") or [])
        ],
        "required_sections": _required_sections(orchestration),
    }


def _workflow(orchestration: dict[str, Any]) -> dict[str, Any]:
    workflow = orchestration.get("research_workflow")
    return workflow if isinstance(workflow, dict) else {}


def _workflow_name(orchestration: dict[str, Any]) -> str:
    return str(_workflow(orchestration).get("name") or "tquant_daily_research")


def _required_sections(orchestration: dict[str, Any]) -> list[str]:
    output = _workflow(orchestration).get("output")
    if not isinstance(output, dict):
        return []
    return [str(item) for item in output.get("required_sections") or [] if str(item).strip()]


def _iter_agent_specs(orchestration: dict[str, Any]) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for phase in _workflow(orchestration).get("phases") or []:
        agents.extend(_phase_agents(phase))
    return agents


def _phase_agents(phase: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(phase.get("agents"), list):
        raw_agents = phase.get("agents") or []
    elif isinstance(phase.get("agent"), dict):
        raw_agents = [phase.get("agent")]
    else:
        raw_agents = []
    agents: list[dict[str, Any]] = []
    for raw_agent in raw_agents:
        if not isinstance(raw_agent, dict):
            continue
        tools = raw_agent.get("tools") or []
        agents.append(
            {
                "name": str(raw_agent.get("name") or ""),
                "prompt_template": str(raw_agent.get("prompt_template") or ""),
                "tools": [
                    str(tool.get("tool_name"))
                    for tool in tools
                    if isinstance(tool, dict) and str(tool.get("tool_name") or "").strip()
                ],
            }
        )
    return agents


def _prompt_anchor_exists(prompt_template: str) -> bool:
    if not prompt_template or "#" not in prompt_template:
        return False
    file_part, anchor = prompt_template.split("#", 1)
    path = PROJECT_ROOT / file_part
    if not path.exists():
        return False
    marker = f"## {anchor.strip()}"
    return marker in path.read_text(encoding="utf-8")


def _find_phase_result(phase_results: list[Any], phase_name: str) -> dict[str, Any] | None:
    for item in phase_results:
        if isinstance(item, dict) and item.get("phase") == phase_name:
            return item
    return None


def _find_agent_result(agent_results: list[Any], agent_name: str) -> dict[str, Any] | None:
    for item in agent_results:
        if isinstance(item, dict) and item.get("name") == agent_name:
            return item
    return None


def _find_tool_call(tool_calls: list[Any], tool_name: str) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for item in tool_calls:
        if not isinstance(item, dict):
            continue
        actual_name = str(item.get("tool_name") or "")
        if _tool_call_matches(actual_name, tool_name):
            matches.append(item)
    if not matches:
        return None
    for item in matches:
        if item.get("ok") is True:
            return item
    return matches[0]


def _tool_call_matches(actual_name: str, expected_name: str) -> bool:
    if actual_name == expected_name:
        return True
    # Hermes may summarize repeated calls as "analyze_stock x10".
    if actual_name.startswith(f"{expected_name} "):
        return True
    # Hermes may also expand per-symbol calls as "analyze_stock_510300".
    return actual_name.startswith(f"{expected_name}_")


def _parse_json_object(stdout: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def run_feishu_daily_push(db: Session) -> tuple[str, str, dict[str, Any]]:
    service = AgentDailyWorkflowService()
    response = service.push_daily_report(db, channel="feishu")
    if not response.sent and "not configured" in response.message:
        return "not_configured", response.message, response.model_dump()
    status = "ok" if response.ok else "failed"
    message = "飞书日报已推送。" if response.sent else response.message
    return status, message, response.model_dump()


def run_qlib_report(
    db: Session,
    *,
    dataset_path: Path,
    lookback_days: int,
    strategy_keys: list[str] | None,
) -> tuple[str, str, dict[str, Any]]:
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    frame = _export_strategy_samples(db, lookback_days=max(20, lookback_days), strategy_keys=strategy_keys)
    frame.to_csv(dataset_path, index=False)
    strategy_report = DEFAULT_STRATEGY_REPORT
    benchmark_report = DEFAULT_BENCHMARK_REPORT
    write_strategy_validation_report(dataset_path, strategy_report, strategy_keys=strategy_keys)
    write_benchmark_report(dataset_path, benchmark_report)
    data = {
        "qlib": qlib_status(),
        "dataset_path": str(dataset_path),
        "strategy_report_path": str(strategy_report),
        "benchmark_report_path": str(benchmark_report),
        "sample_count": int(len(frame)),
        "strategies": sorted(frame["strategy_key"].dropna().unique().tolist()) if not frame.empty else [],
        "columns": frame.columns.tolist(),
    }
    if frame.empty:
        return "empty", "本地未找到可计算 forward return 的策略样本，已生成空报告。", data
    return "ok", "qlib 标准指标报告已生成。", data


def run_openbb_check() -> tuple[str, str, dict[str, Any]]:
    adapter = OpenBBDataAdapter(timeout=3)
    quote_symbols = ["AAPL", "MSFT", "SPY"]
    quotes = [adapter.quote(symbol).__dict__ for symbol in quote_symbols]
    macro = adapter.macro_status(["CPIAUCSL", "DGS10", "GDP"])
    available_quotes = sum(1 for item in quotes if item.get("available"))
    status = "ok" if available_quotes or macro.get("status") == "ok" else "degraded"
    return status, "OpenBB 可选数据源已完成真实探测与降级验收。", {
        "adapter_status": adapter.status(),
        "quotes": quotes,
        "macro": macro,
        "degrade_rule": "OpenBB 失败只标记 degraded，不阻断 A 股核心策略链路。",
    }


def _export_strategy_samples(
    db: Session,
    *,
    lookback_days: int,
    strategy_keys: list[str] | None,
) -> pd.DataFrame:
    trade_dates = _recent_trade_dates(db, lookback_days=lookback_days + 8)
    if not trade_dates:
        return _empty_strategy_samples()
    min_date = trade_dates[0]
    stmt = select(LowBuyResultSnapshot).where(LowBuyResultSnapshot.latest_trade_date >= min_date)
    if strategy_keys:
        stmt = stmt.where(LowBuyResultSnapshot.strategy_key.in_(strategy_keys))
    rows = db.execute(stmt.order_by(LowBuyResultSnapshot.latest_trade_date, LowBuyResultSnapshot.strategy_key)).scalars().all()
    if not rows:
        return _empty_strategy_samples()
    symbols = sorted({row.symbol for row in rows if row.symbol})
    bars = _load_daily_bars(db, symbols=symbols, min_date=min_date)
    records: list[dict[str, Any]] = []
    for row in rows:
        symbol_bars = bars.get(row.symbol) or []
        index = _date_index(symbol_bars).get(row.latest_trade_date)
        if index is None:
            continue
        close0 = float(symbol_bars[index].close_price or 0.0)
        if close0 <= 0:
            continue
        forward = {horizon: _forward_return(symbol_bars, index, horizon, close0) for horizon in (1, 2, 3, 4, 5)}
        effective_horizon, effective_return = _effective_forward_return(forward)
        if forward[1] is None and forward[3] is None and forward[5] is None:
            continue
        payload = _json_loads(row.payload_json)
        records.append(
            {
                "strategy_key": row.strategy_key,
                "symbol": row.symbol,
                "name": row.name,
                "trade_date": row.latest_trade_date,
                "buy_signal_state": row.buy_signal_state,
                "factor_score": float(row.score or payload.get("score") or 0.0),
                "return": effective_return,
                "return_1d": forward[1],
                "return_2d": forward[2],
                "return_3d": forward[3],
                "return_4d": forward[4],
                "return_5d": forward[5],
                "forward_return_1d": forward[1],
                "effective_return_horizon": effective_horizon,
                "close_price": close0,
                "priority_score": float(payload.get("priority_score") or row.score or 0.0),
                "market_state": str(payload.get("market_state") or payload.get("market_state_category") or ""),
                "industry": str(payload.get("sector_name") or payload.get("industry") or ""),
            }
        )
    if not records:
        return _empty_strategy_samples()
    return pd.DataFrame.from_records(records)


def _recent_trade_dates(db: Session, *, lookback_days: int) -> list[str]:
    rows = (
        db.execute(
            select(DailyBarSnapshot.trade_date)
            .distinct()
            .order_by(desc(DailyBarSnapshot.trade_date))
            .limit(max(1, lookback_days))
        )
        .scalars()
        .all()
    )
    return sorted(str(item) for item in rows if item)


def _load_daily_bars(db: Session, *, symbols: list[str], min_date: str) -> dict[str, list[DailyBarSnapshot]]:
    if not symbols:
        return {}
    rows = (
        db.execute(
            select(DailyBarSnapshot)
            .where(DailyBarSnapshot.symbol.in_(symbols), DailyBarSnapshot.trade_date >= min_date)
            .order_by(DailyBarSnapshot.symbol, DailyBarSnapshot.trade_date)
        )
        .scalars()
        .all()
    )
    grouped: dict[str, list[DailyBarSnapshot]] = defaultdict(list)
    for row in rows:
        grouped[row.symbol].append(row)
    return dict(grouped)


def _date_index(bars: list[DailyBarSnapshot]) -> dict[str, int]:
    return {str(row.trade_date): index for index, row in enumerate(bars)}


def _forward_return(bars: list[DailyBarSnapshot], index: int, horizon: int, close0: float) -> float | None:
    target_index = index + horizon
    if target_index >= len(bars):
        return None
    close_n = float(bars[target_index].close_price or 0.0)
    if close_n <= 0:
        return None
    return round(close_n / close0 - 1.0, 6)


def _effective_forward_return(forward: dict[int, float | None]) -> tuple[int | None, float | None]:
    for horizon in (3, 2, 1, 4, 5):
        value = forward.get(horizon)
        if value is not None:
            return horizon, value
    return None, None


def _empty_strategy_samples() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "strategy_key",
            "symbol",
            "name",
            "trade_date",
            "buy_signal_state",
            "factor_score",
            "return",
            "return_1d",
            "return_2d",
            "return_3d",
            "return_4d",
            "return_5d",
            "forward_return_1d",
            "effective_return_horizon",
            "close_price",
            "priority_score",
            "market_state",
            "industry",
        ]
    )


def _load_priority_symbols(db: Session, *, limit: int) -> list[str]:
    latest_date = (
        db.execute(select(LowBuyResultSnapshot.latest_trade_date).order_by(desc(LowBuyResultSnapshot.latest_trade_date)).limit(1))
        .scalars()
        .first()
    )
    if not latest_date:
        return ["510300", "159915", "588000"]
    rows = (
        db.execute(
            select(LowBuyResultSnapshot.symbol)
            .where(LowBuyResultSnapshot.latest_trade_date == latest_date)
            .order_by(desc(LowBuyResultSnapshot.score))
            .limit(max(1, min(limit, 20)))
        )
        .scalars()
        .all()
    )
    symbols = [str(item) for item in rows if item]
    return symbols[:limit] or ["510300", "159915", "588000"]


def _symbols_from_args(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _json_loads(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _timed(name: str, fn) -> StepResult:
    started = time.perf_counter()
    try:
        status, message, data = fn()
    except Exception as exc:  # noqa: BLE001
        status, message, data = "failed", f"{name} 执行异常：{exc}", {}
    duration_ms = int((time.perf_counter() - started) * 1000)
    return StepResult(
        name=name,
        status=status,
        ok=status in {"ok", "empty", "not_configured", "degraded"},
        message=message,
        data=data,
        duration_ms=duration_ms,
    )


def _overall_status(steps: list[StepResult]) -> str:
    if any(not item.ok for item in steps):
        return "failed"
    if any(item.status in {"not_configured", "degraded", "empty"} for item in steps):
        return "degraded"
    return "ok"


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall_status": report.get("overall_status"),
        "steps": [
            {
                "name": item.get("name"),
                "status": item.get("status"),
                "message": item.get("message"),
                "duration_ms": item.get("duration_ms"),
            }
            for item in report.get("steps", [])
        ],
    }


if __name__ == "__main__":
    main()
