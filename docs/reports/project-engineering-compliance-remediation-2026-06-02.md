# Project Engineering Compliance Remediation - 2026-06-02

状态：已执行整改并完成验证
最后核验日期：2026-06-02
适用范围：`backend/`、`frontend/`、`scripts/`、`deploy/`、`docs/`、`tests/`、`data/generated`

## 1. 当前 git 状态摘要

- 分支：`codex/phase4-phase5-architecture`
- 跟踪关系：`origin/codex/phase4-phase5-architecture`，本地 ahead 33
- 开始前工作区：已有未提交改动；本轮未回滚、未覆盖、未删除用户或其他任务已有改动。
- 当前改动类型：
  - 后端守卫与任务边界整改。
  - 前端认证与 SSE 降级整改。
  - 部署脚本与本地清理脚本整改。
  - 文档入口、报告索引和生成缓存治理整改。

开始前记录的 `git status --short --branch`：

```text
## codex/phase4-phase5-architecture...origin/codex/phase4-phase5-architecture [ahead 33]
 M backend/app/core/config.py
 M backend/app/main.py
 M backend/app/runtime/background_jobs.py
 M backend/app/services/factor_mining/compute_engine.py
 M backend/app/services/tasks/queue.py
 M backend/tests/test_cloud_deploy_scripts.py
 M backend/tests/test_factor_mining.py
 M backend/tests/test_full_regression_runner.py
 M backend/tests/test_legacy_routes.py
 M backend/tests/test_ml_online_learning_schedule.py
 M backend/tests/test_phase4_phase5_foundation.py
 M docker-compose.mysql.yml
 M frontend/src/api/appClient.ts
 M frontend/src/api/base.test.ts
 M frontend/src/api/base.ts
 M frontend/src/state/realtime/useQuoteStream.test.tsx
 M frontend/src/state/realtime/useQuoteStream.ts
 M scripts/deploy_cloud_server.sh
 M scripts/quick_cloud_deploy.sh
 M scripts/run_focus_strategy_purged_gap_rerun.py
?? backend/tests/test_purged_gap_rerun_script.py
?? docs/reports/README.md
?? docs/reports/full-project-code-review-2026-06-02.md
?? frontend/src/api/publicApiPaths.ts
?? scripts/clean_local_artifacts.sh
```

## 2. 整改覆盖范围

| 区域 | 覆盖动作 |
|---|---|
| backend | API fallback、runtime background role、RuntimeTask retry/backoff、factor mining code validation、purged gap rerun script safety |
| frontend | auth refresh single-flight、SSE stream token retry/fallback、public API path 去重 |
| scripts/deploy | hardcoded host/key 清理、fast mode 显式确认、API fallback JSON smoke |
| scripts/cleanup | 新增本地缓存清理脚本，dry-run 默认，补可执行位 |
| docs | README 结构修正、reports 索引、全项目审查报告、本整改报告 |
| tests | 后端守卫测试、前端认证/SSE 测试、RuntimeTaskQueue 聚焦拆分测试、脚本安全测试 |
| data/generated | 删除已跟踪 TypeScript 构建缓存，保留未跟踪本地缓存 |

## 3. 发现的不合规项清单

