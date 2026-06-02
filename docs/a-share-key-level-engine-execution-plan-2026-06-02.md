# A 股关键位引擎最终方案

状态：方案定稿，待实现  
日期：2026-06-02  
适用范围：后端计算层、API 输出层、前端展示层、回测验证、实时监控与模拟盘辅助决策  

## 1. 定位

A 股关键位引擎，简称 `AKeyLevel Engine`，用于统一计算和展示大盘、板块、个股的支撑位、压力位、MA30 和盘中关键价位。

该能力只用于：

1. 观察关键位置。
2. 风控提醒。
3. 做 T 辅助判断。
4. 策略复盘解释。
5. 模拟盘和监控页的上下文展示。

该能力不做：

1. 不输出自动买入或卖出建议。
2. 不改变生产排序逻辑。
3. 不改变策略打分边界。
4. 不把观察信号写成交易建议。
5. 不使用信号日之后的数据。

## 2. 核心结论

单一指标不适合直接作为 A 股支撑压力位工具。

最适合当前平台的是融合模型：

1. 成交密集区。
2. 结构关键位。
3. Anchored VWAP。
4. MA5 / MA10 / MA20 / MA30 / MA60。
5. 盘中 VWAP、昨收、今开、分时高低点、整数关口。

最终输出不是一个绝对点位，而是：

1. 支撑区间。
2. 压力区间。
3. 最近支撑价。
4. 最近压力价。
5. 距离百分比。
6. 强度评分。
7. 来源证据。
8. 失效条件。
9. 数据质量。

## 3. 为什么适合 A 股

A 股短线和做 T 场景有几个明显特点：

1. 涨跌停和连板会改变市场记忆。
2. 涨停日、放量突破日、开板日、缺口日是重要锚点。
3. 成交密集区比单根均线更能反映真实筹码压力。
4. 缩量板、一字板、停牌、新股、ST 会导致点位可信度下降。
5. 做 T 更需要动态关键位，而不是静态公式点位。
6. 单独使用 Pivot 或 MA 容易在震荡行情里误判。

因此，关键位必须可解释、可降级、可回测，不能只给一个公式结果。

## 4. 数据来源

### 4.1 个股数据

1. 日线 OHLCV。
2. 分钟线 OHLCV。
3. 实时行情快照。
4. 涨停、跌停、连板、开板信息。
5. 个股所属行业、主题、板块。
6. 数据质量状态。

### 4.2 板块数据

1. 板块指数或板块代理序列。
2. 板块内核心个股表现。
3. 板块成交额变化。
4. 板块强度和相对强弱。

### 4.3 大盘数据

1. 主要指数日线。
2. 指数分钟线。
3. 市场状态。
4. 成交额、涨跌家数、炸板率、连板高度等市场情绪字段。

## 5. 三层覆盖设计

`AKeyLevel Engine` 必须同时覆盖大盘、板块、个股三层。三层使用同一套候选、合并、评分和降级框架，但输入数据、权重和展示重点不同。

### 5.1 大盘关键位

覆盖对象：

1. 上证指数。
2. 深证成指。
3. 创业板指。
4. 沪深 300。
5. 中证 500。
6. 中证 1000。
7. 平台配置的其他核心指数。

大盘输出：

1. 大盘支撑区。
2. 大盘压力区。
3. 最近支撑价。
4. 最近压力价。
5. MA5 / MA10 / MA20 / MA30 / MA60。
6. 距离支撑和压力的百分比。
7. 大盘关键位强度。
8. 市场状态对关键位的加权说明。
9. 数据质量和是否可用于生产观察。

大盘候选来源：

1. 指数前高和前低。
2. 指数平台高低点。
3. 指数缺口。
4. 指数成交密集区。
5. 指数 MA30 / MA60。
6. 昨收、今开、盘中 VWAP。

大盘用途：

1. 判断整体风险。
2. 判断是否适合积极做 T。
3. 给个股和板块关键位加权或降级。
4. 在全市场复盘中解释市场所处位置。

