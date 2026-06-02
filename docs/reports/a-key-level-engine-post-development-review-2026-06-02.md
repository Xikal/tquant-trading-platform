# AKeyLevel Engine 开发后复审报告

日期：2026-06-02  
仓库：`/Users/j/Documents/gupiao`  
复审对象：A 股关键位引擎 `AKeyLevel Engine` 本次开发变更  
权威计划：`docs/a-share-key-level-engine-execution-plan-2026-06-02.md`

## 1. 复审目的

请 Claude 对本次开发做独立复审，重点判断：

1. 是否真正落实权威计划中的 AKeyLevel Engine。
2. 是否仍存在未来函数、同步重算、缓存覆盖不足、交易建议文案越界、三层联动失真等问题。
3. 是否影响现有策略逻辑、回测口径、生产排序。
4. 测试是否覆盖了关键风险，是否存在假绿。

## 2. 本次开发目标

落地统一 A 股关键位引擎，覆盖：

1. 个股关键位：支撑、压力、MA5/10/20/30/60、成交密集区、结构关键位、Anchored VWAP、盘中关键位。
2. 板块关键位：基于成分股代理序列输出统一 schema，并标记研究观察口径。
3. 大盘关键位：优先指数数据，缺指数时使用等权代理序列并降级。
4. 三层联动：大盘/板块不可用或跌破关键支撑时，个股支撑可信度降级。
5. 前端展示：监控页、策略跟踪详情、模拟盘持仓详情、分析页展示只读关键位观察。

硬边界：

1. 不输出买入/卖出建议。
2. 不改生产排序。
3. 不改策略打分边界。
4. 不使用信号日之后数据。
5. 数据不足必须 `insufficient` / `research_only` / `blocked` / `stale`。

## 3. 主要新增文件

后端：

1. `backend/app/api/routes/key_levels.py`
2. `backend/app/models/schema_defs/key_levels.py`
3. `backend/app/services/key_levels/engine.py`
4. `backend/app/services/key_levels/ma_levels.py`
5. `backend/app/services/key_levels/swing_levels.py`
6. `backend/app/services/key_levels/volume_profile.py`
7. `backend/app/services/key_levels/anchored_vwap.py`
8. `backend/app/services/key_levels/score.py`
9. `backend/app/services/key_levels/linkage.py`
10. `backend/app/services/key_levels/materialization.py`
11. `backend/app/services/key_levels/validation.py`
12. `backend/tests/test_key_levels_engine.py`

前端：

1. `frontend/src/features/key-levels/KeyLevelPanel.tsx`
2. `frontend/src/features/key-levels/queries.ts`
3. `frontend/src/features/key-levels/KeyLevelPanel.test.tsx`
4. `frontend/src/styles/workspace/workspace-key-levels.css`

## 4. 主要修改文件

1. `backend/app/api/router.py`
2. `backend/app/models/schema_defs/market.py`
3. `backend/app/services/shared/feature_flags.py`
4. `backend/app/workers/runtime_worker.py`
5. `docs/contracts/openapi.json`
6. `docs/contracts/openapi.hash`
7. `frontend/src/generated/api-types.ts`
8. `frontend/src/api/client.ts`
9. `frontend/src/types/market.ts`
10. `frontend/src/features/monitor/MonitorPage.tsx`
11. `frontend/src/features/strategy-tracking/StrategyTrackingDetailDrawer.tsx`
12. `frontend/src/features/paper/PaperPositionDetailsPanel.tsx`
13. `frontend/src/features/analysis/AnalysisPage.tsx`
14. `frontend/src/features/trading-workspace/MonitorPage.test.tsx`
15. `frontend/src/features/trading-workspace/AnalysisPage.test.tsx`
16. `frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx`
17. `frontend/src/styles/workspace/workspace.css`

## 5. API 与 Schema

新增接口：

1. `GET /api/key-levels/stock/{symbol}`
2. `GET /api/key-levels/sector/{sector_key}`
3. `GET /api/key-levels/market`
4. `GET /api/key-levels/intraday/{symbol}`

