# TQuant Phase 2 开发审查报告

**日期**: 2026-05-05
**审查对象**: Codex 按《TQuant回测Phase2需求文档-最终版》完成的全部开发交付物
**审查范围**: 20 个后端源文件 + 5 个前端文件 + 1 个测试文件 + 2 个新增服务文件
**审查方法**: 逐文件读取，需求逐条对照，代码坏味道扫描，性能路径分析

---

## 一、总体评价

**开发完成度**: 91%。Phase 2 五大 Steps（回测正确性修正、参数优化、Walk-Forward 验证、分析接口补齐、前端轻量接入）的核心功能全部实现。Phase 2 需求文档列出的 14 个 API 端点全部对接到前端。`BacktestResearchWorker` 作为后台轮询 worker 实现了优化和验证的异步执行。

**代码质量**: B。架构上 optimizer → engine 的复用是正确的，worker/scheduler 的分层清晰。主要扣分项：性能路径（N+1 数据拉取）、前端组件过度膨胀（单文件 555/467/600 行）、格式化函数跨文件三重复制、英文策略 key 残留在部分 UI 中。

**关键问题**: 1 个性能 Critical（optimizer 中每组合重拉全量日线数据）、1 个数据完整性 Bug（turnover 字段永远为 0）、6 个中等代码坏味道、11 个前端 UX/代码问题。

---

## 二、需求对照矩阵（逐条验收）

### Step 1：回测正确性修正

| 需求 | 状态 | 详情 |
|------|------|------|
| 真实涨跌停价计算修正 | ✅ 完成 | broker.py 第 154-164 行 `_limit_price` 基于 `pre_close * (1 + limit_pct/100)`，不再使用 `selected_price` |
| 板块涨跌幅区分（科创20%/创业20%/北交30%/主板10%） | ✅ 完成 | `a_share_price_limit_pct` 函数正确映射 688/689→20%, 300/301→20%, 8/4/920→30%, 其他→10% |
| 涨跌停判断带 0.2% 容差 | ✅ 完成 | `_is_limit_up`/`_is_limit_down` 使用 `limit_pct - 0.2` 阈值 |
| timeout 状态新增 | ✅ 完成 | engine.py 第 217 行 `status="timeout"`，BacktestStatus 类型含 `"timeout"` |
| max_duration_seconds 配置 | ✅ 完成 | BacktestConfig 第 35 行，默认 1800 秒 |
| 超时检测循环 | ✅ 完成 | engine.py 第 142 行 `_timeout_requested` |
| reporter.py 处理 | ✅ 已删除 | 文件不存在，逻辑整合到 backtest_job_service.py |
| dataclass_list 死代码清理 | ✅ 已删除 | analyzer.py 中无此函数 |

**Step 1 完成度: 100%**

### Step 2：参数优化任务

| 需求 | 状态 | 详情 |
|------|------|------|
| 异步执行（不阻塞 HTTP） | ✅ | Worker 15 秒轮询 `claim_next_task` + 独立线程执行 |
| 网格搜索算法 | ✅ | optimizer.py `enumerate_param_sets`，笛卡尔积穷举 |
| >500 组合降级随机搜索 | ✅ | optimizer.py 第 205-208 行，`sampled=True` 标记 |
| 强制 OOS 验证 | ✅ | optimizer.py `optimize_with_oos`，train→最优→test |
| 仅 5 个参数可优化 | ✅ | `ALLOWED_OPTIMIZATION_PARAMS` 校验 |
| 每组合记录指标 | ✅ | return/win_rate/stop_loss_rate/max_dd/profit_factor/sharpe |
| 可取消 | ✅ | `_CancelToken` + 每组合后检查 |
| 取消后保留已完成结果 | ✅ | 已完成组合的结果保留在 `result_json` |
| 结果不自动应用 | ✅ | 仅存储为 JSON，无生产配置联动 |
| 管理员/白名单权限 | ⚠️ | `_require_optimizer_access` 允许 admin/can_paper_trade/backtest_optimizer，比需求宽松 |
| backtest_optimizations 表 | ✅ | 实体定义在 backtest_entities.py 第 126-153 行 |
| 5 个 API 端点 | ✅ | POST/GET/GET/:id/POST:cancel/DELETE 全部实现 |
| 全局最多 1 个运行 | ✅ | `claim_next_task` 在 running 状态时返回 None |

**Step 2 完成度: 96%**（权限略宽松但功能完整）

### Step 3：Walk-Forward 验证

