# TQuant 回测系统 Phase 2 需求文档

**日期**: 2026-05-05
**版本**: v1.0
**前置文档**: [v2 最终版需求文档](./TQuant回测闭环需求文档-v2-最终版-2026-05-05.md)、[v2 开发审查报告](./TQuant回测v2开发审查报告-2026-05-05.md)
**定位**: 独立 Phase 2 文档，覆盖 v2 文档 Phase 4-6 的完整实现 + 审查报告遗留修复 + 前端升级 + 实时推送

---

## 一、Phase 2 总目标

在 Phase 1-3 已完成的"提交 → 运行 → 持久化 → 查看净值曲线和交易明细"闭环基础上，将 TQuant 回测系统从**可用的验证工具**升级为**可量化的策略研究平台**。

四个核心能力：

1. **参数优化**——回答"某个策略的参数调到多少最赚钱"
2. **样本外验证**——回答"这个收益在样本外还能赚吗，还是过拟合"
3. **多维归因**——回答"收益从哪里来，哪个策略/行业/市场状态贡献最大"
4. **实时交互**——回答"回测跑到哪了"（不靠轮询猜），多组回测放在一起比

---

## 二、当前状态评估（Phase 2 起点）

### 2.1 v2 审查报告遗留问题

经逐文件确认当前代码，审查报告中 10 个问题的状态如下：

| # | 问题 | 审查时状态 | 当前状态 |
|---|------|-----------|---------|
| 1 | `RealizedTrade` 缺 `holding_days` 字段 | Critical Bug | **已修复** |
| 2 | `fee_amount` 仅含卖出费用 | High Bug | **已修复**（`RealizedTrade.fee_amount` 现包含完整费用） |
| 3 | `requested_price` 错误赋值为 `fill_price` | Medium Bug | **已改进**（优先读取 `order.requested_price`） |
| 4 | analyzer 缺 Sortino/Calmar/基准指标 | High | **已实现**（analyzer.py 第 37-41 行） |
| 5 | broker 涨跌停阈值硬编码 9.8% | High | **仍存在**（broker.py 第 131-136 行） |
| 6 | engine `_dedupe_signals` 同分非确定性 | Medium | **已修复**（现用 `(score, strategy_key)` 元组比较） |
| 7 | daemon 线程 + 无超时检测 | Medium | **仍存在**（backtest_job_service.py 第 204 行） |
| 8 | `result_json` 整存 JSON blob | Medium | **仍存在**（persistence.py 第 158 行） |
| 9 | reporter.py 死代码 | Low | **仍存在** |
| 10 | `dataclass_list` 死代码 | Low | **仍存在**（analyzer.py 第 183 行） |

Phase 2 需修复上述 5 个仍存在的问题（#5、#7、#8、#9、#10），#5 和 #7 为 P0。

### 2.2 已完成的能力（Phase 1-3 交付物）

- 事件驱动日线回测引擎（5 种执行模型、多策略资金竞争、止损止盈、强平）
- 投资组合状态机（FIFO 多 lot 持仓、T+1/ETF T+0）
- 数据提供层（PIT 数据、质量报告、ST 过滤）
- 绩效分析器（13 个核心指标 + 逐策略拆解 + Sortino/Calmar/IR）
- 异步任务管理（提交/取消/状态轮询/权限控制）
- 前端看板（表单提交、任务列表、8 指标卡片、SVG 净值曲线、交易明细表）
- 5 张回测结果表（运行/订单/成交/每日快照/数据质量）+ manifest 表
- 版本记录五元组（code/strategy/fee/data/engine）

### 2.3 optimizer / validator 骨架状态

- `optimizer.py`（49 行）：grid_search 骨架，`max_runs=20` 硬上限，无 OOS 验证
- `validator.py`（63 行）：walk_forward 骨架，需手动传入窗口列表，无 PBO 计算

这两个模块是 Phase 2 的核心升级对象。

---

## 三、Phase 2 功能详规

### 3.1 遗留 Bug 修复（P0）

