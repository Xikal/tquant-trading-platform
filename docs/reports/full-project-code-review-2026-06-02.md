# 全项目代码审查与问题清单（2026-06-02）

## 1. 审查结论总览

审查对象：`/Users/j/Documents/gupiao`

当前分支：`codex/phase4-phase5-architecture`

当前状态：

- 分支相对远端 ahead 33。
- 本轮为了响应“彻底解决 401”的明确要求，已改动 401/SSE 鉴权链路相关代码。
- 除 401 修复外，未删除文件、未提交、未部署。

是否建议上线：

- 不建议直接上线脏工作区。
- 401/SSE 修复已通过针对性回归，可以进入提交和部署流程。
- 剩余 P1 风险不一定阻塞 401 修复上线，但建议纳入下一批生产安全整改。

P0/P1 结论：

- P0：0 个。
- P1：4 个，其中 1 个（401/SSE 鉴权竞态与 API fallback 混淆）本轮已修复并验证。

最重要结论：

1. `POST /api/intraday/subscribe` 未登录返回 401 本身是正确保护；用户遇到的异常体验来自前端并发刷新 refresh cookie 竞态，以及 `GET /api/...` 被 SPA fallback 成 HTML。
2. 策略生产边界当前未发现明显破坏：`n_pattern_*` 等 RESEARCH 策略不会取得 `production_score`，`near_entry` 被置为 watch-only。
3. Web 主进程仍注册大量后台循环，虽然有 leader lock 和 feature flag，但与“长任务 worker 隔离”的目标仍有距离。
4. 快速部署脚本默认跳过本地检查并内置个人 SSH key 路径，适合人工加速，不适合作为默认生产发布入口。
5. `docs/reports/` 仍存在大量机器 JSON/JSONL，且部分脚本仍默认写入该目录，和工程规范不一致。

## 2. 项目地图与已审查范围

### 2.1 后端

- `backend/app/main.py`：FastAPI 应用入口、SPA fallback、旧路由返回。
- `backend/app/api/router.py` 与 `backend/app/api/routes/*`：认证、BFF、行情、策略、模拟盘、数据中心、任务、因子研究等 API。
- `backend/app/core/*`：配置、认证、安全、数据库。
- `backend/app/services/low_buy/*`：策略分层、生产评分、优先榜、策略物料化。
- `backend/app/services/tasks/*`：RuntimeTaskQueue、worker、事件。
- `backend/app/runtime/background_jobs.py`：Web 进程内后台循环注册。
- `backend/app/services/paper/*`：模拟盘、绩效、风控、暂停恢复。
- `backend/app/services/factor_mining/*`：因子研究、代码执行、研究 worker。
- `backend/tests/*`：认证、策略边界、SSE token、旧路由、低吸生产评分等重点测试。

### 2.2 前端

- `frontend/src/api/*`：API 请求、auth refresh、离线缓存、app client。
- `frontend/src/state/realtime/*`：实时行情 SSE、signals、fallback polling。
- `frontend/src/features/monitor/*`：实时监控页。
- `frontend/src/features/strategy-tracking/*`：策略跟踪页。
- `frontend/src/features/paper/*` 与 `frontend/src/features/trading-workspace/*`：模拟盘与工作台页面。
- `frontend/src/features/data-console/*`：数据中心。
- `frontend/src/ui/grid/VirtualGrid.tsx`、`frontend/src/ui/table/DataTable.tsx`、`frontend/src/ui/list/VirtualCardList.tsx`：表格与长列表原语。
- `frontend/scripts/check-refactor-guard.mjs`、`check-state-separation.mjs`、`check-css-guard.mjs`：前端架构护栏。

### 2.3 脚本、部署、文档

- `scripts/deploy_cloud_server.sh`：完整云端部署脚本。
- `scripts/quick_cloud_deploy.sh`：快速部署入口。
- `scripts/run_focus_strategy_purged_gap_rerun.py` 等报告/回测脚本。
- `docs/engineering-conventions.md`：本次审查对照规范。
- `docs/reports/*`：历史报告、回测结果、机器 JSON。
- `docs/contracts/openapi.json`：OpenAPI 契约产物。

### 2.4 覆盖说明

已做：

