#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_READINESS_REPORT = Path("docs/reports/platform-optimization-readiness-2026-06-08.json")
DEFAULT_EXPORT_PLAN = Path("docs/reports/platform-analytics-export-plan-2026-06-08.json")
DEFAULT_SSH_HOST = "43.143.243.97"
DEFAULT_SSH_USER = "ubuntu"
DEFAULT_SSH_KEY = "/Users/j/Downloads/gupiao.pem"
DEFAULT_REMOTE_PROJECT_DIR = "/home/ubuntu/gupiao-upload"
DEFAULT_PUBLIC_BASE_URL = "http://43.143.243.97:18090"
DEFAULT_APP_PORT = "18090"
DEFAULT_MYSQL_SLOW_LOG = "/var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-slow.log"
DEFAULT_TASK_OUTPUT_ROOT = "/app/backend/data/analytics"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_maintenance_plan(
    *,
    readiness_report: dict[str, Any],
    export_plan: dict[str, Any],
    date_tag: str,
    analytics_root: str,
    task_output_root: str = DEFAULT_TASK_OUTPUT_ROOT,
    ssh_host: str = DEFAULT_SSH_HOST,
    ssh_user: str = DEFAULT_SSH_USER,
    ssh_key: str = DEFAULT_SSH_KEY,
    remote_project_dir: str = DEFAULT_REMOTE_PROJECT_DIR,
    public_base_url: str = DEFAULT_PUBLIC_BASE_URL,
    app_port: str = DEFAULT_APP_PORT,
    mysql_slow_log: str = DEFAULT_MYSQL_SLOW_LOG,
) -> dict[str, Any]:
    required_tasks = list((export_plan.get("summary") or {}).get("required_tasks") or [])
    selected_datasets = list((export_plan.get("summary") or {}).get("blocked_datasets") or [])
    ssh = ssh_command_prefix(ssh_host=ssh_host, ssh_user=ssh_user, ssh_key=ssh_key)
    scp = scp_command_prefix(ssh_key=ssh_key)
    remote = lambda command: remote_command(
        command,
        ssh=ssh,
        remote_project_dir=remote_project_dir,
    )
    remote_path = lambda path: f"{ssh_user}@{ssh_host}:{remote_project_dir.rstrip('/')}/{path}"
    ssh_args = f"--ssh-host {ssh_host} --ssh-user {ssh_user} --ssh-key {ssh_key}"
    steps = [
        step(
            "preflight_resource_readiness",
            "只读复验资源与 readiness",
            [
                remote("test -f scripts/install_platform_resource_limits.py && test -f scripts/submit_analytics_manifest_exports.py && test -f docker-compose.mysql.yml && test -f deploy/docker/daemon-resource.json"),
                f"python3 scripts/collect_platform_resource_report.py {ssh_args} --json-output docs/reports/platform-resource-baseline-${{DATE}}.json --markdown-output docs/reports/platform-resource-baseline-${{DATE}}.md",
                f"python3 scripts/verify_mysql_backup_artifact.py {ssh_args} --json-output docs/reports/platform-mysql-backup-verification-${{DATE}}.json --markdown-output docs/reports/platform-mysql-backup-verification-${{DATE}}.md --fail-on-blocking",
                f"python3 scripts/verify_platform_budget.py {ssh_args} --project-dir {remote_project_dir} --json-output docs/reports/platform-budget-${{DATE}}.json --markdown-output docs/reports/platform-budget-${{DATE}}.md",
                "python3 scripts/verify_platform_optimization_readiness.py --backup-verification-report docs/reports/platform-mysql-backup-verification-${DATE}.json --json-output docs/reports/platform-optimization-readiness-${DATE}.json --markdown-output docs/reports/platform-optimization-readiness-${DATE}.md",
            ],
            destructive=False,
        ),
        step(
            "resource_limits_dry_run",
            "预演资源上限配置安装",
            [
                remote("python3 scripts/install_platform_resource_limits.py --backup-root /tmp/tquant-resource-backups-dry-run --json-output docs/reports/platform-resource-limits-dry-run-${DATE}.json"),
                f"{scp} {remote_path('docs/reports/platform-resource-limits-dry-run-${DATE}.json')} docs/reports/platform-resource-limits-dry-run-${{DATE}}.json",
            ],
            destructive=False,
        ),
        step(
            "resource_limits_apply",
            "低峰窗口安装资源上限配置并重启相关服务",
            [
                remote("sudo python3 scripts/install_platform_resource_limits.py --apply --restart-hints --json-output docs/reports/platform-resource-limits-apply-${DATE}.json"),
                f"{scp} {remote_path('docs/reports/platform-resource-limits-apply-${DATE}.json')} docs/reports/platform-resource-limits-apply-${{DATE}}.json",
                remote(slow_log_backup_command(mysql_slow_log)),
                remote("sudo systemctl restart docker"),
                remote("sudo systemctl restart systemd-journald"),
                remote("sudo systemctl restart buildkit || true"),
                remote("sudo logrotate -f /etc/logrotate.d/tquant-mysql-slow-log"),
                remote("sudo docker compose -f docker-compose.mysql.yml up -d mysql"),
                remote("sudo docker compose -f docker-compose.mysql.yml up -d app runtime-scheduler runtime-worker analytics-worker"),
            ],
            destructive=False,
            requires_operator=True,
            rollback=f"SSH to {ssh_user}@{ssh_host}, restore /etc/tquant-resource-backups/<timestamp>/ files, then restart the same services.",
        ),
        step(
            "post_resource_verify",
            "资源配置生效后复验",
            [
                remote(f"curl -f http://127.0.0.1:{app_port}/readyz"),
                f"python3 scripts/collect_platform_resource_report.py {ssh_args} --json-output docs/reports/platform-resource-after-limits-${{DATE}}.json --markdown-output docs/reports/platform-resource-after-limits-${{DATE}}.md",
                f"python3 scripts/verify_platform_budget.py {ssh_args} --project-dir {remote_project_dir} --json-output docs/reports/platform-budget-after-limits-${{DATE}}.json --markdown-output docs/reports/platform-budget-after-limits-${{DATE}}.md",
                f"python3 scripts/verify_mysql_backup_artifact.py {ssh_args} --json-output docs/reports/platform-mysql-backup-verification-after-limits-${{DATE}}.json --markdown-output docs/reports/platform-mysql-backup-verification-after-limits-${{DATE}}.md --fail-on-blocking",
            ],
            destructive=False,
        ),
        step(
            "analytics_manifest_preflight",
            "只读复验 Analytics manifest 并生成导出计划",
            [
                f"python3 scripts/verify_analytics_manifests.py {ssh_args} --analytics-root {analytics_root} --json-output docs/reports/platform-analytics-manifests-${{DATE}}.json --markdown-output docs/reports/platform-analytics-manifests-${{DATE}}.md",
                f"python3 scripts/plan_analytics_manifest_exports.py --manifest-report docs/reports/platform-analytics-manifests-${{DATE}}.json --analytics-root {analytics_root} --task-output-root {task_output_root} --end-date ${{DATE}} --json-output docs/reports/platform-analytics-export-plan-${{DATE}}.json --markdown-output docs/reports/platform-analytics-export-plan-${{DATE}}.md",
                "python3 scripts/submit_analytics_manifest_exports.py --export-plan docs/reports/platform-analytics-export-plan-${DATE}.json --json-output docs/reports/platform-analytics-export-submission-dry-run-${DATE}.json --markdown-output docs/reports/platform-analytics-export-submission-dry-run-${DATE}.md",
            ],
            destructive=False,
        ),
        step(
            "analytics_manifest_enqueue",
            "显式入队缺失 manifest 导出任务",
            [
                remote("mkdir -p docs/reports"),
                f"{scp} docs/reports/platform-analytics-export-plan-${{DATE}}.json {remote_path('docs/reports/platform-analytics-export-plan-${DATE}.json')}",
                remote("PYTHONPATH=backend:. python3 scripts/submit_analytics_manifest_exports.py --export-plan docs/reports/platform-analytics-export-plan-${DATE}.json --apply --confirm-apply submit-analytics-manifest-exports --json-output docs/reports/platform-analytics-export-submission-apply-${DATE}.json --markdown-output docs/reports/platform-analytics-export-submission-apply-${DATE}.md"),
                f"{scp} {remote_path('docs/reports/platform-analytics-export-submission-apply-${DATE}.json')} docs/reports/platform-analytics-export-submission-apply-${{DATE}}.json",
                f"{scp} {remote_path('docs/reports/platform-analytics-export-submission-apply-${DATE}.md')} docs/reports/platform-analytics-export-submission-apply-${{DATE}}.md",
            ],
            destructive=False,
            requires_operator=True,
            rollback="Cancel queued/running runtime task ids via POST /api/runtime-tasks/<task_id>/cancel on the remote server.",
        ),
        step(
            "analytics_worker_observe",
            "观察 analytics worker 与任务队列",
            [
                remote(f'{remote_env_prefix()} && curl -fsS http://127.0.0.1:{app_port}/api/runtime-tasks/summary -H "Authorization: Bearer ${{ADMIN_API_TOKEN:-${{FRONTEND_ADMIN_TOKEN:-}}}}" | python3 -m json.tool'),
                remote(f'{remote_env_prefix()} && curl -fsS http://127.0.0.1:{app_port}/api/runtime-tasks/workers -H "Authorization: Bearer ${{ADMIN_API_TOKEN:-${{FRONTEND_ADMIN_TOKEN:-}}}}" | python3 -m json.tool'),
                remote(f'{remote_env_prefix()} && curl -fsS "http://127.0.0.1:{app_port}/api/runtime-tasks/failures?limit=20" -H "Authorization: Bearer ${{ADMIN_API_TOKEN:-${{FRONTEND_ADMIN_TOKEN:-}}}}" | python3 -m json.tool'),
            ],
            destructive=False,
        ),
        step(
            "analytics_manifest_post_verify",
            "导出完成后复验 manifest",
            [
                f"python3 scripts/verify_analytics_manifests.py {ssh_args} --analytics-root {analytics_root} --json-output docs/reports/platform-analytics-manifests-after-export-${{DATE}}.json --markdown-output docs/reports/platform-analytics-manifests-after-export-${{DATE}}.md --fail-on-blocking",
                f"python3 scripts/plan_analytics_manifest_exports.py --manifest-report docs/reports/platform-analytics-manifests-after-export-${{DATE}}.json --analytics-root {analytics_root} --task-output-root {task_output_root} --end-date ${{DATE}} --json-output docs/reports/platform-analytics-export-plan-after-export-${{DATE}}.json --markdown-output docs/reports/platform-analytics-export-plan-after-export-${{DATE}}.md",
                "python3 scripts/submit_analytics_manifest_exports.py --export-plan docs/reports/platform-analytics-export-plan-after-export-${DATE}.json --json-output docs/reports/platform-analytics-export-submission-dry-run-after-export-${DATE}.json --markdown-output docs/reports/platform-analytics-export-submission-dry-run-after-export-${DATE}.md",
                "python3 scripts/verify_platform_optimization_readiness.py --resource-report docs/reports/platform-resource-after-limits-${DATE}.json --budget-report docs/reports/platform-budget-after-limits-${DATE}.json --backup-verification-report docs/reports/platform-mysql-backup-verification-after-limits-${DATE}.json --manifest-report docs/reports/platform-analytics-manifests-after-export-${DATE}.json --export-plan docs/reports/platform-analytics-export-plan-after-export-${DATE}.json --submission-report docs/reports/platform-analytics-export-submission-dry-run-after-export-${DATE}.json --json-output docs/reports/platform-optimization-readiness-after-export-${DATE}.json --markdown-output docs/reports/platform-optimization-readiness-after-export-${DATE}.md --fail-on-blocking",
            ],
            destructive=False,
        ),
        step(
            "final_validation_gates",
            "最终性能与全量验收 gate",
            [
                f"./scripts/quick_cloud_deploy.sh --verify-only --performance-verify --performance-rounds 3 --performance-samples 8 --host {ssh_host} --user {ssh_user} --key {ssh_key} --port {app_port} --public-base-url {public_base_url}",
                "(cd frontend-next && npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build && npm run e2e && npm run request:trace && npm run screenshot:parity && npm run visual:consistency && npm run perf:compare && npm run css:budget && npm run css:unused-report)",
                "PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_platform_resource_report.py backend/tests/test_platform_budget_verifier.py backend/tests/test_analytics_manifest_verifier.py backend/tests/test_analytics_manifest_export_plan.py backend/tests/test_analytics_manifest_export_submitter.py backend/tests/test_platform_optimization_readiness.py backend/tests/test_platform_maintenance_window_plan.py backend/tests/test_platform_resource_optimization_acceptance.py backend/tests/test_platform_resource_optimization_completion_audit.py backend/tests/test_analytics_layer.py backend/tests/test_analytics_manifest_lifecycle.py backend/tests/test_runtime_task_queue.py backend/tests/test_backtest_v2_worker_persistence.py backend/tests/test_cloud_performance_script.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_bff_strategy_workspace.py backend/tests/test_bff_routes.py::test_strategy_workspace_uses_bff_contract backend/tests/test_contract_first_openapi.py -q",
                "BACKEND_PYTHON=backend/.venv/bin/python python3 scripts/verify_go_rust_performance_acceptance.py",
                'test -n "$(ls -t docs/reports/gupiao-cloud-performance-*.json | head -1)"',
                'python3 scripts/render_platform_resource_optimization_acceptance.py --resource-report docs/reports/platform-resource-after-limits-${DATE}.json --budget-report docs/reports/platform-budget-after-limits-${DATE}.json --manifest-report docs/reports/platform-analytics-manifests-after-export-${DATE}.json --readiness-report docs/reports/platform-optimization-readiness-after-export-${DATE}.json --backup-verification-report docs/reports/platform-mysql-backup-verification-after-limits-${DATE}.json --cloud-performance-report "$(ls -t docs/reports/gupiao-cloud-performance-*.json | head -1)" --json-output docs/reports/platform-resource-optimization-acceptance-after-export-${DATE}.json --markdown-output docs/reports/platform-resource-optimization-acceptance-after-export-${DATE}.md',
                'python3 scripts/audit_platform_resource_optimization_completion.py --acceptance-report docs/reports/platform-resource-optimization-acceptance-after-export-${DATE}.json --resource-report docs/reports/platform-resource-after-limits-${DATE}.json --budget-report docs/reports/platform-budget-after-limits-${DATE}.json --manifest-report docs/reports/platform-analytics-manifests-after-export-${DATE}.json --readiness-report docs/reports/platform-optimization-readiness-after-export-${DATE}.json --backup-verification-report docs/reports/platform-mysql-backup-verification-after-limits-${DATE}.json --cloud-performance-report "$(ls -t docs/reports/gupiao-cloud-performance-*.json | head -1)" --json-output docs/reports/platform-resource-optimization-completion-audit-after-export-${DATE}.json --markdown-output docs/reports/platform-resource-optimization-completion-audit-after-export-${DATE}.md --fail-on-incomplete',
                "git diff --check",
                "git diff --name-only | rg '(^|/)strategy_policy\\.py$|^frontend/' && exit 1 || true",
                "git status --short",
            ],
            destructive=False,
        ),
    ]
    commands = apply_date_tag(steps, date_tag)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_tag": date_tag,
            "analytics_root": analytics_root,
            "task_output_root": task_output_root,
        "execution": {
            "operator_working_directory": "/Users/j/Documents/gupiao",
            "remote_host": ssh_host,
            "remote_user": ssh_user,
            "remote_project_dir": remote_project_dir,
            "ssh_key": ssh_key,
            "public_base_url": public_base_url,
            "app_port": app_port,
            "mysql_slow_log": mysql_slow_log,
            "failure_policy": "Run commands in order and stop on the first non-zero exit.",
        },
        "source_status": (readiness_report.get("evaluation") or {}).get("status"),
        "source_blocking": (readiness_report.get("evaluation") or {}).get("blocking") or [],
        "source_warnings": (readiness_report.get("evaluation") or {}).get("warnings") or [],
        "required_analytics_tasks": required_tasks,
        "selected_datasets": selected_datasets,
        "safety": {
            "does_execute_commands": False,
            "does_deploy": False,
            "does_cutover": False,
            "does_clean_mysql_source_tables": False,
            "does_delete_docker_volumes": False,
            "operator_apply_steps": [item["id"] for item in commands if item.get("requires_operator")],
        },
        "steps": commands,
        "evaluation": {
            "status": "planned",
            "blocking": [],
            "warnings": list((readiness_report.get("evaluation") or {}).get("warnings") or []),
        },
    }


