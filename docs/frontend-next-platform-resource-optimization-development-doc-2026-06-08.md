# frontend-next 与平台资源优化落地开发文档（2026-06-08）

状态：开发文档，待实施
来源需求：`docs/frontend-next-platform-resource-optimization-requirements-2026-06-08.md`
适用范围：`frontend-next/`、平台资源脚本、MySQL 运维、DuckDB/Parquet 分析层、Worker 降载、部署资源门禁
默认结论：不加机器、不替换 MySQL、不自动 cutover；先用单机资源硬上限、前端轻量化、数据冷热分层和部署预构建解决增长失控问题。

## 1. 执行目标

本轮目标不是一次性清理磁盘，而是把持续增长源全部改成“有上限、可观测、可回滚、可阻断”的工程机制。

核心交付：

1. `frontend-next` 高 ROI 优化：`/next/strategy-tracking` 合包、`/next/paper` 虚拟化、CSS 无损瘦身、ECharts 懒加载复核、shared/ui 去重、功能级测试补齐。
2. 单机资源治理：binlog、slow log、Docker log、journal、BuildKit cache、部署归档全部有硬上限和巡检。
3. MySQL 在线事务瘦身：连接池、worker 并发、重任务优先级和内存预算可配置。
4. 数据冷热分层：`daily_bar_snapshots`、`strategy_tracking_snapshots` 等历史大表具备 Parquet 导出、manifest 校验、DuckDB 查询和热库保留窗口。
5. 部署资源门禁：部署前检查磁盘、swap、Docker cache、MySQL 日志；不达标停止，不自动切流。
6. 报告闭环：before/after 指标、命令、风险、回滚、未完成项全部写入 `docs/reports/`。

## 2. 硬边界

1. 不修改 `strategy_policy.py`。
2. 不改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。
3. 旧 `frontend/` 不作为本轮改造对象。
4. `frontend-next/` 不换栈，继续 SolidJS + TanStack + Lightweight Charts + ECharts 低频 adapter + Worker。
5. K 线必须继续使用 Lightweight Charts；不得改回 ECharts。
6. Worker/WASM 只做显示层 filter/sort/derive/downsample，不做生产策略判断。
7. DuckDB/Parquet 只作为分析层和报告层，不作为生产交易事实源。
8. Web 主进程不得新增 24 个月回测、数据补齐、Parquet 导出、DuckDB 报告等重任务。
9. 禁止直接删除 MySQL `.ibd`、binlog 文件、Docker volumes。
10. CSS 优化不得改变当前 `frontend-next` 视觉；禁止 PurgeCSS 批量删除后不截图验证。
11. 云服务器配置变更必须先备份当前配置，必须可回滚。
12. 不部署、不切流，除非用户单独授权。

## 3. 多 Agent 分工

| Agent | 责任 |
| --- | --- |
| A 前端性能 | strategy 合包、paper 虚拟化、ECharts 懒加载、首屏 chunk、请求治理 |
| B CSS/UI | CSS unused report、重复样式合并、`!important` 收敛、视觉一致性 |
| C 平台资源 | 资源巡检脚本、Docker/journal/build cache/deploy backup 上限、报告 |
| D MySQL 运维 | binlog 固化、slow log logrotate、备份/恢复 runbook、连接池预算 |
| E 数据分层 | Parquet 导出、manifest、DuckDB 查询、热库保留窗口、归档校验 |
| F Worker 降载 | worker 并发、低优先级任务窗口、资源预算、健康检查 |
| G QA/报告 | 单测/E2E/性能/资源验收、报告收敛、open-items 更新 |

并行规则：A/B/C 可并行启动；D/F 需要先做资源 baseline；E 必须先完成导出校验再允许任何热库清理；G 贯穿全程。

## 4. 基线采集

实施前必须生成 baseline，不接受“凭感觉优化”。

### 4.1 本地仓库

```bash
cd /Users/j/Documents/gupiao
git status --short
```

记录未跟踪和脏文件，禁止回退用户既有改动。