大盘文案边界：

1. 只能表达市场支撑、压力、风险和观察条件。
2. 不能表达买入或卖出建议。
3. 弱市跌破大盘关键支撑时，只能提示风险升高和观察降级。

### 5.2 板块关键位

覆盖对象：

1. 行业板块。
2. 主题板块。
3. 热点板块。
4. ETF 代理板块。
5. 平台策略使用的主线板块集合。

板块输出：

1. 板块支撑区。
2. 板块压力区。
3. 板块最近支撑价。
4. 板块最近压力价。
5. 板块 MA5 / MA10 / MA20 / MA30 / MA60。
6. 板块相对大盘强弱。
7. 板块核心股共振情况。
8. 板块关键位强度。
9. 板块关键位是否失效。

板块候选来源：

1. 板块指数或代理序列前高前低。
2. 板块平台高低点。
3. 板块成交密集区。
4. 板块 MA30 / MA60。
5. 板块核心股共同支撑区。
6. 板块核心股共同压力区。
7. 板块放量突破日 Anchored VWAP。

板块用途：

1. 判断个股支撑是否有板块支撑。
2. 判断个股压力是否来自板块共振压力。
3. 避免单票孤立判断。
4. 在策略跟踪和模拟盘中解释个股是否仍在主线板块环境内。

板块文案边界：

1. 只能表达板块支撑、压力、强弱和共振。
2. 不把板块走强写成个股买入建议。
3. 板块数据不足时，个股关键位不能因为缺板块数据而伪装成高可信。

### 5.3 个股关键位

覆盖对象：

1. 生产标的池股票。
2. 用户自选股票。
3. 模拟盘持仓。
4. 策略跟踪样本。
5. 全市场扫描候选。

个股输出：

1. 最近支撑区。
2. 最近压力区。
3. 最近支撑价。
4. 最近压力价。
5. 距离支撑百分比。
6. 距离压力百分比。
7. 支撑强度。
8. 压力强度。
9. MA5 / MA10 / MA20 / MA30 / MA60。
10. 涨停日、放量日、平台突破日 Anchored VWAP。
11. 盘中 VWAP、昨收、今开、整数关口。
12. 来源证据。
13. 失效条件。
14. 数据质量。

个股候选来源：

1. 个股前高和前低。
2. 个股平台高低点。
3. 个股缺口。
4. 涨停日关键价。
5. 连板开板日关键价。
6. 放量突破日关键价。
7. 成交密集区。
8. Anchored VWAP。
9. MA30 / MA60。
10. 盘中 VWAP、昨收、今开、整数关口。

个股用途：

1. 实时监控接近关键位提醒。
2. 策略跟踪判断支撑是否失效。
3. 模拟盘持仓判断风险和压力。
4. 分析页解释当前价格位置。
5. 做 T 辅助观察。

个股文案边界：

1. 只表达接近支撑、接近压力、支撑失效、压力待观察。
2. 不输出买入、卖出、重点推荐等动作建议。
3. `near_entry`、`watch`、`observe_confirmed` 仍必须保持观察语义。

### 5.4 三层联动

三层关键位不是孤立输出。

联动规则：

1. 大盘强、板块强、个股支撑强，个股支撑强度可加权。
2. 大盘弱、板块弱、个股支撑强，个股支撑只能保持观察，不得升级为交易动作。
3. 大盘跌破关键支撑时，板块和个股评分统一降级。
4. 板块跌破关键支撑时，板块内个股的支撑可信度降级。
5. 个股接近支撑但板块处于压力区时，只能提示承接待确认。
6. 个股突破压力但大盘和板块未共振时，只能提示突破待验证。
7. 任一层数据不足时，必须在结果里标记，不允许静默忽略。

三层输出优先级：

1. 页面首屏优先展示个股最近支撑和压力。
2. 详情里展示板块和大盘共振。
3. 全市场复盘优先展示大盘和板块关键位。
4. 模拟盘优先展示持仓个股关键位，同时显示板块和大盘降级原因。

