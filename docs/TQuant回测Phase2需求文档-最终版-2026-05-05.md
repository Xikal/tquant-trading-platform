# TQuant 回测系统 Phase 2 需求文档（最终版）

**日期**: 2026-05-05
**版本**: v2.0（经 Codex 交叉审查裁定）
**上一版本**: [v1.0](./TQuant回测Phase2需求文档-2026-05-05.md)（Claude 初稿）
**前置文档**: [v2 最终版需求文档](./TQuant回测闭环需求文档-v2-最终版-2026-05-05.md)、[v2 开发审查报告](./TQuant回测v2开发审查报告-2026-05-05.md)
**审查流程**: Claude 初稿 → Codex 复核 → 本文（逐条纳入 Codex 裁定，得出最终方案）

---

## 裁定总纲

Codex 对初稿的总体评价：方向合理，但不能照单全收。初稿混合了三类内容——已完成但文档未更新的判断、真正需要补齐的核心能力、以及体验增强项。当前最应该做的是先补"回测正确性 + 参数优化 + 样本外验证 + 结果对比"，不要先做 WebSocket 和大规模前端图表重构。

以下为逐条裁定后的最终需求文档。

---

## 一、Phase 2 定位修正

**初稿定位**: 将 TQuant 回测系统从"可用的验证工具"升级为"可量化的策略研究平台"。

**裁定**: 定位本身正确，但范围需要收窄。Phase 2 的核心是**研究闭环**而非**展示系统**。具体来说：

1. **必须做**：回测正确性修正 → 参数优化（异步、可追踪）→ Walk-Forward 样本外验证 → 多维归因接口 → 前端轻量接入
2. **暂缓做**：WebSocket 实时推送、ECharts 完整替换 SVG 图表、收益热力图、分布直方图、toast 通知系统
3. **不做**：贝叶斯优化、分钟级全市场回测、自动应用优化参数、前端图表全面重构

**预计周期**: 稳定可用版约 3-4 周。全部做完（含体验增强）约 6-8 周。**建议先交付 3-4 周的稳定版，等回测闭环跑通后再补展示增强。**

---

## 二、当前状态重新评估

### 2.1 审查报告中已修复的项（文档初稿判断过期）

经 Codex 确认，以下问题在最新代码中已处理，Phase 2 不再重复修复：

| # | 原问题 | 实际状态 |
|---|--------|---------|
| 1 | `RealizedTrade` 缺 `holding_days` 字段 | **已修复**（portfolio.py 第 62 行） |
| 2 | `fee_amount` 仅含卖出费用 | **已修复**（`RealizedTrade.fee_amount` 含完整费用） |
| 3 | `requested_price` 错误赋值 | **已改进**（优先读取 `order.requested_price`） |
| 4 | engine `_dedupe_signals` 同分非确定性 | **已修复**（使用 `(score, strategy_key)` 元组） |
| 5 | analyzer 缺 Sortino/Calmar/基准对比 | **已实现**（analyzer.py 第 37-41 行） |

### 2.2 仍需修复的项

| # | 优先级 | 问题 | 当前代码状态 |
|---|--------|------|-------------|
| 1 | **P0** | 真实涨跌停价计算错误 | broker.py 第 77-78 行，`up_limit`/`down_limit` 传入撮合引擎的值是 `selected_price` 而非 `pre_close * (1 ± limit_pct)`。涨跌停**判断**（`_is_limit_up`/`_is_limit_down`）已有 9.8% 阈值逻辑，但真实涨跌停**价格**计算才是影响撮合的核心问题 |
| 2 | **P0** | 回测超时状态缺失 | 当前只有 `pending/running/completed/failed/cancelled` 五种 status，缺少 `timeout` 状态。超时后的回测无法与普通失败区分 |
| 3 | **P1** | `reporter.py` 死代码 | 45 行代码未被任何生产路径调用。需确认去留——要么接入 job_service 的详情接口，要么删除 |
| 4 | **P1** | `dataclass_list` 死代码 | analyzer.py 第 183-184 行，全项目未引用 |

---

## 三、Phase 2 核心功能详规

### 3.1 回测正确性修正（P0，Phase 2 第一步）

#### 3.1.1 真实涨跌停价传入撮合引擎

**问题**：broker.py 第 77-78 行当前将 `selected_price`（执行价格）作为涨跌停价传入 `PaperMatchingEngine`。这导致撮合引擎在判断是否触及涨跌停时使用的是成交价而非真实涨跌停价。