### 4.2 frontend-next

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run build
npm run perf:compare
npm run css:budget
npm run css:unused-report
npm run request:trace
npm run visual:consistency
```

产出：

1. `docs/reports/frontend-next-performance-optimization-2026-06-08.md`
2. `docs/reports/frontend-next-css-optimization-2026-06-08.md`
3. `docs/reports/frontend-next-visual-consistency-2026-06-08/`

### 4.3 云服务器资源

只读采集：

```bash
df -h /
free -h
sudo docker system df
sudo docker stats --no-stream
sudo journalctl --disk-usage
mysql -e "SHOW BINARY LOGS; SELECT @@binlog_expire_logs_seconds;"
du -sh /var/lib/docker/volumes/tquant-mysql_mysql_data/_data
```

产出：`docs/reports/platform-resource-baseline-2026-06-08.md`。

## 5. Phase A：资源硬上限和巡检

### A1 资源巡检脚本

新增：`scripts/collect_platform_resource_report.py`。

要求：

1. 支持本机运行和云服务器 SSH 运行两种模式。
2. 输出 JSON + Markdown。
3. 采集根分区、内存、swap、Docker images/cache/volumes、容器内存、journal、MySQL volume、binlog、slow log、部署备份。
4. 阈值判断：
   - 根分区 >70% warning，>80% blocking。
   - swap >50% warning。
   - slow log >512M warning。
   - Docker build cache >2G warning。
   - binlog 超过 3 天 warning。
5. 不做清理动作，只报告。

测试：

1. `backend/tests/test_platform_resource_report.py`
2. fixture 覆盖正常、warning、blocking、命令失败。

### A2 MySQL slow log 轮转

新增：

1. `docs/operations/mysql-maintenance-runbook.md`
2. `deploy/mysql/mysql-slow-logrotate.conf` 或同等 deploy 模板。

要求：

```text
size 256M
rotate 14
compress
missingok
copytruncate
```

执行前必须备份当前 slow log；执行后验证 `/readyz` 和 MySQL 查询正常。

### A3 binlog 持久配置

要求：

1. 将 `binlog_expire_logs_seconds=259200` 写入 MySQL 持久配置模板。
2. 增加配置检查脚本或 deploy guard。
3. 不用 `rm` 删除 binlog，只允许 MySQL `PURGE BINARY LOGS`。

### A4 Docker/journal/build cache 上限

要求：

1. Docker daemon log opts：`max-size=50m`、`max-file=3`。
2. journal：`SystemMaxUse=300M`、`MaxRetentionSec=7day`。
3. BuildKit cache：目标 <=2G；部署前超阈值自动提示或清理 build cache，不清 image/volume。
4. 保留最近 3 个 release/backup。

### A5 部署资源 gate

修改 `scripts/deploy_cloud_server.sh`、`scripts/quick_cloud_deploy.sh`：

1. 部署前运行资源检查。
2. blocking 时停止部署。
3. 输出资源 before/after。
4. 不自动 cutover。

验收：

```bash
backend/.venv/bin/pytest backend/tests/test_cloud_deploy_scripts.py backend/tests/test_platform_resource_report.py -q
```

## 6. Phase B：frontend-next 高 ROI 优化

### B1 strategy-tracking BFF 合包

涉及：

1. `frontend-next/src/features/strategy-tracking/StrategyTrackingPage.tsx`
2. `frontend-next/src/shared/api/operations.ts`
3. `frontend-next/src/shared/api/queryKeys.ts`
4. `frontend-next/tests/e2e/strategy-tracking.spec.ts`

要求：

1. 优先走 `/api/bff/v1/workspace/strategy`。
2. 请求数从约 9 降到 <=2。
3. 修复 `items` 422，不能用假数据掩盖。
4. 保留多请求 fallback，并记录 telemetry。
5. 字段 hash/order parity 一致。

### B2 paper 虚拟化

涉及：

1. `frontend-next/src/features/paper/PaperPage.tsx`
2. `frontend-next/src/features/paper/PaperPositionsTable.tsx`
3. `frontend-next/src/features/paper/PaperWorkflowTables.tsx`
4. `frontend-next/src/shared/ui/VirtualList.tsx`

要求：

1. 持仓、委托、成交、绩效长列表使用 shared `VirtualList`。
2. DOM 从约 403 降到 <150。
3. 机甲头像和特效保持现有组件和边界不变。
4. 键盘、滚动、空态、加载态和截图正常。

### B3 CSS 无损瘦身

涉及：

1. `frontend-next/src/shared/styles/legacy-workspace/*.css`
2. `frontend-next/src/features/*/*.css`
3. `frontend-next/scripts/css-unused-report.mjs`
4. `frontend-next/scripts/check-css-guard.mjs`

要求：

1. 先生成 unused report，再人工逐组删除或合并。
2. 合并 paper 三源、login 多源、primitives 重复规则。
3. `!important` 51 -> <=25。
4. CSS raw 目标 <=180KB，若不可达必须写明原因。
5. 每次 CSS 变更后跑截图/视觉一致性。

### B4 图表和首屏 chunk

要求：

1. K 线全部 Lightweight Charts。
2. ECharts 仅低频 chart island 懒加载，首屏 network 不出现 ECharts chunk。
3. `echarts/core` 按需注册。
4. 首屏 raw 412KB -> <=350KB。

### B5 shared/ui 去重

要求：

1. `DataGrid` 纯别名迁移到 `DataTable`。
2. `StatusBadge`、`StatusPill`、`Tag` tone API 收敛。
3. 不直接用第三方默认样式。

## 7. Phase C：MySQL 与 Worker 降载

### C1 连接池和 MySQL 配置

要求：

1. 评估 `max_connections=300` 降到 80-120。
2. Web、runtime worker、scheduler、analytics、backtest 分角色设置 pool size。
3. 不降低到影响 Web/API p95。
4. 每次调整后运行三轮 online performance gate。

### C2 worker 并发和优先级

要求：

1. backtest/analytics/data repair 默认低优先级。
2. 开盘高峰、部署、cutover 验证期间自动降并发或暂停新重任务。
3. runtime worker/scheduler 降低空转频率，但不丢任务、不重复执行。
4. Web 主进程不执行重任务。

测试：

```bash
backend/.venv/bin/pytest backend/tests/test_runtime_task_queue.py backend/tests/test_runtime_scheduler_worker.py backend/tests/test_analytics_worker.py -q
```

## 8. Phase D：DuckDB/Parquet 数据分层

### D1 第一批归档表

优先级：

1. `daily_bar_snapshots`
2. `strategy_tracking_snapshots`
3. `key_level_snapshots`
4. `low_buy_result_snapshots`
5. 回测明细、策略报告、分析报告明细

### D2 导出与 manifest

涉及：

1. `backend/scripts/export_analytics_parquet.py`
2. `backend/app/services/analytics/exporters.py`
3. `backend/app/services/analytics/manifest.py`
4. `backend/app/services/analytics/duckdb_repository.py`

要求：

1. 导出记录源表、日期范围、行数、hash、文件路径、生成时间、质量状态。
2. 数据不足必须显式 `blocked`。
3. 回测和历史分析优先读 Parquet。
4. 不清理 MySQL 源数据，直到 manifest 校验和恢复路径完成。

测试：

```bash
backend/.venv/bin/pytest backend/tests/test_analytics_manifest_lifecycle.py backend/tests/test_analytics_layer.py backend/tests/test_strategy_24m_duckdb_report.py -q
```

## 9. Phase E：预构建部署和门禁

要求：

1. 生产机优先 pull 预构建镜像，不默认重 build。
2. 若必须云端 build，先通过资源 gate，BuildKit cache 超阈值先处理。
3. 部署只保留最近 3 个可回滚版本。
4. 部署后跑：

```bash
python scripts/verify_go_rust_performance_acceptance.py
./scripts/quick_cloud_deploy.sh --verify-only --performance-verify --performance-rounds 3
```

结论写入 `docs/reports/platform-resource-optimization-2026-06-08.md`。

## 10. Phase F：测试和报告收敛

### F1 前端验收

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run request:trace
npm run screenshot:parity
npm run visual:consistency
npm run perf:compare
npm run css:budget
npm run css:unused-report
```