#### 3.1.1 broker 涨跌停阈值按板块区分

当前 `_is_limit_up` 和 `_is_limit_down` 硬编码 `>= 9.8` / `<= -9.8`，不区分板块：

```python
def _is_limit_up(bar: DailyBar) -> bool:
    return float(bar.pct_chg or 0) >= 9.8
```

修复为按 symbol 前缀判断：

| 前缀 | 板块 | 涨跌幅限制 |
|------|------|-----------|
| 68xxxx | 科创板 | ±20% |
| 30xxxx / 301xxx | 创业板 | ±20% |
| 4xxxxx / 8xxxxx | 北交所 | ±30% |
| 其他（00/60） | 主板 | ±10% |

ST 股票为 ±5%（与 `_is_st_signal` 判断联动）。

同时修正 broker 第 77-78 行的 `up_limit` / `down_limit` 传入值——当前传入的是 `selected_price`，应改为基于昨日收盘价计算的真实涨跌停价：

```python
# 修正前
up_limit=to_decimal(selected_price) if _is_limit_up(request.bar) else None

# 修正后
up_limit=to_decimal(bar.pre_close * (1 + limit_pct)) if _is_limit_up(request.bar) else None
```

这需要 `DailyBar` 提供 `pre_close` 字段（当前 data_provider.py 已从 DB 读取 `pre_close`，需确认 bar 中是否包含）。

#### 3.1.2 回测线程改为非 daemon + 超时检测

当前 `backtest_job_service.py` 第 204 行 `daemon=True`，服务器关闭时回测线程被强制终止，中途持久化可能丢失。

修复：
- 改为 `daemon=False`，服务器关闭时等待回测线程完成（需配合 `atexit` 注册的 graceful shutdown）
- 添加 `max_duration_seconds` 参数（默认 1800 = 30 分钟），超时自动设置 cancel token
- 超时后 `status = 'timeout'`（新增状态值），区别于用户主动取消

```python
# backtest_runs 表新增 status 值: 'timeout'
# 超时检测逻辑
def _execute_run(cls, run_id, cancel_token):
    start = time.monotonic()
    # ... 引擎循环中
    if time.monotonic() - start > max_duration:
        cancel_token.cancel()
        run.status = 'timeout'
```

#### 3.1.3 result_json 瘦身

当前 `persistence.py` 第 158 行将完整 `BacktestResult.to_dict()`（含净值曲线、全部订单、全部成交）写入 `result_json` 字段，与 `backtest_daily_snapshots` 和 `backtest_trades` 表重复。

修复：
- `result_json` 仅保留 `metrics` + `config` + `data_quality` + `dataset_manifest`（不含 `equity_curve` 数组、`orders` 数组、`trades` 数组）
- 净值曲线数据从 `backtest_daily_snapshots` 表读取
- 成交数据从 `backtest_trades` 表读取

#### 3.1.4 删除死代码

- 删除 `reporter.py`（45 行），或将其接入 `BacktestJobService._detail` 替代直接读 `result_json`
- 删除 `analyzer.py` 第 183-184 行的 `dataclass_list` 函数

---

### 3.2 参数优化器（Phase 4 完整实现）

#### 3.2.1 功能概述

从骨架升级为完整的参数优化系统，回答"某个策略的参数调到多少在样本内表现最好，且这个最优解在样本外是否依然有效"。

#### 3.2.2 搜索算法

**默认：网格搜索（Grid Search）**

- 用户指定每个参数的取值列表，系统穷举所有组合
- 参数空间 ≤ 500 组合时使用网格搜索
- 超过 500 组合时自动降级为随机搜索（Random Search），并记录 `search_method: "random"` 到结果中

**不做：贝叶斯优化**（v2 裁定暂缓，避免引入 scikit-optimize 依赖和调参挖矿风险）

#### 3.2.3 可优化参数清单

仅允许优化以下参数（v2 裁定约束）：