**修复**：基于 `pre_close`（昨日收盘价）和板块涨跌幅比例计算真实涨跌停价：

```python
# 板块涨跌幅比例映射
def _limit_pct(symbol: str, is_st: bool) -> float:
    if is_st:
        return 0.05
    if symbol.startswith('68'):      # 科创板
        return 0.20
    if symbol.startswith('30'):      # 创业板
        return 0.20
    if symbol.startswith('4') or symbol.startswith('8'):  # 北交所
        return 0.30
    return 0.10                       # 主板

# broker.py 修正
up_limit_price = bar.pre_close * (1 + _limit_pct(request.symbol, request.bar.is_st))
down_limit_price = bar.pre_close * (1 - _limit_pct(request.symbol, request.bar.is_st))

match = self.matching.match(
    ...
    up_limit=to_decimal(up_limit_price) if _is_limit_up(request.bar) else None,
    down_limit=to_decimal(down_limit_price) if _is_limit_down(request.bar) else None,
)
```

前置条件：确认 `DailyBar` 包含 `pre_close` 字段（data_provider.py 从 `daily_bar_snapshots` 读取的行情中有此字段）。

#### 3.1.2 增加 timeout 状态

在 `backtest_runs.status` 枚举中新增 `timeout` 值。超时检测逻辑：

- `BacktestConfig` 新增 `max_duration_seconds` 参数（默认 1800 = 30 分钟）
- engine 主循环每迭代一次检查 `time.monotonic() - start_time > max_duration`
- 超时后设置 cancel token + `status = 'timeout'`
- 超时区别于 `failed`（执行错误）和 `cancelled`（用户主动取消）

#### 3.1.3 死代码清理

- 删除 `analyzer.py` 第 183-184 行的 `dataclass_list` 函数
- `reporter.py`：如果接入 job_service 的详情查询可减少 result_json 体积则接入，否则直接删除。判断标准——看 `to_summary` 是否比当前 `_detail` 读 `result_json` 更高效

---

### 3.2 参数优化任务（Phase 2 核心交付 #1）

#### 3.2.1 功能概述

为单个策略在指定日期范围内搜索最优参数组合。**必须异步执行、可取消、可追踪**，不能在 Web 请求里跑。

#### 3.2.2 搜索算法

- 默认：网格搜索（Grid Search）
- 参数组合 > 500 时自动降级为随机搜索（Random Search），取前 N 个最优
- **不做贝叶斯优化**（当前参数空间不大，网格/随机足够；且贝叶斯引入 scikit-optimize 新依赖，过早）

#### 3.2.3 可优化参数清单

仅允许优化以下参数（v2 裁定约束，不修改策略核心逻辑）：

| 参数 | 类型 | 说明 |
|------|------|------|
| `min_score` | int | 信号最低分 |
| `max_position_pct` | float | 单票最大仓位比例 |
| `max_holding_days` | int | 最大持仓天数 |
| `stop_loss_pct` | float | 止损比例 |
| `take_profit_pct` | float | 止盈比例 |

用户指定每个参数的取值列表（如 `min_score: [70, 75, 80, 85, 90]`），系统穷举组合。

#### 3.2.4 强制样本外验证（硬性约束）

参数优化必须伴随样本外验证：

1. 用户指定总日期范围
2. 系统自动切分：前 80% 为样本内（训练），后 20% 为样本外（验证）
3. 样本内：对每种参数组合运行回测
4. 取样本内最优参数（默认按 Sharpe 排序）
5. 样本外：用最优参数在验证窗口独立运行一次
6. 对比 IS vs OOS 绩效

若 OOS Sharpe < 0 或 OOS 收益较 IS 下降 > 50%，标记为 `oos_downgrade: true`。

#### 3.2.5 必须记录的指标

每个参数组合必须记录：参数值、总收益率、胜率、止损率（触及止损的交易占比）、最大回撤、Profit Factor、Sharpe Ratio、IS/OOS 标记。

#### 3.2.6 异步执行架构

优化任务不在 HTTP 请求线程中执行。架构：

```
POST /api/backtests/optimize
  → 写入 backtest_optimizations 表（status=pending）
  → 后台 Worker 线程取任务（status=running）
    → 循环：对每种参数组合调用 BacktestEngine.run()
    → 每个组合完成后记录结果 + 更新 progress
    → 全部完成后 OOS 验证
    → 写入最终结果（status=completed）
  → 前端轮询 GET /api/backtests/optimize/{id} 获取进度
```

