# 平台优化收口需求文档（2026-06-10）

状态：待实施  
适用范围：`/Users/j/Documents/gupiao` 后端、`frontend-next`、CI、Compose/运维脚本、只读线上验收  
最后核验日期：2026-06-10  
来源计划：`docs/platform-optimization-execution-plan-2026-06-10.md`  
事实依据：`docs/reports/platform-system-check-2026-06-10.md`、`docs/reports/cloud-server-optimization-plan-2026-06-09.md`、当前工作树代码与配置

## 1. 结论

原执行计划中提到的大多数问题真实存在，解决方向可行；但部分描述需要按当前工作树修正后再作为实施需求：

1. `data/settings` 5 个 e2e 过期断言可修，属于测试债务，不需要改产品主流程。
2. CI 全量回归和 `api:check` 串行方向正确；当前 `.github/workflows/ci.yml` 已具备后端全量 pytest 与 `frontend-next` 串行 job 形态，剩余重点是固化“重构/瘦身提交必须全量回归”的规范和补关键 e2e 门。
3. 服务器资源优化可行，仓库已具备 `APP_WORKERS=1`、`mem_limit/cpus`、统一 logging、`analytics-worker` profile、`RUNTIME_WORKER_EMBED_SCHEDULER` 灰度能力；线上执行与性能复测必须单独授权。
4. `analytics/backtest worker 改 profile` 需修正：当前 `analytics-worker` 已是 `profiles: ["analytics"]`，独立 `backtest-worker` 已移除；本需求只要求确认按需语义、清理残留容器、补 Runbook，不要求重新实现 profile。
5. 旧前端退役收尾可行，但当前属在途工作面，必须成对处理守卫、脚本、CI、Docker 和部署 scope，不允许半删。
6. 热读 N+1 只能先测量后修复；`priority_items.py` 中逐候选构建属可疑点，但不得在没有查询计数和 golden 输出一致性前改热路径。
7. 前端 `tanstack-misc` 再拆是可选优化；当前 bundle 已低于预算，必须先用 `chunk:profile` 证明收益。

本需求文档是“收口型需求”：只修体检发现的问题、流程缺口和可验证性能/资源风险，不扩功能、不改策略语义、不部署不切流。

## 2. 硬边界

1. 不修改 `backend/app/services/low_buy/strategy_policy.py`。
2. 不改变生产策略公式、`production_score`、priority board 排序语义、风控阈值、交易日发布口径。
3. `strategy_engine` 保持 shadow-only，`replacement_enabled=false`，不得替代现有生产排序。
4. 不修改收盘数据发布门控：publish-if-ready、invalid OHLC blocker、交易日口径必须保持。
5. 不把研究、ML、因子、重分析任务放回 Web 主进程。
6. 不直接拆成大量微服务；继续遵循模块化单体优先、重任务 Worker 化、DuckDB/Parquet 分析层。
7. 不回滚当前在途的旧前端退役工程改动；涉及同一文件时按协同项处理。
8. 不执行线上部署、停容器、清理 Docker cache、改 sysctl、切流或服务器写操作；这些动作需要用户单独授权。

## 3. 当前事实基线

### 3.1 后端与策略

- 后端为 FastAPI + SQLAlchemy + Alembic，生产 MySQL/本地 SQLite 双形态。
- `production_scoring.py` 已通过 `participates_in_priority_board()` 控制生产分和生产排序准入。
- `strategy_engine/shadow.py` 明确输出 `shadow_only=true`、`replacement_enabled=false`、`production_sort_replaced=false`。
- priority board 热读路径已有缓存、read model 和物化 warmup 机制，热路径修复必须保持输出字段和排序一致。

### 3.2 前端与 e2e