| 编号 | 分类 | 发现 | 风险 |
|---|---|---|---|
| G1-1 | 生成产物位置 | `frontend/tsconfig.node.tsbuildinfo` 被 git 跟踪；`.gitignore` 和 `docs/README.md` 均要求 `frontend/*.tsbuildinfo` 不应跟踪 | 构建缓存污染提交，造成无意义 diff |
| G1-2 | 文档入口 | `README.md` 的前端结构仍写 `components/pages/App.tsx/styles.css`，与当前 `app/features/state/ui/generated` 结构不符 | 新人和审计误判模块边界 |
| G1-3 | 文档产物治理 | `docs/README.md` 在报告区直接列 JSON 历史产物，容易延续将机器产物放进 `docs/reports/` 的习惯 | 新增大型 JSON/zip 混入手写报告区 |
| G1-4 | 本地缓存 | 工作区存在大量未跟踪 `__pycache__`、`.pytest_cache`、`frontend/dist` 可能反复出现 | 本地产物误提交风险 |
| G2-1 | 超长测试 | `backend/tests/test_phase4_phase5_foundation.py` 1191 行，已超过后端测试 800 行必须拆分阈值；本轮新增队列守卫前未拆分 | 综合测试继续膨胀，定位成本高 |
| G2-2 | 历史文档 | 根目录仍有 `IMPLEMENTATION_PLAN.md`、`APP_API_SPEC.md`、`ARCHITECTURE.md` 等历史/当前交叉文档 | 移动会破坏引用链；不移动会增加认知成本 |
| G2-3 | 机器产物 | `docs/reports/` 仍有 377 个历史 JSON/JSONL/zip/parquet 类产物 | 存量审计价值与规范冲突，需要后续迁移批次 |
| G2-4 | 超长历史 Markdown | 多份历史计划/报告超过 Markdown 评审阈值或必须拆分阈值 | 多为审计材料，直接拆分会破坏原始证据 |
| G3-1 | 后台任务边界 | Web runtime background loops 需要明确角色门控 | 多 worker/Web 重复执行重任务 |
| G3-2 | 任务重试 | RuntimeTask 失败或 stale recovery 立即重新 claim，缺少 backoff | 异常时形成热循环 |
| G3-3 | 研究代码安全 | factor mining 公式校验需禁止顶层可执行语句、导入、循环和危险调用 | 研究功能代码执行面过宽 |
| G3-4 | 部署脚本 | 快速部署脚本历史上容易把服务器地址、密钥路径和跳过本地检查混成默认行为 | 误部署、跳过验证或 API fallback 返回 HTML |
| G3-5 | API 401/SSE | token 过期时 protected request 与 SSE stream token 获取需要统一刷新和降级 | 登录失效、实时流中断、页面阻塞 |

## 4. 已整改项清单

### G1：低风险清理

- 删除已跟踪生成缓存 `frontend/tsconfig.node.tsbuildinfo`；删除前引用检查只发现历史清理报告提及，无代码、脚本、部署或测试依赖。报告生成后，本整改报告自身也会命中该文件名。
- 更新 `README.md` 当前项目结构，前端入口改为 `api/app/features/generated/state/styles/ui/scripts`。
- 更新 `docs/README.md` 报告索引，改为指向 `docs/reports/README.md`，不再把 JSON 历史产物作为新增报告示例。
- 新增 `docs/reports/README.md`，明确 `docs/reports/` 端态是人读 Markdown，历史机器产物迁移前保留，新机器产物默认进入 `backend/data/reports/`、`backend/data/analytics/reports/` 或外部 artifact。
- 新增 `scripts/clean_local_artifacts.sh`，默认 dry-run，只清理 `__pycache__`、`*.pyc` 与 `frontend/dist`，不触碰 `backend/data`；已补可执行位。
- 修正 `backend/tests/test_cloud_deploy_scripts.py` 新增断言块缩进为四空格。

### G2：中风险结构整改

- 将 `RuntimeTaskQueue` 的队列事件、stale recovery、retry backoff 测试从超长综合文件拆到 `backend/tests/test_runtime_task_queue.py`。
- `backend/tests/test_phase4_phase5_foundation.py` 从 1191 行降到 1074 行；仍超阈值，但本轮新增职责已从该文件移出，后续不得继续追加无关守卫。
- `frontend/src/api/publicApiPaths.ts` 收敛 public API path 判断，避免 request 层与 app client 重复维护白名单。
- `scripts/run_focus_strategy_purged_gap_rerun.py` 从 shell 字符串执行改为 argv 构造和参数 allowlist，补 `backend/tests/test_purged_gap_rerun_script.py`。

### G3：高风险守卫整改