## 6. 关键位来源

### 6.1 成交密集区

成交密集区是主来源之一。

第一版可用日线高低价和成交额近似分布；第二版再接入分钟线或 tick 级 Volume Profile。

候选规则：

1. 最近 20 / 60 / 120 个交易日分桶统计成交额。
2. 成交额最高的价格带作为高成交密集区。
3. 当前价上方的密集区优先作为压力。
4. 当前价下方的密集区优先作为支撑。
5. 近期成交密集区权重大于久远成交密集区。

### 6.2 结构关键位

结构关键位是 A 股短线里最重要的可解释来源。

候选规则：

1. 最近前高。
2. 最近前低。
3. 平台高点。
4. 平台低点。
5. 缺口上沿。
6. 缺口下沿。
7. 涨停日开盘价、最低价、收盘价。
8. 放量突破日高点和低点。
9. 连板开板日高低点。

结构位需要记录触碰次数和最近一次触碰日期。

### 6.3 Anchored VWAP

Anchored VWAP 用于判断重要事件后的平均持仓成本。

锚点包括：

1. 涨停日。
2. 首板日。
3. 放量突破日。
4. 阶段低点。
5. 平台突破日。
6. 开板放量日。

如果锚点后的 VWAP 与平台位、均线或成交密集区接近，则提高关键位强度。

### 6.4 均线系统

统一补齐：

1. MA5。
2. MA10。
3. MA20。
4. MA30。
5. MA60。

MA30 是中期支撑和趋势判断的重要补充，但不单独作为最高可信支撑。

均线输出：

1. `ma5`
2. `ma10`
3. `ma20`
4. `ma30`
5. `ma60`
6. `close_to_ma5`
7. `close_to_ma10`
8. `close_to_ma20`
9. `close_to_ma30`
10. `close_to_ma60`
11. `reclaim_ma5`
12. `reclaim_ma10`
13. `reclaim_ma20`
14. `reclaim_ma30`
15. `reclaim_ma60`
16. `trend_above_ma30`
17. `trend_above_ma60`

### 6.5 盘中关键位

盘中关键位用于实时监控和做 T 辅助。

来源包括：

1. 分时 VWAP。
2. 昨收。
3. 今开。
4. 分时高点。
5. 分时低点。
6. 整数关口。
7. 计划买点区上下沿。

现有 `GET /api/intraday/key-levels/stream`（`backend/app/services/intraday_key_levels.py`，已含 VWAP/昨收/整数关口/买点区，且走 Go 读取 `load_go_intraday_key_levels`）即第一版盘中能力。统一引擎必须**收敛复用它**，§10 的盘中 API 须对齐此真实路径或提供兼容层，不另起一套（详见 §19.3）。

## 7. 强度评分

每个关键位输出 `strength_score`，满分 100。

基础评分：

| 来源 | 分值 |
|---|---:|
| 成交密集区 | 30 |
| 结构位触碰次数 | 20 |
| Anchored VWAP 共振 | 15 |
| 均线和多周期共振 | 15 |
| 最近有效性 | 10 |
| 市场和板块状态 | 10 |

扣分项：

| 风险 | 扣分 |
|---|---:|
| 已跌破后未收回 | -30 |
| 放量破位 | -25 |
| 板块明显走弱 | -15 |
| 数据不足 | -20 |
| 位置离当前价过远 | -10 |
| 一字板或缩量板换手不足 | -10 |
| 停牌、新股、ST 或流动性不足 | -30 |

## 8. 区间合并

关键位不应只输出单点。

合并规则：

1. 价格相差小于 0.3% 的候选位合并为同一区间。
2. 高波动个股可放宽到 0.5%。
3. 区间中心价作为 `support_price` 或 `resistance_price`。
4. 区间下沿和上沿分别输出。
5. 多来源重合的区间强度更高。
6. 已失效的区间降级，不直接删除，用于复盘。

## 9. 统一 Schema