### F2 后端/平台验收

```bash
cd /Users/j/Documents/gupiao
backend/.venv/bin/pytest backend/tests/test_database_url_driver.py \
  backend/tests/test_market_provider_contract.py \
  backend/tests/test_market_quote_cache_coverage.py \
  backend/tests/test_cloud_performance_script.py \
  backend/tests/test_cloud_deploy_scripts.py -q
python scripts/verify_go_rust_performance_acceptance.py
git diff --check
git status --short
```

### F3 报告

必须新增或更新：

1. `docs/operations/mysql-maintenance-runbook.md`
2. `docs/reports/platform-resource-baseline-2026-06-08.md`
3. `docs/reports/platform-resource-optimization-2026-06-08.md`
4. `docs/reports/frontend-next-performance-optimization-2026-06-08.md`
5. `docs/reports/frontend-next-css-optimization-2026-06-08.md`
6. `docs/frontend-next-cutover-runbook-2026-06-05.md`
7. `PRODUCTION_RUNBOOK.md`

## 11. 验收指标

| 领域 | 指标 | 目标 |
| --- | --- | ---: |
| 前端 | strategy-tracking 请求 | <=2 |
| 前端 | strategy items 422 | 0 |
| 前端 | paper DOM | <150 |
| 前端 | CSS raw | <=180KB，或说明不可达原因 |
| 前端 | `!important` | <=25 |
| 前端 | 首屏 raw | <=350KB |
| 前端 | ECharts 首屏 | 0 |
| 资源 | 根分区 | 长期 <60%，部署期间 <75%，>80% blocking |
| 资源 | Swap | 长期 <20%，短期 <500MiB |
| 资源 | Available memory | >800MiB，或说明单机不可达原因 |
| MySQL | binlog | 3 天，重启不丢 |
| MySQL | slow log | 单文件 <=256M，压缩保留 14 天 |
| Docker | build cache | <=2G 或部署前处理 |
| 数据 | Parquet manifest | 可重复、可校验、可恢复 |
| 性能 | Web/API p95 | 不回退 |
| 策略 | production_score / priority_board | 口径不变 |

