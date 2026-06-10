# 平台优化执行计划（2026-06-10）

> 依据：`docs/reports/platform-system-check-2026-06-10.md`（体检结果）。
> 性质：**收口型计划**——只修体检发现的具体问题与流程缺口，不扩功能、不重构架构。
> 每个工作包独立可验收、可回滚；按 O1→O7 串行或按优先级并行。

---

## 0. 硬边界（全程不可破）

1. 不改 `strategy_policy.py`、生产策略公式、`production_score`、priority board 排序语义、风控阈值。
2. `strategy_engine` 保持 shadow-only；execution model 保持 preview（`replacement_enabled=false`）。
3. 不动收盘数据发布门控（publish-if-ready / invalid OHLC blocker / 交易日口径）。
4. 旧前端不做功能改造（仅退役工程自身收尾）；不部署、不切流，部署需单独授权。
5. 不回滚并行在途的"旧前端退役"工程改动；与其作者协同的项显式标注。
6. 测试修复必须保留原守卫语义（顺序保持、no-write、缺数据不伪造），只对齐文案/seam，不放松断言。

---

## P0（本周内，阻断级）

### O1 对齐 5 个 data/settings e2e（测试债务收口）

- **现状**：`94fc9d2c` 重写了 data/settings 管理令牌门控 UX，5 个 e2e 断言过期：
  - `tests/e2e/backtest-data-settings.spec.ts` ×2
  - `tests/e2e/data-settings-error-states.spec.ts` ×1
  - `tests/e2e/interaction-parity.spec.ts` ×2
- **动作**：
  1. 按文案映射更新断言：
     - `令牌验证未通过` → `管理授权缺失`
     - `[全局配置] 需要先校验管理令牌。` → `请先在顶部校验管理令牌。` / `[X] 当前只读，请先解锁管理操作`
     - `管理员权限校验通过，本页本地编辑已解锁。` → `已使用当前管理员账号解锁本地编辑。`
  2. fixture 补 6 个新端点 mock：`/api/data-quality/coverage`、`/api/data-quality/sla`、`/api/runtime-tasks?limit=*`、`/api/runtime-tasks/summary`、`/api/admin/metrics`、`/api/admin/tasks`（interaction-parity 与 error-states 共用的 `cutover-fixtures.ts` 优先收敛到 `installDataSettingsFixtures`）。
  3. **保留**核心断言：零写请求（`writes()===[]`）、403/503 错误态可见、admin 守卫拦截。
- **归属**：data/settings 是退役工程的活跃工作面，**优先由其作者执行**（避免对半成品 UX 写错断言）；若 2 个工作日内未收口，按上述映射独立执行。
- **验收**：`npx playwright test tests/e2e/backtest-data-settings.spec.ts tests/e2e/data-settings-error-states.spec.ts tests/e2e/interaction-parity.spec.ts --project=chromium` 全绿；`npm run e2e` **47/47**。
- **回滚**：纯测试文件改动，revert 即可。
- **工作量**：0.5–1 人日。

### O2 重构/瘦身类提交强制全量回归（流程缺口，根因级）

- **现状**：`94fc9d2c` 单提交造成 **2 处真实生产回归**（paper 预热误删、核心闭环 smoke 路径误删）+ 7 个红测，但仍被合入——守卫体系有效，**执行纪律缺失**。
- **动作**：
  1. CI（`.github/workflows/ci.yml`，注意该文件正被退役工程修改，**协同改**）：后端 job 跑 `pytest backend/tests`（已有则确认未被裁剪为子集）；新增 frontend-next job：`typecheck + lint + test --run + build`；e2e 至少跑 `monitor-workflows + monitor-live-readiness`（策略守卫关键路径）。
  2. 约定写入 `docs/engineering-conventions.md` §6.11 验收分层：**涉及删除/瘦身/重构的提交，合入前必须本地全量 `pytest backend/tests` + 受影响前端 e2e 全绿**，PR 描述贴结果。
- **验收**：在 CI 上用一个故意删 `paper_position_symbols` 的试验分支验证会被拦截（验完丢弃分支）。
- **回滚**：CI 配置 revert。
- **工作量**：0.5 人日（与退役工程的 CI 改动合并提交）。

---

## P1（两周内）

### O3 CI/本地串行化 api:check 与 vitest（消除假红）

