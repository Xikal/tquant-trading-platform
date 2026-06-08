# 平台资源优化运维窗口执行计划

- 生成时间：`2026-06-08T00:56:04.981393+00:00`
- 日期标签：`2026-06-08`
- 来源 readiness 状态：`blocking`
- 来源阻断项：manifest:manifest_blocked_count=9
- 安全边界：本文件只生成命令计划；不执行命令、不部署、不切流、不清 MySQL 源表、不删 Docker volumes。
- 执行策略：在本地仓库根目录顺序执行命令；命令内显式 SSH 到云服务器的步骤在远端项目目录运行；任一命令失败即停止。

## 执行上下文

- 本地工作目录：`/Users/j/Documents/gupiao`
- 远端主机：`ubuntu@43.143.243.97`
- 远端项目目录：`/home/ubuntu/gupiao-upload`
- MySQL slow log：`/var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-slow.log`
- 失败策略：Run commands in order and stop on the first non-zero exit.

## 步骤

### 1. 只读复验资源与 readiness

- Step ID：`preflight_resource_readiness`
- 需要人工执行：`False`
- 破坏性动作：`False`

```bash
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; test -f scripts/install_platform_resource_limits.py && test -f scripts/submit_analytics_manifest_exports.py && test -f docker-compose.mysql.yml && test -f deploy/docker/daemon-resource.json'
python3 scripts/collect_platform_resource_report.py --ssh-host 43.143.243.97 --ssh-user ubuntu --ssh-key /Users/j/Downloads/gupiao.pem --json-output docs/reports/platform-resource-baseline-2026-06-08.json --markdown-output docs/reports/platform-resource-baseline-2026-06-08.md
python3 scripts/verify_mysql_backup_artifact.py --ssh-host 43.143.243.97 --ssh-user ubuntu --ssh-key /Users/j/Downloads/gupiao.pem --json-output docs/reports/platform-mysql-backup-verification-2026-06-08.json --markdown-output docs/reports/platform-mysql-backup-verification-2026-06-08.md --fail-on-blocking
python3 scripts/verify_platform_budget.py --ssh-host 43.143.243.97 --ssh-user ubuntu --ssh-key /Users/j/Downloads/gupiao.pem --project-dir /home/ubuntu/gupiao-upload --json-output docs/reports/platform-budget-2026-06-08.json --markdown-output docs/reports/platform-budget-2026-06-08.md
python3 scripts/verify_platform_optimization_readiness.py --backup-verification-report docs/reports/platform-mysql-backup-verification-2026-06-08.json --json-output docs/reports/platform-optimization-readiness-2026-06-08.json --markdown-output docs/reports/platform-optimization-readiness-2026-06-08.md
```

### 2. 预演资源上限配置安装

- Step ID：`resource_limits_dry_run`
- 需要人工执行：`False`
- 破坏性动作：`False`

```bash
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; python3 scripts/install_platform_resource_limits.py --backup-root /tmp/tquant-resource-backups-dry-run --json-output docs/reports/platform-resource-limits-dry-run-2026-06-08.json'
scp -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97:/home/ubuntu/gupiao-upload/docs/reports/platform-resource-limits-dry-run-2026-06-08.json docs/reports/platform-resource-limits-dry-run-2026-06-08.json
```

### 3. 低峰窗口安装资源上限配置并重启相关服务

- Step ID：`resource_limits_apply`
- 需要人工执行：`True`
- 破坏性动作：`False`
- 回滚/取消：SSH to ubuntu@43.143.243.97, restore /etc/tquant-resource-backups/<timestamp>/ files, then restart the same services.