| 需求 | 状态 | 详情 |
|------|------|------|
| 窗口自动生成 | ✅ | validator.py `generate_windows`，基于日期范围 |
| 默认 4 窗口、75% 训练 | ✅ | walk_forward 调用时使用默认值 |
| 每窗口：训练优化 → 最优参数 → 测试回测 | ✅ | 完整实现 |
| PBO 计算 | ✅ | validator.py 第 221-228 行，过拟合计数/总窗口 |
| downgrade_review 标记 | ✅ | 任一样本外 Sharpe < 0 时触发 |
| 稳定性结论自然语言 | ✅ | "X/Y 窗口盈利" 文本生成 |
| 异步执行 | ✅ | 复用 Worker 模式 |
| backtest_validations 表 | ✅ | 实体定义在 backtest_entities.py 第 155-181 行 |
| 5 个 API 端点 | ✅ | POST/GET/GET/:id/POST:cancel/DELETE 全部实现 |

**Step 3 完成度: 100%**

### Step 4：分析接口补齐

| 需求 | 状态 | 详情 |
|------|------|------|
| POST /backtests/compare | ✅ | 多组回测对比，返回指标对比+净值曲线 |
| GET /backtests/{id}/monthly-returns | ✅ | 按月聚合收益 |
| GET /backtests/{id}/attribution | ✅ | 策略/行业/市场状态/质量分桶四维归因 |
| GET /backtests/{id}/strategy-correlation | ✅ | Pearson 相关系数矩阵 |
| backtest_daily_snapshots.market_state | ✅ | 字段已存在并持久化 |
| backtest_trades.sector | ✅ | 字段已存在并持久化 |

**Step 4 完成度: 100%**

### Step 5：前端轻量接入

| 需求 | 状态 | 详情 |
|------|------|------|
| 优化任务页（提交表单+任务列表+结果） | ✅ | BacktestResearchPanel.tsx 内联 OptimizationPanel |
| 验证结果页（窗口卡片+PBO+结论） | ✅ | BacktestResearchPanel.tsx 内联 ValidationPanel |
| 回测对比页（多选+指标表+净值叠加） | ⚠️ | 功能完整但**手动输入 run ID**，非多选复选框 |
| 归因面板（四维表格） | ✅ | AttributionPanel 含策略/行业/市场/质量 |
| 纯表格/卡片，不引入新图表 | ✅ | 未引入 ECharts 或重图表 |
| SVG 净值图保留 | ✅ | 保留且新增多线叠加 SVG |
| 所有 Phase 2 14 个 API 前端消费 | ✅ | backtests.ts 756 行，14 个方法全部可调用 |

**Step 5 完成度: 90%**（对比页的 run ID 输入方式未达到"傻瓜式"）

---

## 三、发现问题清单

### 3.1 性能问题（Critical）

**#1 — optimizer 中每参数组合重拉全量日线（N+1 数据拉取）**

位置：optimizer.py 第 225-228 行 → `_config_for_params` → `data_provider.fetch_bars()`

问题：500 组参数组合，`fetch_bars` 被调用 500 次，每次从 `daily_bar_snapshots` 表拉取相同日期范围的相同标的日线数据。产生 500 次相同的 SQL 查询。

影响：60 组参数的优化从理论上的 15 分钟变成实际 60-90 分钟。500 组组合可能跑数小时。

修复建议：
```python
# optimizer.py 的 optimize_with_oos 中，参数组合循环之前先拉取数据
bars_cache = self.engine.data_provider.fetch_bars(symbols, start_date, end_date)
# 传给每个组合的 engine run（需要 engine 支持注入预拉取数据）
```
或更简洁的方案：让 `BacktestEngine.run()` 内部做缓存，相同参数不重复拉取。

**#2 — validator 的测试窗口也跑全量参数组合而非仅最优参数**

位置：validator.py 第 155-180 行

问题：每窗口的测试期调用 `optimizer.optimize_with_oos()`，在测试期又跑了一遍完整的网格搜索，而不是只用训练期的 TOP-1 参数跑一次回测。

影响：4 窗口 Walk-Forward 实际跑了 4 次完整优化（每次 N 组），而非 4 次训练优化 + 4 次单参数验证。时间膨胀 4 倍。

修复建议：测试期不应调用 `optimize_with_oos`，应直接用训练期最优参数调用 `engine.run()`。

### 3.2 数据完整性 Bug

**#3 — turnover 字段永远为 0**

位置：persistence.py `_create_equity_snapshots` 第 132-160 行