| 参数 | 类型 | 说明 | 默认搜索范围 |
|------|------|------|-------------|
| `min_score` | int | 信号最低分 | [70, 75, 80, 85, 90] |
| `max_position_pct` | float | 单票最大仓位 | [0.15, 0.20, 0.25, 0.30] |
| `max_holding_days` | int | 最大持仓天数 | [3, 5, 7, 10, 14] |
| `stop_loss_pct` | float | 止损比例 | [-0.03, -0.05, -0.07, -0.10] |
| `take_profit_pct` | float | 止盈比例 | [0.05, 0.10, 0.15, 0.20] |

不允许修改策略核心逻辑参数（如 `board_count`、`volume_burst_ratio`、`consecutive_count`）。

#### 3.2.4 强制样本外验证

**硬性约束：参数优化必须伴随样本外验证。**

流程：
1. 用户指定总日期范围（如 2024-01-02 至 2026-04-30）
2. 系统自动切分：前 80% 为样本内（训练），后 20% 为样本外（验证）
3. 在样本内对每种参数组合运行回测
4. 取样本内最优参数（默认按 Sharpe 排序），在样本外窗口独立运行一次
5. 对比样本内 vs 样本外的绩效差距

若样本外 Sharpe < 0 或样本外收益下降超过 50%，标记为 `oos_downgrade: true`，前端红色警告。

#### 3.2.5 优化结果持久化

新建表：

```sql
CREATE TABLE backtest_optimizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    name TEXT NOT NULL,
    strategy TEXT NOT NULL,              -- 被优化的策略
    param_grid_json TEXT NOT NULL,       -- 搜索空间
    search_method TEXT NOT NULL,         -- grid | random
    status TEXT NOT NULL DEFAULT 'pending',
    -- 样本内最优
    best_params_json TEXT,
    best_score REAL,                     -- 优化目标值（默认 Sharpe）
    best_metrics_json TEXT,              -- 最优参数的完整指标
    -- 样本外验证
    oos_score REAL,
    oos_metrics_json TEXT,
    oos_downgrade BOOLEAN DEFAULT 0,     -- 是否触发样本外降级
    oos_downgrade_reason TEXT,
    -- 全部候选结果
    candidates_json TEXT,                -- 所有参数组合的得分列表（压缩）
    -- 元信息
    train_date_range TEXT,
    test_date_range TEXT,
    total_runs INTEGER,
    duration_seconds REAL,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### 3.2.6 权限与速率限制

- 参数优化需**管理员权限或白名单用户**
- 优化结果**不自动应用**到生产策略配置，需人工审核后手动修改
- 全局同时最多 1 个优化任务运行

#### 3.2.7 API

```
POST /api/backtests/optimize
```

请求体：

```json
{
  "name": "first_board 参数优化",
  "strategy": "first_board",
  "train_start": "2024-01-02",
  "train_end": "2025-12-31",
  "test_start": "2026-01-02",
  "test_end": "2026-04-30",
  "param_grid": {
    "min_score": [70, 75, 80, 85, 90],
    "max_holding_days": [3, 5, 7, 10, 14],
    "stop_loss_pct": [-0.03, -0.05, -0.07]
  },
  "optimization_target": "sharpe",
  "initial_capital": 500000,
  "execution_model": "open_price"
}
```

响应：

```json
{
  "optimization_id": 15,
  "status": "pending",
  "total_combinations": 60,
  "message": "参数优化任务已提交，预计 60 组回测。"
}
```

```
GET /api/backtests/optimize/{optimization_id}  ← 优化详情
GET /api/backtests/optimize                    ← 优化任务列表（分页）
DELETE /api/backtests/optimize/{id}            ← 删除优化记录
```

---

### 3.3 Walk-Forward 验证器（Phase 5 完整实现）

#### 3.3.1 功能概述

从骨架升级为自动化的样本外稳健性测试。对给定策略在滚动时间窗口上重复"训练→验证"，输出样本外绩效汇总。

#### 3.3.2 窗口生成

用户指定总日期范围后，系统自动生成滚动窗口：

- 默认窗口数 = 4
- 训练窗口 = 总区间的 75%（约 18 个月）
- 测试窗口 = 总区间的 25%（约 6 个月）
- 窗口步长 = 测试窗口长度

示例（总区间 2024-01-02 至 2026-04-30）：

| 窗口 | 训练期 | 测试期 |
|------|--------|--------|
| 1 | 2024-01-02 → 2025-07-01 | 2025-07-02 → 2026-01-02 |
| 2 | 2024-07-02 → 2026-01-02 | 2026-01-05 → 2026-04-30（不足 6 月按实际） |

窗口数和切分比例可配置（`window_count=4`、`train_ratio=0.75`）。

#### 3.3.3 每窗口流程

1. 训练期：运行参数优化（网格搜索），得到最优参数
2. 测试期：用最优参数运行一次回测
3. 记录：训练期 Sharpe、测试期 Sharpe、参数集

#### 3.3.4 PBO（Probability of Backtest Overfitting）

实现简化版 PBO 计算（不引入完整的组合交叉验证）：

对每个窗口，对比样本内排名和样本外排名。如果样本内最优的参数组合在样本外排名大幅下滑（跌出前 30%），标记为过拟合信号。

```python
# 简化 PBO 逻辑
def compute_pbo_risk(oos_ranks: list[int], total_combinations: int) -> str:
    """oos_ranks: 每个窗口最优参数的样本外排名（1 = 最好）"""
    avg_oos_rank = sum(oos_ranks) / len(oos_ranks)
    rank_pct = avg_oos_rank / total_combinations
    if rank_pct > 0.7:
        return "high"      # 样本内最优在样本外排到后 30% = 严重过拟合
    elif rank_pct > 0.4:
        return "medium"
    return "low"
