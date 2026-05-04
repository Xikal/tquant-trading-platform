from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent_tools.audit import agent_audit_summary
from app.agent_tools.registry import list_tool_definitions
from app.api.routes import agent
from app.core.agent_auth import require_current_user_or_agent_token
from app.core.config import get_settings
from app.core.database import get_db
from app.models.schema_defs.agent import AgentDailyReportResponse, AgentProviderHealth


EXPECTED_AGENT_OS_TOOLS = {
    "get_agent_health",
    "get_watchlist_context",
    "get_priority_board",
    "analyze_stock",
    "get_daily_report",
    "get_paper_portfolio",
    "recommend_orders",
    "send_test_notification",
    "send_signal_notification",
    "scan_priority_board_notifications",
    "backtest_strategy",
    "compare_strategies",
    "create_paper_order",
    "get_market_sentiment",
    "get_sector_heatmap",
    "get_position_t_signal",
    "get_market_state_analysis",
    "get_sector_mainline_analysis",
    "cross_validate_strategy_context",
    "check_agent_risk",
    "get_comprehensive_analysis",
}


class _ProviderStub:
    name = "none"

    def health(self) -> AgentProviderHealth:
        return AgentProviderHealth(provider="none", available=True, external_agent=False)


def _override_db():
    yield object()


def _override_user():
    return SimpleNamespace(id=1, username="acceptance", is_active=True)


@pytest.fixture()
def agent_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_ENABLE_WRITE_TOOLS", "false")
    monkeypatch.setenv("AGENT_ENABLE_NOTIFY_TOOLS", "false")
    monkeypatch.setenv("AGENT_ALLOWED_CAPABILITIES", "")
    get_settings.cache_clear()
    monkeypatch.setattr(agent, "create_agent_provider", lambda db=None: _ProviderStub())

    app = FastAPI()
    app.include_router(agent.router, prefix="/api")
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_current_user_or_agent_token] = _override_user
    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()


def test_agent_os_tool_registry_acceptance_contract() -> None:
    tools = {tool.name: tool for tool in list_tool_definitions()}

    missing = EXPECTED_AGENT_OS_TOOLS - set(tools)
    assert not missing
    assert tools["create_paper_order"].permission == "write"
    assert tools["recommend_orders"].permission == "write"
    assert tools["send_signal_notification"].permission == "notify"
    assert tools["scan_priority_board_notifications"].permission == "notify"
    assert tools["get_comprehensive_analysis"].permission == "read"


def test_agent_mcp_lists_write_tools_but_policy_blocks_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_mcp import server

    monkeypatch.setenv("AGENT_ENABLE_WRITE_TOOLS", "false")
    monkeypatch.setenv("AGENT_ENABLE_NOTIFY_TOOLS", "false")
    get_settings.cache_clear()
    try:
        tool_names = {item["name"] for item in server._mcp_tools()}
        assert "recommend_orders" in tool_names
        assert "send_test_notification" in tool_names

        payload = server._legacy_call_tool("recommend_orders", {"limit": 3})

        assert payload["ok"] is False
        assert payload["error"]["code"] == "TOOL_PERMISSION_DENIED"
    finally:
        get_settings.cache_clear()


def test_provider_status_makes_disabled_capabilities_explicit(agent_client: TestClient) -> None:
    response = agent_client.get("/api/agent/provider/status")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "none"
    assert body["tool_count"] == len(list_tool_definitions())
    assert body["write_tools_enabled"] is False
    assert body["notify_tools_enabled"] is False
    assert body["audit_enabled"] is True
    assert "get_comprehensive_analysis" in body["enabled_tools"]
    assert "create_paper_order" in body["disabled_tools"]
    assert "send_signal_notification" in body["disabled_tools"]