- `frontend-next` 为 SolidJS + Vite + TanStack + lightweight-charts。
- `frontend-next/package.json` 已有 `api:check`、`typecheck`、`lint`、`test`、`build`、`e2e`、`chunk:profile` 等脚本，但缺少固定串行聚合脚本 `check:all`。
- `cutover-fixtures.ts` 当前已包含 `/api/data-quality/coverage`、`/api/data-quality/sla`、`/api/runtime-tasks*`、`/api/admin/metrics`、`/api/admin/tasks`、`/api/bff/v1/workspace/settings` 等 data/settings mock。
- `backtest-data-settings.spec.ts`、`data-settings-error-states.spec.ts`、`interaction-parity.spec.ts` 仍存在旧文案或旧页面 heading 断言，需要按当前 UX 对齐。

### 3.3 CI 与工程规范

- 当前 `.github/workflows/ci.yml` 已包含：
  - backend job：`pytest backend/tests`。
  - frontend-next job：`api:check -> typecheck -> lint -> npm test -- --run -> build`。
  - go-rust job 和 deploy job。
- `docs/engineering-conventions.md` §6.11 已有验收分层，但需要补充“删除/瘦身/重构类提交”必须全量回归和 PR 描述贴结果。

### 3.4 资源与部署配置

- `docker-compose.mysql.yml` 当前已配置统一 `x-default-logging`、`mem_limit`、`memswap_limit`、`cpus`。
- `APP_WORKERS` 默认值已是 `1`。
- `runtime-worker` 已暴露 `RUNTIME_WORKER_EMBED_SCHEDULER`，默认 `false`。
- `analytics-worker` 已是按需 profile：`profiles: ["analytics"]`。
- 独立 `backtest-worker` 不应作为常驻服务重新引入；部署脚本保留清理残留容器逻辑。
- `PRODUCTION_RUNBOOK.md` 已描述 analytics 按需、scheduler 灰度和资源相关环境变量。

## 4. 目标与非目标

### 4.1 目标

1. 恢复 `frontend-next` data/settings e2e 全绿，并保留 no-write、403/503、admin 守卫语义。
2. 固化 CI 与本地回归顺序，避免重构/瘦身类提交绕过全量测试。
3. 消除 `api:check` 与 vitest 并发重写 generated types 的假红风险。
4. 将线上资源优化从“方案”转为“可授权执行的运维需求”，并明确只读验收指标。
5. 配合旧前端退役工程收尾，防止旧前端守卫、脚本、CI、Docker 出现半套状态。
6. 为日期窗口类测试建立共享 fixture 时间工具，减少漂移假红。
7. 对 priority board 热读 N+1 风险建立查询计数和 golden 输出守卫，必要时再做批量化。
8. 在资源优化和部署后做线上只读性能复测，形成可追踪报告。

### 4.2 非目标

1. 不新增交易策略、不调整买卖点、不改变仓位/风控参数。
2. 不把 `strategy_engine` 从 shadow 替换为事实源。
3. 不重构整体架构、不微服务化。
4. 不删除旧前端源码目录，除非旧前端退役观察期通过并另行授权。
5. 不为了 bundle 数字强拆 TanStack 依赖。
6. 不在本需求中执行生产部署或服务器写操作。

## 5. 分批需求

### R1. 对齐 5 个 data/settings e2e

优先级：P0  
对应原计划：O1  
性质：测试债务收口

需求：

1. 更新旧文案断言：
   - `令牌验证未通过` 改为当前 `管理授权缺失` 或对应弹窗/Toast 文案。
   - `[全局配置] 需要先校验管理令牌。` 改为 `请先在顶部校验管理令牌。` 或 `[X] 当前只读，请先解锁管理操作`。
   - `管理员权限校验通过，本页本地编辑已解锁。` 改为 `已使用当前管理员账号解锁本地编辑。`
2. 对齐当前页面标题和操作面板命名，尤其是 `/next/data`、`/next/settings` 的 heading。
3. 优先复用 `installDataSettingsFixtures`，避免在单个 spec 中重复维护 endpoint mock。
4. 保留核心安全断言：
   - 默认保护模式下 `writes() === []`。
   - 非 admin 访问显示权限不足。
   - 503/403 错误态不泄漏原始技术错误。
   - 管理令牌只解锁本地意图，不发真实写请求。