- `backend/app/core/config.py` 新增 `runtime_background_role` 配置声明。
- `backend/app/runtime/background_jobs.py` 在 web role 下跳过 runtime background jobs。
- `docker-compose.mysql.yml` 将 app 标记为 `RUNTIME_BACKGROUND_ROLE=web`，runtime-worker 标记为 `worker`。
- `backend/app/services/tasks/queue.py` 对 retryable failure 和 stale recovery 设置 future `run_after`，避免异常热循环。
- `backend/app/services/factor_mining/compute_engine.py` 增加 AST module body 校验，只允许顶层 `compute_factor`、大写常量和 docstring。
- `backend/app/main.py` 对未匹配 `/api/*` 返回 JSON 404，避免 SPA HTML fallback 污染 API。
- `frontend/src/api/base.ts` / `appClient.ts` 统一 auth refresh single-flight，protected request 401 后只重试一次。
- `frontend/src/state/realtime/useQuoteStream.ts` stream token 失败先走认证刷新/重连，达到限制后 fallback poll，不阻塞页面。
- `scripts/quick_cloud_deploy.sh` 移除硬编码云主机和密钥路径，fast mode 必须显式 `--fast-risk-accepted`。
- `scripts/deploy_cloud_server.sh` 和 quick deploy 均增加 `/api/__missing_smoke__` JSON fallback smoke。

## 5. 已删除文件清单

| 路径 | 删除理由 | 引用检查证据 | 风险判断 |
|---|---|---|---|
| `frontend/tsconfig.node.tsbuildinfo` | TypeScript incremental build cache；`.gitignore` 已忽略 `frontend/*.tsbuildinfo`；规范明确不得跟踪 | 删除前 `rg --fixed-strings "tsconfig.node.tsbuildinfo" .` 仅命中 `docs/reports/repository-cleanup-2026-05-27.md` 的历史记录；报告生成后会额外命中本报告 | 低风险；删除后前端构建可重新生成本地缓存，不影响源码、契约或部署 |

未删除：

- 未跟踪的 `frontend/tsconfig.app.tsbuildinfo`：本地缓存，未入库，不需要通过 git 删除。
- 未跟踪 `__pycache__` / `.pytest_cache` / `frontend/dist`：本地验证产物，提供清理脚本，不在本轮直接批量删除，避免误删用户当前运行输出。
- `docs/reports/` 历史 JSON/JSONL/zip：共扫描到 377 个，保留审计价值，后续单独迁移。

## 6. 已移动/重命名文件清单

本轮没有移动或重命名文件。

原因：根目录历史文档和 `docs/reports/` 历史机器产物均有活跃引用或审计价值；移动前需要批量改链接和迁移 manifest，超出本轮低风险整改边界。

## 7. 已拆分超长文件清单

| 原文件 | 新文件 | 整改内容 | 结果 |
|---|---|---|---|
| `backend/tests/test_phase4_phase5_foundation.py` | `backend/tests/test_runtime_task_queue.py` | 拆出 RuntimeTaskQueue 事件、stale recovery、retry backoff 测试 | 原文件减少 117 行；新增队列测试独立运行，`39 passed` |

仍超阈值但暂缓：

- `backend/tests/test_phase4_phase5_foundation.py`：仍 1074 行。后续建议按 runtime worker、ML guard、decision context、quant parameters 继续拆分。
- `backend/tests/test_backtest_v2_api_contract.py`、`backend/tests/test_low_buy_read_paths.py`、`backend/tests/test_backtest_v2_engine_contract.py`：均超过 800 行附近，未在本轮修改，避免把未触达测试做大范围机械重排。
- `frontend/scripts/smoke-responsive.mjs`：939 行，属于现有 smoke runner；本轮只运行验证，不拆脚本以免影响响应式验收入口。
- 多份历史 Markdown：按规范为历史遗留，不因形式拆分破坏审计原文。

## 8. 暂缓整改项和原因

| 暂缓项 | 原因 | 后续建议 |
|---|---|---|
| 根目录历史文档整体迁入 `docs/archive/` | `docs/README.md`、历史审查、脚本和运行说明仍引用；移动会造成链接链式修改 | 建立 `docs/archive/root-docs-2026-06-02/`，先生成引用迁移清单，再一次性改索引 |
| `docs/reports/` 377 个历史机器产物迁移 | 属于回测和审计证据，部分仍被报告引用 | 新增 artifact manifest，按 basename 引用检查后分批迁入 `backend/data/reports/` 或外部 artifact |
| Go/Rust/native 实验链路清理 | 属于可选增强与历史路线，可能影响文档和部署选择 | 先 feature flag/入口审计，再决定是否归档 |
| 大型测试继续拆分 | 需要按领域重组 fixtures 和 helper，风险高于本轮范围 | 单独做 test architecture batch，避免和安全/部署整改混合 |
| `ARCHITECTURE.md` 策略矩阵漂移 | 涉及策略事实源和生产分层说明 | 只记录建议；应以 `strategy_policy` 自动生成或人工同步，需策略边界复审 |

