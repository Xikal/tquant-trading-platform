# AKeyLevel Engine 独立代码复审报告

状态：已完成（独立复审）
适用范围：本次 AKeyLevel Engine 相关变更（不含工作区其他无关脏文件）
最后核验日期：2026-06-02
仓库：`/Users/j/Documents/gupiao`
权威计划：`docs/a-share-key-level-engine-execution-plan-2026-06-02.md`
开发方自评：`docs/reports/a-key-level-engine-post-development-review-2026-06-02.md`
复审范围依据：所有 AKeyLevel 文件均为新增/未跟踪（`git status` 确认），与其他脏文件隔离。

## 复审已运行的验收（真实结果）

| 命令 | 结果 |
|---|---|
| `pytest backend/tests/test_key_levels_engine.py test_runtime_task_queue.py -q` | **23 passed**, 1 warning |
| `npm run api:check` | 通过（openapi 导出 + 类型生成 + `tsc -b` 无错） |
| `npm run lint`（含 state-separation / css / refactor guard） | 通过 |
| `npm test -- --run`（KeyLevelPanel / MonitorPage / StrategyTrackingPage / AnalysisPage） | **4 files, 31 passed** |
| 文案越界 grep | 源码无越界文案；仅测试中存在“断言不出现越界文案” |
| 生产逻辑引用 grep | key_levels 模块/路由**零引用** production_scoring / priority_board / strategy_policy |

未独立重跑（开发方自评称通过）：`npm run build`、`SMOKE_MOCK_AUTH=1 npm run smoke:responsive`（375/768/1440 溢出=0）。如需独立背书，建议补跑。

---

## 1. 复审结论（Approve / Request changes）

**Approve 合入（feature flag 保持默认 OFF）；在生产环境开启 `a_key_level_engine_enabled` 之前 Request changes。**

引擎真实落地了大盘/板块/个股三层支撑、压力、MA5/10/20/30/60、成交密集区、结构位、Anchored VWAP、盘中关键位；**与策略/生产排序完全隔离**、**无交易建议文案**、**无未来函数**、数据质量状态正确、全端点鉴权且拒绝请求时刷新、测试全绿。**无阻断合入的问题。** 但有 4 项运营/性能项（尤其 **物化任务未接调度器 → 线上缓存恒 `stale`**、**用 `SystemSetting` 存上千条大 JSON**）必须在开启 flag 前修复。

---

## 2. 严重问题清单（按严重程度排序，含文件:行号）

### 中（开启 flag 前必须处理）

**M1 物化任务从未自动调度，功能在生产环境形同空转。**
- 证据：`a_key_level_materialization_refresh` 已注册可执行（`backend/app/workers/runtime_worker.py:36,176-177`），但**无任何调度器 enqueue 它**——`backend/app/runtime/background_jobs.py`、`backend/app/workers/latest_data_close_scheduler.py` 均无引用。
- 影响：缓存永不填充 → 所有 `/key-levels/*` 读取返回 `stale_key_level_result`（`backend/app/api/routes/key_levels.py:45,63,80`）。与 analytics-worker “写完未接线” 同类。
- 建议：收盘后每日 enqueue（或在 Runbook 写明手动运维步骤），并补调度测试，再开启 flag。

**M2 `/intraday/{symbol}` 在请求线程做全量日线重算。**
- 证据：`backend/app/api/routes/key_levels.py:83-88` → `AKeyLevelEngine.build_intraday`（`backend/app/services/key_levels/engine.py:113-119`）→ `build_stock`（`:31-50`）`_load_rows`（DB）+ 重算 MA/swing/volume/VWAP，每次请求同步执行。
- 影响：违反“日线重算必须走 worker、API 只读缓存”边界，且与 stock 端点正确的“读缓存 + `with_intraday` 叠加”模式（`key_levels.py:36-44`）不一致。已被 flag/鉴权/单标的限制，非滥用入口，但仍是请求时计算路径。
- 建议：改为读缓存日线 + `with_intraday` 叠加盘中。

**M3 全量物化：单次提交 + 重复读取历史。**
- 证据：`backend/app/services/key_levels/materialization.py:37-47` 遍历全部 active 股票 + 全部板块后**仅 commit 一次**（无分批/checkpoint → 巨型事务、中途失败无法续跑）；`build_sector` 对最多 30 只成分股**再次** `_load_rows`（`engine.py:62-65`），与各股自身 `build_stock` 重复读历史，**无股票级共享缓存**。
- 影响：全量（约 5k 股 + ~100 板块）下重复 DB 读 + 长事务成本高。
- 建议：分批 commit + checkpoint；板块构建复用股票级历史缓存。

