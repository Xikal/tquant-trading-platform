# A股短线做T量化 Web 应用 - 开发文档

## 1. 目录结构（规划）

```text
.
├── backend
│   ├── app
│   │   ├── api
│   │   ├── core
│   │   ├── models
│   │   ├── services
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend
│   ├── src
│   │   ├── api
│   │   ├── components
│   │   ├── pages
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── PROJECT_PLAN.md
└── DEVELOPMENT_GUIDE.md
```

## 2. 后端设计说明

## 2.1 配置

配置分两层：

1. 启动级配置（环境变量）
- `DATABASE_URL`（默认 SQLite）
- `CORS_ORIGINS`

2. 运行级配置（数据库持久化）
- `llm_api_key`
- `llm_base_url`
- `llm_model`
- `data_source`
- `data_source_base_url`
- `database_url`（用于展示和后续切换提示）
- `strategy_min_amount_stock`
- `strategy_min_amount_etf`
- `strategy_min_amplitude_pct`
- `strategy_max_amplitude_pct`
- `strategy_max_atr_pct`
- `strategy_open_phase_min_tradability`
- `strategy_slippage_stock_bps`
- `strategy_slippage_etf_bps`

说明：
- 若在线修改 `database_url`，提示“重启后生效”。

## 2.2 数据源抽象

定义统一接口：

- `search_instruments(keyword, kind)`
- `sync_instruments(kind)`
- `get_realtime_quote(symbol)`
- `get_intraday_kline(symbol, period, limit)`
- `get_sector_snapshot(symbol)`
- `get_market_events(symbol)`
- `get_trading_rules(symbol)`
- `get_microstructure(symbol)`（可选增强）

默认实现为免费 A 股接口适配器，后续新增数据源时只需实现同一接口并注册。

数据源分层：

1. `base`
- 必须支持标的、实时行情、K线

2. `enhanced`
- 板块强度
- 事件风险
- ETF / 品种交易制度

3. `premium_optional`
- 逐笔
- 五档盘口
- 大单流向

说明：
- 即使用户只使用免费数据源，系统也必须可运行。
- 当增强字段不可用时，相关模块自动降级而不是报错。

## 2.3 交易制度识别引擎

系统必须先判断“能不能这样做T”，再判断“怎么做T”。

输出字段建议：
- `instrument_type`
- `market`
- `turnaround_mode`: `t0` / `t1`
- `supports_positive_t`
- `supports_negative_t`
- `same_day_sell_allowed`
- `notes`

用途：
- 股票默认按 T+1 约束处理
- ETF 依据类别与交易制度差异化处理
- 在不允许的制度下，禁止输出不合规的日内建议

## 2.4 做T量化引擎

输入：
- 最新行情（现价、涨跌幅、成交量、日内高低）
- 分时/K线（1m、5m、15m、日线）
- 板块/指数相对强弱
- 可用事件与微结构数据

核心指标：
- MA5 / MA20
- RSI(14)
- MACD(12,26,9)
- VWAP 偏离
- 日内振幅
- 量比
- OBV
- ATR
- 相对板块强弱
- 成本与滑点估算

策略输出字段：
- `action`: `positive_t` / `negative_t` / `hold`
- `entry_price`
- `exit_price`
- `position_pct`
- `stop_loss`
- `risk_level`
- `signal_score`
- `tradability_score`
- `reasons`
- `blocking_rules`

策略要点：
- 第一步：可交易性过滤
- 第二步：交易制度校验
- 第三步：多周期共振判断
- 第四步：分时场景识别
- 第五步：板块联动、成本、事件风控修正
- 正T（先买后卖）：趋势未坏 + 回踩信号
- 反T（先卖后买）：短线过热/冲高 + 回落预期
- 风险高时降仓位并放大止损安全边界
- 若制度或风控不允许，强制返回 `hold`

建议拆分成以下子模块：

1. `tradability_filter`
- 过滤低成交额、低振幅、高点差、低流动性标的

2. `multi_timeframe_engine`
- 同时分析 1m / 5m / 15m / 日线方向

3. `intraday_pattern_engine`
- 识别开盘冲高、开盘回踩、午后回流、尾盘博弈等场景

4. `vwap_volume_engine`
- 判断价格偏离 VWAP 是否具有均值回归或趋势延续意义

5. `sector_linkage_engine`
- 分析个股与行业、指数的同步性

6. `risk_overlay_engine`
- 动态仓位、止损、成本、滑点、事件、纪律风控

## 2.5 AI 增强模块

流程：
1. 量化引擎先输出基础建议
2. 拼接结构化上下文给大模型
3. 要求模型返回 JSON（动作、置信度、风险补充、解释）
4. 与量化建议融合（低置信度不覆盖核心风控）
5. 将结果写入复盘记录

容错：
- 未配置 Key/Model：返回 `ai_enabled = false`，仅量化建议
- API 请求失败：自动降级，给出错误提示但不中断分析

AI 额外职责：
- 解释为什么适合或不适合做T
- 从复盘样本中总结高胜率场景
- 给出执行提醒而不是直接替代风控规则

## 2.6 风控与研究模块

### 动态仓位

建议综合以下因子：
- 信号质量分
- 风险等级
- 日内波动率
- 预计滑点
- 当日已实现盈亏

### 纪律控制

系统级规则建议：
- 单笔最大风险限制
- 单日最大亏损限制
- 连续亏损 N 次暂停
- 高波动异常阶段暂停

### 回测与 Walk-forward