```bash
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; sudo python3 scripts/install_platform_resource_limits.py --apply --restart-hints --json-output docs/reports/platform-resource-limits-apply-2026-06-08.json'
scp -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97:/home/ubuntu/gupiao-upload/docs/reports/platform-resource-limits-apply-2026-06-08.json docs/reports/platform-resource-limits-apply-2026-06-08.json
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; TS=$(date -u +%Y%m%d%H%M%S); sudo mkdir -p /home/ubuntu/mysql-backups/slow-log; if sudo test -f '"'"'/var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-slow.log'"'"'; then sudo cp -a '"'"'/var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-slow.log'"'"' /home/ubuntu/mysql-backups/slow-log/mysql-slow-$TS.log; sudo gzip /home/ubuntu/mysql-backups/slow-log/mysql-slow-$TS.log; fi'
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; sudo systemctl restart docker'
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; sudo systemctl restart systemd-journald'
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; sudo systemctl restart buildkit || true'
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; sudo logrotate -f /etc/logrotate.d/tquant-mysql-slow-log'
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; sudo docker compose -f docker-compose.mysql.yml up -d mysql'
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; sudo docker compose -f docker-compose.mysql.yml up -d app runtime-scheduler runtime-worker backtest-worker analytics-worker'
```

### 4. 资源配置生效后复验

- Step ID：`post_resource_verify`
- 需要人工执行：`False`
- 破坏性动作：`False`

```bash
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; curl -f http://127.0.0.1:18090/readyz'
python3 scripts/collect_platform_resource_report.py --ssh-host 43.143.243.97 --ssh-user ubuntu --ssh-key /Users/j/Downloads/gupiao.pem --json-output docs/reports/platform-resource-after-limits-2026-06-08.json --markdown-output docs/reports/platform-resource-after-limits-2026-06-08.md
python3 scripts/verify_platform_budget.py --ssh-host 43.143.243.97 --ssh-user ubuntu --ssh-key /Users/j/Downloads/gupiao.pem --project-dir /home/ubuntu/gupiao-upload --json-output docs/reports/platform-budget-after-limits-2026-06-08.json --markdown-output docs/reports/platform-budget-after-limits-2026-06-08.md
python3 scripts/verify_mysql_backup_artifact.py --ssh-host 43.143.243.97 --ssh-user ubuntu --ssh-key /Users/j/Downloads/gupiao.pem --json-output docs/reports/platform-mysql-backup-verification-after-limits-2026-06-08.json --markdown-output docs/reports/platform-mysql-backup-verification-after-limits-2026-06-08.md --fail-on-blocking
```

### 5. 只读复验 Analytics manifest 并生成导出计划

- Step ID：`analytics_manifest_preflight`
- 需要人工执行：`False`
- 破坏性动作：`False`

```bash
python3 scripts/verify_analytics_manifests.py --ssh-host 43.143.243.97 --ssh-user ubuntu --ssh-key /Users/j/Downloads/gupiao.pem --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics --json-output docs/reports/platform-analytics-manifests-2026-06-08.json --markdown-output docs/reports/platform-analytics-manifests-2026-06-08.md
python3 scripts/plan_analytics_manifest_exports.py --manifest-report docs/reports/platform-analytics-manifests-2026-06-08.json --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics --end-date 2026-06-08 --json-output docs/reports/platform-analytics-export-plan-2026-06-08.json --markdown-output docs/reports/platform-analytics-export-plan-2026-06-08.md
python3 scripts/submit_analytics_manifest_exports.py --export-plan docs/reports/platform-analytics-export-plan-2026-06-08.json --json-output docs/reports/platform-analytics-export-submission-dry-run-2026-06-08.json --markdown-output docs/reports/platform-analytics-export-submission-dry-run-2026-06-08.md
```

### 6. 显式入队缺失 manifest 导出任务

- Step ID：`analytics_manifest_enqueue`
- 需要人工执行：`True`
- 破坏性动作：`False`
- 回滚/取消：Cancel queued/running runtime task ids via POST /api/runtime-tasks/<task_id>/cancel on the remote server.