def step(
    step_id: str,
    title: str,
    commands: list[str],
    *,
    destructive: bool,
    requires_operator: bool = False,
    rollback: str = "",
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "commands": commands,
        "destructive": destructive,
        "requires_operator": requires_operator,
        "rollback": rollback,
    }


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def ssh_command_prefix(*, ssh_host: str, ssh_user: str, ssh_key: str) -> str:
    return (
        f"ssh -i {shell_quote(ssh_key)} -o BatchMode=yes -o StrictHostKeyChecking=no "
        f"{ssh_user}@{ssh_host}"
    )


def scp_command_prefix(*, ssh_key: str) -> str:
    return f"scp -i {shell_quote(ssh_key)} -o BatchMode=yes -o StrictHostKeyChecking=no"


def remote_command(command: str, *, ssh: str, remote_project_dir: str) -> str:
    script = f"set -eu; cd {shell_quote(remote_project_dir)}; {command}"
    return f"{ssh} {shell_quote(script)}"


def remote_env_prefix() -> str:
    return (
        "set -a; test ! -f .env || . ./.env; set +a; "
        'test -n "${ADMIN_API_TOKEN:-${FRONTEND_ADMIN_TOKEN:-}}"'
    )


def slow_log_backup_command(mysql_slow_log: str) -> str:
    slow_log = shell_quote(mysql_slow_log)
    return (
        "TS=$(date -u +%Y%m%d%H%M%S); "
        "sudo mkdir -p /home/ubuntu/mysql-backups/slow-log; "
        f"if sudo test -f {slow_log}; then "
        f"sudo cp -a {slow_log} /home/ubuntu/mysql-backups/slow-log/mysql-slow-$TS.log; "
        "sudo gzip /home/ubuntu/mysql-backups/slow-log/mysql-slow-$TS.log; "
        "fi"
    )