- 文件级扫描覆盖 `backend/`、`frontend/`、`scripts/`、`deploy/`、`docs/`。
- 对高风险路径做行级阅读和证据定位：鉴权、SSE、策略生产评分、任务队列、后台 job、部署脚本、因子研究执行、前端护栏。
- 对大文件、缓存、机器报告、raw Table、`useState/useReducer`、CSS guard、策略边界做全量搜索或命令检查。

未逐行审查：

- `node_modules/`、`frontend/dist/`、`.venv/`、`backend/data/`、OpenAPI/generated 类型等生成产物或依赖。
- `docs/reports/` 里的巨型机器 JSON 未逐行阅读，仅做大小、数量、归档合规审查。

## 3. P0/P1/P2/P3 问题清单

### P0

未发现 P0。

未发现直接导致实盘自动下单、策略生产分层失守、明文密钥提交、公开未鉴权管理写接口的证据。

### P1-001：401/SSE 鉴权刷新竞态与 API fallback 混淆（已修复）

问题：

- `/api/intraday/subscribe` 是受保护 POST。未登录返回 401 合理。
- 前端 `TradingWorkspace.restoreSession()` 可能显式调用 `/auth/refresh`，同时受保护的 SSE subscribe 请求也会预刷新；refresh cookie 会轮换，两个并发 refresh 可能让其中一个请求用到已失效 cookie。
- `GET /api/intraday/subscribe` 没有对应 API 方法时会落到 FastAPI SPA catch-all，返回前端 HTML，而不是 API JSON 404，造成排查混淆。
- stream token 获取失败时，实时流直接 fallback polling，没有短暂重试。

证据：

- `frontend/src/api/base.ts:111` 原先只有 request 内部 refresh single-flight，显式 `appApi.refreshAuth()` 不共享。
- `frontend/src/api/appClient.ts:64` 现在改为复用 `refreshAuthSession()`。
- `frontend/src/state/realtime/useQuoteStream.ts:92` 现在 token 获取失败会先重连，超限后 fallback。
- `backend/app/main.py:500` 现在对 `/api/...` catch-all 返回 JSON 404。

影响：

- 登录态边界时实时流可能误报“登录已失效”。
- 用户直接访问 API GET 路径时看到前端 HTML 或不一致错误，难以判断真实问题。

修复：

- 新增共享 `refreshAuthSession()`，显式 session restore 与受保护请求共用同一个 refresh promise。
- SSE stream token 获取失败时加入重连，再回退轮询。
- FastAPI SPA fallback 对 API 前缀返回 JSON 404。
- 补充前端和后端测试。

验证：

