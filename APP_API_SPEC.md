# App API 接口规范

适用项目：`gupiao`  
当前日期：`2026-05-25`
文档状态：`V2，包含 Web BFF/Go/Rust 生产主路径契约`

## 0. Web/服务端新增契约（2026-05-25）

### 0.1 `GET /api/bff/v1/workspace/monitor`

`schema_version=v14`。除原有 `monitor_snapshot`、`market_breadth`、`sector_relative_strength`、`paired_hedge`、`partial_errors` 外，新增：

| 字段 | 类型 | 兼容策略 |
|---|---|---|
| `market_pulse` | object/null | 子源失败时返回 null 或 `data_quality=partial/unavailable`，页面不得白屏 |
| `review_status` | object/null | 无模拟盘账户时为今日空状态 |
| `review_reports` | array | 无报告时为空数组 |

`market_pulse` 必含：`updated_at`、`data_quality`(`fresh/stale/partial/unavailable`)、`data_quality_text`、`market_strength_text`、`leader_strength_text`、`emotion_text`、`hourly_snapshot_text`、`pulse_level`、`pulse_text`、`suggested_action`、`partial_errors`。

`review_status` 必含：`trade_date`、`status`、`status_text`、`has_midday`、`has_close`、`next_trigger_at`、`risk_alert_count`、`suggested_action`。

### 0.2 `GET /api/market/pulse`

返回盘中统一 pulse，聚合市场宽度、小时全市场快照、龙头强度与情绪温度。部分子源失败时返回 `data_quality=partial` 并填充 `partial_errors[]`。

### 0.3 `GET /api/paper/performance/review-summary`

返回实时监控页复盘摘要：

```json
{
  "review_status": {"status": "midday_ready", "next_trigger_at": "2026-05-25 15:05"},
  "review_reports": []
}
```

模拟盘页面只保留历史入口，不作为午盘/收盘复盘主展示入口。

### 0.4 Go 服务生产主路径

| 服务 | 生产入口 | 回退/观测 |
|---|---|---|
| `bff-gateway` | `/api/bff/v1/workspace/monitor` 聚合 monitor/pulse/review | `tquant_bff_gateway_aggregate_hits_total`、`proxy_fallbacks_total`、`cache_hits_total` |
| `market-read-service` | quote batch、sector strength、intraday key levels、intraday latest batch | `tquant_market_read_hits_total`、`fallbacks_total`、`partials_total` |
| `scan-worker` | `/api/scan-worker/v1/run` | `production_scan_enabled=true`、`production_write_enabled=true`，失败返回 fallback reason 且不写 latest |

生产环境配置 Go URL 时必须同时配置 `TQUANT_INTERNAL_SERVICE_TOKEN`；Go 服务在 `APP_ENVIRONMENT=production` 且 token 为空时拒绝启动。

### 0.5 Rust 计算主路径

`RUST_FINANCE_MATH_ENABLED=true` 为生产默认。Rust wheel 作为镜像产物安装，Python wrapper 保留 fallback 并暴露 `tquant_rust_math_hits_total`、`fallbacks_total`、`errors_total`、`disabled_total`。

## 1. 目标

后端维持一套服务，同时支持：

- Web 端完整功能
- App 端精简功能

App 端当前只保留两类能力：

- 实时监控
- 选股宝典

对应实现入口：

- 路由：[backend/app/api/routes/app_mobile.py](/Users/j/Documents/gupiao/backend/app/api/routes/app_mobile.py)
- 聚合服务：[backend/app/services/app_mobile/service.py](/Users/j/Documents/gupiao/backend/app/services/app_mobile/service.py)
- 响应模型：[backend/app/models/schema_defs/app_mobile.py](/Users/j/Documents/gupiao/backend/app/models/schema_defs/app_mobile.py)

## 2. 基本原则