def apply_date_tag(steps: list[dict[str, Any]], date_tag: str) -> list[dict[str, Any]]:
    output = []
    for item in steps:
        copied = dict(item)
        copied["commands"] = [command.replace("${DATE}", date_tag) for command in item.get("commands") or []]
        output.append(copied)
    return output


def render_markdown(plan: dict[str, Any]) -> str:
    execution = plan.get("execution") or {}
    lines = [
        "# 平台资源优化运维窗口执行计划",
        "",
        f"- 生成时间：`{plan.get('generated_at', '')}`",
        f"- 日期标签：`{plan.get('date_tag', '')}`",
        f"- 来源 readiness 状态：`{plan.get('source_status', '')}`",
        f"- 来源阻断项：{', '.join(plan.get('source_blocking') or []) or '无'}",
        "- 安全边界：本文件只生成命令计划；不执行命令、不部署、不切流、不清 MySQL 源表、不删 Docker volumes。",
        "- 执行策略：在本地仓库根目录顺序执行命令；命令内显式 SSH 到云服务器的步骤在远端项目目录运行；任一命令失败即停止。",
        "",
        "## 执行上下文",
        "",
        f"- 本地工作目录：`{execution.get('operator_working_directory', '')}`",
            f"- 远端主机：`{execution.get('remote_user', '')}@{execution.get('remote_host', '')}`",
            f"- 远端项目目录：`{execution.get('remote_project_dir', '')}`",
            f"- MySQL slow log：`{execution.get('mysql_slow_log', '')}`",
            f"- 失败策略：{execution.get('failure_policy', '')}",
        "",
        "## 步骤",
        "",
    ]
    for index, item in enumerate(plan.get("steps") or [], start=1):
        lines.extend(
            [
                f"### {index}. {item.get('title')}",
                "",
                f"- Step ID：`{item.get('id')}`",
                f"- 需要人工执行：`{bool(item.get('requires_operator'))}`",
                f"- 破坏性动作：`{bool(item.get('destructive'))}`",
            ]
        )
        if item.get("rollback"):
            lines.append(f"- 回滚/取消：{item.get('rollback')}")
        lines.extend(["", "```bash"])
        lines.extend(item.get("commands") or [])
        lines.extend(["```", ""])
    return "\n".join(lines)