- 全局最多 1 个优化任务同时运行
- 支持取消（`POST /api/backtests/optimize/{id}/cancel`）
- 取消后保留已完成组合的结果

#### 3.2.7 优化结果不自动应用

**优化结果不自动应用**到生产策略配置。最多生成"建议参数"，必须人工确认后才能手动修改策略配置。这是过拟合防护的硬约束。

#### 3.2.8 API

```
POST   /api/backtests/optimize              ← 提交优化任务（需管理员/白名单）
GET    /api/backtests/optimize              ← 优化任务列表（分页）
GET    /api/backtests/optimize/{id}         ← 优化详情（含各参数组合得分排名）
POST   /api/backtests/optimize/{id}/cancel  ← 取消优化
DELETE /api/backtests/optimize/{id}         ← 删除优化记录
```

请求体：

```json
{
  "name": "first_board 参数优化",
  "strategy": "first_board",
  "param_grid": {
    "min_score": [70, 75, 80, 85, 90],
    "max_holding_days": [3, 5, 7, 10, 14],
    "stop_loss_pct": [-0.03, -0.05, -0.07]
  },
  "train_start": "2024-01-02",
  "train_end": "2025-12-31",
  "test_start": "2026-01-02",
  "test_end": "2026-04-30",
  "optimization_target": "sharpe",
  "initial_capital": 500000,
  "execution_model": "open_price"
}
```

#### 3.2.9 权限

- 参数优化需**管理员权限或白名单用户**
- 不允许公开触发计算密集任务

---

### 3.3 Walk-Forward 样本外验证（Phase 2 核心交付 #2）

#### 3.3.1 功能概述

对给定策略在滚动时间窗口上重复"训练→验证"，输出样本外绩效汇总和稳定性结论。避免策略只在历史样本内过拟合。

#### 3.3.2 窗口自动生成

用户指定总日期范围，系统自动生成滚动窗口：

- 默认窗口数 = 4
- 训练窗口比例 = 75%（约 18 个月），测试窗口 = 25%（约 6 个月）
- 窗口步长 = 测试窗口长度

示例（总区间 2024-01-02 至 2026-04-30，约 28 个月）：

| 窗口 | 训练期 | 测试期 |
|------|--------|--------|
| 1 | 2024-01-02 → 2025-07-01 | 2025-07-02 → 2026-01-02 |
| 2 | 2024-07-02 → 2026-01-02 | 2026-01-05 → 2026-04-30 |

窗口数和比例可配置（`window_count`、`train_ratio`）。

#### 3.3.3 每窗口流程

1. 训练期：运行参数优化（网格搜索），得到最优参数
2. 测试期：用最优参数运行一次回测
3. 记录：训练期 Sharpe、测试期 Sharpe、最优参数集

#### 3.3.4 PBO（Probability of Backtest Overfitting）

简化版 PBO 计算：对每个窗口，对比样本内排名和样本外排名。如果样本内最优的参数组合在样本外排名大幅下滑（跌出前 30%），视为过拟合信号。

输出 PBO 风险评级：`low` / `medium` / `high`。

#### 3.3.5 策略降级标记

若任一样本外窗口的 Sharpe < 0，策略标记为 `downgrade_review_required`。前端显示警告。

#### 3.3.6 验证必须输出的结论

- 每个窗口的训练/测试 Sharpe、收益率、最大回撤
- 平均样本外 Sharpe
- 样本外通过率（Sharpe > 0 的窗口数 / 总窗口数）
- PBO 风险评级
- 稳定性结论（"该策略在 3/4 窗口样本外盈利，稳定性良好" 或 "该策略仅在 1/4 窗口样本外盈利，建议暂缓实盘"）

#### 3.3.7 异步执行架构

同优化任务——不在 HTTP 请求线程中执行，Worker 异步处理，支持取消和进度查询。

#### 3.3.8 API

```
POST   /api/backtests/validate              ← 提交验证任务（需登录）
GET    /api/backtests/validate              ← 验证任务列表（分页）
GET    /api/backtests/validate/{id}         ← 验证详情（含各窗口结果）
POST   /api/backtests/validate/{id}/cancel  ← 取消验证
DELETE /api/backtests/validate/{id}         ← 删除验证记录
```

请求体：

