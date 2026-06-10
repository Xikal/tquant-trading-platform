# 平台系统性体检报告（2026-06-10）

> 范围：**后端 + 数据库 + 新前端 frontend-next**（旧前端按要求不在审查范围；其上仅保留此前已授权的白屏自愈修复）。
> 重点：策略正确性、性能、稳定性。
> 方式：全量测试实跑 + 失败根因逐个定位 + 最小修复 + 复验。
> 并行保护：工作树存在在途的"旧前端退役"工程（`legacy-frontend-retirement-execution-2026-06-10.md`、CI/Dockerfile/部署脚本、frontend-next chunkReload 移植等），本轮未触碰、未回滚。

---

## 一、总体结论

| 层 | 体检结果 | 状态 |
|---|---|---|
| 策略正确性守卫 | 67/67 passed（production_scoring / priority board variants / lanes / replacement / trade-date / strategy_engine boundary+gate / execution model boundary） | ✅ |
| 后端全量 pytest | 修复前 **1470 passed / 7 failed** → 修复后 **1477 passed / 0 failed** | ✅（本轮修复 7 个） |
| 数据库迁移 | 42 个迁移，全新库 `alembic upgrade head` 冒烟通过 | ✅ |
| 新前端工程门禁 | typecheck / lint（含 boundary+bundle guard）/ api:check / build 全绿 | ✅ |
| 新前端单测 | **124/124 passed**（此前偶发 2 失败=与 api:check 并发重写 generated 类型的竞态，隔离复跑两次均全绿） | ✅ |
| 新前端 e2e | 修复前 40 passed / 7 failed → **42 passed / 5 failed**；剩余 5 个全部定性为 data/settings 令牌门控文案重写后的过期断言（测试债务，非产品缺陷） | ⚠️ 见 P0-1 |
| Bundle 体积 | **1.22MB → 650KB JS / 22 chunks**（echarts 依赖与 chunk 完全移除，dist 总 844K） | ✅ 重大改善 |

**最重要的发现：瘦身提交 `94fc9d2c` 造成 2 处真实回归（已修复）**——这证明守卫测试体系有效，但也暴露"瘦身类提交未跑全量回归"的流程缺口。

---

## 二、策略正确性（重点项逐条）

### 2.1 守卫测试全绿（67 项）
- 生产门唯一性：`production_score` 仅 buy_now/soft_buy_now；非生产策略分=null。
- priority board 排序语义、strategy variants、lanes 行为不变。
- `strategy_engine` shadow-only 边界、execution model preview 不替代事实源——守卫均通过。
- 交易日读路径（published/expected trade date）测试通过，周末/节假日口径正确。

### 2.2 发现并修复：quote cache 预热丢失 paper 持仓（真实生产回归）
- **根因**：瘦身提交 `94fc9d2c` 把 `paper_position_symbols` 从 `market_quote_cache_refresh.py` 整体删除（模块内 "paper" 零引用），导致 `build_quote_cache_demand_symbols` 的热读需求集不再包含模拟盘持仓 → **paper 页持仓实时报价不再预热**，回落 MySQL fallback / stale。
- **影响**：模拟盘持仓价格新鲜度与读性能劣化；违背 G1 缓存覆盖设计（持仓属于热读需求集）与测试契约。
- **修复**：恢复 `PaperPosition` import、`HOLDING_CORE_LIMIT=300` 常量、`paper_position_symbols()` 函数（按 git 历史原实现），并入需求集合 union。
- **复验**：`test_quote_cache_warmup_includes_all_hot_demand_sets`、`test_target_symbols_keeps_core_hot_read_demand_before_liquidity_tail` 转绿。

### 2.3 发现并修复：核心闭环 smoke 路径被误删
- **根因**：同一瘦身提交把 `/backtest`、`/paper` 从 `smoke-responsive.mjs` 路径表删除——但这两个是**核心交易闭环路由**（瘦身硬边界明确不可动）。后端守卫 `test_responsive_smoke_covers_all_workspace_routes` 正确报红。
- **修复**：恢复两条路径（1 行）。守卫转绿。

### 2.4 展示层正确性（沿用 06-08 审计 + 本轮 e2e 复验）
- 新前端不重排生产榜（仅 lane 过滤）、不重算分数、发布交易日口径、缺数据不伪造——监控页 e2e「preserves priority order + no-write」修复 lane 标签后**转绿**，核心断言（顺序保持、零写请求）保留。

---

## 三、后端 7 个失败的完整处置

| # | 失败 | 根因 | 处置 |
|---|---|---|---|
| 1-2 | `test_market_quote_cache_refresh` ×2 | **真实回归**（见 2.2） | 修生产代码，恢复 paper 预热 |
| 3-5 | `test_analytics_layer` ×3（manifest row_count 0≠1） | 测试日期漂移：fixture 未设时间戳，DB 默认 `created_at/generated_at`=今天(6/10)，落在导出窗口(≤6/8)外 | fixture 加显式 `datetime(2026,6,8,…)`（StrategyTrackingSnapshot.generated_at / BacktestRun.created_at / AnalysisLog.created_at） |
| 6 | `test_key_levels_materialization_readiness` | 测试 seam 过期：close_refresh 重构后 `DailyHistoryRepository` 不在模块级；followups 新增直接 `db.execute` 的存在性检查 | 删过期 patch；stub `enqueue_after_close_followups`（key-level 入队在其之前、独立，断言不变） |
| 7 | `test_responsive_smoke_covers_all_workspace_routes` | **守卫正确报红**（见 2.3） | 恢复 smoke 路径 |