```

#### 3.3.5 策略降级标记

若验证中任一样本外窗口的 Sharpe < 0：
- 策略标记为 `downgrade_review_required`
- 前端显示红色提示："该策略在样本外验证中表现不佳，建议暂缓实盘应用"

#### 3.3.6 持久化

```sql
CREATE TABLE backtest_validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    name TEXT NOT NULL,
    strategy TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    config_json TEXT NOT NULL,           -- 验证配置（窗口数、切分比例等）
    -- 汇总
    window_count INTEGER,
    oos_pass_rate REAL,                  -- 样本外通过率
    avg_oos_sharpe REAL,
    avg_is_sharpe REAL,
    pbo_risk TEXT,                       -- low | medium | high
    downgrade_review BOOLEAN DEFAULT 0,
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

#### 3.3.7 API

```
POST /api/backtests/validate
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

```
GET /api/backtests/validate/{validation_id}  ← 验证详情
GET /api/backtests/validate                  ← 验证任务列表（分页）
```

---

### 3.4 多维归因（Phase 3 剩余 + Phase 6）

#### 3.4.1 行业归因

当前 analyzer.py 的 `_by_strategy` 只做策略维度拆解，缺行业维度。

实现：
- 按申万一级行业对每笔成交的收益进行分组汇总
- 输出：每个行业的交易次数、净收益、胜率、贡献度（该行业收益 / 总收益）
- 前端展示：行业归因表（条形图或表格）

行业分类数据来源：
1. 项目中已有 `industry.py` 或相关行业分类文件（需确认）
2. 或在回测数据准备阶段，从 akshare `stock_industry_clf_hist_sw` 查询历史行业归属

**重要约束**：行业分类可能存在历史偏差（标的被重新分类），报告中必须标注。

#### 3.4.2 市场状态归因

按 8 类市场状态（来自 `market_state` 服务）对每笔交易的收益进行分组：

- 输出：每种市场状态下的交易次数、胜率、平均收益、累计收益
- 前端展示：市场状态归因表

数据来源：回测期间每日的市场状态标签（项目已有 `market_state` 判断逻辑）。

实现方式：在 `engine.py` 主循环中，每交易日记录当前市场状态，存入 `PortfolioSnapshot`。analyzer 在分析时按市场状态聚合。

#### 3.4.3 数据质量分桶归因

按数据质量报告中的指标将回测区间分为高/中/低质量区间：

- 高质量：缺失率 < 1%、零价异常 < 5 条
- 中等质量：缺失率 1-3%
- 低质量：缺失率 > 3% 或零价异常 > 10 条

对每个分桶的收益表现进行独立统计，帮助用户判断"这段回测数据的可信度"。

#### 3.4.4 策略相关性矩阵（Phase 6）

对多策略联合回测的输出，计算策略间收益相关性矩阵：

```python
# 对每个策略的每日收益序列，计算 Pearson 相关系数
corr_matrix = {
    "first_board": {"first_board": 1.0, "volume_shrink": 0.32, ...},
    "volume_shrink": {"first_board": 0.32, "volume_shrink": 1.0, ...},
}
```

前端以热力图展示，帮助用户判断策略组合的分散化程度。

---

### 3.5 多组回测对比

#### 3.5.1 功能概述

允许用户选择多组已完成回测，在同一视图中对比关键指标。

#### 3.5.2 API

```
POST /api/backtests/compare
```

请求体：

```json
{
  "run_ids": [42, 45, 47]
}
```

响应：

```json
{
  "runs": [
    {
      "id": 42,
      "name": "...",
      "metrics": { ... },
      "equity_points": [...]
    }
  ],
  "comparison_table": {
    "columns": ["total_return_pct", "sharpe", "max_drawdown_pct", "win_rate_pct", "trade_count"],
    "rows": [...]
  }
}
```

前端展示：多线净值曲线叠加图 + 指标对比表格。

---

### 3.6 前端升级

#### 3.6.1 净值曲线升级为 ECharts

当前 SVG 轻量图（`EquityMiniChart`）替换为 ECharts 实现的交互式图表：

- **多线叠加**：策略净值 + 基准净值 + 回撤填充区域
- **缩放与平移**：dataZoom 组件，可拖拽选择时间范围
- **Tooltip**：悬停显示日期、净值、日收益率、回撤
- **买卖点标注**：在净值曲线上标记买入/卖出点（markPoint）
- **回撤区域**：净值曲线下方用半透明红色填充回撤区域

项目已有 ECharts 依赖（`LazyKlineChart.tsx` 使用），无需新增依赖。

技术方案：
- 新建 `EquityChart.tsx` 组件（约 200 行），使用 `echarts-for-react` 或直接操作 ECharts 实例
- 保留 `EquityMiniChart` 作为 loading 态或小屏降级方案

#### 3.6.2 月度收益热力图

新建 `MonthlyReturnHeatmap.tsx`：

- X 轴 = 年份、Y 轴 = 月份、颜色 = 收益率（红赚绿亏）
- 数据来源：从 `BacktestDailySnapshot` 计算月度收益
- 新增 API：`GET /api/backtests/{run_id}/monthly-returns`

#### 3.6.3 收益分布直方图

新建 `ReturnDistributionChart.tsx`：

- 单笔交易收益率的分布直方图
- 叠加正态分布拟合曲线
- 标注均值、中位数、偏度

#### 3.6.4 策略拆解对比表

升级当前 8 指标卡片为可展开的策略拆解对比表：

- 行 = 策略、列 = 指标（交易数、净收益、胜率、Sharpe、贡献度）
- 支持按指标排序
- 胜率 < 50% 的策略行标灰

#### 3.6.5 优化/验证结果视图

- 优化结果页：参数组合排名表、最优参数 vs 默认参数对比、样本内 vs 样本外对比
- 验证结果页：窗口卡片组（每窗口一卡片，显示训练/测试 Sharpe）、PBO 风险评级

#### 3.6.6 全局 loading 与 toast 通知

- 提交优化/验证任务后 toast 提示"任务已提交"
- 任务完成时 toast 提示"优化完成，样本外 Sharpe: X.XX"
- 样本外降级时 toast 红色警告

---

### 3.7 实时进度推送（WebSocket）

#### 3.7.1 问题

当前前端通过轮询更新任务状态和进度。优化和验证任务耗时更长（可能需要 5-30 分钟），轮询体验差。

#### 3.7.2 方案

使用 FastAPI 原生 WebSocket 支持，建立轻量级进度推送通道：

```
WebSocket /ws/backtest/{run_id}          ← 单个回测的进度推送
WebSocket /ws/backtest/optimize/{id}     ← 优化任务的进度推送
WebSocket /ws/backtest/validate/{id}     ← 验证任务的进度推送
```

推送消息格式：

```json
{
  "type": "progress",
  "run_id": 42,
  "progress_pct": 35.0,
  "message": "回测进行中: 2025-08-15 (156/480 交易日)",
  "timestamp": "2026-05-05T14:30:00"
}
```

```json
{
  "type": "completed",
  "run_id": 42,
  "status": "completed",
  "message": "回测完成，总收益 +12.35%"
}
```

```json
{
  "type": "error",
  "run_id": 42,
  "status": "failed",
  "message": "数据不足：回测区间内无有效交易日"
}
```

实现要点：
- WebSocket 端点需认证（从 query param 传递 token 或利用已有 cookie session）
- engine 循环中通过回调函数推送进度（每 N 个交易日推送一次，默认每 10 个交易日）
- 前端使用 `useEffect` + `useRef` 管理 WebSocket 生命周期
- 连接断开时自动重连（exponential backoff，最大 5 次）
- WebSocket 仅推送进度事件，不影响回测结果的持久化（结果仍通过 REST API 获取）

---

## 四、API 扩展总览

```
# 已有（Phase 1-3）
POST   /api/backtests                    ← 提交回测
GET    /api/backtests                    ← 回测列表
GET    /api/backtests/{run_id}           ← 回测详情
GET    /api/backtests/{run_id}/equity    ← 净值曲线
GET    /api/backtests/{run_id}/trades    ← 交易明细
POST   /api/backtests/{run_id}/cancel    ← 取消回测
DELETE /api/backtests/{run_id}           ← 删除回测

