# 大盘/板块/个股支撑压力位与 MA30 补齐开发文档

状态：待实现  
目标日期：2026-06-01  
适用范围：后端计算层、API 输出层、前端展示层、回测/复盘口径

## 1. 目标

把当前平台里“支撑位 / 压力位 / 关键位 / 均线”能力补齐为统一能力，覆盖：

1. 大盘
2. 板块
3. 个股

同时补齐 30 日线能力，并把 5/10/20/30/60 日线做成统一输出口径。

## 2. 当前缺口

当前仓库已经具备：

- 个股层面的 MA5 / MA10 / MA20 / MA60
- 关键位、entry zone、support_distance_pct
- 大盘/板块的强弱、压力、情绪、买卖压力代理

缺失的是：

- MA30 的统一字段与计算链路
- 大盘/板块/个股三层统一的支撑位与压力位输出
- 支撑/压力位的产品化 schema
- 前端统一展示
- 统一测试与验收口径

## 3. 补齐范围

### 3.1 均线层

统一补齐：

- MA5
- MA10
- MA20
- MA30
- MA60

并补齐以下衍生字段：

- `close_to_ma5`
- `close_to_ma10`
- `close_to_ma20`
- `close_to_ma30`
- `close_to_ma60`
- `reclaim_ma5`
- `reclaim_ma10`
- `reclaim_ma20`
- `reclaim_ma30`
- `reclaim_ma60`
- `trend_above_ma30`
- `trend_above_ma60`
- `ma5_ma10_ma20_confluence_pct`

### 3.2 支撑/压力层

统一补齐：

- `support_price`
- `resistance_price`
- `support_distance_pct`
- `resistance_distance_pct`
- `support_level_type`
- `resistance_level_type`
- `support_strength`
- `resistance_strength`
- `key_level_candidates`

支持来源包括：

- 均线
- VWAP
- 前高 / 前低
- 平台高低点
- 昨收
- 整数关口
- 盘中关键位

### 3.3 三层对象

1. 大盘：指数 / 市场状态的支撑压力位
2. 板块：行业 / 主题的支撑压力位
3. 个股：股票本体的支撑压力位

### 3.4 前端展示

统一在以下页面展示：

- monitor
- analysis
- strategy tracking
- paper / review 相关页面

展示内容：

- 当前支撑位
- 当前压力位
- 距离支撑 / 压力的百分比
- MA30 状态
- MA5/10/20/30/60 状态
- 数据质量 / 是否可用

## 4. 不做什么

1. 不改策略核心逻辑
2. 不改生产排序逻辑
3. 不引入新依赖
4. 不换技术栈
5. 不引未来函数
6. 不把 `near_entry` 直接晋升为生产推荐
7. 不把观察池信号混进生产收益排行

## 5. 口径要求

1. 所有支撑 / 压力位必须只使用信号日及以前的数据
2. 数据不足时必须显式降级
3. 缺失时用 `no_data` / `research_only` / `blocked` 等明确状态
4. 不允许空值伪装成有效结论
5. 价格级支撑压力必须可追溯到具体规则来源

## 6. 后端修改建议

### 6.1 计算层

建议新增或扩展：

- `backend/app/services/low_buy/main_force_model_features.py`
- `backend/app/services/low_buy/candidate_metrics.py`
- `backend/app/services/intraday_key_levels.py`
- `backend/app/services/market/sectors.py`
- `backend/app/services/market/review.py`
- `backend/app/services/decision_context/intraday_entry.py`

### 6.2 schema 层

建议扩展：

- `backend/app/models/schema_defs/decision_context.py`
- `backend/app/models/schema_defs/market.py`
- `backend/app/models/schema_defs/common.py`
- 相关 screener / candidate schema

### 6.3 API 层

建议补齐：

- intraday key levels 输出
- decision context 输出
- market review 输出
- sector relative strength 输出

## 7. 前端修改建议

建议统一在前端展示：

- 当前支撑位 / 压力位
- MA30
- MA5/10/20/30/60 的站上 / 跌破状态
- key levels 列表
- 数据质量提示

优先页面：

- `frontend/src/features/monitor/MonitorPage.tsx`
- `frontend/src/features/analysis/*`
- `frontend/src/features/strategy-tracking/*`
- `frontend/src/features/paper/*`

## 8. 测试要求

必须补的测试：

1. MA30 计算测试
2. 支撑 / 压力位计算测试
3. 大盘 / 板块 / 个股三层输出测试
4. 缺数据降级测试
5. API schema 测试
6. 前端展示测试
7. 不引未来函数测试

## 9. 验收标准

1. MA30 在后端 schema 和 API 中可见
2. 大盘 / 板块 / 个股都有统一支撑 / 压力位输出
3. 前端能展示这些字段
4. 数据不足时清晰降级
5. 不影响现有策略逻辑和生产边界
6. 所有新增测试通过

## 10. 交付物

- 后端代码修改
- schema 修改
- API 修改
- 前端展示修改
- 测试
- 变更说明文档