- 核心服务层共用，不拆双份业务逻辑
- App 只消费 `/api/app/*`
- App 接口必须稳定、聚合、轻量
- 所有聚合响应统一包含 `updated_at`、`is_stale`、`warnings`
- App 不暴露研究、回测、系统配置等 Web 管理能力
- `/api/app/home`、`/api/app/watchlist*`、`/api/app/low-buy/{symbol}`、`/api/app/low-buy/{symbol}/favorite` 需要登录态；公共行情与策略榜单仍全局共享。

## 3. 通用约定

### 3.1 Base URL

- `https://your-domain.com/api/app/...`

### 3.2 Content-Type

- 请求：`application/json`
- 响应：`application/json`

### 3.3 鉴权

登录接口返回 `access_token`，`refresh_token` 通过 httpOnly Cookie 下发，不在响应体回显。App 调用用户私有接口时必须带：

```text
Authorization: Bearer <access_token>
```

认证接口：

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/auth/register` | `POST` | 注册并登录 |
| `/api/auth/login` | `POST` | 登录 |
| `/api/auth/refresh` | `POST` | 刷新 token |
| `/api/auth/logout` | `POST` | 退出登录 |
| `/api/auth/me` | `GET` | 当前用户 |

### 3.4 通用元信息字段

除动作接口外，所有 App 聚合接口都包含：

| 字段 | 类型 | 含义 |
|---|---|---|
| `updated_at` | `string` | 当前聚合结果时间 |
| `is_stale` | `boolean` | 是否为降级或可能过期的数据 |
| `warnings` | `string[]` | 降级说明或提示信息 |

### 3.5 动作接口响应

自选增删、从选股宝典加入自选，统一返回：

```json
{
  "message": "自选股已保存",
  "symbol": "510300"
}
```

模型定义见：

- [backend/app/models/schema_defs/app_mobile.py](/Users/j/Documents/gupiao/backend/app/models/schema_defs/app_mobile.py)

### 3.6 错误响应

沿用 FastAPI 默认格式：

```json
{
  "detail": "错误说明"
}
```

推荐按当前实现理解：

- `200`：成功
- `400`：参数通过但底层数据源失败
- `404`：标的不存在
- `422`：请求参数不合法
- `500`：服务内部错误

## 4. App V1 接口清单

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/auth/register` | `POST` | 注册并登录 |
| `/api/auth/login` | `POST` | 登录 |
| `/api/auth/refresh` | `POST` | 刷新登录态 |
| `/api/auth/logout` | `POST` | 退出登录 |
| `/api/auth/me` | `GET` | 当前用户 |
| `/api/app/bootstrap` | `GET` | App 启动配置 |
| `/api/app/home` | `GET` | 实时监控首页聚合 |
| `/api/app/watchlist` | `GET` | 自选股列表 |
| `/api/app/watchlist` | `POST` | 新增或更新自选 |
| `/api/app/watchlist/{symbol}` | `GET` | 单标的监控详情 |
| `/api/app/watchlist/{symbol}` | `DELETE` | 删除自选 |
| `/api/app/low-buy` | `GET` | 选股宝典首页 |
| `/api/app/low-buy/{symbol}` | `GET` | 候选详情 |
| `/api/app/low-buy/{symbol}/favorite` | `POST` | 一键加入自选 |

## 5. 详细接口定义

### 5.1 `GET /api/app/bootstrap`

用途：返回 App 端静态元信息，避免前端硬编码。

请求参数：无

响应示例：

```json
{
  "app_name": "A股短线做T助手",
  "app_version": "1.0.0",
  "min_supported_version": "1.0.0",
  "tabs": [
    { "key": "home", "title": "实时监控" },
    { "key": "low_buy", "title": "选股宝典" }
  ],
  "default_refresh_seconds": 20,
  "market_disclaimer": "数据仅供研究与辅助决策，不构成投资建议。",
  "feature_flags": {
    "watchlist_enabled": true,
    "low_buy_enabled": true
  },
  "updated_at": "2026-04-22 10:00:00",
  "is_stale": false,
  "warnings": []
}
```

说明：

- 当前版本号由服务端静态定义
- 不返回数据库、调参、模型供应商等后台配置

### 5.2 `GET /api/app/home`

用途：实时监控首页聚合接口。

