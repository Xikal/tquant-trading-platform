# 剩余 7 项执行状态与授权门报告

- 日期：2026-06-11
- 项目：`/Users/j/Documents/gupiao`
- 当前分支：`codex/phase4-phase5-architecture`
- 已提交 commit：`0f7b6283` (`online stability paper task and legacy frontend cleanup`)
- 执行原则：本轮只完成本地验证与提交；线上部署、重启、生产数据库写入、线上清理、`frontend/` 物理删除均未获明确授权，因此未执行。

## 1. 本地提交前验证

已完成。

| 检查项 | 结果 |
| --- | --- |
| `git status --short` | 提交前仅本批代码、测试、报告和计划文件 |
| diff 范围 | `Dockerfile.prebuilt`、backend readyz/runtime/low-buy、相关测试、审计/实施/计划文档 |
| `strategy_policy.py` | 无 diff |
| `production_scoring.py`、`priority_board.py` | 无 diff |
| `PAPER_RUNTIME_TASKS_ENABLED` | 未新增；仅在计划/报告中作为禁止项出现 |
| `git diff --check` | PASS |
| 部署脚本语法 | `bash -n scripts/deploy_cloud_server.sh scripts/quick_cloud_deploy.sh scripts/one_click_cloud_deploy.sh scripts/prod_preflight.sh` PASS |
| deploy scope 语法 | `python3 -m py_compile scripts/deploy_scope.py` PASS |

测试：

```text
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_low_buy_materialization_priority_board.py \
  backend/tests/test_frontend_next_level1_cutover.py \
  backend/tests/test_bff_routes.py \
  backend/tests/test_bff_monitor_workspace.py \
  backend/tests/test_bff_strategy_workspace.py \
  backend/tests/test_bff_settings_workspace.py \
  backend/tests/test_market_provider_contract.py \
  backend/tests/test_market_quote_cache_refresh.py \
  backend/tests/test_deploy_scope.py \
  backend/tests/test_cloud_deploy_scripts.py -q

150 passed, 1 LibreSSL warning
```

## 2. Git 提交

已完成。

```text
commit 0f7b6283
message: online stability paper task and legacy frontend cleanup
```

提交后 `git status --short` 为 clean。随后本报告作为最终授权门记录单独生成，并将单独提交。

## 3. 线上部署

未执行。原因：部署、切流、容器重启属于硬边界中的生产写操作，当前没有明确授权。

按现有资料，部署入口和线上信息为：

| 项 | 依据 |
| --- | --- |
| 服务器 | `ubuntu@43.143.243.97` |
| SSH key | `/Users/j/Downloads/gupiao.pem` |
| 远端目录 | `/home/ubuntu/gupiao-upload` |
| 主 compose | `docker-compose.mysql.yml` |
| 项目部署脚本 | `scripts/one_click_cloud_deploy.sh`、`scripts/quick_cloud_deploy.sh`、`scripts/deploy_cloud_server.sh` |
| 域名 | `https://weisilianghua.cloud`、`https://www.weisilianghua.cloud` |
| 直连入口 | `http://43.143.243.97:18090` |

建议授权后执行前先输出并确认：

```bash
git rev-parse --short HEAD
./scripts/one_click_cloud_deploy.sh --scope all --host 43.143.243.97 --key /Users/j/Downloads/gupiao.pem
```

影响：

- 会发布 backend/runtime worker/前端镜像或包。
- 会造成受控容器替换或重启。
- 会让 `skipped` runtime task、low-buy 隔离和 readyz timeout 代码在线生效。

回滚：

- 按 `docs/operations/deployment-topology-runbook.md` 回滚上一 release/镜像。
- 若仅 backend/runtime 异常，优先回滚 `app` 与 `runtime-worker`。
- 若 prebuilt artifact 异常，禁用 prebuilt 路径，回常规根 `Dockerfile` 发布。

## 4. 部署后线上验证

未执行。原因：未部署，线上仍未运行 commit `0f7b6283`。

授权部署后建议验证：

```bash
BASE=http://43.143.243.97:18090
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/healthz"
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/readyz"
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/"
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/next/monitor"
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/next/monitor/market"
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/next/strategy-tracking"
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/next/analysis"
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/next/backtest"
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/next/data"
curl -sS -w '\nstatus=%{http_code} time=%{time_total}\n' "$BASE/next/settings"
```

受保护 API 需用线上 `.env` 中的管理 token 或登录态，只读验证：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 '
set -eu
cd /home/ubuntu/gupiao-upload
set -a; test ! -f .env || . ./.env; set +a
TOKEN="${ADMIN_API_TOKEN:-${FRONTEND_ADMIN_TOKEN:-}}"
curl -fsS http://127.0.0.1:18090/api/runtime-tasks/summary -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool
curl -fsS "http://127.0.0.1:18090/api/runtime-tasks/failures?limit=20" -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool
'
```

重点验收：

- `/readyz` 不再长时间挂起。
- removed paper runtime task 进入 `skipped`，failed/retry 不再增长。
- low-buy 非生产策略缺失进入 `skipped_strategies`，生产必需策略缺失仍失败。
- BFF 慢源返回 `partial_errors`，不拖垮核心页面。
- 旧 `frontend/dist`、`frontend-hot`、`frontend-legacy`、`__legacy` 不回流。

## 5. 长时间稳定性观察

未执行。原因：需要线上部署后观察，且完整交易时段观察无法在未部署状态完成。

授权部署后建议观察：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 '
set -eu
cd /home/ubuntu/gupiao-upload
date
uptime
free -m
df -h
df -ih
sudo docker compose -f docker-compose.mysql.yml ps
sudo docker stats --no-stream
sudo docker compose -f docker-compose.mysql.yml logs --tail=200 app
sudo docker compose -f docker-compose.mysql.yml logs --tail=200 runtime-worker
sudo docker compose -f docker-compose.mysql.yml logs --tail=200 runtime-scheduler
sudo docker compose -f docker-compose.mysql.yml logs --tail=120 mysql
sudo docker compose -f docker-compose.mysql.yml logs --tail=120 redis
'
```