```json
{
  "name": "first_board Walk-Forward 验证",
  "strategy": "first_board",
  "start_date": "2024-01-02",
  "end_date": "2026-04-30",
  "window_count": 4,
  "train_ratio": 0.75,
  "initial_capital": 500000,
  "execution_model": "open_price"
}
```

---

### 3.4 回测分析接口补齐（Phase 2 核心交付 #3）

#### 3.4.1 多组回测对比

```
POST /api/backtests/compare
{
  "run_ids": [42, 45, 47]
}
```

响应包含：各回测关键指标对比表 + 各回测的净值曲线数据（前端叠加显示）。

#### 3.4.2 月度收益

```
GET /api/backtests/{run_id}/monthly-returns
```

返回按月聚合的收益数据。从 `backtest_daily_snapshots` 表按月汇总。

#### 3.4.3 归因接口

```
GET /api/backtests/{run_id}/attribution
```

返回：
- **策略归因**：每个策略的独立绩效（已有 `_by_strategy`）
- **行业归因**：按行业分组的交易次数、净收益、胜率、贡献度
- **市场状态归因**：按 8 类市场状态分组的交易次数、胜率、平均收益
- **数据质量分桶**：按质量高/中/低分组的收益对比

行业分类数据来源：项目中已有的行业分类逻辑，或从回测数据准备阶段查询。报告中标注"行业分类可能存在历史偏差"。

---

### 3.5 前端接入（Phase 2 核心交付 #4）

**裁定**：前端先做功能入口，用表格和轻量图，后续再上复杂图表。不要一次性重构所有前端图表，避免引入新的 bundle 和交互风险。

#### 3.5.1 新增页面/入口

| 页面 | 内容 | 图表策略 |
|------|------|---------|
| 优化任务页 | 提交表单（策略选择、参数网格、日期范围）+ 任务列表 + 结果详情（参数排名表、IS vs OOS 对比） | **纯表格**，不引入新图表 |
| 验证结果页 | 窗口卡片组（每窗口显示训练/测试 Sharpe）+ PBO 评级 + 稳定性结论 | **纯卡片 + 文本** |
| 回测对比页 | 多选已完成回测 → 指标对比表 + 净值曲线叠加 | 复用现有 SVG 净值图（多线叠加即可） |
| 归因面板 | 策略归因表 + 行业归因表 + 市场状态归因表 + 质量分桶 | **纯表格** |

#### 3.5.2 保持现有前端

- SVG 净值曲线保留，不做 ECharts 替换
- 8 指标卡片保留
- 交易明细表保留

#### 3.5.3 不做的前端

- WebSocket 实时推送（当前轮询足够，先把任务状态和结果表做稳）
- ECharts 完整净值曲线（含缩放/tooltip/买卖点标注）
- 月度收益热力图
- 收益分布直方图
- toast 通知系统

以上在 Phase 2 稳定版跑通后，作为 Phase 2.5（体验增强）再考虑。

---

### 3.6 策略相关性矩阵

对多策略联合回测，计算策略间收益序列的 Pearson 相关系数。以表格展示，帮助判断策略组合的分散化程度。

实现方式：从已有回测的每日快照数据中提取各策略的日收益序列，计算两两相关系数。不新增回测运行——仅从已有数据计算。

API：

```
GET /api/backtests/{run_id}/strategy-correlation
```

---

## 四、数据库变更

### 4.1 新增表