**M4 用 `SystemSetting` 做大规模缓存不合适。**
- 证据：每个结果一行 `system_settings`，存完整 `KeyLevelResult` JSON（`materialization.py:113-127`）；无 `trade_date` 读路径执行 `LIKE 'prefix:%' ORDER BY key DESC LIMIT 1`（`materialization.py:98-103`）——每次读扫描+排序；旧日期条目无清理 → 跨交易日无限增长。
- 影响：配置表被塞入上千条大 JSON，热读路径 LIKE 扫描，表膨胀。
- 建议：用专用表或 analytics/parquet 存储；读路径加索引/精确键；旧日期条目设清理。

### 低 / Nit

**L5** `KeyLevelValidationService` 为生产路径 dead code：仅 `backend/tests/test_key_levels_engine.py` 引用，无任何 route/worker/script/报告消费（`backend/app/services/key_levels/validation.py`）。按规范 §6.10 **列出不删**，建议接线到 worker/报告或标记 `research_only`。
**L6** 路由无效/误导参数：`stock/sector/market` 端点接收 `lookback_days` 但读预算缓存（引擎默认 120）→ 校验后被忽略（`key_levels.py:28,53,70`）；`include_intraday=true` 在 sector/market 端点会强制返回 `stale`（`:61,78`）；`threshold_pct` 仅在 `include_intraday` 时生效。
**L7** `backend/app/services/key_levels/engine.py` 463 行 > 评审阈值 400（规范 §4.1）——允许合入，后续扩展前建议拆分（reader/scorer/merger）。
**N8** `_merge_candidates` 合并后主 `level_type` 取较强候选（`engine.py:350`），evidence 做并集——主类型可能与并集来源略不一致，evidence 数组已缓解（`:349`）。
**N9** 一字板（不可买入的一字涨停）在 `_limit_up_anchor_candidates`（`swing_levels.py:84-103`）未进一步降级；属观察位，影响小。
**N10** `validation.py:113,131` 用 `distance_pct(...)` 作真值判断，可用但写法别扭（nit）。

---

## 3. 正确性：未来函数 / 数据口径

**未发现未来函数。**
- 引擎按 `trade_date or latest_trade_date_for_symbol` 限定数据范围，`as_of = rows[-1].trade_date`（`engine.py:230-235,197`）。
- 验证服务每个样本仅用 `all_rows[:index+1]` 计算关键位，前向 `index+1:` 仅用于**测量**触达后是否反弹/失效（这是前向验证的定义，不是泄漏）（`validation.py:90-97,105`）；`touch_pct` 正确排除深破位（`:138-142`）。
- 代理/大盘序列强制 `research_only`（`engine.py:74-77,108-110`）。
- 数据质量状态正确：样本不足 `insufficient`、停牌/退市 `blocked`、无清晰支撑压力 `research_only`、缓存缺失 `stale`（`engine.py:160-178,225`、`materialization.py:130-161`）。口径为观察用途，非收益/PF，无误读。

---

## 4. 架构

符合工程规范：新增资源路由 + service 模块 + schema + feature flag + worker task；前端落 `features/key-levels/` 复用 `DataTable`/`Collapse`/`MetricGrid`；market schema 复用 key-level schema（`market.py:8-14,176-195`）；state-separation/refactor guard 通过。**架构缺口**：M1（worker 未接调度器）、M4（`SystemSetting` 是配置存储，不适合大规模 JSON 缓存）。模块边界清晰，key_levels 与生产逻辑零耦合。

---

## 5. 安全与权限

- 全端点鉴权：`router = APIRouter(prefix="/key-levels", dependencies=[Depends(get_current_user)])`（`key_levels.py:20`）。
- `?refresh=` 显式 422 拒绝（`key_levels.py:95-97`）。
- feature flag 默认关、更新走既有合规路径（`feature_flags.py`，flag 读有缓存）。
- **唯一残留同步计算入口：`/intraday/{symbol}`（见 M2）**——已鉴权+flag 限制+单标的，非滥用向量，但应改为缓存支撑。无注入面（路径/查询均强类型校验）。

---

## 6. 性能