观察周期：

- 最低：部署后 1-2 小时。
- 推荐：一个完整交易时段。
- 进一步：24 小时后台任务周期。

## 6. 历史 paper failed task 清理

未执行。原因：生产数据库写操作未授权。

只读盘点建议：

```sql
SELECT task_type, status, COUNT(*) AS count,
       MIN(created_at) AS first_seen,
       MAX(updated_at) AS last_seen
FROM runtime_tasks
WHERE task_type IN (
  'paper_review_report',
  'paper_portfolio_execution_preview',
  'paper_ledger_reconcile_preview'
)
OR task_type LIKE 'paper\_%'
GROUP BY task_type, status
ORDER BY count DESC;
```

授权后的推荐写入方案：

```sql
UPDATE runtime_tasks
SET status = 'skipped',
    error_message = '',
    run_after = NULL,
    locked_by = '',
    locked_at = NULL,
    active_idempotency_key = NULL,
    progress_pct = 100,
    finished_at = COALESCE(finished_at, NOW()),
    result_json = JSON_OBJECT(
      'ok', true,
      'skipped', true,
      'reason', 'removed_feature',
      'feature', 'paper_trading',
      'status', 'skipped_removed_feature',
      'cleanup_source', 'manual_authorized_cleanup_2026_06_11'
    )
WHERE status IN ('failed', 'queued')
  AND (
    task_type IN (
      'paper_review_report',
      'paper_portfolio_execution_preview',
      'paper_ledger_reconcile_preview'
    )
    OR task_type LIKE 'paper\_%'
  );
```

影响：

- 降低 failed/retry 噪音。
- 不删除历史业务表和样本。
- 修改 `runtime_tasks` 行，需要备份或事务回滚方案。

回滚：

- 执行前导出受影响行到备份表或 JSON。
- 如需回滚，按备份恢复原 `status/error_message/result_json/run_after/active_idempotency_key`。

## 7. 线上旧资源清理

未执行。原因：线上资源删除/清理未授权。

只读盘点建议：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 '
set -eu
cd /home/ubuntu/gupiao-upload
sudo docker ps -a
sudo docker images
sudo docker system df
sudo find /home/ubuntu -maxdepth 1 -type f \( -name "gupiao-deploy-*" -o -name "gupiao-delta-deploy-*" -o -name "gupiao-frontend-hot-*" -o -name "gupiao_remote_verify*.sh" \) -print
sudo test -d /app/frontend/dist && sudo du -sh /app/frontend/dist || true
sudo nginx -T 2>/dev/null | grep -E "frontend-hot|frontend-legacy|__legacy|html-root|weisilianghua" || true
'
```

授权后优先使用项目安全脚本或明确清单，禁止：

- `docker image prune -a`
- `docker volume prune`
- 未审查通配删除

## 8. `frontend/` 物理删除

未执行。原因：这是单独高风险批次，当前未获明确授权，且仍需 native/mobile owner review 和归档。

删除前置门槛：

1. `frontend-next` 线上稳定观察完成。
2. `scripts/version_sync.py`、`scripts/harden_native_release_config.py` 的 `frontend/android`、`frontend/ios` 依赖完成 owner review。
3. 全仓引用复扫只剩历史文档、清理保护和 guard 测试。
4. 创建归档 tag/branch 或压缩包。
5. 用户明确授权删除。

建议删除前复扫：

```bash
rg -n "frontend/|frontend/dist|frontend-legacy|frontend-hot|__legacy|html-root" \
  Dockerfile Dockerfile.prebuilt deploy scripts backend .github Makefile docs frontend-next
```

影响：

- 移除旧源码和旧前端测试。
- 可能影响 native/mobile 辅助脚本和历史对照流程。
- 必须保留 `frontend-next/`。

回滚：

- 从归档 tag/branch 恢复 `frontend/`。
- 或回退删除 commit。

## 问题分级

| 等级 | 问题 | 当前状态 |
| --- | --- | --- |
| P0 | 无已证实 P0 | 未部署，未新增线上风险 |
| P1 | 线上 MySQL/runtime-worker OOM、低吸任务失败、域名 reset | 来自 2026-06-11 线上审计；本地修复已提交，线上待授权部署验证 |
| P2 | BFF/provider 慢源降级、Docker cache/旧资源清理 | 本地测试覆盖降级；清理待授权 |
| P3 | `frontend-web` 验证栈和旧 `frontend/` 物理删除 | 待观察期和单独授权 |

## 本轮未执行项

- 未部署。
- 未切流。
- 未重启线上服务。
- 未执行线上稳定性长观察。
- 未写生产数据库。
- 未清理线上旧资源。
- 未删除 `frontend/`。

这些未完成项均需要用户明确授权或部署后时间窗口。

## 简短结论

1. 当前线上是否可用：本轮未重新验证线上；上一次审计结论是部分可用但存在 P1 稳定性风险。
2. 是否存在影响核心功能的问题：是，上一次审计显示 MySQL/runtime-worker OOM、低吸物化失败和域名 reset。
3. 最大资源瓶颈：内存，尤其 MySQL 和 runtime-worker。
4. 是否有 P0/P1：未证实 P0；P1 仍需线上部署后复验。
5. 本轮执行写操作：本地 git commit；未执行线上写操作、重启、清理、部署。
6. 仍需授权：线上部署、部署后验证、长稳观察、历史 paper failed task 清理、旧资源清理、`frontend/` 物理删除。