关键 schema：

1. `KeyLevelCandidate`
2. `KeyLevelResult`
3. `KeyLevelDataQuality`
4. `KeyLevelDirection`
5. `KeyLevelScope`
6. `KeyLevelType`

新增关键字段：

1. `engine_version`
2. `as_of`
3. `adjust_mode`
4. `intraday_included`
5. `invalidate_below`
6. `invalidate_volume_x`
7. `support_zone_low/high`
8. `resistance_zone_low/high`
9. `support_distance_pct`
10. `resistance_distance_pct`
11. `key_level_candidates`
12. `warnings`

## 6. Feature Flag 与缓存

新增 feature flag：

`a_key_level_engine_enabled`

行为：

1. 默认 `off`。
2. 关闭时前端不展示关键位空块。
3. 关闭时 API 返回 `blocked`。
4. 开启后 API 优先读物化缓存。
5. 日线关键位重算必须走 runtime worker，不允许普通 API 请求同步刷新。

新增 runtime task：

`a_key_level_materialization_refresh`

设计意图：

1. 默认覆盖全部 active 股票和全部板块。
2. 只有 payload 显式传 `stock_limit` / `sector_limit` 时才限制范围。
3. 写入 `SystemSetting` 缓存。

## 7. 已修复的复审问题

此前内部复审发现 4 个问题，已按 TDD 修复：

1. 默认物化只覆盖 80 只股票 / 20 个板块。
   - 已改为默认全量覆盖。
   - 测试：`test_key_level_materialization_default_covers_all_active_stocks_and_sectors`

2. API 暴露 `refresh=true` 导致请求时同步重算。
   - 已移除公开 refresh 参数。
   - 显式拒绝 `?refresh=true`，返回 422。
   - 测试：`test_key_level_api_does_not_allow_request_time_refresh`

3. 验证服务 `touch_pct` 未使用，深破位也算触达。
   - 已按支撑区和 touch_pct 判断触达。
   - 测试：`test_key_level_validation_uses_touch_pct_without_counting_deep_break_as_touch`

4. 验证服务每个样本日重复查 DB。
   - 已改为一次预取历史 rows 后内存滑窗计算。
   - 测试：`test_key_level_validation_prefetches_history_instead_of_querying_per_sample`

## 8. 已运行验收