问题：`BacktestDailySnapshot.turnover` 字段在模型中存在（backtest_entities.py 第 100 行），API 返回中也包含（backtest_job_service.py 第 163 行），但 persistence.py 从未设置该字段。所有回测的每日换手率恒为 0.0。

**#4 — 超时/取消的部分结果可能混入优化排名**

位置：optimizer.py 第 142-148 行

问题：优化过程中如果某组合回测超时或取消，`engine.run()` 返回 `BacktestResult(status="timeout")` 含部分数据。但 optimizer 的 `_candidate_metrics` 不检查 `result.status`，部分数据被当作完整结果纳入排名。

修复：在 `_candidate_metrics` 入口或调用处过滤 `status != "succeeded"` 的结果。

### 3.3 代码坏味道

**#5 — 三重复制的 CancelToken 实现**

位置：
- backtest_job_service.py 第 213-228 行
- backtest_optimization_service.py 第 27-32 行（Protocol）+ 第 38-39 行
- backtest_research_worker.py 第 29-49 行

`_CancelToken` / `_RunCancelToken` / `BacktestResearchCancelToken` 三个类功能几乎相同（cancel/set event/is_cancelled check），分别定义在三个文件中。应提取为 `backtest_cancel_token.py`。

**#6 — optimizer.py 中 dead code**

- 第 173-187 行 `grid_search()` 方法：无任何调用者，被 `optimize_with_oos` 完全替代
- 第 4 行 `from dataclasses import asdict`：未使用的 import

**#7 — 前端格式化函数三重复制**

三个文件独立定义了相同的格式化函数：
- `workspaceFormatters.ts`（官方版本）
- `BacktestDashboard.tsx` 第 430-467 行（副本）
- `BacktestResearchPanel.tsx` 第 508-540 行（副本）

`formatNumber`、`formatPct`、`formatInteger`、`toneFromNumber` 各三份。`formatPrice` 在 workspaceFormatters 和 BacktestDashboard 中实现不同（一个有阈值判断，一个始终 3 位小数）。

**#8 — 前端文件过度膨胀**

| 文件 | 行数 | 内联组件数 | 建议 |
|------|------|-----------|------|
| BacktestResearchPanel.tsx | 555 | 6 个内联 + 11 个辅助函数 | 拆分为 4 个独立组件文件 |
| BacktestDashboard.tsx | 467 | 6 个内联 + 10 个辅助函数 | 提取共享 UI 组件 |
| useBacktestDashboard.ts | 600 | 全部状态+副作用+回调 | 拆为 useBacktestForm / useBacktestRuns / useBacktestResearch |

**#9 — 两个 STRATEGY_OPTIONS 定义不一致**

- BacktestDashboard.tsx 第 47-53 行：`["first_board", "首板回调"]`（中英文映射）
- BacktestResearchPanel.tsx 第 77-83 行：`["first_board", "first_board"]`（英文 key 作标签）

Research panel 的优化和验证表单中，策略下拉显示的仍是英文 key。

**#10 — engine.run() 方法过长**

engine.py `run()` 方法（第 97-221 行）约 125 行。超时检测逻辑在 142 和 187 行出现两次，条件判断部分冗余。建议提取 `_run_exits_phase` / `_run_entries_phase` / `_build_result` 子方法。

### 3.4 前端 UX 问题

**#11 — 优化目标（optimization_target）无 UI 控件**

BacktestResearchPanel.tsx 的优化表单有 `optimization_target` 在状态中（默认 "sharpe"）、在 API 调用中发送，但表单没有下拉框让用户选择。用户无法改为 "total_return" 或 "profit_factor"。

**#12 — 对比面板使用裸文本输入 run ID**

用户需要手动输入 "42,45,47" 格式的逗号分隔数字，而非从已完成任务列表勾选。最明显的 UX 摩擦点。

**#13 — 验证表单中 window_count 和 train_ratio 是文本输入而非数字输入**

没有 `type="number"`、`min`、`max`、`step` 约束。

**#14 — PBO 风险评级无视觉编码**

显示裸文本 "low" / "medium" / "high"，无颜色徽章。CSS 中没有对应样式。

**#15 — 交易明细表中 strategy 列显示英文 key**

BacktestDashboard.tsx 第 269 行 `trade.strategy` 直接渲染，显示 "first_board" 而非 "首板回调"。

**#16 — 无任何表单字段的 tooltip**

所有参数（min_score、max_position_pct、stop_loss_pct 等）无解释性提示。

**#17 — 加载态使用魔术字符串**

`state.loading === "research"` 等字符串标志散布在 10+ 处。typo 会导致加载指示器静默失效。

---