读端点（stock/sector/market）正确只读缓存。风险集中在**全量物化**：M3（单提交 + 重复读历史）、M4（上千 `SystemSetting` 大 JSON + LIKE 扫描读 + 无清理）。flag-off/小规模下不发作，**全量生产开启前必须处理**。`build_market` 无指数时取 80 股、`build_sector` 取 30 成分——有界，合理。前端每面板用 `["feature-flags", flag]` query key（`queries.ts:9`）——同页多面板按该 key 去重，未造成 N 次调用；可进一步复用全局 feature-flags 查询（低优化项）。

---

## 7. 前端（375px / 折叠详情 / flag 关闭隐藏）

- **flag 关闭即隐藏**：`queries.ts` 用 `enabled: feature.data === true`（:25,35,46）门控 → **关闭时不发 API**；`KeyLevelPanel.tsx:98` 识别 `blocked + 功能开关关闭` → 面板隐藏，无空块。✓
- **折叠详情**：AntD `Collapse`（`KeyLevelPanel.tsx:1,65`）+ `MetricGrid`。✓
- **375px**：复用响应式 `MetricGrid`/`Collapse`；开发方自评 `smoke:responsive` 报 375/768/1440 溢出=0。**本次未独立重跑 smoke**（lint/vitest 已过）；如需独立背书建议补跑。

---

## 8. 测试：有效 vs 仍缺

**有效**：后端 `test_key_levels_engine.py`（23 passed）覆盖此前 4 项修复（全量覆盖、refresh-422、touch_pct 不计深破、预取不逐样本查库）、insufficient/blocked、验证；前端 `KeyLevelPanel.test.tsx` 含**交易建议文案缺席守卫** + 3 个页面套件（31 passed）。

**建议补充**：
1. **调度测试**：断言每日调度器 enqueue `a_key_level_materialization_refresh`（覆盖 M1）。
2. **三层联动单测**：`apply_three_layer_linkage` 在大盘/板块 `insufficient`/`blocked`/支撑跌破时降级（`linkage.py`，当前无专门单测）。
3. **`/intraday` 数据源测试**：（M2 修复后）断言其不做请求时日线重算、走缓存。
4. **物化分批/幂等测试**：重跑不产生重复行、部分失败可续跑（覆盖 M3）。
5. **缓存增长/清理测试**：旧日期条目有界（覆盖 M4）。

---

## 9. 是否影响策略逻辑 / 回测口径 / 生产排序（明确回答）

**不影响。** `backend/app/services/key_levels/*` 与 `routes/key_levels.py` **零引用** `production_scoring`/`priority_board`/`priority_items`/`strategy_policy`/`production_score`（grep 确认）。它不写优先榜、不写生产分、不进回测路径，只读日线、只写自己的 `akey_level_cache:*` SystemSetting 键。策略逻辑、24M 回测口径、生产排序均未触碰。

---

## 10. dead code / 未使用参数（列出，不自行删除）

- `validation.py`：`KeyLevelValidationService` 生产未接线（仅测试引用）→ 接线到报告/worker 或标记 `research_only`。
- `key_levels.py`：`lookback_days` 在缓存读端点被忽略（:28,53,70）；`include_intraday` 在 sector/market 仅强制 `stale`（:61,78）；`threshold_pct` 仅 `include_intraday` 时生效。
- `engine.py`：`with_intraday` 是正确的盘中叠加路径，但 `/intraday` 路由经 `build_intraday` 绕过它（M2）——两条盘中路径有冗余，需收敛。

---

## 附：硬边界对照表

| 硬边界 | 结论 | 证据 |
|---|---|---|
| 不输出买入/卖出建议 | ✅ | 源码无越界文案 + `KeyLevelPanel.test.tsx` 守卫 |
| 不改生产排序 | ✅ | 零引用生产排序/优先榜 |
| 不改策略打分边界 | ✅ | 零引用 strategy_policy/production_scoring |
| 不使用信号日之后数据 | ✅ | `engine.py:230-235,197`；`validation.py:90-97` |
| 数据不足必须 insufficient/research_only/blocked/stale | ✅ | `engine.py:160-178,225`；`materialization.py:130-161` |

**收尾判断：阻断项在“运营（接调度器）+ 缓存存储扩展”，应在生产开启 flag 前完成，而非合入前。** 此前内部 4 项修复均已独立核验为真实修复。