```sql
-- 参数优化任务
CREATE TABLE backtest_optimizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    name TEXT NOT NULL,
    strategy TEXT NOT NULL,
    param_grid_json TEXT NOT NULL,
    search_method TEXT NOT NULL DEFAULT 'grid',
    optimization_target TEXT NOT NULL DEFAULT 'sharpe',
    status TEXT NOT NULL DEFAULT 'pending',
    progress_pct REAL DEFAULT 0,
    total_combinations INTEGER NOT NULL DEFAULT 0,
    completed_combinations INTEGER NOT NULL DEFAULT 0,
    -- 样本内最优
    best_params_json TEXT,
    best_is_score REAL,
    best_is_metrics_json TEXT,
    -- 样本外验证
    best_oos_score REAL,
    best_oos_metrics_json TEXT,
    oos_downgrade INTEGER DEFAULT 0,
    oos_downgrade_reason TEXT,
    -- 全部候选结果
    candidates_json TEXT,
    -- 日期范围
    train_start TEXT,
    train_end TEXT,
    test_start TEXT,
    test_end TEXT,
    -- 配置快照
    base_config_json TEXT,
    -- 元信息
    duration_seconds REAL,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Walk-Forward 验证任务
CREATE TABLE backtest_validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    name TEXT NOT NULL,
    strategy TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress_pct REAL DEFAULT 0,
    config_json TEXT NOT NULL,
    -- 汇总指标
    window_count INTEGER,
    oos_pass_rate REAL,
    avg_oos_sharpe REAL,
    avg_is_sharpe REAL,
    pbo_risk TEXT,
    downgrade_review INTEGER DEFAULT 0,
    stability_conclusion TEXT,
    -- 每窗口详情
    windows_json TEXT,
    -- 元信息
    duration_seconds REAL,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 4.2 变更已有表

```sql
-- backtest_runs 新增字段
ALTER TABLE backtest_runs ADD COLUMN max_duration_seconds INTEGER DEFAULT 1800;
ALTER TABLE backtest_runs ADD COLUMN optimization_id INTEGER REFERENCES backtest_optimizations(id);
ALTER TABLE backtest_runs ADD COLUMN validation_id INTEGER REFERENCES backtest_validations(id);

-- backtest_daily_snapshots 新增字段（归因用）
ALTER TABLE backtest_daily_snapshots ADD COLUMN market_state TEXT;

-- backtest_trades 新增字段（归因用）
ALTER TABLE backtest_trades ADD COLUMN sector TEXT;
```

### 4.3 status 枚举扩展

`backtest_runs.status` 新增值：`timeout`

---

## 五、API 扩展总览

```
# 已有（Phase 1-3，不变）
POST   /api/backtests
GET    /api/backtests
GET    /api/backtests/{run_id}
GET    /api/backtests/{run_id}/equity
GET    /api/backtests/{run_id}/trades
POST   /api/backtests/{run_id}/cancel
DELETE /api/backtests/{run_id}

# Phase 2 新增（分析接口）
POST   /api/backtests/compare                        ← 多组回测对比
GET    /api/backtests/{run_id}/monthly-returns       ← 月度收益
GET    /api/backtests/{run_id}/attribution            ← 归因数据
GET    /api/backtests/{run_id}/strategy-correlation   ← 策略相关性

# Phase 2 新增（优化任务，需管理员/白名单）
POST   /api/backtests/optimize
GET    /api/backtests/optimize
GET    /api/backtests/optimize/{id}
POST   /api/backtests/optimize/{id}/cancel
DELETE /api/backtests/optimize/{id}

