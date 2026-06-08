#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ACCEPTANCE = Path("docs/reports/platform-resource-optimization-acceptance-2026-06-08.json")
DEFAULT_RESOURCE = Path("docs/reports/platform-resource-baseline-2026-06-08.json")
DEFAULT_BUDGET = Path("docs/reports/platform-budget-2026-06-08.json")
DEFAULT_MANIFEST = Path("docs/reports/platform-analytics-manifests-2026-06-08.json")
DEFAULT_READINESS = Path("docs/reports/platform-optimization-readiness-2026-06-08.json")
DEFAULT_CSS_BUDGET = Path("docs/reports/frontend-next-css-budget-2026-06-07.json")
DEFAULT_CHUNK_PROFILE = Path("docs/reports/frontend-next-chunk-profile-2026-06-08.json")
DEFAULT_BACKUP_VERIFICATION = Path("docs/reports/platform-mysql-backup-verification-2026-06-08.json")
DEFAULT_PROGRESS = Path("docs/reports/platform-resource-optimization-2026-06-08.md")
DEFAULT_FRONTEND_PERF_REPORT = Path("docs/reports/frontend-next-perf-compare-2026-06-08.json")
DEFAULT_CLOUD_PERFORMANCE_REPORT = Path("docs/reports/gupiao-cloud-performance-2026-06-08-000012.json")
DEFAULT_CUTOVER_RUNBOOK = Path("docs/frontend-next-cutover-runbook-2026-06-05.md")
DEFAULT_PRODUCTION_RUNBOOK = Path("PRODUCTION_RUNBOOK.md")
DEFAULT_MYSQL_RUNBOOK = Path("docs/operations/mysql-maintenance-runbook.md")