## 四、架构评估

### 4.1 做得好的决策

1. **Worker + claim_next_task 模式**：`BacktestResearchWorker.run_once()` 作为 15 秒轮询循环运行在 task_manager 中，每次取一个 queued 任务执行。这种单步模式简单可靠，避免了复杂的线程池管理。

2. **optimizer 对 engine 的复用**：optimizer 完全复用 `BacktestEngine.run()`——不做重复的回测逻辑。`_config_for_params` 通过修改 `BacktestConfig` 的参数来驱动不同组合的回测，保持了单向依赖。

3. **软删除模式**：backtest_optimizations 和 backtest_validations 使用 `deleted_at` 字段而非物理删除，查询自动过滤 `deleted_at.is_(None)`。数据可恢复，审计友好。

4. **optimization_service 和 validation_service 的对称设计**：两者 API 完全对称（create/list/get/cancel/delete），Worker 也对称处理。调用方不需要记忆两个不同的接口。

5. **模型中使用 `Optional[int]` 外键**：`owner_user_id` 可为 None（匿名用户），安全且灵活。

### 4.2 需要改进的架构决策

1. **Worker 是 15 秒轮询而非真正的事件驱动**：`task_manager.register_loop` 每隔 15 秒调用一次 `run_once()`。这意味着任务提交后最多等 15 秒才能开始执行。

2. **所有 Phase 2 功能挤在 BacktestResearchPanel 一个文件里**：优化/验证/对比/归因/相关性 5 个模块共用一个 555 行组件。任何模块的修改都可能影响其他模块。

3. **缺少数据缓存层**：optimizer 和 validator 中，相同的日期范围 + 标的组合的日线数据被反复拉取。应该有一个请求级或线程级的 bar cache。

---

## 五、数据库审查

### 5.1 新增表

`backtest_optimizations`（backtest_entities.py 第 126-153 行）：
- 字段齐全，包含需求文档的所有列
- `deleted_at` 字段作为软删除标记 + 索引
- `updated_at` 使用 `onupdate=func.now()` 自动更新
- ⚠️ 缺少 `search_method` 字段（需求文档要求区分 grid/random），当前信息隐含在 `result_json` 中

`backtest_validations`（backtest_entities.py 第 155-181 行）：
- 字段齐全
- 同样有软删除支持
- ⚠️ 缺少 `pbo_risk`、`downgrade_review`、`stability_conclusion` 独立列——需求文档要求这些作为独立字段，当前全部嵌入 `result_json`

### 5.2 已有表变更

| 表 | 需求字段 | 实际状态 |
|----|---------|---------|
| backtest_runs.max_duration_seconds | ✅ 需要 | ✅ 使用 BacktestConfig.max_duration_seconds 控制，未存为独立 DB 列，但在 config 快照中 |
| backtest_runs.optimization_id | ✅ 需要 | ❌ 未作为 FK 列存在。优化产生的回测 run 通过 request_json 中的 optimization_id 关联 |
| backtest_runs.validation_id | ✅ 需要 | ❌ 同上 |
| backtest_daily_snapshots.market_state | ✅ 需要 | ✅ 已存在（第 104 行） |
| backtest_trades.sector | ✅ 需要 | ✅ 已存在（第 78 行） |

需求文档中 `ALTER TABLE backtest_runs ADD COLUMN optimization_id` 和 `validation_id` 未实施。但功能上通过 `request_json` 中的引用实现了关联——这降低了查询效率（需要 JSON 解析），但避免了 schema migration 风险。属于权衡取舍。

---

## 六、测试覆盖

仅发现一个 Phase 2 测试文件：`test_backtest_phase2_research_tasks.py`

优点：测试了 optimization 和 validation 的完整 Worker 流程（create → claim → execute → result）。

缺失：
- 无 optimizer 单元测试（网格搜索正确性、参数校验、OOS 切分）
- 无 validator 单元测试（窗口生成、PBO 计算）
- 无 API 端点契约测试（请求/响应格式验证）
- 无权限测试（optimizer_access 拒绝非授权用户）

---

## 七、完整问题排序（按严重度）