# Phase 2 新增
POST   /api/backtests/compare            ← 多组回测对比
POST   /api/backtests/optimize           ← 参数优化（需管理员）
GET    /api/backtests/optimize           ← 优化任务列表
GET    /api/backtests/optimize/{id}      ← 优化详情
DELETE /api/backtests/optimize/{id}      ← 删除优化记录
POST   /api/backtests/validate           ← Walk-Forward 验证
GET    /api/backtests/validate           ← 验证任务列表
GET    /api/backtests/validate/{id}      ← 验证详情
GET    /api/backtests/{run_id}/monthly-returns   ← 月度收益
GET    /api/backtests/{run_id}/attribution       ← 归因数据（行业+市场状态+质量分桶）

# WebSocket
WS     /ws/backtest/{run_id}             ← 回测进度推送
WS     /ws/backtest/optimize/{id}        ← 优化进度推送
WS     /ws/backtest/validate/{id}        ← 验证进度推送
```

---

## 五、数据库新增/变更

### 5.1 新增表

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
    best_params_json TEXT,
    best_is_score REAL,
    best_is_metrics_json TEXT,
    best_oos_score REAL,
    best_oos_metrics_json TEXT,
    oos_downgrade INTEGER DEFAULT 0,
    oos_downgrade_reason TEXT,
    candidates_json TEXT,
    train_date_range TEXT,
    test_date_range TEXT,
    total_runs INTEGER NOT NULL DEFAULT 0,
    completed_runs INTEGER NOT NULL DEFAULT 0,
    base_config_json TEXT,
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
    config_json TEXT NOT NULL,
    window_count INTEGER,
    oos_pass_rate REAL,
    avg_oos_sharpe REAL,
    avg_is_sharpe REAL,
    pbo_risk TEXT,
    downgrade_review INTEGER DEFAULT 0,
    windows_json TEXT,
    duration_seconds REAL,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 5.2 变更已有表

```sql
-- backtest_runs 新增字段
ALTER TABLE backtest_runs ADD COLUMN timeout_seconds INTEGER DEFAULT 1800;
ALTER TABLE backtest_runs ADD COLUMN optimization_id INTEGER REFERENCES backtest_optimizations(id);
ALTER TABLE backtest_runs ADD COLUMN validation_id INTEGER REFERENCES backtest_validations(id);