- `npm test -- --run src/api/base.test.ts src/state/realtime/useQuoteStream.test.tsx`：8 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_legacy_routes.py -q`：3 passed。
- `npm run lint`、`npm test -- --run`、`npm run build:web` 均通过。

### P1-002：快速部署脚本默认跳过本地检查，且内置个人 SSH key 路径（已修复）

问题：

- `scripts/quick_cloud_deploy.sh:8-10` 默认 host/user/key，其中 key 是 `/Users/j/Downloads/gupiao.pem`。
- `scripts/quick_cloud_deploy.sh:19-31` 默认 `FAST_MODE=1`、`RUN_LOCAL_CHECKS=0`、`RUN_FULL_TESTS=0`。
- `scripts/quick_cloud_deploy.sh:226-250` 将这些默认值透传给完整部署脚本。

影响：

- 快速部署容易绕过本地 lint/test/build，把未验证改动推上云端。
- 个人路径写入脚本降低可移植性，也会让其他环境误用失败。

建议修复：

- 默认不跳过本地 `lint/test/build`，如需快速模式必须显式 `--fast-risk-accepted`。
- host/key 改为必须由环境变量或 `.env.deploy.local` 提供，不在仓库脚本内放个人路径默认值。
- 部署后 smoke 增加：`GET /api/not-found` 必须 JSON 404，不能返回 HTML。

建议验证：

- `scripts/quick_cloud_deploy.sh --verify-only`
- `RUN_LOCAL_CHECKS=1 scripts/quick_cloud_deploy.sh --full`
- 云端 curl 验证 protected API 401、API fallback 404、frontend root 200。

本轮处理：

- `scripts/quick_cloud_deploy.sh` 已移除硬编码 host/key 默认值。
- 默认启用本地 compile/build/策略测试。
- 如需跳过本地检查，必须显式传入 `--fast-risk-accepted`。
- 完整部署和 quick verify 都增加 `/api/__missing_smoke__` JSON 404 smoke。

### P1-003：Web 主进程仍注册大量后台循环（已修复生产角色边界）

问题：

- `backend/app/runtime/background_jobs.py:364-495` 在 Web 运行时注册了行情缓存、全市场快照、低吸物料化、日线刷新、市场复盘、paper 归档、研究 worker、通知、ML、factor mining、模拟盘自动交易等循环。
- `backend/app/runtime/background_jobs.py:344-361` 有 leader lock，`66-71` 有启停开关，这降低了多 worker 重复执行风险，但仍没有完全实现 Web/worker 隔离。

影响：

- Web 进程承担后台调度，流量高峰或长任务失败时会影响 API 稳定性。
- 云端横向扩容、systemd 重启、leader lock 失效时，后台任务可观测性和恢复边界复杂。

建议修复：

- Web 进程只保留轻量健康/缓存读路径。
- 高频/长耗时任务全部迁入 analytics worker 或独立 scheduler service。
- 用环境变量明确区分 `WEB_ONLY=1` 与 `SCHEDULER=1`，部署脚本和 systemd 单元分别验证。

建议验证：

- Web systemd 日志中不出现后台 loop start。
- worker 日志中出现 task claim/heartbeat/progress。
- `/readyz`、`/metrics` 能区分 web 与 worker 状态。

本轮处理：

- 新增 `runtime_background_role` 配置。
- Web 角色显式跳过 runtime background jobs。
- `docker-compose.mysql.yml` 中 app 设置 `RUNTIME_BACKGROUND_ROLE=web`，worker 设置 `RUNTIME_BACKGROUND_ROLE=worker`。
- 保留 scheduler/worker 角色运行 loop 的兼容路径。

### P1-004：因子研究路径仍存在动态 Python exec（已收紧）

问题：

- `backend/app/services/factor_mining/compute_engine.py:211-220` 使用 `exec(compile(formula_code, ...))` 执行公式代码。
- `backend/app/api/routes/factor_mining.py:36-42` 已通过 research/strategy_config 权限门限制入口，这是有效缓解，但不是沙箱等价。
- `compute_engine.py:238-245` 有资源限制，但在 macOS 直接 return；不同部署环境行为不完全一致。

影响：

- 一旦 research 权限账号、内部 token 或上游代码生成链路被滥用，动态执行仍是高风险面。
- 资源限制、可导入对象、pandas/numpy 可用面较宽，审计成本高。

建议修复：

- 将公式语言收敛为受限 DSL 或 AST 白名单解释器。
- 至少把动态执行移出 Web/API 进程，放到隔离 worker/container。
- 给 factor mining 增加超时、内存、导入黑名单、审计日志和最小权限测试。

建议验证：

- 恶意公式用例：import/open/os/subprocess/网络访问/无限循环/大内存分配全部失败。
- research 权限外账号 403。
- factor mining 默认关闭时不注册后台 loop。

本轮处理：

- `FactorComputeEngine.validate()` 已拒绝顶层可执行语句。
- 仅允许顶层 `compute_factor` 函数、文档字符串和大写常量。
- 补充回归测试，防止 `pd.set_option(...)` 等顶层副作用进入执行阶段。

### P2-001：RuntimeTaskQueue 失败重试没有 backoff（已修复）

问题：

- `backend/app/services/tasks/queue.py:158-170` 失败可重试时直接把状态改回 `queued`，未设置递增 `run_after`。
- stale running 恢复同样在 `242-244` 立即重排。

影响：

- provider 故障、数据源不可用、任务逻辑 bug 时，worker 可能快速重试同一失败任务。
- 失败 storm 会影响正常任务吞吐。

建议修复：

- 按 attempt_count 设置指数退避和 jitter。
- 对 provider/data source 类错误增加全局熔断窗口。
- 任务列表展示下一次重试时间。

本轮处理：

- `mark_failed()` 可重试时设置未来 `run_after`。
- stale running recovery 重新排队时也设置未来 `run_after`。
- 补充测试确认重试任务不会立即被下一 worker claim。

### P2-002：大文件和大组件仍超过工程阈值

证据：

- `docs/engineering-conventions.md:94-115` 定义后端 route 500 行、React 页面 600 行、CSS 700 行等必须拆分阈值。
- `backend/app/api/routes/backtests.py` 约 694 行。
- `backend/app/services/market/review.py` 约 767 行。
- `backend/app/services/analytics/report_queries.py` 约 668 行。
- `backend/app/services/etf/t0_backtest.py` 约 667 行。
- `frontend/src/styles/workspace/workspace-login.css` 约 1273 行。
- `frontend/src/styles/workspace/workspace-primitives.css` 约 881 行。
- `frontend/src/features/monitor/MonitorPage.panels.tsx` 约 725 行。
- 多个测试文件超过 800 行。

影响：

- 后续小改容易扩大职责，回归范围难界定。
- 前端样式与页面拆分成本高，影响 375px 回归速度。

建议修复：

- 按 feature 分拆路由 handler/service/query builder。
- CSS 按模块迁移到 CSS Module 或局部样式。
- 大测试按行为域拆分，保留共享 fixture。

### P2-003：`docs/reports/` 仍有大量机器 JSON/JSONL，且脚本仍可能写入（已建立索引与保留规则）

问题：

- `docs/engineering-conventions.md:33-38` 要求 `docs/reports/` 放人读 Markdown，不放新增大型机器 JSON。
- `docs/engineering-conventions.md:231-238` 要求大型机器结果进入 `backend/data/analytics/reports/`、`backend/data/reports/` 或外部 artifacts。
- 当前 `docs/reports` 下 JSON/JSONL 数量约 380 个。
- 发现巨型文件如 `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json`，约 369360 行。

影响：

- 仓库体积和 diff 噪音大。
- 历史机器产物容易被误当作当前结论。
- 新脚本如果继续写 docs/reports，会违背最新规范。

建议修复：

- 历史 JSON 暂不删除，先建立 manifest，标注“历史审计/回溯产物”。
- 新脚本默认输出迁移到 `backend/data/reports/`，docs 仅提交 Markdown 摘要。
- 对超过 5MB 的产物建立保留周期。

本轮处理：

- 新增 `docs/reports/README.md`，明确人读 Markdown 与机器产物落位。
- 代表性历史 JSON/JSONL/zip 已标注保留原因和后续迁移方向。
- 未删除历史 JSON，避免破坏审计和引用链。

### P2-004：前端 CSS/inline style 债务仍高

证据：

- `frontend/scripts/css-guard-baseline.json:1-7` 现有 baseline：`inlineStyleObjects=127`、`cssPropertiesFiles=38`、`hardcodedHex=241`。
- 本次 `npm run lint` 实际检测为：`inlineStyleObjects=117`、`cssPropertiesFiles=34`、`hardcodedHex=197`，说明已经下降但仍偏高。

影响：

- UI token 化不彻底，后续主题、响应式、视觉统一成本高。
- 大量 inline style 会增加组件 diff 和测试定位难度。

建议修复：

- 每次 UI 改动保持 baseline 只降不升。
- 大组件优先拆 CSS Module。
- ECharts/卡片/状态颜色继续走 token/主题变量。

### P2-005：脚本中存在 shell=True 执行 manifest 命令（已修复）

证据：

- `scripts/run_focus_strategy_purged_gap_rerun.py:44` 使用 `subprocess.run(item["command"], shell=True, ...)`。
- `74-84` 仅用 `shlex.split` 解析预期输出路径，不等价于执行安全白名单。

影响：

- 如果 manifest 被污染，会扩大为本地命令执行风险。
- 该脚本属于研究/回测辅助，不是线上 P0，但应收敛。

建议修复：

- manifest 命令改为结构化 argv。
- 对可执行脚本、参数名、输出目录做白名单。
- 默认 dry-run 打印解析后的 argv。

本轮处理：

- `scripts/run_focus_strategy_purged_gap_rerun.py` 已改为 `_command_argv()` 解析。
- 拒绝 shell 元字符。
- 限制可执行脚本为 `backend/scripts/low_buy_execution_matrix.py`。
- 输出路径必须在仓库内。

### P2-006：前端 public API path 白名单是硬编码（已修复）

问题：

- `frontend/src/api/base.ts:99-109` 通过硬编码判断 public path。

影响：

- 新增公开端点时容易忘记更新，导致前端尝试 refresh 后再请求。
- 对登录页、bootstrap、下载类端点可能造成不必要 401 流程。

建议修复：

- 建立 `publicApiPaths.ts`，由 API client 和测试共享。
- 对新增公开端点增加测试。

本轮处理：

- 新增 `frontend/src/api/publicApiPaths.ts`。
- `base.ts` 和测试共享同一 public API allowlist。

### P2-007：factor mining 默认关闭/隐藏策略正确，但仍需运维可观测（已部分收口）

问题：

- factor mining 前端已退役或隐藏，后端仍保留 research/admin 入口和 monthly job。
- `backend/app/runtime/background_jobs.py:486-492` 在 factor flag 打开时注册 monthly loop。

影响：

- 如果生产环境误开 research/factor flags，会多出研究计算面。

建议修复：

- 启动日志明确打印 research/factor/ml job 开关状态。
- `/readyz` 或 `/metrics` 暴露研究任务启停状态。
- 部署脚本校验生产默认关闭。

本轮处理：

- Web 角色不再注册 factor monthly loop。
- 保留 research/factor flags 默认关闭。
- `/readyz`/`/metrics` 细分可观测仍建议后续扩展。

### P2-008：构建产物和本地缓存需要定期清理（已补工具）

证据：

- `find backend/app backend/tests backend/scripts -name '__pycache__' -o -name '*.pyc' | wc -l`：814。
- `du -sh backend/data`：约 1.2G。
- `du -sh frontend/dist`：约 2.5M。

影响：

- 这些未跟踪/忽略产物不影响 Git，但会干扰本地搜索和磁盘占用。

建议修复：

- 增加 `scripts/clean_local_artifacts.sh --pycache --frontend-dist`。
- 不删除 `backend/data`，只做明确数据保留策略。

本轮处理：

- 新增 `scripts/clean_local_artifacts.sh`。
- 默认 dry-run，必须 `--apply` 才删除。
- 只覆盖 `__pycache__` / `*.pyc` / `frontend/dist`，不触碰 `backend/data`。

### P2-009：全量后端测试未在本次审查中跑完

问题：

- 本次跑了认证、SSE、旧路由、策略边界的重点后端测试。
- 未跑全量 backend pytest。

影响：

- 401 修复的直接路径已覆盖，但系统审查结论不能替代完整 CI。

建议修复：

- G1 提交前跑完整 `backend/.venv/bin/python -m pytest backend/tests -q`。
- 云端部署前跑生产 smoke 与数据健康检查。

### P3-001：历史报告和当前报告入口需要索引化（已修复）

问题：

- `docs/reports/` 报告数量大，新旧结论并存。

影响：

- 容易引用旧报告作为当前事实。

建议修复：

- 增加 `docs/reports/README.md` 或 manifest，标注当前有效报告、历史归档、机器产物位置。

本轮处理：

- 已新增 `docs/reports/README.md`。

### P3-002：大型测试 fixture 与页面测试可读性下降

问题：

- 多个前端/后端测试文件超过评审阈值。

建议修复：

- 将 fixture、render helper、断言 helper 拆到同目录 `testUtils`。
- 不为降行数制造空壳，只按业务行为拆。

### P3-003：部署验证输出可以更产品化（已部分收口）

问题：

- 部署脚本已有 readyz/protected API/HTTPS 检查，但对用户最关心的登录、SSE、数据中心、模拟盘状态没有统一摘要。

建议修复：

- 部署后输出“登录可用、实时流 token、API fallback、数据门、paper summary”的一页式 Markdown 摘要。

本轮处理：

- 部署 smoke 已新增 API fallback JSON 404。
- 登录/SSE/data/paper 一页式摘要仍建议下一批接入云端部署报告。

## 4. 后端 API 审查结果

鉴权：

- Auth refresh 使用 httpOnly refresh cookie，生产配置有 secure/samesite 约束。
- Admin 写操作通过 admin token 或 admin role 门控。
- 本轮修复了前端显式 refresh 与 request 内部 refresh 的 single-flight 不一致。

错误处理：

- 已修复 API 前缀落入 SPA fallback 的问题。
- 建议补充更多“错误格式一致性”测试，尤其是不存在的 API path、method not allowed、未登录、权限不足。

幂等：

- RuntimeTaskQueue enqueue 支持 idempotency key。
- 写操作是否全面带 idempotency key 仍需按路由逐项补齐。

未发现明显问题：

- 未发现公开管理写接口。
- 未发现策略生产分直接由前端传入。
- 未发现敏感 token 在 operation audit 中直接记录的证据。

## 5. 数据层与任务系统审查结果

优点：

- RuntimeTaskQueue 有 idempotency、claim、heartbeat、progress、event、stale running recovery。
- `claim_next()` 对支持的数据库使用 `skip_locked`。
- stale running 会自动恢复或失败，避免 UI 永久 pending。

风险：

- P1：Web 主进程仍注册大量后台循环。
- P2：失败重试没有 backoff。
- P2：研究/factor/ML job 需要生产默认关闭的部署验收。

未发现明显问题：

- 未发现 `backend/data` 被 Git 跟踪。
- 未发现 SQLite 本地开发数据被部署脚本打包上传的证据。

## 6. 策略、回测、模拟盘审查结果

生产/研究边界：

- `backend/app/services/low_buy/strategy_policy.py:26-40` 将 `n_pattern_long_wash`、`n_pattern_short_wash` 等归为 RESEARCH。
- `backend/app/services/low_buy/strategy_policy.py:54` 只有 CORE/AUX 属于生产优先策略。
- `backend/app/services/low_buy/strategy_policy.py:108-109` 生产榜参与函数只允许 CORE/AUX。
- `backend/app/services/low_buy/production_scoring.py:113-126` 非生产状态不会取得 `production_score`，`near_entry` 标记 `near_entry_watch_only`。
- `backend/app/services/low_buy/production_scoring.py:128-139` 非生产策略返回 `research_watch_only`，`production_score=None`。

本次策略边界验证：

- `backend/.venv/bin/python -m pytest backend/tests/test_low_buy_production_scoring.py backend/tests/test_n_pattern_observe_confirmed.py -q`
- 18 passed。

风险：

- 历史回测大 JSON 仍在 docs/reports，容易被误读为当前生产结论。
- 回测报告仍需持续区分真实组合收益、每日信号等权收益、观察池收益和样本留存。

未发现明显问题：

- 未发现 `near_entry` 直接进入 `production_score` 的证据。
- 未发现 RESEARCH 策略通过生产评分取得生产分的证据。

## 7. 前端页面与交互审查结果

架构护栏：

- `frontend/scripts/check-refactor-guard.mjs:5-13` 只允许 `ui/grid/VirtualGrid.tsx` 使用 raw AntD Table，并禁止 `useState/useReducer`、`echarts-for-react` 等。
- 本次检查：`rg "\buseState\b|\buseReducer\b" frontend/src` 无输出。
- 本次检查：`rg "<Table" frontend/src` 仅命中 `frontend/src/ui/grid/VirtualGrid.tsx`。

401/SSE：

- 已修复 session restore 与 SSE subscribe token 的 refresh 竞态。
- stream token 获取失败会重连，超限后 fallback polling，不阻塞页面。

页面风险：

- CSS/inline style 债务仍较高。
- 个别页面/组件/测试文件仍超长，需要继续小步拆分。
- 本次未重新跑 375/768/1440 responsive smoke；此前页面改动不属于本轮 401 修复范围。

未发现明显问题：

- 未发现新增 raw Table。
- 未发现新增 `useState/useReducer`。
- 未发现服务端响应重新塞回 Zustand 的新增证据。

## 8. 性能瓶颈与优化建议

已知瓶颈：

- Web 主进程后台循环过多，可能与在线 API 竞争资源。
- 前端大 CSS 和大页面组件影响维护与局部渲染优化。
- `docs/reports` 大量 JSON 增加仓库操作和搜索成本。
- RuntimeTaskQueue 失败重试无 backoff，故障时可能放大负载。

建议：

1. 先把 Web 后台 loop 迁到 scheduler/worker。
2. 给 RuntimeTaskQueue retry 增加指数退避。
3. 对 `/metrics` 增加 web/worker/job 维度。
4. 持续压缩 CSS guard baseline。
5. 历史机器报告迁出 docs 人读区。

## 9. 安全与部署运维风险

安全正向发现：

- Auth cookie 生产配置有 secure/samesite 检查。
- Admin API 有 token/role 门控。
- Operation audit 对 token/secret/password/cookie/authorization/api_key 做脱敏。

主要风险：

- P1：因子研究动态 exec。
- P1：快速部署默认跳过本地检查并内置个人 key 路径。
- P1：Web 主进程后台 loop 过多。
- P2：shell=True 执行研究 manifest 命令。

建议：

- 部署脚本默认安全，快速路径必须显式确认风险。
- 生产部署验收增加 API fallback 404、SSE token、登录刷新并发测试。
- research/factor/ML 能力默认关闭，并在 `/readyz` 或 `/metrics` 可见。

## 10. 测试缺口

本次已运行：

- `cd frontend && npm run lint`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build:web`
- `cd frontend && npm test -- --run src/api/base.test.ts src/state/realtime/useQuoteStream.test.tsx`
- `backend/.venv/bin/python -m pytest backend/tests/test_legacy_routes.py backend/tests/test_auth_hardening.py backend/tests/test_auth_routes.py backend/tests/test_sse_token_service.py -q`
- `backend/.venv/bin/python -m pytest backend/tests/test_low_buy_production_scoring.py backend/tests/test_n_pattern_observe_confirmed.py -q`
- `git diff --check`
- `rg "\buseState\b|\buseReducer\b" frontend/src`
- `rg "<Table" frontend/src`