验收：

```bash
cd frontend-next
npx playwright test tests/e2e/backtest-data-settings.spec.ts tests/e2e/data-settings-error-states.spec.ts tests/e2e/interaction-parity.spec.ts --project=chromium
npm run e2e
```

通过标准：目标 3 个文件全绿；全量 e2e 达到当前基线 47/47 或列明仅剩与本需求无关的外部原因。

回滚：纯测试文件和 fixture 改动，可按文件 revert。

### R2. 固化重构/瘦身类全量回归门

优先级：P0  
对应原计划：O2  
性质：流程缺口修复

需求：

1. 确认 CI backend job 保持 `pytest backend/tests` 全量，不得裁剪为子集。
2. 确认 CI frontend-next job 保持串行：`api:check -> typecheck -> lint -> test -> build`。
3. 在 CI 中补关键 e2e 门，至少覆盖：
   - `frontend-next/tests/e2e/monitor-workflows.spec.ts`
   - `frontend-next/tests/e2e/monitor-live-readiness.spec.ts`
4. 更新 `docs/engineering-conventions.md` §6.11：
   - 删除、瘦身、迁移、重构、退役类提交，合入前必须跑 `pytest backend/tests`。
   - 影响 `frontend-next` 时必须跑 `api:check`、`typecheck`、`lint`、`test --run`、`build`，并跑受影响 e2e。
   - PR 或交付说明必须贴命令与结果，不能只写“通过”。
5. 不要求每次提交都跑全站 e2e；但涉及旧前端退役、入口切换、监控页、数据/设置页时必须跑对应 e2e。

验收：

```bash
python - <<'PY'
from pathlib import Path
ci = Path('.github/workflows/ci.yml').read_text()
assert 'pytest backend/tests' in ci
assert 'npm run api:check' in ci
assert 'npm run typecheck' in ci
assert 'npm run lint' in ci
assert 'npm test -- --run' in ci
assert 'npm run build' in ci
PY
rg -n "删除|瘦身|重构|全量回归|pytest backend/tests" docs/engineering-conventions.md
```

建议附加验证：创建本地临时试验分支，故意破坏 `paper_position_symbols` 或核心 smoke 路径，确认 CI/测试会失败；试验分支丢弃，不合入。

### R3. 本地 `check:all` 串行化

优先级：P1  
对应原计划：O3  
性质：假红消除

需求：

1. 在 `frontend-next/package.json` 增加：

```json
"check:all": "npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build"
```

2. CI 保持同样顺序，不并行运行 `api:check` 与 vitest。
3. 文档或交付说明中要求本地变更优先跑 `npm run check:all`。

验收：

```bash
cd frontend-next
npm run check:all
npm run check:all
npm run check:all
```

通过标准：连续 3 次全绿，无 generated type 竞态失败。

### R4. 线上资源优化执行需求

优先级：P1  
对应原计划：O4、O8  
性质：运维授权项

需求：

1. 保留当前仓库已落地的资源边界：
   - `APP_WORKERS: ${APP_WORKERS:-1}`
   - 每个核心服务有 `mem_limit`、`memswap_limit`、`cpus`
   - 统一 `logging` 配置
   - `analytics-worker` 按需 profile
   - `RUNTIME_WORKER_EMBED_SCHEDULER=false` 默认关闭
2. 线上执行前先做只读基线：
   - `free -m`
   - `df -h /`
   - `docker system df`
   - `docker stats --no-stream`
   - `/readyz`
   - `/metrics` 中 market-read、BFF、local quote cache 指标
3. 授权后分步执行：
   - 清理 Docker build cache：`docker builder prune -af`
   - 在 nginx 仍指向主栈 `18090` 时停 separated 验证栈
   - 设置 `vm.swappiness=10`
   - 保持 analytics worker 默认不常驻，仅按需 `--profile analytics` 拉起
   - 灰度 `RUNTIME_WORKER_EMBED_SCHEDULER=true`
   - 完整观察 1 个交易日后，才可单独授权停独立 `runtime-scheduler`