```ts
type KeyLevelDirection = "support" | "resistance" | "neutral";

type KeyLevelType =
  | "volume_profile"
  | "swing_high"
  | "swing_low"
  | "platform_high"
  | "platform_low"
  | "gap"
  | "limit_up_anchor"
  | "anchored_vwap"
  | "ma5"
  | "ma10"
  | "ma20"
  | "ma30"
  | "ma60"
  | "intraday_vwap"
  | "open"
  | "prev_close"
  | "round_number";

type KeyLevelDataQuality =
  | "ok"
  | "insufficient"
  | "stale"
  | "blocked"
  | "research_only";

type KeyLevelCandidate = {
  price: number;
  zone_low: number;
  zone_high: number;
  direction: KeyLevelDirection;
  level_type: KeyLevelType;
  strength_score: number;
  evidence: string[];
  invalid_condition: string;
  last_touched_date?: string;
  touch_count?: number;
  source_window_days?: number;
  invalidate_below?: number;     // 机器可读失效价：跌破即触发降级/预警（§19.5）
  invalidate_volume_x?: number;  // 放量倍数阈值，配合失效价驱动 SSE 预警
};

type KeyLevelResult = {
  symbol: string;
  name?: string;
  scope: "stock" | "sector" | "market";
  trade_date: string;
  latest_price: number;
  engine_version: string;        // 评分/算法版本，回测可复现（§19.4）
  as_of: string;                 // 数据截止时点，只用信号日及以前（§19.1）
  adjust_mode: "qfq" | "hfq" | "none"; // 日线级候选统一前复权
  intraday_included: boolean;    // 是否合并盘中级关键位

  support_price: number | null;
  support_zone_low: number | null;
  support_zone_high: number | null;
  support_distance_pct: number | null;
  support_strength: number;
  support_level_type: KeyLevelType | "";

  resistance_price: number | null;
  resistance_zone_low: number | null;
  resistance_zone_high: number | null;
  resistance_distance_pct: number | null;
  resistance_strength: number;
  resistance_level_type: KeyLevelType | "";

  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma30: number | null;
  ma60: number | null;

  close_to_ma5: number | null;
  close_to_ma10: number | null;
  close_to_ma20: number | null;
  close_to_ma30: number | null;
  close_to_ma60: number | null;

  trend_above_ma30: boolean | null;
  trend_above_ma60: boolean | null;

  key_level_candidates: KeyLevelCandidate[];
  data_quality: KeyLevelDataQuality;
  explanation: string;
  warnings: string[];
};
```

## 10. API 设计

新增 API：

1. `GET /api/key-levels/stock/{symbol}`
2. `GET /api/key-levels/sector/{sector_key}`
3. `GET /api/key-levels/market`
4. `GET /api/key-levels/intraday/{symbol}`

第一版参数：

| 参数 | 说明 |
|---|---|
| `trade_date` | 可选，默认最近交易日 |
| `lookback_days` | 默认 120 |
| `include_intraday` | 是否合并盘中关键位 |
| `threshold_pct` | 接近提醒阈值，默认 0.3 |

返回必须包含：

1. 统一 schema。
2. 数据质量。
3. 证据说明。
4. 失效条件。

## 11. 后端落地结构

建议新增：

1. `backend/app/services/key_levels/engine.py`
2. `backend/app/services/key_levels/volume_profile.py`
3. `backend/app/services/key_levels/swing_levels.py`
4. `backend/app/services/key_levels/anchored_vwap.py`
5. `backend/app/services/key_levels/ma_levels.py`
6. `backend/app/services/key_levels/score.py`
7. `backend/app/services/key_levels/schema.py`
8. `backend/app/api/routes/key_levels.py`
9. `backend/app/models/schema_defs/key_levels.py`

职责边界：

1. route 只做参数解析、鉴权和响应编排。
2. engine 负责调度各类关键位来源。
3. scorer 负责强度评分。
4. schema 负责输出契约。
5. 不在前端拼后端聚合逻辑。

## 12. 前端展示

新增组件：