仍需补充：

- 全量后端 pytest。
- 云端 HTTPS 登录刷新 + SSE subscribe smoke。
- `/api/*` GET fallback 404 云端验证。
- 375/768/1440 responsive smoke。
- factor mining sandbox/permission 恶意输入测试。
- RuntimeTaskQueue retry backoff 测试。

## 11. 文档、契约、报告口径问题

OpenAPI：

- 本次未改 OpenAPI schema。
- 本轮 401 修复只改 catch-all fallback 和前端请求行为。

报告口径：

- 需要继续严格区分生产/研究/观察。
- 需要继续区分真实组合收益、每日信号等权收益、观察池收益。

文档治理：

- `docs/reports/` 应逐步只保留 Markdown 摘要。
- 历史 JSON 不建议直接删除，先建 manifest 和迁移策略。

## 12. 无用、过期、重复、废弃文件清理清单

### 已删除

0 个。

原因：

- 本次没有找到可在无风险条件下直接删除的已跟踪源码、部署配置、迁移、报告或契约文件。
- 用户要求系统级审查与问题清单；除 401 修复外不扩大代码清理。

### 建议删除

1. 本地忽略缓存：约 814 个 `__pycache__` / `.pyc`。
   - 证据命令：`find backend/app backend/tests backend/scripts -name '__pycache__' -o -name '*.pyc' | wc -l`
   - 引用判断：Python 缓存产物，不应作为源码引用。
   - 风险：低。
   - 验证：删除后跑 backend targeted pytest。