## 12. 回滚方案

1. 前端合包：关闭合包 flag，回旧多请求 fallback。
2. 虚拟化：回非虚拟列表渲染。
3. CSS：逐 commit 回退，不批量回退业务代码。
4. MySQL 配置：恢复备份配置，重启前确认当前连接和 `/readyz`。
5. slow log：只截断日志，不影响数据；如 logrotate 异常，禁用新增配置。
6. worker 降载：恢复原并发和常驻策略。
7. Parquet 分层：不清 MySQL 源数据前，直接关闭冷数据读取。
8. 预构建部署：回旧部署脚本，但必须通过资源 gate。

## 13. 不完成不得进入 cutover

以下任一项失败，都不能进入正式 cutover：

1. frontend-next 验收命令未全绿。
2. 资源 gate 有 blocking。
3. Web/API p95 回退。
4. binlog/slow log 没有持久策略。
5. Parquet 归档缺 manifest 或校验失败。
6. 旧前端、生产策略口径、`strategy_policy.py` 被误改。
7. 报告中仍有“已完成/未完成”互相矛盾。

## 14. 最终交付说明模板

最终汇报必须包含：

1. 新增/修改文件。
2. 完成的 Phase 和 Agent 分工。
3. frontend-next 指标 before/after。
4. 云服务器资源 before/after。
5. MySQL binlog/slow log/备份状态。
6. Worker 降载和 Web/API 性能结果。
7. Parquet manifest 和数据归档状态。
8. 测试命令和结果。
9. 旧 `frontend/` 是否未改。
10. 后端是否改动及原因。
11. 是否影响平台功能：必须明确回答“不影响”或说明风险。
12. 回滚方式。
13. 未完成项。
14. cutover 是否仍需用户单独授权。