请求参数：无

响应结构：

- `summary.total`：监控卡片总数
- `summary.positive_t_count`：正 T 信号数
- `summary.negative_t_count`：反 T 信号数
- `summary.hold_count`：观望数
- `summary.high_risk_count`：高风险数
- `items[]`：监控卡片列表

卡片关键字段：

| 字段 | 含义 |
|---|---|
| `symbol` / `name` | 标的基础信息 |
| `base_position` / `available_position` / `cost_basis` | 持仓信息 |
| `quote` | 行情快照 |
| `signal` | 策略建议与风险等级 |
| `rules` | 交易规则说明 |
| `headline_reason` | 首页主原因文案 |
| `headline_blocker` | 首页阻断文案 |
| `error` | 单卡片错误信息，正常时为 `null` |
| `updated_at` | 单卡片更新时间 |
| `is_stale` | 单卡片是否过期 |

响应示例：

```json
{
  "summary": {
    "total": 1,
    "positive_t_count": 1,
    "negative_t_count": 0,
    "hold_count": 0,
    "high_risk_count": 0
  },
  "items": [
    {
      "symbol": "510300",
      "name": "沪深300ETF",
      "base_position": 1200,
      "available_position": 900,
      "cost_basis": 3.45,
      "memo": "app-smoke",
      "quote": {
        "symbol": "510300",
        "name": "沪深300ETF",
        "market": "SH",
        "instrument_type": "etf",
        "last_price": 3.478,
        "change_pct": 0.86,
        "change_amount": 0.03,
        "open_price": 3.451,
        "high_price": 3.482,
        "low_price": 3.446,
        "prev_close": 3.448,
        "volume": 123456789,
        "amount": 456789123,
        "turnover_rate": null,
        "volume_ratio": null,
        "timestamp": "2026-04-22 10:01:00"
      },
      "signal": {
        "action": "positive_t",
        "entry_price": 3.46,
        "exit_price": 3.49,
        "position_pct": 25.0,
        "stop_loss": 3.42,
        "risk_level": "medium",
        "signal_score": 72.0,
        "tradability_score": 80.0,
        "confidence": 67.0,
        "expected_profit_pct": 0.8,
        "scenario": "trend_retrace",
        "reasons": ["接近均线支撑，允许试仓。"],
        "blocking_rules": [],
        "take_profit": 3.49,
        "strategy_notes": "优先看承接和分时回踩。"
      },
      "rules": {
        "symbol": "510300",
        "turnaround_mode": "t0",
        "supports_positive_t": true,
        "supports_negative_t": true,
        "same_day_sell_allowed": true,
        "requires_base_position": false,
        "notes": "ETF 可日内回转"
      },
      "headline_reason": "接近均线支撑，允许试仓。",
      "headline_blocker": "",
      "error": null,
      "updated_at": "2026-04-22 10:01:00",
      "is_stale": false
    }
  ],
  "updated_at": "2026-04-22 10:01:01",
  "is_stale": false,
  "warnings": []
}
```

说明：

- 顶层 `warnings` 来自卡片级错误去重汇总
- 若某张卡片行情失败，该卡片 `is_stale=true`，同时顶层 `warnings` 会包含该错误

### 5.3 `GET /api/app/watchlist`

用途：获取移动端轻量自选列表。

请求参数：无

响应字段：

- `items[]`：当前自选列表
- 每个元素结构与现有 `WatchlistItemOut` 一致

响应示例：

```json
{
  "items": [
    {
      "symbol": "510300",
      "name": "沪深300ETF",
      "base_position": 1200,
      "available_position": 900,
      "cost_basis": 3.45,
      "memo": "app-smoke",
      "created_at": "2026-04-22T10:00:00"
    }
  ],
  "updated_at": "2026-04-22 10:02:00",
  "is_stale": false,
  "warnings": []
}
```

### 5.4 `POST /api/app/watchlist`

用途：新增或更新自选。

请求体：