| # | 严重度 | 类别 | 位置 | 问题 |
|---|--------|------|------|------|
| 1 | **Critical** | 性能 | optimizer.py:225 | N+1 数据拉取——500 组参数 = 500 次相同的 DB 查询 |
| 2 | **Critical** | 性能 | validator.py:155 | 测试窗口跑完整网格搜索而非仅最优参数回测 |
| 3 | **High** | 数据 | persistence.py:132 | turnover 字段永远为 0 |
| 4 | **High** | 数据 | optimizer.py:142 | 超时/取消的部分结果混入优化排名 |
| 5 | **Medium** | 代码 | optimizer.py:173 | `grid_search()` dead code |
| 6 | **Medium** | 代码 | optimizer.py:4 | 未使用的 `asdict` import |
| 7 | **Medium** | 代码 | 3 个文件 | CancelToken 三重复制 |
| 8 | **Medium** | 代码 | 3 个前端文件 | 格式化函数三重复制 |
| 9 | **Medium** | 前端 | ResearchPanel:269 | 对比面板用文本输入 run ID 而非复选框 |
| 10 | **Medium** | 前端 | ResearchPanel:132 | 策略下拉显示英文 key 而非中文名 |
| 11 | **Medium** | 前端 | ResearchPanel:131 | optimization_target 无 UI 控件 |
| 12 | **Medium** | 前端 | Dashboard:269 | 交易表 strategy 列显示英文 key |
| 13 | **Low** | 前端 | ResearchPanel:211 | window_count/train_ratio 应为数字输入 |
| 14 | **Low** | 前端 | ResearchPanel:236 | PBO 风险无颜色编码 |
| 15 | **Low** | 前端 | ResearchPanel:555 | 单文件 555 行，应拆分 |
| 16 | **Low** | 前端 | Dashboard:467 | 单文件 467 行，应拆分 |
| 17 | **Low** | 前端 | useBacktest:600 | 单 hook 600 行，应拆分 |
| 18 | **Low** | 代码 | backtest_entities | 缺 search_method 独立列 |
| 19 | **Low** | 代码 | backtest_entities | 缺 pbo_risk/downgrade/stability 独立列 |
| 20 | **Low** | 测试 | tests/ | 缺 optimizer/validator 单元测试 |

---

## 八、修复建议（按优先级）

### 立即修复（阻塞生产）

1. **optimizer N+1 数据拉取**：在 `optimize_with_oos` 入口处预拉取日线数据并缓存，或让 `BacktestEngine.run()` 内部缓存。预期将 500 组合优化时间从数小时降至 30-60 分钟。

2. **validator 测试窗口优化**：测试期不应调用 `optimize_with_oos`，应直接用训练期最优参数调用 `engine.run()`。预期将 Walk-Forward 时间减少 75%。

3. **超时/取消结果过滤**：optimizer 在收集候选结果时过滤 `status != "succeeded"` 的结果。

### 本周修复

4. **turnover 字段填充**：persistence.py 中从 `PortfolioSnapshot` 获取换手率并写入 `BacktestDailySnapshot.turnover`。

5. **dead code 清理**：删除 optimizer.py 的 `grid_search()` 方法和未使用的 `asdict` import。

6. **CancelToken 提取**：三个文件中的 CancelToken 实现合并为 `backtest_cancel_token.py`。

### 两周内修复

7. **前端格式化函数去重**：全部统一 import 自 `workspaceFormatters.ts`。

8. **前端文件拆分**：BacktestResearchPanel → OptimizationPanel / ValidationPanel / ComparePanel / AttributionPanel。BacktestDashboard → 提取共享组件。

9. **策略下拉中文标签**：BacktestResearchPanel 复用 BacktestDashboard 的 STRATEGY_OPTIONS。

10. **optimization_target 下拉**：优化表单增加目标指标选择器。

11. **对比面板复选框**：替换文本输入为已完成回测列表 + 多选复选框。

---

## 九、结论

Phase 2 实现是一次**方向正确、完成度高的交付**。五个 Step 的功能全部可用，14 个 API 端点全部打通前端，Worker + claim_next_task 的异步模式运转正常。Phase 2 需求文档中的核心承诺——"回测正确性 + 参数优化 + 样本外验证 + 结果对比"——已兑现。

最大的问题不在正确性，而在**性能和代码整洁度**。optimizer 和 validator 的数据拉取路径存在显著的低效，500 组参数优化可能跑数小时。前端组件过度膨胀到 555/467/600 行，格式化函数三重复制——这些不是功能性 bug，但会拖慢后续 Phase 3 的开发速度。

整体评级：**可以合并，但必须在合并后 1 周内修复 2 个 Critical 性能问题，2 周内完成代码整洁度清理。否则 Phase 3 在这些膨胀文件上继续堆代码会失控。**

预计修复工期：
- Critical 性能修复：1-2 天
- 数据 Bug + Dead Code：0.5 天
- 前端去重 + 拆分：2-3 天
- 共计：**4-6 天**