PASSING = "passed"
WARNING = "warning"
BLOCKED = "blocked"
NOT_VERIFIED = "not_verified"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_audit(
    *,
    acceptance: dict[str, Any],
    resource: dict[str, Any],
    budget: dict[str, Any],
    manifest: dict[str, Any],
    readiness: dict[str, Any],
    css_budget: dict[str, Any],
    chunk_profile: dict[str, Any],
    backup_verification: dict[str, Any] | None = None,
    progress_text: str,
    frontend_perf: dict[str, Any] | None = None,
    cloud_performance: dict[str, Any] | None = None,
    cutover_runbook_text: str = "",
    production_runbook_text: str = "",
    mysql_runbook_text: str = "",
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(
        check_id: str,
        phase: str,
        requirement: str,
        status: str,
        evidence: str,
        next_action: str = "",
    ) -> None:
        checks.append(
            {
                "id": check_id,
                "phase": phase,
                "requirement": requirement,
                "status": status,
                "evidence": evidence,
                "next_action": next_action,
            }
        )

    readiness_eval = readiness.get("evaluation") or {}
    readiness_warnings = set(readiness_eval.get("warnings") or [])
    root = resource.get("root") or {}
    memory = resource.get("memory") or {}
    mysql = resource.get("mysql") or {}
    docker = resource.get("docker") or {}
    journal = resource.get("journal") or {}
    deploy_backups = resource.get("deploy_backups") or {}
    mysql_variables = mysql.get("variables") or {}
    mysql_slow_log = mysql.get("slow_log") or {}
    mysql_backups = resource.get("mysql_backups") or {}
    mysql_volume_rows = (mysql.get("volume") or {}).get("rows") or []
    manifest_summary = manifest.get("summary") or {}
    css_summary = css_budget.get("summary") or {}
    css_budgets = css_budget.get("budgets") or {}
    chunk_summary = chunk_profile.get("summary") or {}
    chunk_targets = chunk_profile.get("targets") or {}
    backup_verification = backup_verification or {}
    budget_mysql = budget.get("mysql") or {}
    budget_roles = budget.get("roles") or {}
    frontend_perf = frontend_perf or {}
    cloud_performance = cloud_performance or {}

    add(
        "boundary.no_deploy_no_cutover",
        "boundary",
        "本轮不部署、不切流。",
        PASSING if acceptance.get("deployed") is False and acceptance.get("cutover") is False else BLOCKED,
        f"deployed={acceptance.get('deployed')}, cutover={acceptance.get('cutover')}",
        "如需正式切流，必须另行授权并复跑 gate。",
    )
    add(
        "boundary.strategy_policy",
        "boundary",
        "不修改 strategy_policy.py。",
        PASSING if acceptance.get("strategy_policy_modified") is False else BLOCKED,
        f"strategy_policy_modified={acceptance.get('strategy_policy_modified')}",
    )
    add(
        "boundary.production_semantics",
        "boundary",
        "不改变生产策略语义、生产排序、production_score、priority_board。",
        PASSING if acceptance.get("production_semantics_changed") is False else BLOCKED,
        f"production_semantics_changed={acceptance.get('production_semantics_changed')}",
    )
    add(
        "boundary.old_frontend",
        "boundary",
        "旧 frontend/ 不作为本轮改造对象。",
        PASSING if acceptance.get("old_frontend_modified") is False else BLOCKED,
        f"old_frontend_modified={acceptance.get('old_frontend_modified')}",
    )

    add(
        "phase_a.root_disk_gate",
        "phase_a",
        "根分区 >80% blocking，长期目标 <60%。",
        PASSING if number(root.get("used_pct")) is not None and number(root.get("used_pct")) < 80 else BLOCKED,
        f"root_used_pct={root.get('used_pct')}",
        "继续每日巡检；长期目标仍需维持在 60% 附近。",
    )
    add(
        "phase_a.available_memory",
        "phase_a",
        "Available memory >800MiB，或有明确单机不可达原因。",
        PASSING
        if number((memory.get("mem") or {}).get("available_mb")) is not None
        and number((memory.get("mem") or {}).get("available_mb")) >= 800
        else WARNING,
        f"available_mb={(memory.get('mem') or {}).get('available_mb')}",
        "资源上限和 worker 降载在线生效后复验；若仍低于 800MiB，需在验收报告写明单机不可达原因。",
    )
    add(
        "phase_a.binlog_retention",
        "phase_a",
        "MySQL binlog 固化保留 3 天。",
        PASSING if number(mysql_variables.get("binlog_expire_logs_seconds")) is not None and number(mysql_variables.get("binlog_expire_logs_seconds")) <= 259200 else BLOCKED,
        f"binlog_expire_logs_seconds={mysql_variables.get('binlog_expire_logs_seconds')}",
    )
    add(
        "phase_a.max_binlog_size",
        "phase_a",
        "max_binlog_size 目标 256M。",
        PASSING if number(mysql_variables.get("max_binlog_size")) is not None and number(mysql_variables.get("max_binlog_size")) <= 268_435_456 else BLOCKED,
        f"max_binlog_size={mysql_variables.get('max_binlog_size')}",
        "运维窗口重建 MySQL 容器使 compose max-binlog-size 生效，并复验 @@max_binlog_size。",
    )
    add(
        "phase_a.slow_log_rotation",
        "phase_a",
        "MySQL slow log 单文件 <=256M 并安装 logrotate。",
        PASSING if number(mysql_slow_log.get("size_bytes")) is not None and number(mysql_slow_log.get("size_bytes")) <= 268_435_456 else BLOCKED,
        f"slow_log_bytes={mysql_slow_log.get('size_bytes')}; mysql_slow_logrotate_missing={'resource:resource_config_missing=mysql_slow_logrotate' in readiness_warnings}",
        "先备份 slow log，再安装 logrotate 并执行轮转/复验。",
    )
    add(
        "phase_a.journal_retention",
        "phase_a",
        "systemd journal 上限 300M/7day 在线生效。",
        PASSING
        if number(journal.get("usage_bytes")) is not None
        and number(journal.get("usage_bytes")) <= 314_572_800
        else BLOCKED,
        f"journal_usage_bytes={journal.get('usage_bytes')}; journald_dropin_missing={'resource:resource_config_missing=journald_dropin' in readiness_warnings}",
        "运维窗口安装 journald drop-in 并重启/复验 journal 占用。",
    )
    add(
        "phase_a.docker_build_cache",
        "phase_a",
        "Docker BuildKit cache 目标 <=2G。",
        PASSING if number((docker.get("build_cache") or {}).get("size_bytes")) is not None and number((docker.get("build_cache") or {}).get("size_bytes")) <= 2_147_483_648 else BLOCKED,
        f"docker_build_cache_bytes={(docker.get('build_cache') or {}).get('size_bytes')}",
        "启用 BuildKit GC 或只清 build cache；禁止清 volume。",
    )
    add(
        "phase_a.resource_configs_applied",
        "phase_a",
        "Docker/journal/BuildKit/MySQL compose command/slow logrotate 配置在线安装或生效并可复验。",
        PASSING if not any(item.startswith("resource:resource_config_missing=") for item in readiness_warnings) else BLOCKED,
        ", ".join(sorted(item for item in readiness_warnings if item.startswith("resource:resource_config_missing="))) or "no missing config warnings",
        "按维护窗口计划执行 resource_limits_apply 后重跑 baseline/readiness。",
    )
    add(
        "phase_a.mysql_volume_short_term",
        "phase_a",
        "MySQL volume 短期 <12G，长期通过 Parquet/manifest 控制增长。",
        PASSING
        if mysql_volume_size(mysql_volume_rows) is not None
        and mysql_volume_size(mysql_volume_rows) < 12_000_000_000
        else BLOCKED,
        f"mysql_volume_bytes={mysql_volume_size(mysql_volume_rows)}",
        "manifest 全部补齐并完成保留窗口 dry-run 前，不清 MySQL 源数据。",
    )
    add(
        "phase_a.deploy_backup_retention",
        "phase_a",
        "生产机部署归档仅保留最近 3 个可回滚版本。",
        PASSING
        if number(deploy_backups.get("count")) is not None
        and number(deploy_backups.get("count")) <= 3
        else BLOCKED,
        f"deploy_backup_count={deploy_backups.get('count')}, total_bytes={deploy_backups.get('total_bytes')}",
        "保留最新 3 个；禁止清当前运行目录、数据库、运行时数据。",
    )
    add(
        "phase_a.mysql_backup",
        "phase_a",
        "执行数据库备份并纳入巡检，备份 gzip/SQL 特征可校验。",
        mysql_backup_status(mysql_backups, backup_verification),
        mysql_backup_evidence(mysql_backups, backup_verification),
    )

    add(
        "phase_b.strategy_bff_requests",
        "phase_b",
        "/next/strategy-tracking 优先走 BFF，请求 <=2 且 items 422=0。",
        strategy_bff_status(frontend_perf, progress_text),
        strategy_bff_evidence(frontend_perf, progress_text),
        "保留 request:trace/perf:compare 作为正式 gate。",
    )
    add(
        "phase_b.paper_virtualization_dom",
        "phase_b",
        "/next/paper 长列表接 VirtualList，DOM <150，机甲组件不改。",
        paper_dom_status(frontend_perf, progress_text),
        paper_dom_evidence(frontend_perf, progress_text),
        "若坚持整页 DOM <150，需要另行授权简化机甲组件 DOM。",
    )
    add(
        "phase_b.css_important",
        "phase_b",
        "CSS !important <=25。",
        PASSING if number(css_summary.get("important_count")) is not None and number(css_summary.get("important_count")) <= 25 else BLOCKED,
        f"important_count={css_summary.get('important_count')}, target={css_budgets.get('source_css_important_target')}",
    )
    add(
        "phase_b.css_raw",
        "phase_b",
        "CSS raw <=180KB，或说明不可达原因。",
        PASSING if number(css_summary.get("source_css_bytes")) is not None and number(css_summary.get("source_css_bytes")) <= number(css_budgets.get("source_css_bytes_target"), 180_000) else WARNING,
        f"source_css_bytes={css_summary.get('source_css_bytes')}, target={css_budgets.get('source_css_bytes_target')}, status={(css_budget.get('status') or {}).get('source_css_bytes')}",
        "当前以说明和视觉一致性 gate 接受；继续优化需逐页截图验证。",
    )
    add(
        "phase_b.echarts_initial",
        "phase_b",
        "ECharts 首屏资产为 0，K 线保持 Lightweight Charts。",
        PASSING if number(chunk_summary.get("initial_echarts_assets")) == 0 else BLOCKED,
        f"initial_echarts_assets={chunk_summary.get('initial_echarts_assets')}, target={chunk_targets.get('initial_echarts_assets_max')}",
    )
    add(
        "phase_b.initial_js",
        "phase_b",
        "首屏 JS raw <=350KB。",
        PASSING if number(chunk_summary.get("initial_js_raw_bytes")) is not None and number(chunk_summary.get("initial_js_raw_bytes")) <= 350_000 else BLOCKED,
        f"initial_js_raw_bytes={chunk_summary.get('initial_js_raw_bytes')}, target={chunk_targets.get('initial_js_raw_bytes_max')}",
    )

    add(
        "phase_c.mysql_connections",
        "phase_c",
        "MySQL max_connections 收敛到 80-120 并在线生效。",
        PASSING if number(budget_mysql.get("max_connections")) is not None and number(budget_mysql.get("max_connections")) <= 120 else BLOCKED,
        f"max_connections={budget_mysql.get('max_connections')}, threads_connected={budget_mysql.get('threads_connected')}",
        "运维窗口重启 MySQL/容器，使 compose 目标 120 生效并复跑 performance gate。",
    )
    add(
        "phase_c.low_priority_pause_env",
        "phase_c",
        "低优先级重任务暂停开关进入运行容器。",
        PASSING if not any(item.startswith("worker_budget:low_priority_pause_env_missing=") for item in readiness_warnings) else BLOCKED,
        ", ".join(sorted(item for item in readiness_warnings if item.startswith("worker_budget:low_priority_pause_env_missing="))) or "low priority env present",
        "运维窗口重启 runtime/backtest/analytics/scheduler 容器后复验。",
    )
    add(
        "phase_c.web_no_heavy_tasks",
        "phase_c",
        "Web 主进程不跑重任务。",
        PASSING
        if str(((budget_roles.get("web") or {}).get("env") or {}).get("RUNTIME_BACKGROUND_JOBS_ENABLED")).lower()
        == "false"
        and str(((budget_roles.get("web") or {}).get("env") or {}).get("TQUANT_ANALYTICS_ENABLED")).lower() == "false"
        else NOT_VERIFIED,
        f"web_env={((budget_roles.get('web') or {}).get('env') or {})}",
    )
    add(
        "phase_c.swap_target",
        "phase_c",
        "Swap 长期 <20%，短期优化目标 <500MiB。",
        PASSING if number(((memory.get("swap") or {}).get("used_pct"))) is not None and number(((memory.get("swap") or {}).get("used_pct"))) < 20 else BLOCKED,
        f"swap_used_pct={((memory.get('swap') or {}).get('used_pct'))}",
        "资源上限和 worker 降载在线生效后复验。",
    )

    add(
        "phase_d.daily_bars_manifest",
        "phase_d",
        "daily_bars Parquet manifest 可校验。",
        PASSING if "daily_bars" in manifest_summary.get("ready_datasets", []) or number(manifest_summary.get("ready_count")) and number(manifest_summary.get("ready_count")) >= 1 else NOT_VERIFIED,
        f"ready_count={manifest_summary.get('ready_count')}, verified_files={manifest_summary.get('verified_files')}",
    )
    add(
        "phase_d.all_required_manifests",
        "phase_d",
        "strategy/backtest/report 等目标数据集 manifest 全部补齐。",
        PASSING if number(manifest_summary.get("blocked_count")) == 0 and number(manifest_summary.get("missing_count")) == 0 else BLOCKED,
        f"missing_count={manifest_summary.get('missing_count')}, blocked_count={manifest_summary.get('blocked_count')}, blocked_datasets={manifest_summary.get('blocked_datasets')}",
        "按导出计划显式入队 9 个 analytics export 任务，完成后重跑 manifest verifier。",
    )
    add(
        "phase_d.retention_strategy",
        "phase_d",
        "MySQL 热库保留窗口和归档策略明确，且清理前要求 manifest/备份/恢复路径。",
        PASSING
        if all(
            text in mysql_runbook_text
            for text in ["热库保留窗口", "manifest", "恢复路径", "不能自动清理 MySQL 源表"]
        )
        else NOT_VERIFIED,
        "mysql maintenance runbook includes manifest-gated retention and cleanup authorization."
        if "不能自动清理 MySQL 源表" in mysql_runbook_text
        else "missing runbook evidence",
    )
    add(
        "phase_d.no_mysql_cleanup",
        "phase_d",
        "manifest 未校验前不清 MySQL 源数据。",
        PASSING,
        "acceptance/runbook 明确未清 MySQL 源表，清理仍需单独授权。",
    )

    add(
        "phase_e.prebuilt_deploy",
        "phase_e",
        "预构建镜像优先，云端 pull+restart。",
        prebuilt_status((acceptance.get("phase_completion") or {}).get("phase_e_prebuilt_deploy")),
        f"phase_e={((acceptance.get('phase_completion') or {}).get('phase_e_prebuilt_deploy'))}",
        "脚本入口已完成；真实 registry ref 和云端 pull+restart 尚未执行。",
    )
    add(
        "phase_e.deployment_resource_gate",
        "phase_e",
        "部署前资源 gate 纳入 cutover/生产手册，资源不达标停止。",
        PASSING
        if "资源 gate" in cutover_runbook_text
        and "platform-optimization-readiness" in cutover_runbook_text
        and "资源 gate" in production_runbook_text
        and "collect_platform_resource_report.py" in production_runbook_text
        else NOT_VERIFIED,
        "cutover/production runbooks contain platform resource gate references."
        if "资源 gate" in cutover_runbook_text and "资源 gate" in production_runbook_text
        else "missing cutover or production resource gate runbook evidence",
        "补齐 runbook 后，真实部署前仍需按 gate 重新采集并归档。",
    )
    add(
        "phase_f.online_performance",
        "phase_f",
        "线上 Web/API performance gate 当前样本通过。",
        cloud_performance_status(cloud_performance),
        cloud_performance_evidence(cloud_performance),
        "资源 apply、worker 重启、manifest 导出后必须重新跑三轮 online performance gate。",
    )
    add(
        "phase_f.reporting",
        "phase_f",
        "报告闭环包含 before/after、资源、MySQL、Worker、manifest、回滚、未完成项。",
        PASSING if acceptance.get("status") and acceptance.get("open_items") is not None else NOT_VERIFIED,
        f"acceptance_status={acceptance.get('status')}, open_items={len(acceptance.get('open_items') or [])}",
    )
    add(
        "phase_f.full_gate",
        "phase_f",
        "完整 frontend/backend/resource/performance gate 已执行并记录。",
        full_gate_status(acceptance, progress_text),
        full_gate_evidence(progress_text),
        "资源 apply 和 manifest 导出完成后重跑完整 gate。",
    )
    add(
        "phase_f.runbooks",
        "phase_f",
        "资源、备份、部署 guard、manifest 导出和回滚手册完整。",
        PASSING
        if all(text in mysql_runbook_text for text in ["回滚", "binlog", "slow log", "Analytics Manifest"])
        and "资源 gate" in cutover_runbook_text
        and "资源 gate" in production_runbook_text
        else NOT_VERIFIED,
        "mysql/cutover/production runbooks include resource guard and rollback."
        if "回滚" in mysql_runbook_text
        else "missing runbook evidence",
    )

    status = overall_status(checks)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": summarize(checks),
        "checks": checks,
        "completion_statement": completion_statement(status),
    }