```json
{
  "symbol": "510300",
  "name": "沪深300ETF",
  "base_position": 1200,
  "available_position": 900,
  "cost_basis": 3.45,
  "memo": "app-smoke"
}
```

响应：

```json
{
  "message": "自选股已保存",
  "symbol": "510300"
}
```

说明：

- 成功后会触发监控信号后台刷新
- 当前实现对“新增”和“更新”使用同一动作接口

### 5.5 `GET /api/app/watchlist/{symbol}`

用途：查看单标的监控详情。

响应字段：

- 顶层基础信息与 `home.items[]` 一致
- 增加 `detail_sections`

`detail_sections` 字段：

| 字段 | 含义 |
|---|---|
| `reasons` | 当前信号理由列表 |
| `blocking_rules` | 当前阻断规则列表 |
| `strategy_notes` | 策略备注 |

响应示例：

```json
{
  "symbol": "510300",
  "name": "沪深300ETF",
  "base_position": 1200,
  "available_position": 900,
  "cost_basis": 3.45,
  "memo": "app-smoke",
  "quote": {
    "symbol": "510300",
    "name": "沪深300ETF",
    "market": "SH",
    "instrument_type": "etf",
    "last_price": 3.478,
    "change_pct": 0.86,
    "change_amount": 0.03,
    "open_price": 3.451,
    "high_price": 3.482,
    "low_price": 3.446,
    "prev_close": 3.448,
    "volume": 123456789,
    "amount": 456789123,
    "turnover_rate": null,
    "volume_ratio": null,
    "timestamp": "2026-04-22 10:01:00"
  },
  "signal": {
    "action": "positive_t",
    "entry_price": 3.46,
    "exit_price": 3.49,
    "position_pct": 25.0,
    "stop_loss": 3.42,
    "risk_level": "medium",
    "signal_score": 72.0,
    "tradability_score": 80.0,
    "confidence": 67.0,
    "expected_profit_pct": 0.8,
    "scenario": "trend_retrace",
    "reasons": ["接近均线支撑，允许试仓。"],
    "blocking_rules": [],
    "take_profit": 3.49,
    "strategy_notes": "优先看承接和分时回踩。"
  },
  "rules": {
    "symbol": "510300",
    "turnaround_mode": "t0",
    "supports_positive_t": true,
    "supports_negative_t": true,
    "same_day_sell_allowed": true,
    "requires_base_position": false,
    "notes": "ETF 可日内回转"
  },
  "detail_sections": {
    "reasons": ["接近均线支撑，允许试仓。"],
    "blocking_rules": [],
    "strategy_notes": "优先看承接和分时回踩。"
  },
  "updated_at": "2026-04-22 10:01:00",
  "is_stale": false,
  "warnings": []
}
```

### 5.6 `DELETE /api/app/watchlist/{symbol}`

用途：删除自选。

响应：

```json
{
  "message": "已删除",
  "symbol": "510300"
}
```

说明：

- 删除后会清理该标的监控缓存，并触发后台刷新

### 5.7 `GET /api/app/low-buy`

用途：选股宝典首页。

Query 参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `strategy` | `string` | `classic_retrace` | 策略键 |
| `limit` | `integer` | `12` | 返回候选上限，范围 `1-40` |
| `scan_limit` | `integer` | `48` | 快速扫描范围，范围 `12-480` |
| `scan_mode` | `quick \| full` | `quick` | `full` 表示优先读取物化全量结果，拿不到时仍允许快速候选降级 |

响应字段：

- `strategy`：策略说明
- `summary`：扫描摘要
- `priority_board`：移动端优先级看板
- `confirmed_candidates`：确认候选
- `watch_candidates`：观察候选

`summary` 关键字段：

| 字段 | 含义 |
|---|---|
| `full_scan_ready` | 是否已有可读物化结果 |
| `full_scan_in_progress` | 是否存在后台全量计算 |
| `pool_size` | 策略池规模 |
| `scanned_count` | 实际扫描数 |
| `matched_count` | 命中候选数 |

响应示例：