4. MySQL buffer pool 调整以当前机器内存和监控为准，不能盲目降到过低；建议区间 384M-512M。
5. 不将 `APP_WORKERS 2 -> 1` 计入新的线上收益，除非只读基线证明线上当前确实大于 1。

验收：

```bash
free -m
df -h /
docker stats --no-stream
curl -fsS https://weisilianghua.cloud/readyz
```

目标：

- Swap 已用 < 300M。
- 空闲内存 > 1G。
- 常驻容器 7-8 个左右，或报告列明保留原因。
- `/readyz` 全 true。
- 收盘发布、定时刷新、priority materialization 正常。
- 24M 报告或分析任务可通过 `--profile analytics` 按需完成。

回滚：

- swappiness 改回原值。
- separated 栈重新 `up -d`。
- `RUNTIME_WORKER_EMBED_SCHEDULER=false` 并恢复独立 scheduler。
- analytics profile 语义不变；如任务堆积，按需启动 analytics worker。

### R5. 旧前端退役收尾联动

优先级：P1  
对应原计划：O5、O9  
性质：协同项

需求：

1. 不抢当前旧前端退役工作面；只在退役 PR/批次内要求成对收尾。
2. 退役完成时成对处理：
   - 旧前端 smoke 脚本与后端守卫一起下线或一起保留。
   - CI 中旧前端 job 与 artifact 一起移除。
   - Dockerfile、deploy/frontend、nginx、deploy scope 一起收口到 `frontend-next`。
   - 旧前端 service worker/chunkReload 过渡修复在部署观察期内保持有效，不在观察前物理删除源码。
3. 删除 `frontend/` 源码目录必须满足：
   - `frontend-next` 线上稳定观察 1-2 个交易日。
   - 无入口需要回滚旧前端。
   - `frontend/` 当前未提交改动已归档、提交或明确废弃。
   - 创建可回滚 tag 或保留上一版镜像。

验收：

```bash
rg -n "frontend-legacy|frontend-hot|frontend/dist|html-root|__legacy" Dockerfile deploy scripts backend .github Makefile
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py -q
cd frontend-next && npm run check:all
```

通过标准：引用只剩历史说明、兼容阻断或明确归档说明；无“删脚本留守卫”或“删守卫留脚本”的半套状态。

### R6. 日期窗口测试工具

优先级：P2  
对应原计划：O6  
性质：测试稳定性治理

需求：

1. 在 `backend/tests/support/` 新增共享时间工具，例如：
   - `within_export_window(end_date, offset_days=0)`
   - `fixed_export_datetime(date_text, hour=9, minute=0)`
2. 约定任何受日期窗口过滤影响的导出、analytics、read path 测试，fixture 必须显式设置 `created_at`、`generated_at` 或同类时间戳。
3. 将本轮已修过或已知易漂移测试改用工具：
   - `backend/tests/test_analytics_layer.py`
   - `backend/tests/test_low_buy_read_paths.py`
