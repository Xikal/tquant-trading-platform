#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.audit_legacy_routes import audit_legacy_route_usage
from scripts.deploy_scope import resolve_deploy_scope


DEFAULT_D5_SUMMARY = Path("docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json")
DEFAULT_BUDGET = Path("docs/reports/platform-budget-current-2026-06-12-post-sla-disable.json")
DEFAULT_REMEDIATION = Path("docs/reports/cloud-resource-contention-remediation-2026-06-12.md")
DEFAULT_PROVIDER_REPORT = Path("docs/reports/provider-degraded-cooldown-market-regime-optimization-2026-06-12.md")
DEFAULT_DOMAIN_RUNBOOK = Path("docs/operations/domain-entry-runbook.md")
DEFAULT_DEPLOYMENT_RUNBOOK = Path("docs/operations/deployment-topology-runbook.md")
DEFAULT_WORKER_RUNBOOK = Path("docs/operations/worker-runbook.md")
DEFAULT_LEGACY_RUNBOOK = Path("docs/operations/legacy-route-removal.md")
DEFAULT_BACKEND_MAIN = Path("backend/app/main.py")

COMPLETE = "complete"
BLOCKED = "blocked"
OBSERVATION_REQUIRED = "observation_required"
NEEDS_AUTHORIZATION = "needs_authorization"
NEEDS_INVESTIGATION = "needs_investigation"
PARTIAL = "partial"


@dataclass(frozen=True)
class Check:
    check_id: str
    requirement: str
    status: str
    evidence: str
    next_action: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.check_id,
            "requirement": self.requirement,
            "status": self.status,
            "evidence": self.evidence,
            "next_action": self.next_action,
        }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_audit(
    *,
    d5_summary: dict[str, Any],
    budget: dict[str, Any],
    remediation_text: str,
    provider_text: str,
    domain_runbook_text: str,
    deployment_runbook_text: str,
    worker_runbook_text: str,
    legacy_runbook_text: str,
    backend_main_text: str,
) -> dict[str, Any]:
    checks = [
        _d5_observation_check(d5_summary),
        _scheduler_embed_check(d5_summary),
        _mysql_root_cause_check(d5_summary, budget),
        _domain_entry_check(domain_runbook_text),
        _provider_warning_check(d5_summary, provider_text),
        _runtime_task_noise_check(remediation_text),
        _legacy_frontend_guard_check(deployment_runbook_text, legacy_runbook_text, backend_main_text),
        _on_demand_worker_runbook_check(worker_runbook_text, deployment_runbook_text),
        _data_quality_sla_check(remediation_text),
    ]
    summary = _summarize(checks)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": summary["overall_status"],
        "summary": summary,
        "checks": [check.to_dict() for check in checks],
    }


def _d5_observation_check(d5_summary: dict[str, Any]) -> Check:
    missing = d5_summary.get("missing_checkpoints") or []
    ready = bool(d5_summary.get("d5_ready"))
    full = bool(d5_summary.get("full_trading_day_complete"))
    if ready and full:
        status = COMPLETE
        action = "D5 observation gate is satisfied; scheduler embed can move to an explicit authorization decision."
    else:
        status = OBSERVATION_REQUIRED
        action = "Collect the missing formal trading-day checkpoints and regenerate the D5 summary."
    return Check(
        "d5.full_trading_day_observation",
        "Complete a full valid trading-day stability observation before scheduler consolidation.",
        status,
        f"d5_ready={ready}; full_trading_day_complete={full}; missing_checkpoints={','.join(missing) or 'none'}",
        action,
    )


def _scheduler_embed_check(d5_summary: dict[str, Any]) -> Check:
    ready = bool(d5_summary.get("d5_ready"))
    blockers = d5_summary.get("d5_blockers") or []
    return Check(
        "d5.scheduler_embed_cutover",
        "Do not stop standalone runtime-scheduler until D5 is ready and user authorizes the cutover.",
        NEEDS_AUTHORIZATION if ready else BLOCKED,
        f"d5_ready={ready}; blockers={','.join(blockers) or 'none'}",
        "If and only if D5 is ready, run the scheduler embed maintenance-window plan with rollback prepared.",
    )