至少支持：
- 参数化回测
- 信号日志导出
- 滚动窗口样本外验证
- 胜率、盈亏比、最大回撤、收益曲线

## 2.7 API 规范（建议）

### 市场数据

- `GET /api/instruments?keyword=&kind=all&page=1&page_size=50`
- `POST /api/instruments/sync`
- `GET /api/quote/{symbol}`
- `GET /api/kline/{symbol}?period=1m&limit=240`
- `GET /api/instruments/{symbol}/rules`
- `GET /api/instruments/{symbol}/sector`
- `GET /api/instruments/{symbol}/events`

### 自选池

- `GET /api/watchlist`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{symbol}`
- `GET /api/watchlist/quotes`
- `GET /api/watchlist/signals`

### 分析

- `POST /api/analyze`
- `POST /api/analyze/batch`

请求示例：

```json
{
  "symbol": "600519",
  "prefer_strategy": "auto",
  "include_events": true,
  "include_ai": true
}
```

响应建议附加：
- `regime_check`
- `sector_strength`
- `event_risks`
- `cost_estimate`
- `discipline_state`

### 系统配置

- `GET /api/settings`
- `PUT /api/settings`

### 研究与复盘

- `GET /api/replays`
- `GET /api/replays/{id}`
- `POST /api/backtests`
- `GET /api/backtests/{id}`

## 3. 前端设计说明

## 3.1 页面结构

1. 监控面板（Watchlist）
- 实时表格（代码、名称、现价、涨跌幅、信号、风险）
- 展示交易制度、信号质量分、是否适合做T
- 添加/删除自选
- 定时刷新（如 3~5 秒）

2. 分析页（Analysis）
- 代码搜索与切换
- ECharts 图表（K线 + 均线 + 成交量）
- 量化建议卡片（正T/反T、点位、仓位、止损）
- 多周期共振区
- 板块联动区
- 交易制度与成本提示
- 事件风险卡片
- AI 解释区（结论 + 风险提醒）

3. 配置页（Settings）
- LLM 配置：API Key、Base URL、Model
- DB 配置：Database URL
- 数据源配置：数据源类型 + 接口地址
- 风控配置：最大单笔风险、最大日内亏损、连亏熔断

4. 研究页（Research）
- 信号日志
- 复盘记录
- 胜率/盈亏比/回撤统计
- 回测结果展示

## 3.2 前端工程约束

- TypeScript 类型完整
- API 请求统一封装
- 错误态/空态必须可见
- 图表刷新与轮询分离，避免重复渲染
- 图表区域需同时支持分时与 K 线切换
- 复杂卡片需支持“降级提示”，例如盘口数据不可用时显示原因

## 4. 数据库设计（初版）

## 4.1 instruments

- `id` INTEGER PK
- `symbol` TEXT UNIQUE INDEX
- `name` TEXT
- `market` TEXT
- `instrument_type` TEXT (`stock` / `etf`)
- `updated_at` DATETIME

## 4.2 instrument_rules

- `id` INTEGER PK
- `symbol` TEXT UNIQUE INDEX
- `turnaround_mode` TEXT
- `supports_positive_t` INTEGER
- `supports_negative_t` INTEGER
- `same_day_sell_allowed` INTEGER
- `notes` TEXT
- `updated_at` DATETIME

## 4.3 watchlist

- `id` INTEGER PK
- `symbol` TEXT UNIQUE INDEX
- `created_at` DATETIME

## 4.4 system_settings

- `id` INTEGER PK
- `key` TEXT UNIQUE INDEX
- `value` TEXT
- `updated_at` DATETIME

## 4.5 analysis_logs

- `id` INTEGER PK
- `symbol` TEXT
- `action` TEXT
- `signal_score` REAL
- `risk_level` TEXT
- `payload_json` TEXT
- `created_at` DATETIME

## 4.6 signal_replays

- `id` INTEGER PK
- `analysis_log_id` INTEGER
- `outcome` TEXT
- `pnl_pct` REAL
- `max_favorable_excursion` REAL
- `max_adverse_excursion` REAL
- `review_notes` TEXT
- `created_at` DATETIME

## 4.7 backtest_runs

- `id` INTEGER PK
- `name` TEXT
- `params_json` TEXT
- `result_json` TEXT
- `created_at` DATETIME

## 5. 开发顺序建议

1. 先后端：配置、数据模型、行情接口、交易制度识别
2. 再量化：特征计算、做T策略、动态仓位、风控覆盖
3. 再研究：日志、复盘、回测
4. 再前端：四页框架 + API 接入 + 图表渲染
5. 最后联调：轮询、异常处理、降级逻辑、文档

## 6. 测试建议

- 单元测试：
- 指标计算准确性（RSI、MACD）
- 策略输出边界（极端波动、无数据）
- 交易制度拦截是否正确
- 成本/滑点和仓位缩放逻辑

- 接口测试：
- 分析接口正常/降级链路
- 配置写入后读取一致性
- 回测接口结果结构完整
- 增强数据不可用时的降级链路

- 前端测试：
- 页面渲染与数据刷新
- 配置保存与错误提示
- 研究页统计可视化
- 多周期/风险卡片在移动端不溢出

## 7. 启动说明（预览）

后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

## 8. 合规与风险提示（建议在页面固定展示）

1. 系统输出仅用于研究与学习，不构成投资建议。
2. 交易需考虑滑点、手续费、流动性、涨跌停及 T+1 规则。
3. 模型分析存在不确定性，应设置严格止损与仓位控制。
4. ETF 与股票的日内回转制度可能不同，系统应优先以规则引擎判断。