```bash
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; mkdir -p docs/reports'
scp -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no docs/reports/platform-analytics-export-plan-2026-06-08.json ubuntu@43.143.243.97:/home/ubuntu/gupiao-upload/docs/reports/platform-analytics-export-plan-2026-06-08.json
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; PYTHONPATH=backend:. python3 scripts/submit_analytics_manifest_exports.py --export-plan docs/reports/platform-analytics-export-plan-2026-06-08.json --apply --confirm-apply submit-analytics-manifest-exports --json-output docs/reports/platform-analytics-export-submission-apply-2026-06-08.json --markdown-output docs/reports/platform-analytics-export-submission-apply-2026-06-08.md'
scp -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97:/home/ubuntu/gupiao-upload/docs/reports/platform-analytics-export-submission-apply-2026-06-08.json docs/reports/platform-analytics-export-submission-apply-2026-06-08.json
scp -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97:/home/ubuntu/gupiao-upload/docs/reports/platform-analytics-export-submission-apply-2026-06-08.md docs/reports/platform-analytics-export-submission-apply-2026-06-08.md
```

### 7. 观察 analytics worker 与任务队列

- Step ID：`analytics_worker_observe`
- 需要人工执行：`False`
- 破坏性动作：`False`

```bash
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; set -a; test ! -f .env || . ./.env; set +a; test -n "${ADMIN_API_TOKEN:-${FRONTEND_ADMIN_TOKEN:-}}" && curl -fsS http://127.0.0.1:18090/api/runtime-tasks/summary -H "Authorization: Bearer ${ADMIN_API_TOKEN:-${FRONTEND_ADMIN_TOKEN:-}}" | python3 -m json.tool'
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; set -a; test ! -f .env || . ./.env; set +a; test -n "${ADMIN_API_TOKEN:-${FRONTEND_ADMIN_TOKEN:-}}" && curl -fsS http://127.0.0.1:18090/api/runtime-tasks/workers -H "Authorization: Bearer ${ADMIN_API_TOKEN:-${FRONTEND_ADMIN_TOKEN:-}}" | python3 -m json.tool'
ssh -i '/Users/j/Downloads/gupiao.pem' -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@43.143.243.97 'set -eu; cd '"'"'/home/ubuntu/gupiao-upload'"'"'; set -a; test ! -f .env || . ./.env; set +a; test -n "${ADMIN_API_TOKEN:-${FRONTEND_ADMIN_TOKEN:-}}" && curl -fsS "http://127.0.0.1:18090/api/runtime-tasks/failures?limit=20" -H "Authorization: Bearer ${ADMIN_API_TOKEN:-${FRONTEND_ADMIN_TOKEN:-}}" | python3 -m json.tool'
```

### 8. 导出完成后复验 manifest

- Step ID：`analytics_manifest_post_verify`
- 需要人工执行：`False`
- 破坏性动作：`False`

```bash
python3 scripts/verify_analytics_manifests.py --ssh-host 43.143.243.97 --ssh-user ubuntu --ssh-key /Users/j/Downloads/gupiao.pem --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics --json-output docs/reports/platform-analytics-manifests-after-export-2026-06-08.json --markdown-output docs/reports/platform-analytics-manifests-after-export-2026-06-08.md --fail-on-blocking
python3 scripts/plan_analytics_manifest_exports.py --manifest-report docs/reports/platform-analytics-manifests-after-export-2026-06-08.json --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics --end-date 2026-06-08 --json-output docs/reports/platform-analytics-export-plan-after-export-2026-06-08.json --markdown-output docs/reports/platform-analytics-export-plan-after-export-2026-06-08.md
python3 scripts/submit_analytics_manifest_exports.py --export-plan docs/reports/platform-analytics-export-plan-after-export-2026-06-08.json --json-output docs/reports/platform-analytics-export-submission-dry-run-after-export-2026-06-08.json --markdown-output docs/reports/platform-analytics-export-submission-dry-run-after-export-2026-06-08.md
python3 scripts/verify_platform_optimization_readiness.py --resource-report docs/reports/platform-resource-after-limits-2026-06-08.json --budget-report docs/reports/platform-budget-after-limits-2026-06-08.json --backup-verification-report docs/reports/platform-mysql-backup-verification-after-limits-2026-06-08.json --manifest-report docs/reports/platform-analytics-manifests-after-export-2026-06-08.json --export-plan docs/reports/platform-analytics-export-plan-after-export-2026-06-08.json --submission-report docs/reports/platform-analytics-export-submission-dry-run-after-export-2026-06-08.json --json-output docs/reports/platform-optimization-readiness-after-export-2026-06-08.json --markdown-output docs/reports/platform-optimization-readiness-after-export-2026-06-08.md --fail-on-blocking
```