4. 工具注释必须说明：不能依赖 DB 默认 today 时间。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_layer.py backend/tests/test_low_buy_read_paths.py -q
rg -n "datetime\\.utcnow\\(|datetime\\.now\\(|server_default|func\\.now\\(" backend/tests/test_analytics_layer.py backend/tests/test_low_buy_read_paths.py
```

通过标准：目标测试全绿；目标 fixture 不再依赖 DB 默认当前时间。

### R7. TanStack chunk 评估

优先级：P2  
对应原计划：O7  
性质：可选前端性能评估

需求：

1. 先执行 `npm run chunk:profile`，读取 `docs/reports/frontend-next-chunk-profile-2026-06-08.md/json` 或新日期报告。
2. 判断 `tanstack-table`、`tanstack-virtual`、`tanstack-misc` 的真实引用面。
3. 只有当 table/virtual 仅被少数非首屏页面使用，且 lazy 拆分不会增加首屏 chunk 和交互延迟时，才实施按页 lazy。
4. 若收益不足，产出“不拆”结论，禁止为拆而拆。

验收：

```bash
cd frontend-next
npm run build
npm run chunk:profile
npm run lint
npm test -- --run
```

通过标准：bundle budget 绿；首屏 JS 不增加；e2e 不新增失败；或形成明确“不拆”报告。

### R8. Priority board 热聚合 N+1 测量与修复

优先级：P1  
对应原计划：O10  
性质：后端热读性能守卫

需求：

1. 为 priority board 构建增加查询计数测试：
   - 构造 N=20 候选。
   - 使用 SQLAlchemy `before_cursor_execute` 监听目标表查询。
   - 断言单次榜单构建 DB 往返小于上界。
2. 增加 golden 输出一致性：
   - 同输入输出序列化后计算 sha256。
   - 修复前后 `items` 顺序、`production_score`、`priority_score`、lane、risk、strategy_engine_shadow 字段一致。
3. 只有当计数测试证明存在随 N 线性增长的 DB 往返时，才做批量化：
   - market context、shadow 状态、策略绩效、行业/板块上下文一次预取。
   - 逐行查询改为 `in_` 批量或缓存传入。
4. 不修改 `score_low_buy_candidate_for_production()` 语义，不改 `strategy_policy.py`。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_production_scoring.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_read_paths.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

通过标准：查询计数有上界；golden sha256 一致；策略守卫全绿。

### R9. 线上性能复测闭环

优先级：P1  
对应原计划：O11  
性质：只读线上验收

前置条件：R4 已获授权执行并完成至少一次稳定观察；或用户单独授权只读线上复测。

需求：

1. 拉取 `/metrics`，记录：
   - `local_quote_cache_*`
   - `tquant_market_read_redis_hits_total`
   - `tquant_market_read_cache_miss_total`
   - `tquant_market_read_mysql_fallbacks_total`
   - `tquant_market_read_unresolved_misses_total`
   - `bff_partial_timeout` 或等价 BFF timeout 指标
2. 执行现有性能脚本：

```bash
python3 scripts/measure_cloud_go_rust_performance.py --samples 8 --rounds 3
```

3. 产出报告：
   - `docs/reports/cloud-performance-recheck-2026-06-XX.md`
   - 可选 JSON 原始结果
4. 判断目标：
   - `monitor_bff` p95 <= 500ms。
   - `priority_board` p95 <= 500ms。
   - `bff_partial_timeout = 0`。
   - market-read unresolved = 0。
   - Redis 命中率目标 >= 90%；若未达标，必须列明 miss/fallback 是否来自 ETF、非 demand set、TTL 或预热缺口。

通过标准：达标或给出残差原因和下一步，不允许只写“性能正常”。

### R10. Rust 复用收尾评估

优先级：P2  
对应原计划：O12  
性质：测量后可选优化

需求：

1. 仅当 R9 显示扫描、回测或 analytics 墙钟仍是瓶颈时推进。
2. 一次只替换一个文件或一个计算函数。
3. 每个替换必须有 Rust vs Python parity 测试，数值误差 <= `1e-9` 或业务认可阈值。
4. Rust 只能做数学/指标加速；不得成为策略事实源，不得并行实现新的 `portfolio_backtest_metrics` 口径。
5. 保留 Python fallback，并用 metrics 记录 hit/fallback/error。

验收：

```bash
cd rust/tquant-rs && cargo test
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

## 6. 依赖与执行顺序

推荐顺序：

```text
R1 -> R2 -> R3
  \       \-> R5
   \-> R6

R4 --线上授权与观察--> R9 -> R10(可选)

R8 可与 R1-R3 并行，但必须独立提交、独立验收。
R7 只在基线稳定后评估。
```