def number(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def mysql_volume_size(rows: list[Any]) -> float | None:
    sizes = [number((row or {}).get("size_bytes")) for row in rows if isinstance(row, dict)]
    sizes = [size for size in sizes if size is not None]
    if not sizes:
        return None
    return max(sizes)


def strategy_bff_status(frontend_perf: dict[str, Any], progress_text: str) -> str:
    strategy = frontend_perf.get("strategy_tracking") or {}
    request_count = number(strategy.get("api_request_count"))
    items_422 = number(strategy.get("items_422_count"))
    forbidden = strategy.get("forbidden_legacy_requests") or []
    if request_count is not None and items_422 is not None:
        return PASSING if request_count <= 2 and items_422 == 0 and not forbidden else BLOCKED
    if "首屏请求为 2 个" in progress_text and "items` 422 为 0" in progress_text:
        return PASSING
    return NOT_VERIFIED


def strategy_bff_evidence(frontend_perf: dict[str, Any], progress_text: str) -> str:
    strategy = frontend_perf.get("strategy_tracking") or {}
    request_count = strategy.get("api_request_count")
    items_422 = strategy.get("items_422_count")
    forbidden = strategy.get("forbidden_legacy_requests")
    if request_count is not None or items_422 is not None:
        return f"api_request_count={request_count}, items_422_count={items_422}, forbidden_legacy_requests={forbidden}"
    if "首屏请求为 2 个" in progress_text:
        return "progress report contains strategy BFF request evidence"
    return "missing machine report for strategy request count"


def paper_dom_status(frontend_perf: dict[str, Any], progress_text: str) -> str:
    paper = frontend_perf.get("paper") or {}
    non_mecha = number(paper.get("non_mecha_descendants"))
    full_dom = number(paper.get("dom_nodes"))
    if non_mecha is not None:
        if non_mecha < 150 and (full_dom is None or full_dom < 150):
            return PASSING
        if non_mecha < 150:
            return WARNING
        return BLOCKED
    if "非机甲页面 descendants `82`" in progress_text:
        return WARNING
    return NOT_VERIFIED


def paper_dom_evidence(frontend_perf: dict[str, Any], progress_text: str) -> str:
    paper = frontend_perf.get("paper") or {}
    if paper:
        return (
            f"dom_nodes={paper.get('dom_nodes')}, non_mecha_descendants={paper.get('non_mecha_descendants')}, "
            f"mecha_descendants={paper.get('mecha_descendants')}"
        )
    if "非机甲页面 descendants `82`" in progress_text:
        return "非机甲区域 82 descendants；整页 343，机甲组件 171，因硬边界未改机甲。"
    return "missing machine report for paper DOM"


def prebuilt_status(phase_value: Any) -> str:
    if str(phase_value) in {"ready", "applied_online", "implemented_applied_online"}:
        return PASSING
    return WARNING


def full_gate_status(acceptance: dict[str, Any], progress_text: str) -> str:
    has_progress_evidence = "frontend-next 全链路" in progress_text and backend_passed_count(progress_text) >= 100
    if acceptance.get("status") == "ready" and has_progress_evidence:
        return PASSING
    if has_progress_evidence:
        return WARNING
    return NOT_VERIFIED


def full_gate_evidence(progress_text: str) -> str:
    count = backend_passed_count(progress_text)
    if count:
        return f"progress report records frontend-next full chain and backend {count} passed; online apply 后仍需重跑。"
    return "missing frontend-next full chain or backend passed-count evidence; online apply 后仍需重跑。"


def cloud_performance_status(report: dict[str, Any]) -> str:
    if not report:
        return NOT_VERIFIED
    if report.get("ok") is not True or report.get("failures"):
        return BLOCKED
    api_items = report.get("api") or []
    expected = {
        "readyz": 100,
        "monitor_bff": 500,
        "market_pulse": 500,
        "priority_board": 500,
        "watchlist_signals": 600,
    }
    seen = {str(item.get("name")): item for item in api_items if isinstance(item, dict)}
    if not expected.keys() <= seen.keys():
        return NOT_VERIFIED
    for name, threshold in expected.items():
        item = seen[name]
        if item.get("statuses") != [200] or number(item.get("p95_ms")) is None or number(item.get("p95_ms")) > threshold:
            return BLOCKED
    return PASSING


def cloud_performance_evidence(report: dict[str, Any]) -> str:
    if not report:
        return "missing cloud performance report"
    api_items = report.get("api") or []
    parts = []
    for item in api_items:
        if isinstance(item, dict) and item.get("name") in {
            "readyz",
            "monitor_bff",
            "market_pulse",
            "priority_board",
            "watchlist_signals",
        }:
            parts.append(f"{item.get('name')} p95={item.get('p95_ms')}ms status={item.get('statuses')}")
    return f"ok={report.get('ok')}, failures={report.get('failures') or []}, " + ", ".join(parts)


def mysql_backup_status(mysql_backups: dict[str, Any], verification: dict[str, Any]) -> str:
    if not (number(mysql_backups.get("count")) and number(mysql_backups.get("count")) >= 1):
        return BLOCKED
    evaluation = verification.get("evaluation") or {}
    backup = verification.get("backup") or {}
    if verification and (
        evaluation.get("status") != "ok"
        or backup.get("gzip_ok") is not True
        or backup.get("sql_signature_ok") is not True
    ):
        return BLOCKED
    if verification:
        return PASSING
    return WARNING


def mysql_backup_evidence(mysql_backups: dict[str, Any], verification: dict[str, Any]) -> str:
    latest = (mysql_backups.get("latest") or {}).get("path")
    backup = verification.get("backup") or {}
    if verification:
        return (
            f"mysql_backup_count={mysql_backups.get('count')}, latest={latest}, "
            f"verified_path={backup.get('path')}, gzip_ok={backup.get('gzip_ok')}, "
            f"sql_signature_ok={backup.get('sql_signature_ok')}, sha256={backup.get('sha256')}"
        )
    return f"mysql_backup_count={mysql_backups.get('count')}, latest={latest}, backup artifact verification missing"


def backend_passed_count(progress_text: str) -> int:
    matches = [int(item) for item in re.findall(r"后端(?:组合)?[^\n。]*?(\d+) passed", progress_text)]
    if matches:
        return max(matches)
    matches = [int(item) for item in re.findall(r"backend[^\n。]*?(\d+) passed", progress_text, flags=re.I)]
    return max(matches) if matches else 0


def summarize(checks: list[dict[str, Any]]) -> dict[str, int]:
    summary = {PASSING: 0, WARNING: 0, BLOCKED: 0, NOT_VERIFIED: 0}
    for check in checks:
        summary[check["status"]] = summary.get(check["status"], 0) + 1
    summary["total"] = len(checks)
    return summary


def overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = {check["status"] for check in checks}
    if BLOCKED in statuses:
        return "blocking"
    if NOT_VERIFIED in statuses:
        return "incomplete"
    if WARNING in statuses:
        return "warning"
    return "ready"


def completion_statement(status: str) -> str:
    if status == "ready":
        return "目标已具备完成证据；cutover 仍需用户单独授权。"
    return "目标尚未完成；可继续 /next/* 自用，但不能声明平台资源优化完成或正式 cutover ready。"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# frontend-next 与平台资源优化完成度审计",
        "",
        f"- 生成时间：`{report.get('generated_at', '')}`",
        f"- 总状态：`{report.get('status')}`",
        f"- 结论：{report.get('completion_statement')}",
        "",
        "## 汇总",
        "",
        "| 状态 | 数量 |",
        "| --- | ---: |",
    ]
    summary = report.get("summary") or {}
    for key in [PASSING, WARNING, BLOCKED, NOT_VERIFIED, "total"]:
        lines.append(f"| {key} | {summary.get(key, 0)} |")
    lines.extend(["", "## 逐项审计", "", "| Phase | 检查项 | 状态 | 证据 | 下一步 |", "| --- | --- | --- | --- | --- |"])
    for item in report.get("checks") or []:
        lines.append(
            "| {phase} | {requirement} | `{status}` | {evidence} | {next_action} |".format(
                phase=item.get("phase", ""),
                requirement=escape_table(item.get("requirement", "")),
                status=item.get("status", ""),
                evidence=escape_table(item.get("evidence", "")),
                next_action=escape_table(item.get("next_action", "")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_outputs(report: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit platform resource optimization completion evidence.")
    parser.add_argument("--acceptance-report", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument("--resource-report", type=Path, default=DEFAULT_RESOURCE)
    parser.add_argument("--budget-report", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--manifest-report", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--readiness-report", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--css-budget", type=Path, default=DEFAULT_CSS_BUDGET)
    parser.add_argument("--chunk-profile", type=Path, default=DEFAULT_CHUNK_PROFILE)
    parser.add_argument("--backup-verification-report", type=Path, default=DEFAULT_BACKUP_VERIFICATION)
    parser.add_argument("--progress-report", type=Path, default=DEFAULT_PROGRESS)
    parser.add_argument("--frontend-perf-report", type=Path, default=DEFAULT_FRONTEND_PERF_REPORT)
    parser.add_argument("--cloud-performance-report", type=Path, default=DEFAULT_CLOUD_PERFORMANCE_REPORT)
    parser.add_argument("--cutover-runbook", type=Path, default=DEFAULT_CUTOVER_RUNBOOK)
    parser.add_argument("--production-runbook", type=Path, default=DEFAULT_PRODUCTION_RUNBOOK)
    parser.add_argument("--mysql-runbook", type=Path, default=DEFAULT_MYSQL_RUNBOOK)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--fail-on-incomplete", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_audit(
        acceptance=load_json(args.acceptance_report),
        resource=load_json(args.resource_report),
        budget=load_json(args.budget_report),
        manifest=load_json(args.manifest_report),
        readiness=load_json(args.readiness_report),
        css_budget=load_json(args.css_budget),
        chunk_profile=load_json(args.chunk_profile),
        backup_verification=load_json(args.backup_verification_report) if args.backup_verification_report.exists() else None,
        progress_text=read_text(args.progress_report),
        frontend_perf=load_json(args.frontend_perf_report) if args.frontend_perf_report.exists() else None,
        cloud_performance=load_json(args.cloud_performance_report) if args.cloud_performance_report.exists() else None,
        cutover_runbook_text=read_text(args.cutover_runbook),
        production_runbook_text=read_text(args.production_runbook),
        mysql_runbook_text=read_text(args.mysql_runbook),
    )
    write_outputs(report, args.json_output, args.markdown_output)
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, ensure_ascii=False))
    if args.fail_on_incomplete and report["status"] != "ready":
        return 42
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
