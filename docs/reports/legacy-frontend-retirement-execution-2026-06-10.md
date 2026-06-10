# 旧前端运行链路退役执行报告

日期：2026-06-10

## 结论

本轮已将旧 `frontend/` 从运行入口、镜像构建、分离前端 nginx、部署 scope 和 CI artifact 链路中退役。线上平台目标入口改为 `frontend-next/`。

本轮未物理删除 `frontend/` 源码目录，因为当前工作树中该目录存在未提交改动，直接删除会破坏既有工作。源码删除应在观察期通过、确认无回滚需求后单独执行。

## 已完成

| 模块 | 结果 |
| --- | --- |
| 后端静态入口 | `/`、旧业务路径、`/next/*` 均由 `frontend-next/dist` 承接 |
| API fallback | `/api/*` 继续返回 JSON 404，不进入 SPA fallback |
| legacy assets | `/__legacy/*` 返回 404 |
| readyz | `frontend_next_dist` 成为真实前端 readiness；`frontend_dist` 仅保留兼容别名 |
| Dockerfile | 主镜像不再构建/复制旧 `frontend/dist` |
| 分离前端镜像 | 只构建/复制 `frontend-next/dist` |
| nginx | 移除 `html-root` 与 `/__legacy/assets/` |
| deploy scope | `frontend-hot` / `frontend-legacy` 显式 scope 阻断；`frontend/**` 不触发旧前端部署 |
| CI | 停止旧前端 job 与 `frontend-dist` artifact |
| Makefile | `deploy-cloud-web` 改为构建和部署 `frontend-next` |

## 未执行

- 未删除 `frontend/` 源码目录。
- 未部署到云服务器。
- 未改生产策略公式、排序、分数或风控语义。

## 验证结果

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py -q` | 62 passed / 1 LibreSSL warning |
| `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_agent_routes.py backend/tests/test_bff_monitor_workspace.py -q` | 92 passed / 1 LibreSSL warning |
| `bash -n scripts/deploy_cloud_server.sh scripts/quick_cloud_deploy.sh scripts/one_click_cloud_deploy.sh scripts/prod_preflight.sh` | PASS |
| `python3 -m py_compile scripts/deploy_scope.py` | PASS |
| `cd frontend-next && npm run api:check` | PASS |
| `cd frontend-next && npm run lint` | PASS |
| `cd frontend-next && npm test -- --run` | 25 files / 131 tests passed |
| `cd frontend-next && npm run build` | PASS |
| `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ci.yml"); puts "yaml:ok"'` | PASS |
| `git diff --check` | PASS |

## 后续删除条件

1. `frontend-next` 线上稳定观察至少 1-2 个交易日。
2. 没有任何入口需要回滚旧前端。
3. 当前 `frontend/` 下未提交改动已经归档、提交或明确废弃。
4. 运行 `rg -n "frontend-legacy|frontend-hot|frontend/dist|html-root|__legacy" Dockerfile deploy scripts backend .github Makefile` 只剩历史清理/兼容说明。
5. 删除源码前创建可回滚 tag 或保留上一版镜像。

## 建议下一步

先完成本地验证和一次 frontend-next-only 镜像构建，再由用户单独授权部署。部署后观察期通过，再执行 `frontend/` 源码物理删除批次。