def _mysql_root_cause_check(d5_summary: dict[str, Any], budget: dict[str, Any]) -> Check:
    mysql_warnings = [item for item in d5_summary.get("warnings", []) if str(item).startswith("mysql_slow_queries=")]
    budget_eval = budget.get("evaluation") or {}
    if not mysql_warnings and budget_eval.get("status") == "ok":
        status = COMPLETE
        action = "Keep routine monitoring."
    else:
        status = NEEDS_INVESTIGATION
        action = "Run a slow-query/index/p95 review; change indexes or machine size only after evidence and authorization."
    return Check(
        "mysql.root_cause",
        "Close MySQL slow-query, connection-pool, index, and machine-size root causes.",
        status,
        f"budget_status={budget_eval.get('status', 'unknown')}; mysql_warnings={','.join(mysql_warnings) or 'none'}",
        action,
    )


def _domain_entry_check(domain_runbook_text: str) -> Check:
    has_runbook = "Current Known Symptom" in domain_runbook_text and "TLS" in domain_runbook_text
    return Check(
        "domain.tls_sni_reset",
        "Resolve public domain TLS/SNI reset separately from resource contention work.",
        NEEDS_AUTHORIZATION,
        f"domain_runbook_present={has_runbook}",
        "Capture nginx/DNS/CDN/WAF evidence, then authorize a domain-entry maintenance change or provider ticket.",
    )


def _provider_warning_check(d5_summary: dict[str, Any], provider_text: str) -> Check:
    signals = [
        item
        for item in [*d5_summary.get("warnings", []), *d5_summary.get("d5_blockers", [])]
        if str(item).startswith("scheduler_provider_warning")
    ]
    has_guard_report = "Configurable Cooldown Follow-Up" in provider_text
    if signals:
        status = NEEDS_INVESTIGATION
        action = "Recheck scheduler logs during the next trading window and tune provider cooldown/cache only with fresh evidence."
    else:
        status = COMPLETE if has_guard_report else PARTIAL
        action = "Keep provider warning checks in the D5 collector."
    return Check(
        "provider.scheduler_warning_residual",
        "Eliminate residual provider warning bursts before scheduler embed.",
        status,
        f"guard_report_present={has_guard_report}; provider_signals={','.join(signals) or 'none'}",
        action,
    )


def _runtime_task_noise_check(remediation_text: str) -> Check:
    has_historical_noise = "historical failed" in remediation_text or "Historical failed" in remediation_text
    return Check(
        "runtime_tasks.historical_failed_noise",
        "Reduce historical failed RuntimeTask noise without deleting production evidence casually.",
        NEEDS_AUTHORIZATION if has_historical_noise else COMPLETE,
        f"historical_failed_noise_recorded={has_historical_noise}",
        "Prepare an archive/marking migration and execute only after DB-write authorization and backup confirmation.",
    )


def _legacy_frontend_guard_check(deployment_runbook_text: str, legacy_runbook_text: str, backend_main_text: str) -> Check:
    hot = resolve_deploy_scope([], explicit_scope="frontend-hot")
    legacy = resolve_deploy_scope([], explicit_scope="frontend-legacy")
    route_audit = audit_legacy_route_usage()
    retired_assets = "Legacy frontend assets have been retired" in backend_main_text
    runbook_current = "--scope frontend-next" in deployment_runbook_text and "--scope frontend-hot --frontend-hot-required" not in deployment_runbook_text
    legacy_doc_mentions_scope = "frontend-hot" in legacy_runbook_text and "frontend-legacy" in legacy_runbook_text
    ok = hot.blocked and legacy.blocked and route_audit["finding_count"] == 0 and retired_assets and runbook_current and legacy_doc_mentions_scope
    return Check(
        "legacy_frontend.retirement_guard",
        "Keep frontend-hot/frontend-legacy/__legacy retired and prevent old frontend re-entry.",
        COMPLETE if ok else PARTIAL,
        (
            f"frontend_hot_blocked={hot.blocked}; frontend_legacy_blocked={legacy.blocked}; "
            f"legacy_route_findings={route_audit['finding_count']}; retired_assets={retired_assets}; "
            f"runbook_current={runbook_current}; legacy_doc_mentions_scope={legacy_doc_mentions_scope}"
        ),
        "If partial, update runbooks/tests before any frontend deploy.",
    )


def _on_demand_worker_runbook_check(worker_runbook_text: str, deployment_runbook_text: str) -> Check:
    required_terms = [
        "analytics-worker",
        "backtest",
        "ML",
        "factor",
        "stop analytics-worker",
        "RUNTIME_LOW_PRIORITY_TASKS_PAUSED",
    ]
    combined = f"{worker_runbook_text}\n{deployment_runbook_text}"
    missing = [term for term in required_terms if term not in combined]
    return Check(
        "optional_workers.on_demand_runbook",
        "Document on-demand analytics/backtest/ML/factor operation without making them resident.",
        COMPLETE if not missing else PARTIAL,
        f"missing_terms={','.join(missing) or 'none'}",
        "Fill missing runbook terms and keep analytics/backtest/ML/factor outside the always-on profile.",
    )