依赖说明：

1. R1 是恢复 e2e 基线的前置。
2. R2/R3 是防止后续收口再次引入假绿或假红。
3. R4/R9 涉及线上，只能在单独授权后执行。
4. R5 依赖旧前端退役工程当前批次，不应抢同一工作面。
5. R8 不依赖线上，但修改热路径前必须先有查询计数和 golden。

## 7. 总体验收

本需求完成时必须满足：

- `frontend-next` e2e 全绿，至少 data/settings 相关 3 个 spec 全绿。
- `pytest backend/tests` 全绿。
- `frontend-next` 有 `check:all` 串行脚本，CI 顺序不并发 `api:check` 与 vitest。
- CI 或工程规范明确删除/瘦身/重构类提交的全量回归要求。
- Compose/Runbook 保持资源边界、analytics 按需、scheduler 灰度能力。
- 若获线上授权执行资源优化，则 Swap <300M、空闲内存 >1G、`/readyz` 全 true。
- 若获线上授权做性能复测，则产出 `cloud-performance-recheck` 报告，p95 和 metrics 有明确达标/残差结论。
- priority board 热读若改代码，必须有查询计数上界和 golden 一致性。
- 全程未修改策略语义、生产排序、`production_score`、交易日发布门控。
- 未经单独授权不得部署、切流或执行服务器写操作。

## 8. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| e2e 文案修复误改产品代码 | 引入 UX 或安全语义变化 | R1 只改测试/fixture，保留 no-write 和 admin 守卫 |
| CI 增加 e2e 后变慢 | PR 等待时间上升 | 只纳入关键路径 e2e，全量 e2e 可保留本地/夜间 |
| scheduler 合并后定时任务延迟 | 收盘发布或刷新延迟 | 先灰度 1 个交易日，保留独立 scheduler 回滚 |
| analytics 按需导致任务排队 | 24M 报告等待 | Runbook 明确 `--profile analytics` 启停命令 |
| N+1 修复改变排序 | 生产榜偏移 | golden sha256 + 策略守卫全绿后才合入 |
| TanStack 拆分收益不足 | 增加复杂度和加载抖动 | 先报告，不满足收益条件就不拆 |
| 当前工作树在途改动多 | 误回滚他人工作 | 实施前后都执行 `git status --short`，只改本需求文件范围 |

## 9. 交付物

1. 代码/测试改动：
   - R1、R2、R3、R6、R8 按独立提交交付。
2. 文档/规范：
   - 更新 `docs/engineering-conventions.md`。
   - 必要时更新 `PRODUCTION_RUNBOOK.md` 和 `docs/operations/*runbook.md`。
3. 报告：
   - R7 如不拆，输出一句话结论或短报告。
   - R9 输出 `docs/reports/cloud-performance-recheck-2026-06-XX.md`。
4. 线上执行证据：
   - 仅在用户授权后提供 raw command/result，不能用本地测试冒充线上状态。

## 10. 实施提示词

后续可按以下提示词直接执行：

```text
请在 /Users/j/Documents/gupiao 按 docs/platform-optimization-requirements-2026-06-10.md 串行实施。开始前必须执行 git status --short，保护当前在途改动。严格遵守硬边界：不改 strategy_policy.py、不改变 production_score、priority board 排序、生产策略语义、风控阈值、交易日发布门控；不部署、不切流、不执行服务器写操作，除非我单独授权。

执行顺序：先 R1 修 data/settings e2e，再 R2/R3 固化 CI 与本地 check:all；R8 可单独做但必须先加查询计数和 golden，一律先测量后修。R4/R9 只整理本地可执行脚本和只读验收说明，不要连服务器写操作。旧前端退役相关 R5 只做协同收尾，不回滚当前在途退役工程。

每批完成后跑对应验收命令，失败必须定位根因，不能放松断言。交付说明要列出改了哪些文件、跑了哪些命令、哪些未跑及原因，并明确是否部署/切流（默认没有）。
```