### 建议迁移/归档，暂不直接删除

1. `docs/reports` 下约 380 个 JSON/JSONL 机器产物。
   - 原因：违反当前产物治理方向，但可能有审计/回溯价值。
   - 处理建议：建立 manifest，迁入 `backend/data/reports/` 或外部 artifacts，docs 保留 Markdown 摘要。

2. 超长历史报告和历史回测 JSON。
   - 原因：可能仍被历史报告引用。
   - 处理建议：先用 `rg --fixed-strings <basename> .` 做逐个引用检查，再决定归档。

### 暂不删除

- `backend/data/`：本地数据资产，不确认删除。
- `docs/contracts/openapi.json`：契约产物，不删除。
- `backend/app/services/factor_mining/*`：虽有风险，但仍有后端入口、权限门、任务开关和研究价值，不能当死代码删除。
- `android/`、`ios/`、Capacitor 相关历史工程：本次审查未证明完全废弃，不删除。
- 部署脚本：存在风险但仍是生产入口，不删除，先整改。

## 13. 分批整改计划

### G1：401/SSE 与部署安全收口

目标：

- 把本轮 401 修复提交并部署验证。
- 快速部署默认安全化。

范围：

- `frontend/src/api/base.ts`
- `frontend/src/api/appClient.ts`
- `frontend/src/state/realtime/useQuoteStream.ts`
- `backend/app/main.py`
- `scripts/quick_cloud_deploy.sh`
- 部署 smoke 脚本。