- **现状**：`api:check` 重写 `src/generated/api-types.ts` 与 vitest 并发 → 偶发 2 个假失败（本轮实测复现：并发批 2 失败，隔离复跑 2 次全绿）。
- **动作**：CI 步骤排序为 `api:check → typecheck → lint → test → build`（禁止并行段）；本地 `package.json` 加聚合脚本 `check:all` 固化顺序。
- **验收**：连续 3 次 `npm run check:all` 全绿无抖动。
- **工作量**：0.25 人日。

### O4 线上服务器内存优化落地（稳定性最大杠杆）

- **现状**：4C/3.7G 机器 Swap 1.74G/1.99G 重度使用；体检确认这是线上稳定性（含前端 chunk 加载慢/白屏诱因之一）的最大环境因素。
- **动作**：按既有《`docs/reports/cloud-server-optimization-plan-2026-06-09.md`》执行 P0+P1：
  1. `docker builder prune -af`（−11.8G 磁盘）+ 停分离验证栈 + `vm.swappiness=10`；
  2. `APP_WORKERS=2→1`、analytics/backtest worker 改 compose profile 按需、mysql `innodb_buffer_pool_size=256M`；
  3. 观察一个交易日后合并 runtime-scheduler 进 runtime-worker（−450M，体检确认 `runtime_worker_embed_scheduler` 开关已存在）。
- **验收**：`free -m` Swap <300M、空闲 >1G；`/readyz` 全 true；收盘发布/定时刷新按时；`docker stats` 常驻内存较基线 ↓~700M–1G。
- **回滚**：每步独立（重启分离栈 / 改回 WORKERS / 重启独立 scheduler）。
- **归属**：需服务器操作授权，**本计划不代执行**。
- **工作量**：0.5 人日 + 1 交易日观察。

### O5 旧前端退役收尾联动（消除双栈维护）

- **现状**：退役工程在途（`legacy-frontend-retirement-execution-2026-06-10.md`、CI/Dockerfile/部署脚本、echarts 移除、chunkReload 移植均已落）。
- **动作**（协同项，不抢工作面）：
  1. 退役完成时**同步退役旧前端守卫**（如 `test_responsive_smoke_covers_all_workspace_routes` 与 `smoke-responsive.mjs` 一起下线，而非再次出现"删脚本留守卫"或"删守卫留脚本"的半套状态）；
  2. 确认旧前端白屏自愈修复（tquant-sw v4 / chunkReload）在退役前的过渡期内随最后一次旧前端部署生效；
  3. 退役后删除 `frontend/` 相关 CI job 与依赖安装，缩短流水线。
- **验收**：退役 PR 内旧前端守卫/脚本/CI 成对增删；全量 pytest + frontend-next e2e 全绿。
- **工作量**：并入退役工程，增量 ~0.5 人日。

---

## P2（跟进，非阻断）

### O6 analytics 测试日期防漂移工具

- **现状**：本轮 3 个 fixture 因 `created_at` 默认=今天落在导出窗口外而假红；此前 `test_low_buy_read_paths` 也出现过同类漂移。**同类问题已发生 ≥2 次**。
- **动作**：`backend/tests/` 增加共享工具（如 `tests/support/timefreeze.py`）：提供 `within_export_window(end_date, offset_days)` 风格的时间构造 + 文档注释"任何带日期窗口过滤的导出/读路径测试，fixture 必须显式时间戳"；将本轮修过的 4 处改用该工具作为示范。
- **验收**：`pytest backend/tests/test_analytics_layer.py backend/tests/test_low_buy_read_paths.py` 绿；grep 确认目标测试不再依赖 DB 默认时间戳。
- **工作量**：0.5 人日。

### O7 tanstack-misc 139KB 评估再拆（可选）

- **现状**：bundle 650KB 已远低于预算，`tanstack-misc` 139KB 为最大第三方块之一（router/query/table/virtual 合包）。
- **动作**：先用 `npm run chunk:profile` 看各页实际引用面；仅当 table/virtual 只被 2 个以下页面使用时才按页 lazy 拆分；否则**保持现状**（避免为拆而拆）。
- **验收**：拆分后 bundle budget 仍绿、首屏 chunk 不增、e2e 全绿；或出具"不拆"结论一句话记录。
- **工作量**：0.5 人日（含评估）。

---

## 专项一：云服务器资源占用缩减（O8–O9）

> 回答「资源占用是否可以减小」：**可以，且大部分配置已在仓库就绪，缺的是线上执行与三个收尾杠杆。** 当前线上：4C/3.7G、Swap 1.74G/1.99G 重度使用、Docker build cache 11.8G、分离验证栈空跑。