```json
{
  "strategy": {
    "strategy_key": "classic_retrace",
    "strategy_title": "原始低吸法",
    "strategy_subtitle": "关注回撤后的承接修复",
    "strategy_logic": "优先看回撤后的低吸机会。"
  },
  "summary": {
    "as_of_date": "2026-04-22",
    "latest_trade_date": "2026-04-22",
    "pool_size": 120,
    "scanned_count": 48,
    "matched_count": 3,
    "full_scan_ready": true,
    "full_scan_in_progress": false
  },
  "priority_board": {
    "market_state": "watch",
    "market_state_text": "存在接近买点的候选",
    "items": [
      {
        "symbol": "300750",
        "name": "宁德时代",
        "strategy_key": "classic_retrace",
        "strategy_title": "原始低吸法",
        "strategy_titles": ["原始低吸法"],
        "strategy_count": 1,
        "latest_price": 18.8,
        "change_pct": -1.2,
        "quote_timestamp": "2026-04-22 10:05:00",
        "buy_signal_state": "near_entry",
        "buy_signal_text": "接近买点",
        "priority_score": 81.2,
        "strategy_weight_score": 81.2,
        "industry_rotation_bonus": 0.0,
        "industry_rotation_text": "新能源",
        "action_summary": "等待承接确认",
        "blocked_reason": "",
        "entry_zone_low": 18.5,
        "entry_zone_high": 18.9,
        "stop_loss": 17.9,
        "suggested_position_pct": 20.0,
        "suggested_position_text": "先试 2 成"
      }
    ]
  },
  "confirmed_candidates": [],
  "watch_candidates": [
    {
      "strategy_key": "classic_retrace",
      "strategy_title": "原始低吸法",
      "symbol": "300750",
      "name": "宁德时代",
      "market": "SZ",
      "instrument_type": "stock",
      "sector_name": "新能源",
      "latest_price": 18.8,
      "change_pct": -1.2,
      "quote_timestamp": "2026-04-22 10:05:00",
      "board_date": "2026-04-20",
      "board_count": 1,
      "retracement_days": 2,
      "score": 81.2,
      "entry_zone_low": 18.5,
      "entry_zone_high": 18.9,
      "stop_loss": 17.9,
      "take_profit": 19.8,
      "ma5": 18.7,
      "ma10": 18.1,
      "ma20": 17.6,
      "volume_burst_ratio": 1.8,
      "volume_shrink_ratio": 0.7,
      "support_distance_pct": 1.1,
      "execution_ready": true,
      "execution_note": "接近入场区，可观察承接",
      "entry_distance_pct": 0.2,
      "suggested_position_pct": 20.0,
      "suggested_position_text": "先试 2 成",
      "confirmed_trade_date": null,
      "summary_reason": "回撤后接近入场区",
      "buy_signal_state": "near_entry",
      "buy_signal_text": "接近买点",
      "buy_signal_hint": "等待承接确认",
      "reasons": ["回撤后接近入场区"],
      "risks": ["若跌破支撑则无效"],
      "tags": ["低吸", "观察"]
    }
  ],
  "updated_at": "2026-04-22 10:05:00",
  "is_stale": false,
  "warnings": []
}
```

降级语义：

- 若命中物化结果，返回 `full_scan_ready=true`
- 若未命中物化结果，会回退到快速候选视图
- 发生回退时，`warnings` 会明确提示当前结果来自快速候选视图
- `scan_mode=full` 不会在请求线程里强制跑全量扫描，它只是“优先取全量物化结果”

### 5.8 `GET /api/app/low-buy/{symbol}`

用途：查看单个候选详情。

Query 参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `strategy` | `string` | `classic_retrace` | 策略键 |
| `scan_limit` | `integer` | `72` | 详情兜底扫描上限，范围 `12-480` |

响应结构：

- `candidate`：候选详情，结构与 `LowBuyCandidateOut` 一致
- `favorite_status.in_watchlist`：是否已在自选
- `favorite_status.watchlist_symbol`：已入自选时的 symbol

响应示例：