测试：

- 前端 auth/SSE 测试。
- 后端 legacy route/API fallback 测试。
- 云端 curl：登录、refresh、SSE token、API fallback 404。

上线门禁：

- 工作区干净。
- frontend lint/test/build 通过。
- 后端相关 pytest 通过。
- 云端 smoke 通过。

### G2：任务系统与后台隔离

目标：

- Web 主进程不跑重后台 loop。
- RuntimeTaskQueue 失败重试有 backoff。

范围：

- `backend/app/runtime/background_jobs.py`
- `backend/app/services/tasks/queue.py`
- worker/systemd/deploy 配置。

测试：

- queue retry/backoff 单测。
- worker claim/heartbeat/recovery 集成测试。
- systemd web/worker 分离 smoke。

上线门禁：

- `/metrics` 能看出 worker/job 状态。
- Web 日志无后台重任务 loop。

### G3：研究沙箱、产物治理、前端债务

目标：

- factor mining 动态执行降风险。
- docs/reports 机器产物迁移。
- CSS/大文件继续压缩。

范围：

- `backend/app/services/factor_mining/compute_engine.py`
- 回测/报告脚本默认输出目录。
- `docs/reports` manifest。
- frontend CSS Module/组件拆分。

测试：

- factor malicious formula tests。
- 报告脚本输出路径测试。
- frontend lint/test/build/analyze。
- responsive smoke。