后端：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_key_levels_engine.py backend/tests/test_runtime_task_queue.py -q
```

结果：`23 passed, 1 warning`

OpenAPI / 前端类型：

```bash
cd frontend && npm run api:check
```

结果：通过。

前端：

```bash
cd frontend && npm run lint
cd frontend && npm test -- --run src/features/key-levels/KeyLevelPanel.test.tsx src/features/trading-workspace/MonitorPage.test.tsx src/features/strategy-tracking/StrategyTrackingPage.test.tsx src/features/trading-workspace/AnalysisPage.test.tsx
cd frontend && npm run build
```

结果：均通过。

响应式 smoke：

此前已运行：

```bash
cd frontend && SMOKE_MOCK_AUTH=1 npm run smoke:responsive
```

结果：30 个页面/视口组合通过，375/768/1440 最大横向溢出 `0`。

## 9. 请 Claude 重点复审的问题

### 9.1 正确性

1. `backend/app/services/key_levels/engine.py`
   - 是否仍可能使用信号日之后的数据。
   - `_load_rows()` 的日期范围是否合理。
   - `_merge_candidates()` 合并后主 `level_type` 是否会造成来源误读。
   - `with_intraday()` 是否只轻量合并盘中数据。

2. `backend/app/services/key_levels/swing_levels.py`
   - gap 和 limit-up anchor 的判定是否符合 A 股常见口径。
   - 一字板、停牌、新股是否应进一步降级。

3. `backend/app/services/key_levels/materialization.py`
   - 使用 `SystemSetting` 存缓存是否存在容量、并发、覆盖或 key 冲突问题。
   - 全量 active 股票物化时是否需要分批 commit / checkpoint。
   - 缓存 key 哈希是否足够稳定可追溯。

4. `backend/app/services/key_levels/validation.py`
   - 内存滑窗是否仍保持无未来函数。
   - 触达/反弹/失效定义是否足够严谨。
   - 是否需要输出 Markdown 摘要或 JSON 报告路径。

### 9.2 架构

1. key-levels 模块是否边界清晰。
2. API 是否真正只读缓存。
3. worker 物化是否应该接入已有调度器，而不只是 runtime task 可执行。
4. feature flag 默认 off 的前后端行为是否一致。

### 9.3 性能

1. 全量物化所有 active 股票时，`build_sector()` 是否会重复读取股票历史，造成过高成本。
2. 板块代理序列是否需要共享股票级缓存或批量数据加载。
3. `SystemSetting` 缓存大 JSON 是否适合全量规模。
4. 前端每个页面都查 `settings/feature-flags` 是否可以复用已有全局查询。

### 9.4 安全与权限

1. `/api/key-levels/*` 是否有足够鉴权。
2. `?refresh=true` 已拒绝，但是否还存在其他方式触发同步重算。
3. feature flag 更新是否仍只允许合规权限路径。

### 9.5 文案边界

重点 grep：

```bash
rg -n "建议买入|建议卖出|强烈推荐|直接低吸|必涨|压力突破即可买入" \
  backend/app/services/key_levels backend/app/api/routes/key_levels.py frontend/src/features/key-levels
```

预期：不应出现交易建议越界文案。

## 10. 建议 Claude 使用的复审命令

```bash
cd /Users/j/Documents/gupiao

git status --short --branch

PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_key_levels_engine.py \
  backend/tests/test_runtime_task_queue.py \
  -q

cd frontend
npm run api:check
npm run lint
npm test -- --run src/features/key-levels/KeyLevelPanel.test.tsx \
  src/features/trading-workspace/MonitorPage.test.tsx \
  src/features/strategy-tracking/StrategyTrackingPage.test.tsx \
  src/features/trading-workspace/AnalysisPage.test.tsx
npm run build
```

可选响应式：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run preview -- --host 127.0.0.1
SMOKE_MOCK_AUTH=1 npm run smoke:responsive
```

## 11. 已知工作区状态

当前 worktree 本来就包含多项其他脏文件。本报告只覆盖 AKeyLevel 相关变更。复审时请不要把无关改动混入结论。

AKeyLevel 相关路径可用以下命令聚焦：

```bash
git status --short -- \
  backend/app/api/routes/key_levels.py \
  backend/app/api/router.py \
  backend/app/models/schema_defs/key_levels.py \
  backend/app/models/schema_defs/market.py \
  backend/app/services/key_levels \
  backend/app/services/shared/feature_flags.py \
  backend/app/workers/runtime_worker.py \
  backend/tests/test_key_levels_engine.py \
  docs/contracts/openapi.json \
  docs/contracts/openapi.hash \
  frontend/src/api/client.ts \
  frontend/src/features/key-levels \
  frontend/src/features/monitor/MonitorPage.tsx \
  frontend/src/features/strategy-tracking/StrategyTrackingDetailDrawer.tsx \
  frontend/src/features/paper/PaperPositionDetailsPanel.tsx \
  frontend/src/features/analysis/AnalysisPage.tsx \
  frontend/src/features/trading-workspace/AnalysisPage.test.tsx \
  frontend/src/features/trading-workspace/MonitorPage.test.tsx \
  frontend/src/features/strategy-tracking/StrategyTrackingPage.test.tsx \
  frontend/src/generated/api-types.ts \
  frontend/src/styles/workspace/workspace.css \
  frontend/src/styles/workspace/workspace-key-levels.css \
  frontend/src/types/market.ts
```

## 12. 复审结论模板

请 Claude 输出：

1. 是否通过复审：`Approve` / `Request changes`
2. 最高优先级 findings，按严重程度排序。
3. 是否存在未来函数风险。
4. 是否存在交易建议文案越界。
5. 是否存在同步重算或性能风险。
6. 是否影响策略逻辑、回测口径、生产排序。
7. 建议补充的测试。