## 9. 风险判断

- 策略逻辑：未修改生产策略计算、策略分层、选股规则或策略阈值。
- 回测口径：未修改回测收益口径、样本选择、费用、滑点、成交假设。
- 生产排序：未修改 production scoring、priority board 排序逻辑或生产策略准入规则。
- 部署配置：未部署；仅修改部署脚本安全默认和 smoke 检查。`docker-compose.mysql.yml` 只增加 `RUNTIME_BACKGROUND_ROLE` 角色声明，目的是隔离 Web 与 worker 后台任务。
- API 契约：未新增/删除接口字段；`/api/*` fallback 从 HTML 改为 JSON 404，属于错误响应边界修正。OpenAPI/generated types 无字段语义变更。

## 10. 验证命令和结果

已完成的阶段验证：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_runtime_task_queue.py backend/tests/test_phase4_phase5_foundation.py -q
```

结果：

```text
39 passed, 1 warning in 2.93s
```

最终完整验证：

```bash
cd frontend && npm run api:check && npm run lint && npm test -- --run && npm run build:web && npm run analyze
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run smoke:responsive
git diff --check
rg "\buseState\b|\buseReducer\b" frontend/src
rg "<Table" frontend/src
```

结果摘要：

- Frontend：`api:check`、lint、Vitest、`build:web`、analyze 均通过。
- OpenAPI 导出：`sha256=eeaad0612d692a3d65a1292129a795fa662fe87b1be3a6d44b8184e4cfd83f5d`。
- Frontend Vitest：50 files / 154 tests passed。
- CSS guard：`inlineStyleObjects=117`、`cssPropertiesFiles=34`、`smallFonts=0`、`hardcodedHex=197`、`cssHardcodedHex=0`。
- Analyze：`total_gzip_kb=782.07`，`first_screen_js_gzip_kb=9`。
- Backend：1098 passed / 1 LibreSSL warning。
- Responsive smoke：通过，`frontend/dist/responsive-smoke-report.json`，`ok=true`，375px mobile 10 pages，`max_mobile_overflow_x=0`，failed=0。
- `git diff --check`：通过。
- `rg "\buseState\b|\buseReducer\b" frontend/src`：无命中。
- `rg "<Table" frontend/src`：仅 `frontend/src/ui/grid/VirtualGrid.tsx`。

脚本专项验证：

```bash
bash -n scripts/quick_cloud_deploy.sh scripts/deploy_cloud_server.sh scripts/clean_local_artifacts.sh
backend/.venv/bin/python -m pytest backend/tests/test_cloud_deploy_scripts.py backend/tests/test_purged_gap_rerun_script.py -q
```

结果：脚本语法检查通过；脚本安全专项测试 11 passed。

## 11. 后续建议

1. 建立 `docs/reports/artifact-manifest-2026-06-02.md`，逐项记录历史 JSON/zip 的引用、审计价值和迁移目标。
2. 将 `backend/tests/test_phase4_phase5_foundation.py` 继续拆分为 runtime worker、ML guard、decision context、quant parameters 四个测试文件。
3. 将 `docs/README.md` 当前索引与根目录历史文档解耦，逐步把不再作为当前依据的根目录计划迁入 `docs/archive/`。
4. 对 `ARCHITECTURE.md` 建立从 `strategy_policy` 同步策略矩阵的流程，避免策略数量和生产层口径再次漂移。
5. 将 `frontend/scripts/smoke-responsive.mjs` 拆为 CLI、browser runner、assertion helpers 和 report writer，降低响应式 smoke 维护成本。
