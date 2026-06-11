# 旧前端退役决策包（2026-06-11）

## 结论

本轮只做决策包与引用扫描，不物理删除 `frontend/`。

当前生产运行、CI、Docker 与分离部署主路径已经指向 `frontend-next/`，未发现旧 `frontend/` 仍作为默认 Web 入口、CI 构建产物或生产静态服务事实源。旧 `frontend/` 仍存在以下保留理由：历史回滚/对照资料、本地清理脚本保护项、版本同步与 native 发布辅助脚本、历史需求与验收报告引用。因此 `frontend/` 可标记为 `retired-source / archive_candidate`，但不得在本轮删除。

## 扫描范围

- CI：`.github/workflows/ci.yml`
- Docker/Compose：`Dockerfile`、`deploy/frontend/Dockerfile`、`docker-compose.separated.yml`
- Backend：`backend/app/main.py`、`backend/app/services/settings_runtime.py`、`backend/app/services/agent_context_service.py`
- Deploy/Scripts：`scripts/deploy_scope.py`、`scripts/deploy_cloud_server.sh`、`scripts/deploy_delta_package.py`、`scripts/clean_local_artifacts.sh`、`scripts/version_sync.py`、`scripts/harden_native_release_config.py`
- Docs：`docs/`、`docs/reports/`

## 运行依赖判定

| 维度 | 当前状态 | 判定 |
| --- | --- | --- |
| Backend 静态服务 | `backend/app/main.py` 使用 `frontend-next/dist`；`/__legacy/*` 返回旧资源已退役 404；`frontend_dist` readiness 兼容字段也指向 `frontend-next/dist` | 旧前端不是运行事实源 |
| Docker 主镜像 | 根 `Dockerfile` 构建并复制 `frontend-next/dist` 到 `/app/frontend-next/dist` | 旧前端不是镜像产物 |
| 分离前端镜像 | `deploy/frontend/Dockerfile` 只构建 `frontend-next`，nginx 只复制到 `/usr/share/nginx/html-next/` | 旧前端不是前端容器产物 |
| 分离 Compose | `frontend-web` 挂载 `./frontend-next/dist:/usr/share/nginx/html-next:ro`，`backend-api` 设置 `SERVE_FRONTEND_STATIC=false` | 旧前端不参与分离部署服务 |
| CI | `.github/workflows/ci.yml` 只安装、检查、测试、构建并上传 `frontend-next/dist` artifact | 旧前端不是 CI 默认产物 |
| 部署 scope | `scripts/deploy_scope.py` 将 `frontend/` 分类为 `frontend-retired`，显式 `frontend-hot/frontend-legacy` 会 blocked | 旧前端上线 scope 已退役 |

## 仍需保留的引用

| 引用类型 | 文件/路径 | 处理建议 |
| --- | --- | --- |
| 本地清理保护 | `scripts/clean_local_artifacts.sh` 的 `--frontend-dist` | 保留，属于本地 dry-run 默认的清理辅助，不是生产依赖 |
| Delta 打包忽略/保护 | `scripts/deploy_delta_package.py` 中 `frontend/node_modules`、`frontend/dist`、旧生成类型路径 | 保留到旧前端归档完成，避免误把旧产物纳入包 |
| Native 发布辅助 | `scripts/version_sync.py`、`scripts/harden_native_release_config.py` 引用 `frontend/android`、`frontend/ios` | 标记 `keep_until_owner_review`，需单独确认移动端退役/迁移策略 |
| 历史部署清理 | `gupiao-frontend-hot-*` 清理逻辑 | 保留，属于历史远端包清理，不是新部署路径 |
| 审计/测试 | `scripts/audit_legacy_routes.py`、`backend/tests/test_*` 中旧前端断言 | 保留，用来防止旧入口被重新启用 |
| 文档历史 | `docs/` 与 `docs/reports/` 大量旧前端计划、parity、验收记录 | 不批量改写；后续做文档归档时再按时间线迁移 |

## 不删除的原因

1. 本任务硬边界明确禁止物理删除 `frontend/`。
2. `frontend/` 仍承载 native/mobile 相关脚本路径，无法证明完全无业务保留价值。
3. 大量历史文档以旧前端作为 parity 与切流记录依据，直接删除会降低追溯性。
4. 当前目标是“收口决策”，不是源目录瘦身执行。

## 后续删除门槛

只有在单独授权后，才可进入删除/归档执行阶段；执行前至少满足：

1. `frontend-next` 已完成约定观察期，线上默认入口稳定。
2. Native/mobile 方向确认不再依赖 `frontend/android` 与 `frontend/ios`，或已迁移到新目录。
3. `scripts/version_sync.py`、native 发布脚本、delta 打包忽略、清理脚本已完成替代方案。
4. CI、Docker、backend、deploy、scripts、docs 引用复扫通过，删除清单可回滚。
5. 有归档 tag/branch 或压缩包，保留旧前端源码追溯。
6. 用户明确授权物理删除。

## 本轮动作

- 未删除 `frontend/`。
- 未修改旧前端源码。
- 未部署、未切流、未执行线上写操作。