def test_daily_report_route_can_be_manually_triggered(
    agent_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class _ReportServiceStub:
        def daily_report(self, db):  # noqa: ANN001, ARG002
            calls.append("daily_report")
            return AgentDailyReportResponse(
                trade_date="2026-05-04",
                generated_at="2026-05-04 15:10:00",
                headline="manual trigger ok",
                market_overview={"state": "repair"},
                sector_mainline={"mainlines": []},
                operation_checklist=["confirm market state"],
                markdown="# TQuant Daily Report",
            )

    monkeypatch.setattr(agent, "report_service", _ReportServiceStub())

    response = agent_client.get("/api/agent/reports/daily")

    assert response.status_code == 200
    body = response.json()
    assert calls == ["daily_report"]
    assert body["headline"] == "manual trigger ok"
    assert body["market_overview"]["state"] == "repair"
    assert body["operation_checklist"] == ["confirm market state"]


def test_agent_audit_summary_groups_recent_tool_calls() -> None:
    rows = [
        SimpleNamespace(
            ok=True,
            tool_name="get_priority_board",
            result_summary=json.dumps({"agent_id": "agent-alpha"}),
        ),
        SimpleNamespace(
            ok=False,
            tool_name="create_paper_order",
            result_summary=json.dumps({"agent_id": "agent-alpha"}),
        ),
        SimpleNamespace(
            ok=True,
            tool_name="get_daily_report",
            result_summary=json.dumps({"agent_id": "agent-beta"}),
        ),
    ]

    class _AuditResult:
        def scalars(self):
            return self

        def all(self):
            return rows

    class _AuditDb:
        def execute(self, statement):  # noqa: ANN001, ARG002
            return _AuditResult()

    summary = agent_audit_summary(_AuditDb(), agent_id="agent-alpha")

    assert summary["db_available"] is True
    assert summary["recent_call_count"] == 2
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    assert {item["tool_name"] for item in summary["tool_top"]} == {
        "get_priority_board",
        "create_paper_order",
    }


def test_research_modules_can_summarize_offline_exports(tmp_path: Path) -> None:
    from research.backtest import benchmark, strategy_validation
    from research.factor_research import alpha_exploration

    frame = pd.DataFrame(
        [
            {
                "symbol": "510300",
                "trade_date": "2026-05-04",
                "strategy_key": "first_board",
                "return_3d": 0.035,
                "drawdown_5d": -0.012,
                "factor_score": 0.8,
                "forward_return_1d": 0.01,
            },
            {
                "symbol": "300001",
                "trade_date": "2026-05-05",
                "strategy_key": "first_board",
                "return_3d": -0.01,
                "drawdown_5d": -0.026,
                "factor_score": 0.3,
                "forward_return_1d": -0.02,
            },
        ]
    )
    export_path = tmp_path / "offline.csv"
    frame.to_csv(export_path, index=False)

    assert benchmark.benchmark_summary(export_path)["rows"] == 2
    strategy_summary = strategy_validation.summarize_strategy_results(export_path, "first_board")
    assert strategy_summary.sample_count == 2
    assert strategy_summary.win_rate_3d == 50.0
    assert alpha_exploration.summarize_factor_input(export_path)["symbols"] == 2


def test_research_data_sync_help_does_not_require_database() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "research/data_sync/tquant_to_qlib.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--database-url" in result.stdout


def test_agent_os_acceptance_script_helpers_are_structured() -> None:
    from scripts import agent_os_acceptance

    empty_frame = agent_os_acceptance._empty_strategy_samples()

    assert {
        "strategy_key",
        "factor_score",
        "forward_return_1d",
        "return_1d",
        "return_5d",
    }.issubset(set(empty_frame.columns))
    assert agent_os_acceptance._overall_status([]) == "ok"
    assert agent_os_acceptance._summary({"overall_status": "ok", "steps": []}) == {
        "overall_status": "ok",
        "steps": [],
    }


def test_hermes_orchestration_contract_and_result_validation() -> None:
    from scripts import agent_os_acceptance

    orchestration = agent_os_acceptance._load_orchestration(agent_os_acceptance.DEFAULT_ORCHESTRATION)
    status, _, contract = agent_os_acceptance.validate_orchestration_contract(orchestration)

    assert status == "ok"
    assert set(contract["agents"]) == {
        "market_state_analyst",
        "sector_heat_analyst",
        "technical_analyst",
        "strategy_validator",
        "portfolio_manager",
    }

    result = {
        "ok": True,
        "workflow_name": "tquant_daily_research",
        "phase_results": [
            {
                "phase": "parallel_analysis",
                "agents": [
                    {
                        "name": "market_state_analyst",
                        "executed": True,
                        "tool_calls": [
                            {"tool_name": "get_market_state_analysis", "ok": True, "error_code": None},
                            {"tool_name": "get_priority_board", "ok": True, "error_code": None},
                            {"tool_name": "get_agent_health", "ok": True, "error_code": None},
                        ],
                    },
                    {
                        "name": "sector_heat_analyst",
                        "executed": True,
                        "tool_calls": [
                            {"tool_name": "get_sector_mainline_analysis", "ok": True, "error_code": None},
                            {"tool_name": "get_priority_board", "ok": True, "error_code": None},
                        ],
                    },
                    {
                        "name": "technical_analyst",
                        "executed": True,
                        "tool_calls": [
                            {"tool_name": "analyze_stock", "ok": True, "error_code": None},
                            {"tool_name": "get_watchlist_context", "ok": True, "error_code": None},
                            {"tool_name": "get_priority_board", "ok": True, "error_code": None},
                        ],
                    },
                ],
            },
            {
                "phase": "cross_validation",
                "agents": [
                    {
                        "name": "strategy_validator",
                        "executed": True,
                        "tool_calls": [
                            {"tool_name": "cross_validate_strategy_context", "ok": True, "error_code": None},
                            {"tool_name": "check_agent_risk", "ok": True, "error_code": None},
                        ],
                    }
                ],
            },
            {
                "phase": "decision",
                "agents": [
                    {
                        "name": "portfolio_manager",
                        "executed": True,
                        "tool_calls": [
                            {"tool_name": "get_comprehensive_analysis", "ok": True, "error_code": None},
                            {
                                "tool_name": "recommend_orders",
                                "ok": False,
                                "error_code": "TOOL_PERMISSION_DENIED",
                                "permission_denied": True,
                            },
                            {"tool_name": "get_paper_portfolio", "ok": True, "error_code": None},
                        ],
                    }
                ],
            },
        ],
        "final_markdown": "\n".join(
            [
                "### 市场概览",
                "### 板块主线",
                "### 持仓做T信号",
                "### 选股宝典 TOP 10",
                "### 风控检查",
                "### 操作检查清单",
            ]
        ),
        "errors": [],
    }

    validation = agent_os_acceptance.validate_hermes_workflow_result(orchestration, result)

    assert validation["ok"] is True
    assert validation["errors"] == []


def test_hermes_orchestration_result_requires_all_declared_tools() -> None:
    from scripts import agent_os_acceptance

    orchestration = agent_os_acceptance._load_orchestration(agent_os_acceptance.DEFAULT_ORCHESTRATION)
    validation = agent_os_acceptance.validate_hermes_workflow_result(
        orchestration,
        {
            "workflow_name": "tquant_daily_research",
            "phase_results": [
                {"phase": "parallel_analysis", "agents": [{"name": "market_state_analyst", "executed": True, "tool_calls": []}]}
            ],
            "final_markdown": "### 市场概览",
        },
    )

    assert validation["ok"] is False
    assert any("未调用工具" in item or "缺少 phase" in item for item in validation["errors"])