```json
{
  "candidate": {
    "strategy_key": "classic_retrace",
    "strategy_title": "原始低吸法",
    "symbol": "300750",
    "name": "宁德时代",
    "market": "SZ",
    "instrument_type": "stock",
    "sector_name": "新能源",
    "latest_price": 18.8,
    "change_pct": -1.2,
    "quote_timestamp": "2026-04-22 10:05:00",
    "board_date": "2026-04-20",
    "board_count": 1,
    "retracement_days": 2,
    "score": 81.2,
    "entry_zone_low": 18.5,
    "entry_zone_high": 18.9,
    "stop_loss": 17.9,
    "take_profit": 19.8,
    "ma5": 18.7,
    "ma10": 18.1,
    "ma20": 17.6,
    "volume_burst_ratio": 1.8,
    "volume_shrink_ratio": 0.7,
    "support_distance_pct": 1.1,
    "execution_ready": true,
    "execution_note": "接近入场区，可观察承接",
    "entry_distance_pct": 0.2,
    "suggested_position_pct": 20.0,
    "suggested_position_text": "先试 2 成",
    "confirmed_trade_date": null,
    "summary_reason": "回撤后接近入场区",
    "buy_signal_state": "near_entry",
    "buy_signal_text": "接近买点",
    "buy_signal_hint": "等待承接确认",
    "reasons": ["回撤后接近入场区"],
    "risks": ["若跌破支撑则无效"],
    "tags": ["低吸", "观察"]
  },
  "favorite_status": {
    "in_watchlist": false,
    "watchlist_symbol": null
  },
  "updated_at": "2026-04-22 10:05:00",
  "is_stale": false,
  "warnings": []
}
```

说明：

- 若列表里已有该标的但当前快照缺失，服务会做一次扩大范围的快速兜底扫描
- 若最终仍未找到，则返回 `404`

### 5.9 `POST /api/app/low-buy/{symbol}/favorite`

用途：从选股宝典一键加入自选。

请求体：

```json
{
  "name": "宁德时代",
  "base_position": 1000,
  "available_position": 1000,
  "cost_basis": null,
  "memo": "来自选股宝典"
}
```

响应：

```json
{
  "message": "自选股已保存",
  "symbol": "300750"
}
```

说明：

- 该接口复用自选写入逻辑
- 成功后同样会触发监控信号后台刷新

## 6. 后端运行与降级说明

相关文件：

- 启动与后台任务：[backend/app/main.py](/Users/j/Documents/gupiao/backend/app/main.py)
- 运行时配置：[backend/app/core/config.py](/Users/j/Documents/gupiao/backend/app/core/config.py)
- 低吸移动端读取：[backend/app/services/low_buy/mobile.py](/Users/j/Documents/gupiao/backend/app/services/low_buy/mobile.py)

当前策略：

- 服务启动后会后台预热 App 低吸物化结果和监控信号
- sqlite 场景下使用限时预热，优先保证服务可用而不是无限等待全量完成
- 因此 `full_scan_ready=true` 代表“当前已有可读物化结果”，不代表扫描一定覆盖最大池子
- 这是移动端的刻意取舍：先保证有稳定结果，再追求更大覆盖面

## 7. 验证方式

自动验证入口：

- 冒烟脚本：[scripts/app_api_smoke.sh](/Users/j/Documents/gupiao/scripts/app_api_smoke.sh)
- 路由测试：[backend/tests/test_app_mobile_routes.py](/Users/j/Documents/gupiao/backend/tests/test_app_mobile_routes.py)
- 服务测试：[backend/tests/test_app_mobile_service.py](/Users/j/Documents/gupiao/backend/tests/test_app_mobile_service.py)

建议联调前至少执行：

```bash
cd /Users/j/Documents/gupiao/backend
.venv/bin/python -m unittest discover -s tests
cd /Users/j/Documents/gupiao
scripts/app_api_smoke.sh
```

## 8. 当前范围外能力

以下能力仍只保留在 Web 端：

- 分析页
- 研究复盘
- 回测能力
- 系统配置
- 数据源配置
- 模型配置

App 侧不建议直接消费这些接口。