复验：**后端全量 1477 passed / 0 failed**。

---

## 四、数据库

- **迁移**：42 个版本；全新 sqlite `alembic upgrade head` 一次通过（最新：market_calendar_dates / key_level_snapshots / trading_experience_suite / minute_bar_metadata / track_record_drift）。
- **索引**：热表模型索引齐备（paper_entities 34 处、low_buy_entities 39 处、market_entities 133 处 `Index/index=True` 命中）。
- **数据保真门控**（前轮已确认、本轮守卫复验）：收盘 15:01 后刷新、publish-if-ready（不完整不发布当日、显示上一交易日）、`invalid_ohlc/duplicate/missing` → blocker 不静默续跑。
- **建议**：MySQL 生产侧 `innodb_buffer_pool_size` 右调与备份保留期优化见已有《cloud-server-optimization-plan-2026-06-09.md》，未重复展开。

---

## 五、新前端（frontend-next）

### 5.1 性能（显著改善，来自在途退役工程，本轮实测确认）
- **JS 650,464 bytes / 22 chunks**（bundle budget 通过），对比上轮 1.22MB/29 chunks **降 47%**。
- **echarts 完全移除**（package.json 0 依赖、dist 0 chunk），图表全量 lightweight-charts；dist 总 844K。
- 最大块：vendor 160.6KB、tanstack-misc 139KB、index 66.9KB、StrategyTracking 48.2KB——均健康。

### 5.2 稳定性
- chunkReload 白屏自愈已由在途工程**移植进 frontend-next**（`src/app/chunkReload.ts` + `RouteLoading.tsx`），与旧前端修复同模式。
- 单测偶发失败定性：与 `api:check` 并发重写 `generated/api-types.ts` 的竞态，**非真实失败**（隔离复跑 2 次全绿）。

### 5.3 e2e：42 passed / 5 failed（全部测试债务，非产品缺陷）
- **已修 2 个**：monitor-workflows / monitor-live-readiness 引用已被重设计的策略变体 tabs（前排加权/前排极精选）→ 对齐新行动 lane tabs（全部候选/观察池/可买入），**保留顺序保持 + no-write 核心断言**。
- **剩余 5 个**（backtest-data-settings ×2、data-settings-error-states ×1、interaction-parity ×2）：data/settings 页管理令牌门控 UX 在 `94fc9d2c` 重写，旧断言文案已不存在。文案映射：
  - `令牌验证未通过` → `管理授权缺失`
  - `[全局配置] 需要先校验管理令牌。` → `请先在顶部校验管理令牌。` / `[X] 当前只读，请先解锁管理操作`
  - `管理员权限校验通过，本页本地编辑已解锁。` → `已使用当前管理员账号解锁本地编辑。`
  - 未补 mock 的新端点：`/api/data-quality/{coverage,sla}`、`/api/runtime-tasks*`、`/api/admin/{metrics,tasks}`、`/api/bff/v1/workspace/settings`
- 未在本轮重写这 5 个 spec：data/settings 门控流程属在途工程的活跃工作面，由其作者按上述映射收尾最稳妥（避免对半成品 UX 写错断言）。

---

## 六、优化建议（按优先级）

### P0（立即）
1. **对齐 5 个 data/settings e2e**：按 §5.3 文案映射更新断言 + fixture 补 6 个新端点 mock。预计 <1 人日。
2. **瘦身/重构类提交强制全量回归**：`94fc9d2c` 一个提交造成 2 处真实回归 + 7 个红测——建议此类提交合入前必跑 `pytest backend/tests` 全量 + frontend-next e2e（守卫体系已证明有效，缺的是执行纪律）。

### P1（短期）
3. **CI 串行化 api:check 与 vitest**：避免 generated 类型重写竞态造成假红。
4. **服务器内存优化执行**：按既有《cloud-server-optimization-plan-2026-06-09.md》落地（停分离栈、APP_WORKERS=1、scheduler 合并、swappiness），脱离 Swap——这是当前线上稳定性最大杠杆。
5. **退役工程收尾联动**：旧前端退役完成后，删除双栈维护成本（smoke-responsive 等旧前端守卫届时同步退役，而非再次误删）。

### P2（跟进）
6. tanstack-misc 139KB 可评估按页 lazy 再拆（非紧迫，budget 内）。
7. analytics 导出测试建议统一改用相对"窗口内"时间工具函数，杜绝同类日期漂移再发。

---

## 七、本轮改动清单（最小修复，均已复验）

| 文件 | 性质 |
|---|---|
| `backend/app/services/market_quote_cache_refresh.py` | **生产修复**：恢复 paper 持仓预热（import + 常量 + 函数 + 需求集合并入） |
| `backend/tests/test_analytics_layer.py` | 测试修复：3 个 fixture 显式时间戳 |
| `backend/tests/test_key_levels_materialization_readiness.py` | 测试修复：seam 对齐 + followups stub |
| `frontend/scripts/smoke-responsive.mjs` | 守卫修复：恢复核心闭环 `/backtest` `/paper` 路径 |
| `frontend-next/tests/e2e/monitor-workflows.spec.ts` | e2e 对齐新 lane tabs（保留顺序/no-write 断言） |
| `frontend-next/tests/e2e/monitor-live-readiness.spec.ts` | 同上 |

未改：`strategy_policy.py`、生产排序、`production_score`、风控阈值、shadow-only 边界。未部署、未切流。