### 9. 最终性能与全量验收 gate

- Step ID：`final_validation_gates`
- 需要人工执行：`False`
- 破坏性动作：`False`

```bash
./scripts/quick_cloud_deploy.sh --verify-only --performance-verify --performance-rounds 3 --performance-samples 8 --host 43.143.243.97 --user ubuntu --key /Users/j/Downloads/gupiao.pem --port 18090 --public-base-url http://43.143.243.97:18090
(cd frontend-next && npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build && npm run e2e && npm run request:trace && npm run screenshot:parity && npm run visual:consistency && npm run perf:compare && npm run css:budget && npm run css:unused-report)
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_platform_resource_report.py backend/tests/test_platform_budget_verifier.py backend/tests/test_analytics_manifest_verifier.py backend/tests/test_analytics_manifest_export_plan.py backend/tests/test_analytics_manifest_export_submitter.py backend/tests/test_platform_optimization_readiness.py backend/tests/test_platform_maintenance_window_plan.py backend/tests/test_platform_resource_optimization_acceptance.py backend/tests/test_platform_resource_optimization_completion_audit.py backend/tests/test_analytics_layer.py backend/tests/test_analytics_manifest_lifecycle.py backend/tests/test_runtime_task_queue.py backend/tests/test_backtest_v2_worker_persistence.py backend/tests/test_cloud_performance_script.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_bff_strategy_workspace.py backend/tests/test_bff_routes.py::test_strategy_workspace_uses_bff_contract backend/tests/test_contract_first_openapi.py -q
BACKEND_PYTHON=backend/.venv/bin/python python3 scripts/verify_go_rust_performance_acceptance.py
test -n "$(ls -t docs/reports/gupiao-cloud-performance-*.json | head -1)"
python3 scripts/render_platform_resource_optimization_acceptance.py --resource-report docs/reports/platform-resource-after-limits-2026-06-08.json --budget-report docs/reports/platform-budget-after-limits-2026-06-08.json --manifest-report docs/reports/platform-analytics-manifests-after-export-2026-06-08.json --readiness-report docs/reports/platform-optimization-readiness-after-export-2026-06-08.json --backup-verification-report docs/reports/platform-mysql-backup-verification-after-limits-2026-06-08.json --cloud-performance-report "$(ls -t docs/reports/gupiao-cloud-performance-*.json | head -1)" --json-output docs/reports/platform-resource-optimization-acceptance-after-export-2026-06-08.json --markdown-output docs/reports/platform-resource-optimization-acceptance-after-export-2026-06-08.md
python3 scripts/audit_platform_resource_optimization_completion.py --acceptance-report docs/reports/platform-resource-optimization-acceptance-after-export-2026-06-08.json --resource-report docs/reports/platform-resource-after-limits-2026-06-08.json --budget-report docs/reports/platform-budget-after-limits-2026-06-08.json --manifest-report docs/reports/platform-analytics-manifests-after-export-2026-06-08.json --readiness-report docs/reports/platform-optimization-readiness-after-export-2026-06-08.json --backup-verification-report docs/reports/platform-mysql-backup-verification-after-limits-2026-06-08.json --cloud-performance-report "$(ls -t docs/reports/gupiao-cloud-performance-*.json | head -1)" --json-output docs/reports/platform-resource-optimization-completion-audit-after-export-2026-06-08.json --markdown-output docs/reports/platform-resource-optimization-completion-audit-after-export-2026-06-08.md --fail-on-incomplete
git diff --check
git diff --name-only | rg '(^|/)strategy_policy\.py$|^frontend/' && exit 1 || true
git status --short
```