1. `KeyLevelPanel`
2. `KeyLevelMiniSummary`
3. `KeyLevelEvidenceList`
4. `KeyLevelStrengthTag`

展示页面：

1. 实时监控页。
2. 策略跟踪详情。
3. 模拟盘持仓详情。
4. 分析页 K 线旁边。
5. 全市场复盘详情。

桌面展示：

1. 最近支撑区。
2. 最近压力区。
3. 距离百分比。
4. 强度评分。
5. 来源标签。
6. 失效条件。
7. 数据质量。

移动端展示：

> 距最近支撑约 1.2%，来自平台低点、成交密集区和 MA30 共振；若放量跌破并收不回，支撑降级。

移动端只展示核心一句话和详情折叠，不堆长表格。

## 13. 文案边界

允许文案：

1. 接近支撑。
2. 接近压力。
3. 支撑待确认。
4. 支撑已降级。
5. 压力位仍在。
6. 突破后需观察能否站稳。
7. 数据不足，仅观察。

禁止文案：

1. 建议买入。
2. 建议卖出。
3. 强烈推荐。
4. 必涨。
5. 压力突破即可买入。
6. 支撑附近直接低吸。

## 14. 测试要求

后端测试：

1. MA30 计算测试。
2. 支撑位计算测试。
3. 压力位计算测试。
4. 成交密集区候选测试。
5. Anchored VWAP 测试。
6. 区间合并测试。
7. 强度评分测试。
8. 数据不足降级测试。
9. 不引未来函数测试。
10. API schema 测试。

前端测试：

1. 支撑/压力字段展示。
2. 数据不足展示。
3. 观察文案不出现买入建议。
4. 375px 移动端不溢出。
5. 详情折叠可访问。

回测验证：

1. 触达支撑后 1 / 3 / 5 日表现。
2. 跌破支撑后失败率。
3. 突破压力后延续率。
4. 不同行情状态下的有效性。
5. 不同行业和流动性下的有效性。

## 15. 实施顺序

### Phase 1：个股关键位

1. 补 MA30。
2. 输出 MA5 / MA10 / MA20 / MA30 / MA60。
3. 做结构关键位。
4. 做日线成交密集区近似。
5. 输出个股支撑/压力 schema。
6. 接入分析页和监控详情。

### Phase 2：盘中关键位收敛

1. 复用现有盘中关键位能力。
2. 合并实时 VWAP、昨收、今开、整数关口。
3. 接入 SSE 接近提醒。
4. 前端展示接近关键位提醒。

### Phase 3：板块和大盘关键位

1. 板块关键位。
2. 大盘指数关键位。
3. 市场状态对评分加权。
4. 全市场复盘展示关键位。
5. 三层联动降级规则。
6. 板块和大盘结果纳入统一 schema。

### Phase 4：命中率验证

1. 24 个月历史回测。
2. 市场状态分层验证。
3. 个股流动性分层验证。
4. 输出命中率和失效率报告。

## 16. 验收标准

1. MA30 在后端 schema 和 API 中可见。
2. 大盘支撑/压力位可计算并返回。
3. 板块支撑/压力位可计算并返回。
4. 个股支撑/压力位可计算并返回。
5. 前端能分别展示大盘、板块、个股最近支撑、最近压力、距离、强度、来源、失效条件。
6. 数据不足时显示 `insufficient` 或 `research_only`。
7. 观察文案不出现买入/卖出建议。
8. 所有计算只使用信号日及以前数据。
9. 新增后端测试和前端测试通过。
10. 375px 移动端无横向溢出。
11. 不影响现有策略逻辑、回测口径和生产排序。

## 17. 最终形态

平台最终应形成统一关键位能力：

1. 盘前看大盘和板块关键位。
2. 盘中看个股是否接近关键位。
3. 策略跟踪看支撑是否失效。
4. 模拟盘看持仓距离压力和支撑。
5. 复盘看关键位是否有效。

最终输出示例：