# Phase 2 新增（验证任务，需登录）
POST   /api/backtests/validate
GET    /api/backtests/validate
GET    /api/backtests/validate/{id}
POST   /api/backtests/validate/{id}/cancel
DELETE /api/backtests/validate/{id}
```

权限：
- 优化端点：管理员或白名单用户（403 拒绝非授权用户）
- 验证端点：需登录
- 对比/归因/月度收益：需登录（回测所有者或管理员）
- 所有计算密集端点不允许公开访问

---

## 六、不改动的内容

- 现有策略信号逻辑（`low_buy/` 下的所有策略文件）
- 现有回测引擎核心逻辑（`engine.py` 的买卖时序、资金竞争、止损止盈）
- 现有撮合引擎和费用模型（`paper/` 服务）
- 现有前端看板的表单、任务列表、净值图、交易明细表（保留，不做破坏性重构）

---

## 七、不做清单（明确排除）

1. **WebSocket 实时推送**——当前轮询足够，先把任务状态和结果表做稳。体验增强阶段再做
2. **ECharts 替换 SVG 净值图**——SVG 轻量图够用，不做重型图表重构
3. **贝叶斯优化**——参数空间不大，网格/随机搜索足够。且引入新依赖过早
4. **分钟级全市场回测**——数据量和成本不适合当前阶段
5. **自动应用优化参数**——只生成"建议参数"，必须人工确认
6. **收益热力图、分布直方图**——体验增强阶段再做
7. **toast 通知系统**——体验增强阶段再做
8. **多策略联合参数优化**——先做单策略优化跑通方法论

---

## 八、实施路线

### Step 1：回测正确性修正（3-4 天）

- [ ] 真实涨跌停价计算（broker.py `up_limit`/`down_limit` 修正）
- [ ] 超时状态新增（`timeout` status + engine 超时检测）
- [ ] 死代码清理（`dataclass_list` 删除 + `reporter.py` 去留确认）
- [ ] 确认 `DailyBar.pre_close` 字段可用

### Step 2：参数优化任务（5-6 天）

- [ ] `backtest_optimizations` 表创建
- [ ] Pydantic schema（请求/响应/详情）
- [ ] `optimizer.py` 从骨架升级（网格搜索 + 随机降级 + IS/OOS 自动切分）
- [ ] Worker 异步执行（全局队列 + 取消支持 + 进度更新）
- [ ] API 端点（提交/列表/详情/取消/删除）
- [ ] 权限控制（管理员/白名单）
- [ ] 前端优化任务页（提交表单 + 任务列表 + 参数排名表 + IS vs OOS 对比）

### Step 3：Walk-Forward 验证（4-5 天）

- [ ] `backtest_validations` 表创建
- [ ] Pydantic schema
- [ ] `validator.py` 从骨架升级（自动窗口生成 + PBO 计算 + 稳定性结论）
- [ ] Worker 异步执行（复用 Step 2 的 Worker 模式）
- [ ] API 端点
- [ ] 前端验证结果页（窗口卡片组 + PBO 评级 + 稳定性结论）

### Step 4：回测分析接口 + 前端接入（3-4 天）

- [ ] 多组回测对比 API + 前端对比页
- [ ] 月度收益 API + 前端月度收益表
- [ ] 归因接口（行业 + 市场状态 + 质量分桶 + 策略相关性）
- [ ] 前端归因面板（策略归因表 + 行业归因表 + 市场状态归因表 + 相关性矩阵表）

### Step 5：收尾验收（2-3 天）

- [ ] first_board 策略完整链路测试（参数优化 → Walk-Forward 验证 → 归因分析）
- [ ] 端到端测试（API 鉴权、异步取消、OOS 降级告警）
- [ ] 性能验证（60 组参数优化 ≤ 3 小时、4 窗口验证 ≤ 1.5 小时）
- [ ] 文档更新

---

## 九、验收标准

### Step 1 验收

1. 科创板（68 开头）涨跌停价基于 `pre_close * 1.20` 计算，主板（60 开头）基于 `pre_close * 1.10`
2. 回测运行超过 30 分钟自动标记 `timeout`，不影响其他任务
3. `reporter.py` 已删除或已接入 job_service

### Step 2 验收

1. 对 first_board 做 5×5=25 组网格搜索，15 分钟内完成
2. 优化结果页显示样本内排名表 + IS vs OOS 对比
3. 若 OOS Sharpe < 0，前端显示红色降级警告
4. 非管理员调用 optimize 返回 403
5. 优化中可取消，取消后状态为 `cancelled`

### Step 3 验收

1. 对 first_board 做 4 窗口 Walk-Forward 验证，输出每窗口 IS/OOS Sharpe
2. PBO 风险评级正确（可手工验证其中一窗口的计算）
3. 稳定性结论自然语言可读
4. 样本外全部亏损时标记 `downgrade_review`
5. 验证中可取消

### Step 4 验收

1. 3 组回测的对比表显示关键指标差异，净值曲线叠加可见
2. 月度收益表按月聚合正确（与日度快照交叉验证）
3. 归因面板显示至少 3 个行业的收益贡献
4. 策略相关性矩阵数值合理（不出现 NaN 或 ±1.0 极端值）

### Step 5 验收（完整链路）

1. first_board 策略完成完整链路：参数优化 → 最优参数 OOS 验证 → Walk-Forward 验证 → 归因分析
2. 所有接口有鉴权（非登录用户无法触发计算密集任务）
3. 优化和验证的异步任务不阻塞 HTTP 请求
4. 策略信号逻辑无任何改动

---

## 十、结论

Phase 2 最终版聚焦四个字：**研究闭环**。不追求展示效果，不追求实时推送，不追求花哨图表。核心交付是：让用户能用系统自动搜索最优参数、自动验证样本外稳健性、自动归因收益来源——并用表格和轻量图看到结果。

比初稿砍掉了 WebSocket、ECharts、热力图、分布直方图、toast 通知——这些在回测闭环跑通后，作为 Phase 2.5（体验增强）再补。

预计 3-4 周交付稳定可用版。之后可根据实际使用反馈决定是否投入展示增强。

**不改变现有策略逻辑。所有接口必须有鉴权。优化结果必须区分样本内和样本外。优化参数不自动应用。**