### 已在仓库落地（执行 O4 重新部署即生效，勿重复开发）

| 项 | 仓库现状（2026-06-10 实测） |
|---|---|
| 逐服务资源上限 | compose 已配 `mem_limit/cpus`：mysql 1024m/1.5C、app 768m/1.5C、runtime-worker 768m/1.5C、runtime-scheduler 640m/1C、analytics 512m/1C、redis 128m、migration/backup 各 512m/256m |
| APP_WORKERS | 默认已是 **1**（compose `:-1`） |
| scheduler 合并开关 | `RUNTIME_WORKER_EMBED_SCHEDULER` 已实现，默认 false，**一个 env 翻转即省 ~472M 常驻** |
| DB 驱动 | 已切 `mysql+mysqldb`（mysqlclient C 驱动） |

### O8 线上资源收口（在 O4 基础上补三个收尾杠杆）

- **现状缺口**：
  1. **上限之和超物理内存**：1024+768+768+640+512+128(+go/migration/backup) ≈ **3.9G+ > 3.7G RAM**——即使全配了 limit，仍是超卖状态，Swap 风险未根除；
  2. `analytics-worker`/`backtest-worker` 仍 `restart: unless-stopped` 常驻（任务低频，空载占基线内存）；
  3. 日志轮转仅 1 处 `options:` 命中，**未覆盖全部服务**。
- **动作**：
  1. **翻转 `RUNTIME_WORKER_EMBED_SCHEDULER=true`** 并停独立 scheduler 容器（观察一个交易日：收盘发布/定时入队正常）→ 上限之和 −640M，**落回物理内存以内**；
  2. analytics/backtest worker 改 compose `profiles: [heavy]` 按需拉起（重任务前 `--profile heavy up`，跑完 down），写入 runbook；
  3. 日志 `logging: {options: {max-size: "10m", max-file: "3"}}` 补齐到全部服务；
  4. 服务器侧执行（同 O4）：`docker builder prune -af`（−11.8G）、停分离验证栈（公网未代理）、`vm.swappiness=10`、mysql 容器内 `innodb_buffer_pool_size` 与 1024m limit 对齐（建议 384–512M）。
- **量化目标**：常驻容器 13→**7–8**；上限之和 ≤3.2G（< 物理内存）；Swap 1.74G→**<300M**；磁盘 62%→~40%。
- **验收**：`free -m`、`docker stats --no-stream`、`/readyz` 全 true、收盘发布按时、24M 报告可按需拉起完成。
- **回滚**：env 翻回 / profile 改回常驻 / 重启分离栈，每步独立。
- **工作量**：0.5 人日 + 1 交易日观察（与 O4 合并执行）。

### O9 镜像与构建产物瘦身（随退役工程）

- **现状**：Docker 镜像 14.23G（含双前端构建链）；build cache 已由 O8-4 处理。
- **动作**：旧前端退役完成后——Dockerfile 移除 `frontend/` 构建阶段与依赖安装；删除旧镜像 tag；CI 移除旧前端 job（与 O5 成对执行）。
- **量化目标**：镜像总量预计 −2~4G；CI 时长缩短（少一套 npm install + build）。
- **归属**：并入退役工程，**不抢工作面**。
- **工作量**：增量 ~0.25 人日。

---

## 专项二：性能提升（O10–O12）

> 回答「性能是否可以提高」：**可以，三个方向：① 消除 Swap 是当前最大性能杠杆（已由 O4/O8 覆盖）；② 热读路径还有一个已知 N+1 待核验修复；③ 缓存命中率需要线上度量闭环。** 前端 bundle 已 650KB/echarts 已移除，前端侧无大杠杆剩余（仅 O7 可选项）。

### 已落地（勿重复开发）

| 项 | 现状 |
|---|---|
| 行情缓存按需预热 | `build_quote_cache_demand_symbols` 已上线（榜单/监控/自选/持仓/追踪/板块/指数 ETF 七类需求集；本轮体检已修复 paper 持仓缺口）+ 覆盖率告警函数已存在 |
| DB C 驱动 | mysqlclient 已切换（全链路 DB I/O 提速） |
| Rust 数学库复用 | 引用面 1 文件 → **11 文件**（rolling/ATR/RSI/VWAP 等已接热路径） |
| 前端 | bundle 1.22MB→650KB、echarts 移除、lightweight-charts、BFF 合包（monitor 2 请求）、VirtualList |