```json
{
  "symbol": "000001",
  "name": "平安银行",
  "scope": "stock",
  "trade_date": "2026-06-02",
  "latest_price": 10.12,
  "support_price": 9.88,
  "support_zone_low": 9.82,
  "support_zone_high": 9.95,
  "support_distance_pct": -2.37,
  "support_strength": 82,
  "support_level_type": "platform_low",
  "resistance_price": 10.52,
  "resistance_zone_low": 10.45,
  "resistance_zone_high": 10.62,
  "resistance_distance_pct": 3.95,
  "resistance_strength": 76,
  "resistance_level_type": "volume_profile",
  "ma30": 9.91,
  "trend_above_ma30": true,
  "key_level_candidates": [
    {
      "price": 9.88,
      "zone_low": 9.82,
      "zone_high": 9.95,
      "direction": "support",
      "level_type": "platform_low",
      "strength_score": 82,
      "evidence": ["20日平台低点", "成交密集区", "MA30 共振", "涨停日 Anchored VWAP"],
      "invalid_condition": "放量跌破 9.82 且收不回，支撑降级"
    }
  ],
  "data_quality": "ok",
  "explanation": "当前离最近支撑约 2.37%，支撑来自平台低点、成交密集区和 MA30 共振；若放量跌破并收不回，支撑降级。",
  "warnings": []
}
```

## 18. 结论

`AKeyLevel Engine` 是当前平台最适合 A 股短线做 T 的支撑压力位方案。

它的优势是：

1. 可解释。
2. 可回测。
3. 可降级。
4. 适合 A 股涨跌停和事件驱动结构。
5. 能服务实时监控、策略跟踪、模拟盘和全市场复盘。
6. 不会把观察关键位误包装成交易建议。

## 19. 工程与口径增补（评审，2026-06-02）

> 本节是对上文的修订与补充，**实现时以本节为准**（与上文冲突处覆盖上文）。

### 19.1 复权口径（必须先定，否则历史关键位整体错位）
全部**日线级**候选（前高/前低、缺口、平台高低点、涨停日锚点、放量突破日、成交密集区、Anchored VWAP、MA5–MA60）统一使用**前复权(qfq)**，与 `backend/app/services/market/providers/akshare_history.py`（`adjust="qfq"`）一致；除权除息日历史价位必须复权对齐。盘中实时价为不复权现价时，比较前换算到同一口径。schema 输出 `adjust_mode`。

### 19.2 计算成本与缓存（重算走 worker，禁 Web 后台 loop）
全市场每张卡都要关键位，按请求同步算 Volume Profile + Anchored VWAP + swing + MA 成本过高，且违反 `engineering-conventions §5.3`。落地分两段：
1. **日线级关键位**：收盘后由 **worker 物化**进缓存/表（复用 `low_buy_materialization.py` / `monitor_snapshot_cache.py` 模式 + checkpoint 幂等），API 与监控/扫描只**读缓存**。
2. **盘中级关键位**：VWAP / 分时高低 / 接近提醒按需实时算（轻量）。
新增"日线物化任务"接入 runtime-task/worker；性能预算见 §19.12。

### 19.3 与现有能力收敛（勿造第二套）
1. 盘中关键位**已存在** `services/intraday_key_levels.py`（VWAP、昨收、整数关口 `_round_number_levels`、买点区，走 Go 读取），真实路由 **`GET /api/intraday/key-levels/stream`**；§10 的盘中 API 须对齐此路径或提供兼容层。
2. MA 复用 `services/indicators.py` 的 `moving_average(values, window)`，"补 MA30"= window=30 调用，勿重写。
3. 个股**已有** `entry_zone_low/high`、`stop_loss`（计划买点/止损）。关键位的 `support/resistance` 必须与之对账，前端分区标注"计划买点"vs"结构支撑/压力"，避免同页出现两个矛盾的"支撑/买点"。