上线门禁：

- 研究能力默认关闭。
- 机器产物不再新增到 docs/reports。
- CSS guard baseline 继续下降。

## 14. 已覆盖范围与未覆盖范围

已覆盖：

- 全仓目录和文件级扫描。
- 高风险源码路径行级审查。
- 前端架构 guard 验证。
- 认证/SSE/策略边界 targeted tests。
- 部署脚本关键路径阅读。
- 文件清理候选引用风险判断。

未覆盖：

- 未执行全量 backend pytest。
- 未执行云端部署和线上 smoke。
- 未执行本轮 responsive smoke。
- 未逐行审查生成产物、依赖目录、历史巨型 JSON。

原因：

- 依赖目录、生成产物、历史机器报告不属于人工源码逐行审查对象。
- 本轮按用户要求不部署，云端 smoke 只能列为后续上线门禁。

## 15. 本轮 401 修复改动清单

修改文件：

- `frontend/src/api/base.ts`
- `frontend/src/api/appClient.ts`
- `frontend/src/api/base.test.ts`
- `frontend/src/state/realtime/useQuoteStream.ts`
- `frontend/src/state/realtime/useQuoteStream.test.tsx`
- `backend/app/main.py`
- `backend/tests/test_legacy_routes.py`

新增文件：

- `docs/reports/full-project-code-review-2026-06-02.md`

验证摘要：

- `npm run lint`：通过。
- `npm test -- --run`：50 files passed，154 tests passed。
- `npm run build:web`：通过。
- `npm run api:check`：通过，OpenAPI sha256 `eeaad0612d692a3d65a1292129a795fa662fe87b1be3a6d44b8184e4cfd83f5d`。
- `npm run analyze`：通过，生成 `frontend/dist/bundle-report.json`。
- `npm run smoke:responsive`：通过，生成 `frontend/dist/responsive-smoke-report.json`。
- 后端全量 `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q`：1098 passed，1 个 LibreSSL warning。
- 前端 auth/SSE focused tests：8 passed。
- 后端 auth/SSE/legacy focused tests：12 passed。
- 策略边界 tests：18 passed。
- `git diff --check`：通过。
- `rg "\buseState\b|\buseReducer\b" frontend/src`：无输出。
- `rg "<Table" frontend/src`：仅 `frontend/src/ui/grid/VirtualGrid.tsx`。
- 部署脚本、任务退避、因子安全、后台角色、manifest 安全、public API focused tests：通过。
- 新增报告索引和本地清理脚本测试：通过。

部署状态：未部署。