def _data_quality_sla_check(remediation_text: str) -> Check:
    complete = "DATA_QUALITY_SLA Disable Rollout" in remediation_text and "no new `data_quality_sla_refresh` queued task appeared" in remediation_text
    return Check(
        "data_quality_sla.non_core_requeue",
        "Stop non-core data_quality_sla_refresh from re-entering queue while analytics-worker is non-resident.",
        COMPLETE if complete else PARTIAL,
        f"sla_rollout_recorded={complete}",
        "Keep DATA_QUALITY_SLA_ENABLED=false in the small-host profile unless analytics-worker is made resident.",
    )


def _summarize(checks: list[Check]) -> dict[str, Any]:
    counts = {status: 0 for status in [COMPLETE, BLOCKED, OBSERVATION_REQUIRED, NEEDS_AUTHORIZATION, NEEDS_INVESTIGATION, PARTIAL]}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    if counts[BLOCKED] or counts[OBSERVATION_REQUIRED]:
        overall = "blocked"
    elif counts[NEEDS_AUTHORIZATION] or counts[NEEDS_INVESTIGATION] or counts[PARTIAL]:
        overall = "open_items"
    else:
        overall = "complete"
    return {"overall_status": overall, **counts}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Cloud Resource Remaining Closure Audit",
        "",
        f"- Generated at: `{report.get('generated_at', '')}`",
        f"- Status: `{report.get('status', '')}`",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    summary = report.get("summary", {})
    for status in [COMPLETE, BLOCKED, OBSERVATION_REQUIRED, NEEDS_AUTHORIZATION, NEEDS_INVESTIGATION, PARTIAL]:
        lines.append(f"| `{status}` | {summary.get(status, 0)} |")
    lines.extend(["", "## Checks", "", "| ID | Status | Evidence | Next action |", "| --- | --- | --- | --- |"])
    for check in report.get("checks", []):
        lines.append(
            "| `{}` | `{}` | {} | {} |".format(
                check.get("id", ""),
                check.get("status", ""),
                str(check.get("evidence", "")).replace("|", "\\|"),
                str(check.get("next_action", "")).replace("|", "\\|"),
            )
        )
    lines.extend(
        [
            "",
            "## Operations Not Executed",
            "",
            "- This audit reads local reports, runbooks, and source guards only.",
            "- No remote shell command.",
            "- No deployment or cutover.",
            "- No Docker restart/recreate/remove.",
            "- No `.env` change.",
            "- No DB write.",
            "- No nginx/systemd/DNS/CDN change.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit remaining cloud-resource closure gates from local evidence.")
    parser.add_argument("--d5-summary", type=Path, default=DEFAULT_D5_SUMMARY)
    parser.add_argument("--budget-report", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--remediation-report", type=Path, default=DEFAULT_REMEDIATION)
    parser.add_argument("--provider-report", type=Path, default=DEFAULT_PROVIDER_REPORT)
    parser.add_argument("--domain-runbook", type=Path, default=DEFAULT_DOMAIN_RUNBOOK)
    parser.add_argument("--deployment-runbook", type=Path, default=DEFAULT_DEPLOYMENT_RUNBOOK)
    parser.add_argument("--worker-runbook", type=Path, default=DEFAULT_WORKER_RUNBOOK)
    parser.add_argument("--legacy-runbook", type=Path, default=DEFAULT_LEGACY_RUNBOOK)
    parser.add_argument("--backend-main", type=Path, default=DEFAULT_BACKEND_MAIN)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    report = build_audit(
        d5_summary=load_json(args.d5_summary),
        budget=load_json(args.budget_report),
        remediation_text=read_text(args.remediation_report),
        provider_text=read_text(args.provider_report),
        domain_runbook_text=read_text(args.domain_runbook),
        deployment_runbook_text=read_text(args.deployment_runbook),
        worker_runbook_text=read_text(args.worker_runbook),
        legacy_runbook_text=read_text(args.legacy_runbook),
        backend_main_text=read_text(args.backend_main),
    )
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, ensure_ascii=False))
    return 42 if args.fail_on_blocked and report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