-- backtest_daily_snapshots 新增字段（市场状态归因用）
ALTER TABLE backtest_daily_snapshots ADD COLUMN market_state TEXT;
ALTER TABLE backtest_daily_snapshots ADD COLUMN quality_bucket TEXT;

-- backtest_trades 新增字段（行业归因用）
ALTER TABLE backtest_trades ADD COLUMN sector TEXT;
ALTER TABLE backtest_trades ADD COLUMN market_state TEXT;
```

### 5.3 status 枚举扩展

`backtest_runs.status` 新增值：
- `timeout` — 超时终止

---

## 六、实施路线（Phase 2 内部阶段）

### Phase 2-A：Bug 修复 + 基础升级（1 周）

- [ ] broker 涨跌停阈值按板块区分（P0）
- [ ] 回测线程改非 daemon + 超时检测（P0）
- [ ] result_json 瘦身
- [ ] 删除 reporter.py 和 dataclass_list 死代码
- [ ] WebSocket 进度推送基础设施
- [ ] 前端接入 WebSocket（替换详情页轮询）

### Phase 2-B：归因补齐（1 周）

- [ ] 行业归因（`_by_sector`）
- [ ] 市场状态归因（`_by_market_state`）
- [ ] 数据质量分桶归因
- [ ] `GET /api/backtests/{run_id}/attribution` API
- [ ] 前端归因面板（行业表 + 市场状态表 + 质量分桶）

### Phase 2-C：优化器（2 周）

- [ ] optimizer.py 从骨架升级（自动 OOS 切分、候选排序、结果持久化）
- [ ] POST/GET /api/backtests/optimize 端点
- [ ] 优化任务异步执行 + 进度推送
- [ ] 优化结果页（参数排名表 + IS vs OOS 对比 + 降级警告）
- [ ] 管理员权限控制

### Phase 2-D：验证器（1.5 周）

- [ ] validator.py 从骨架升级（自动窗口生成、PBO 计算、降级标记）
- [ ] POST/GET /api/backtests/validate 端点
- [ ] 验证任务异步执行 + 进度推送
- [ ] 验证结果页（窗口卡片组 + PBO 评级）

### Phase 2-E：对比 + 前端图表升级（1.5 周）

- [ ] 多组回测对比 API + 前端对比视图
- [ ] ECharts 净值曲线（多线叠加、缩放、tooltip、买卖点、回撤填充）
- [ ] 月度收益热力图
- [ ] 收益分布直方图
- [ ] 策略拆解对比表（可排序）
- [ ] BACKTEST_STRATEGY_CORRELATION（相关性矩阵）

### Phase 2-F：收尾（0.5 周）

- [ ] 前端 toast 通知系统
- [ ] 全局 loading 状态优化
- [ ] 端到端测试（优化 + 验证 + 归因 + 对比完整链路）
- [ ] 数据分析：first_board 策略 2024-2026 完整参数优化 + Walk-Forward 验证

---

## 七、技术约束与注意事项

### 7.1 不引入新依赖

- **后端**：不新增 pip 依赖。所有计算使用标准库 + 已有依赖（scipy 可用于相关性矩阵，如项目已有）
- **前端**：ECharts 已在 package.json 中，不新增依赖

### 7.2 性能目标

- 单策略 2 年回测：≤ 3 分钟（与 Phase 1 一致）
- 60 组参数的网格搜索（含样本外验证）：≤ 3 小时
- 4 窗口 Walk-Forward 验证：≤ 1.5 小时
- 优化/验证任务并发上限：全局 1 个

### 7.3 过拟合防护（重申）

- 参数优化**必须**伴随样本外验证，不做纯样本内优化
- 优化结果**不自动应用**到生产策略
- 样本外降级时前端红色警告，不可忽略
- PBO 标记为 "high" 的策略需人工 review 后才能用于实盘

### 7.4 复用优先

- 优化器和验证器内部复用 `BacktestEngine.run()`，不重写回测逻辑
- 归因数据从已有成交和快照表读取，不重新计算
- WebSocket 复用 FastAPI 原生支持，不引入 Socket.IO 或第三方库

---

## 八、验收标准

### Phase 2-A 验收

1. broker 对科创板（68 开头）使用 ±20% 涨跌停判断，主板（60 开头）使用 ±10%
2. 回测超时 5 分钟后自动标记 timeout（测试用短超时）
3. result_json 不再包含 equity_curve 数组（大小下降 > 80%）
4. reporter.py 已删除或已接入

### Phase 2-B 验收

1. first_board 策略回测结果中显示行业分布（至少 3 个行业的收益贡献）
2. 市场状态归因表显示至少 3 种状态的胜率差异
3. 数据质量分桶标注"高质量区间收益 +X%，低质量区间收益 -Y%"

### Phase 2-C 验收

1. 对 first_board 的 min_score + max_holding_days 做 5×5=25 组网格搜索，15 分钟内完成
2. 优化结果页显示样本内 vs 样本外 Sharpe 对比
3. 若样本外 Sharpe < 0，前端显示红色降级警告
4. 非管理员调用 optimize 端点返回 403

### Phase 2-D 验收

1. 对 first_board 做 4 窗口 Walk-Forward 验证，输出每窗口训练/测试 Sharpe
2. PBO 风险评级计算正确（可手工验证）
3. 样本外窗口全部 Sharpe < 0 的策略标记 downgrade_review

### Phase 2-E 验收

1. 净值曲线支持缩放/平移/tooltip，显示买卖点标记
2. 月度热力图显示完整回测期间的月度收益颜色矩阵
3. 收益分布直方图叠加正态拟合曲线
4. 策略拆解表可点击列头排序

### Phase 2-F 验收（完整链路）

1. first_board 策略完成：参数优化 → 最优参数样本外验证 → Walk-Forward 验证 → 归因分析
2. 全链路数据一致：优化结果中的回测 run_id 可跳转到独立回测详情页
3. WebSocket 进度推送延迟 < 3 秒

---

## 九、不做清单

以下功能明确不在 Phase 2 范围：

1. **分钟级回测**——Phase 2 仍为日线级。分钟级留待 Phase 3+
2. **多策略联合参数优化**——先做单策略优化跑通方法论，联合优化留待 Phase 3+
3. **Fama-French 因子归因**——v2 明确移除，A 股短线低吸平台价值有限
4. **贝叶斯优化**——暂缓，v2 裁定
5. **HTML/Markdown 报告导出**——JSON + 前端优先
6. **自动化参数应用到生产**——人工审核是硬约束
7. **实时行情数据接入回测**——回测仅用历史 PIT 数据

---

## 十、结论

Phase 2 将 TQuant 回测系统从"能跑通的验证链"升级为"能回答策略质量问题的研究平台"。核心交付物：

- **参数优化器**：让用户知道"参数调到多少最好"，且强制样本外验证防止自欺欺人
- **Walk-Forward 验证器**：让用户知道"这个策略在没见过的新数据上还能赚吗"
- **多维归因**：让用户知道"收益从哪里来，哪个策略在哪种市场状态下有效"
- **前端图表升级**：让用户能用交互式图表探索数据，而非被动看静态 SVG
- **WebSocket 实时推送**：让用户知道回测跑哪了，不用反复点刷新

预计总工期 7.5 周。全部完成后，TQuant 的策略研究能力将从"人工看回测结果"升级为"系统自动搜索最优参数 + 自动验证稳健性 + 自动归因收益来源"。

Phase 2 不追求多策略联合优化、分钟级回测或因子模型——这些是方法论上的深水区，应在单策略优化和验证方法论跑通后再考虑。