### 19.4 评分校准、clamp 与版本
1. `strength_score` 最终 **clamp 到 [0,100]**（扣分叠加可为负）；低于阈值标 `research_only`、不展示为高可信。
2. §7 权重为先验，**Phase 4 命中率验证应反向校准**，不长期手填。
3. schema 加 `engine_version`/`score_version`，回测可复现、报告口径可追溯（§6.6）。

### 19.5 机器可读失效与条件预警
`invalid_condition` 保留文案，同时新增结构化失效：`invalidate_below`（跌破价）、`invalidate_volume_x`（放量倍数），用于驱动盘中"接近/跌破"**SSE 条件预警**并接入飞书/多渠道通知——顺带补上平台目前缺的主动预警能力。

### 19.6 整数关口分级与盘中边界
"整数关口"步长按价格量级缩放（如 <5 元 0.1/0.5、5–20 元 0.5/1、20–100 元 1/5、>100 元 5/10），复用并扩展现有 `_round_number_levels`。盘中 VWAP/分时高低只用当日数据，不引未来。

### 19.7 板块代理序列定义
A 股多数主题板块无干净可交易指数，"板块代理序列"必须显式定义：构造法（等权 / 成交额加权 / 自由流通市值加权）、成分来源与稳定性、再平衡频率；板块层有**独立 data_quality**，代理不可信时个股不得因缺板块数据伪装高可信（呼应 §5.2 边界）。

### 19.8 命中率验证口径（Phase 4 先写死定义）
1. 明确"命中/反弹/失效"的可计算定义（如：触达=进支撑区间；有效=N 日内自支撑反弹≥X%；失效=放量跌破区间下沿且 M 日未收回）。
2. 含**退市/ST/停牌**样本防幸存者偏差；分行情状态、分行业、分流动性分层。
3. 做**样本外(OOS)/滚动验证**，不只看 24M 样本内总命中率（§6.6）。
4. 回测大 JSON 落 `backend/data/.../reports`，`docs/reports/` 只放 Markdown 摘要（§6.7）。

### 19.9 停牌、新股、一字板边界
MA/密集区窗口按**交易日**计（非自然日）；停牌洞、上市不足窗口 → `insufficient`；一字板(开=高=低=收)使 Anchored VWAP 退化，须走 §7 扣分并降级，不得给高分。

### 19.10 三层联动给量化阈值
§5.4 的"强/弱"落到系数，例如：大盘跌破关键支撑 → 板块与个股支撑分 ×0.7；板块跌破支撑 → 板块内个股支撑可信度 ×0.8；任一层数据不足 → 对应层标记并整体降一档。系数在 Phase 3 校准。

### 19.11 数据质量打通数据中心
关键位 `data_quality` 用统一枚举（`ok/insufficient/stale/blocked/research_only`），并把"关键位数据集"纳入已建**数据中心 / SLA**，缺数据可见、可回补。

### 19.12 Feature flag / 性能预算 / 回退 / 验收命令
1. **Feature flag**：新能力默认 `off`（研究/重任务，§6.3）；关闭时监控/分析回到既有展示，不出现空块或假分。
2. **性能预算**：单股 API P95 < 300ms（读缓存）；全市场日线物化收盘后在既定时窗内完成；盘中 SSE 增量轻量。
3. **回退**：关 flag 即隐藏关键位面板与 API 入口；物化表可丢弃重建；不影响现有策略/回测/排序。
4. **验收命令**：后端 `key_levels` 相关 pytest（MA/支撑/压力/密集区/AnchoredVWAP/区间合并/评分 clamp/复权一致/未来函数/停牌边界/schema）；前端 `lint + typecheck + build:web`，`smoke:responsive` 相关页 375/768/1440 视口 0 横滚；契约改动跑 `api:check`。

### 19.13 Schema 新增字段（汇总，已写入 §9）
- `KeyLevelResult` 增：`engine_version`、`as_of`、`adjust_mode`、`intraday_included`。
- `KeyLevelCandidate` 增：`invalidate_below`、`invalidate_volume_x`。
- §14 测试相应补：复权一致、评分 clamp、整数关口分级、停牌/新股/一字板降级、机器可读失效字段。