### O10 热聚合 N+1 核验与修复（后端读路径）

- **现状**：`backend/app/services/low_buy/priority_items.py:71` 仍存在逐行循环；此前审计标记其逐行调用生产打分/上下文存在 DB 往返放大的嫌疑。**先测量后修**，不允许凭猜测改热路径。
- **动作**：
  1. 写一个"查询计数"测试：构造 N=20 候选，断言一次榜单构建的 DB 往返 ≤ 上界（用 SQLAlchemy event 监听 `before_cursor_execute` 计数）；
  2. 若超界：共享上下文（market_context/shadow 状态）一次预取传入，逐行查询改 `in_` 批量；
  3. **golden 守卫**：修复前后同输入榜单字段 sha256 一致（排序/分数零漂移）。
- **验收**：查询计数测试绿；`test_low_buy_production_scoring`、priority variants 等 67 个策略守卫全绿；榜单输出逐字节一致。
- **回滚**：按文件 revert；不改任何口径。
- **工作量**：1 人日。

### O11 线上性能度量闭环（命中率与 p95 基线门）

- **现状**：预热与覆盖率告警代码已就绪，但**线上命中率/延迟从未在优化后复测**（上一次云报告：market-read Redis 命中 ~20%、`monitor_bff` p95 一度 852ms——均为优化前数据）。
- **动作**（O4/O8 部署后执行，只读）：
  1. 拉 `/metrics`：`local_quote_cache_*`、market-read `hits/mysql_fallbacks/unresolved`、`bff_partial_timeout`；
  2. 跑既有云性能脚本取 `monitor_bff/priority_board` p95；
  3. 与目标门对比：**Redis 命中 ≥90%、mysql_fallbacks ≤ 旧基线×0.2、bff_partial_timeout=0、p95 ≤500ms**；
  4. 未达标项回查（预热集合是否覆盖、TTL、worker 刷新频率），形成一页结论报告。
- **验收**：产出 `docs/reports/cloud-performance-recheck-2026-06-XX.md`，各指标达门或列明残差与下一步。
- **工作量**：0.5 人日（需服务器只读访问）。

### O12 Rust 复用收尾（可选，测量先行）

- **现状**：11 文件已接入；剩余 pandas/numpy 热点（回测引擎内层循环、analytics 聚合）未全量替换。
- **动作**：仅当 O11 显示扫描/回测墙钟仍是瓶颈时推进：逐文件替换 + **parity 1e-9 测试**（同输入 Rust vs Python 数值一致）+ 一文件一提交；`rust_math_*` metrics 监控 fallback 率。
- **边界**：不并行实现 `portfolio_backtest_metrics`（唯一事实源），只在其内部加速。
- **工作量**：按 O11 结论再排（预估 2–4 人日）。

---

## 执行顺序与依赖

```
O1（e2e 对齐，等退役作者 2 天 → 否则自接）─┐
O2（CI 全量回归门）──────────────────────┼─→ 全绿基线 → O5 / O9（随退役收尾）
O3（api:check 串行）─────────────────────┘
O4 + O8（服务器资源收口，独立授权，随时可做）──→ O11（性能复测，部署后）──→ O12（按结论可选）
O10（N+1 测量先行，可与 O1–O3 并行）
O6 / O7（基线稳定后跟进）
```

## Definition of Done

- [ ] frontend-next e2e 47/47、单测全绿、bundle budget 绿
- [ ] 后端全量 pytest 持续 0 失败（CI 强制）
- [ ] CI 含 frontend-next job 且步骤串行，无竞态假红
- [ ] **资源**：常驻容器 7–8、上限之和 ≤3.2G（< 物理内存）、线上 Swap <300M、磁盘 ~40%、`/readyz` 全 true（O4+O8 授权执行后）
- [ ] **性能**：榜单构建 DB 往返有上界守卫且 golden 一致（O10）；线上复测 Redis 命中 ≥90%、`bff_partial_timeout=0`、热端点 p95 ≤500ms 或列明残差（O11）
- [ ] 退役收尾时旧前端守卫/构建链成对下线（O5+O9），无半套状态
- [ ] 日期漂移类假红有共享工具防再发
- [ ] 全程未触碰策略语义/生产排序/发布门控；未部署未切流（O4/O8/O11 的服务器操作需单独授权）