def write_outputs(plan: dict[str, Any], json_output: Path | None, markdown_output: Path | None) -> None:
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(plan), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a safe platform resource optimization maintenance window.")
    parser.add_argument("--readiness-report", type=Path, default=DEFAULT_READINESS_REPORT)
    parser.add_argument("--export-plan", type=Path, default=DEFAULT_EXPORT_PLAN)
    parser.add_argument("--date-tag", default="2026-06-08")
    parser.add_argument("--analytics-root", default="/var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics")
    parser.add_argument("--task-output-root", default=DEFAULT_TASK_OUTPUT_ROOT)
    parser.add_argument("--ssh-host", default=DEFAULT_SSH_HOST)
    parser.add_argument("--ssh-user", default=DEFAULT_SSH_USER)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--remote-project-dir", default=DEFAULT_REMOTE_PROJECT_DIR)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    parser.add_argument("--app-port", default=DEFAULT_APP_PORT)
    parser.add_argument("--mysql-slow-log", default=DEFAULT_MYSQL_SLOW_LOG)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = build_maintenance_plan(
        readiness_report=load_json(args.readiness_report),
        export_plan=load_json(args.export_plan),
        date_tag=str(args.date_tag),
        analytics_root=str(args.analytics_root),
        task_output_root=str(args.task_output_root),
        ssh_host=str(args.ssh_host),
        ssh_user=str(args.ssh_user),
        ssh_key=str(args.ssh_key),
        remote_project_dir=str(args.remote_project_dir),
        public_base_url=str(args.public_base_url),
        app_port=str(args.app_port),
        mysql_slow_log=str(args.mysql_slow_log),
    )
    write_outputs(plan, args.json_output, args.markdown_output)
    print(json.dumps(plan["evaluation"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
