# TQuant Agent OS 实施计划（终版）

**日期**: 2026-05-04
**基于**: Claude 项目审查（82 项）→ Codex 复核（裁剪至 27 项）→ GitHub 10 项目调研 → Hermes 现状核验 → 最终方案
**目标**: 将 TQuant 从 Pilot-ready 推向 Production-ready，基于现有 Hermes Agent 基础设施建立可持续的量化研究体系

---

## 〇、Hermes 当前接入状态（基线）

在制定实施计划前，先确认已有的 Hermes Agent 基础设施。以下全部**已实现**：

### 0.1 Agent Provider 体系

```
backend/app/agent_providers/
├── base.py              → AgentProvider 抽象基类
├── factory.py           → 9 个 provider 统一工厂（按 agent_provider 配置路由）
├── hermes_provider.py   → Hermes 适配器（当前生产 provider）★
├── mcp_provider.py      → MCP 协议适配器
├── langgraph_provider.py
├── openai_agents_provider.py
├── crewai_provider.py
├── openclaw_provider.py
├── pydantic_ai_provider.py
├── custom_http_provider.py
├── none_provider.py
└── remote_gateway.py    → RemoteAgentGatewayClient（Hermes 通过它调用工具）
```

**关键设计**：`HermesProvider` 是适配器模式。Hermes 在外部编排 prompt，但工具执行永远在 TQuant 的 Agent Safe API 内完成。Hermes 不获得数据库或 shell 访问权。

### 0.2 Agent API 路由（已完整实现）

```
/api/agent/                           → router.py:41（auth: require_current_user_or_agent_token）
├── GET  /health                      → 项目与 Agent 能力层健康状态
├── GET  /context/watchlist           → 自选和持仓监控摘要
├── GET  /context/priority-board      → 全策略优先级榜（limit 1-50）
├── POST /context/analysis            → 单只股票做T条件分析
├── GET  /context/paper-portfolio     → 模拟盘账户/持仓/绩效
├── POST /context/recommend-orders    → 模拟委托建议（不执行下单）
├── GET  /reports/daily               → 规则化每日复盘报告
├── POST /notify/test                 → 测试通知通道
├── POST /notify/signal               → 去重信号通知
├── POST /notify/scan-priority-board  → 扫描优先级榜发通知
├── GET  /provider/status             → provider 状态 + 工具清单
└── POST /provider/invoke             → 直接工具调用（admin only）
```

### 0.3 Agent Tools 清单（10 个，已实现）

| 工具名 | 方法 | 权限 | 描述 |
|--------|------|------|------|
| `get_agent_health` | GET | read | Agent 健康状态 |
| `get_watchlist_context` | GET | read | 自选持仓监控 |
| `get_priority_board` | GET | read | 全策略优先级榜 |
| `analyze_stock` | POST | read | 单股做T分析 |
| `get_daily_report` | GET | read | 每日复盘报告 |
| `get_paper_portfolio` | GET | read | 模拟盘摘要 |
| `recommend_orders` | POST | write | 委托建议（不执行） |
| `send_test_notification` | POST | notify | 测试通知 |
| `send_signal_notification` | POST | notify | 去重信号通知 |
| `scan_priority_board_notifications` | POST | notify | 扫描并发送信号通知 |

### 0.4 安全模型（已实现）

- **三级权限**：`read` / `write` / `notify`（`agent_tools/policy.py`）
- **Write 工具默认禁用**：`agent_enable_write_tools=False`
- **Notify 工具默认禁用**：`agent_enable_notify_tools=False`
- **审计默认开启**：`agent_audit_enabled=True`
- **双重认证**：`require_current_user_or_agent_token`（用户 token 或 agent token）
- **Admin 隔离**：`/api/agent/provider/invoke` 仅 admin（`require_admin_auth`）

### 0.5 配置键

```python
# backend/app/core/config.py
agent_provider: str = "none"           # "hermes" | "mcp" | "langgraph" | ...
agent_api_token: str = ""             # Agent 调用 TQuant API 的 token
hermes_api_url: str = ""              # Hermes orchestrator URL
hermes_api_key: str = ""              # Hermes API key
agent_enable_write_tools: bool = False
agent_enable_notify_tools: bool = False
agent_audit_enabled: bool = True
agent_timeout_seconds: int = 10
agent_allowed_capabilities: list[str] = []
```

### 0.6 已接入的后台任务

`main.py` 中已有 Agent 信号扫描定时循环：
```python
task_manager.register_loop(
    name="agent_priority_notifications",
    target=_scan_priority_notifications_once,
    interval_seconds=max(settings.notification_signal_scan_interval_seconds, 30),
)
```

---

## 一、Codex 开源项目分析验证

Codex 对 10 个 GitHub 项目的分析经逐项核实，结论准确。核实星标（2026-05 实时）：

| 项目 | Codex 定位 | 核实星标 | 对本项目价值 |
|------|-----------|---------|------------|
| **QuantDinger** | Agent Gateway / MCP / 审计 / paper-only | **1,000+** | Agent 安全边界设计参考 |
| **daily_stock_analysis** | 每日报告 + 多渠道推送 | **31,100+** | 报告结构 + 推送机制 |
| **TradingAgents** | 多 Agent 交易决策框架 | **65,000+** | 角色分工 + 辩论→决策流程 |
| **TradingAgents-CN** | A 股本地化 | **24,700** | ⚠️ `app/`/`frontend/` 专有授权，不能碰代码 |
| **qlib** | 因子验证 + 回测标准化 | **41,000+** | 离线研究环境 |
| **Vibe-Trading** | 自然语言→策略→回测 | **4,000+** | 71 技能 + MCP 工具设计 |
| **OpenBB** | 统一金融数据平台 | **66,600+** | 海外/宏观数据扩展 |
| **FinceptTerminal** | C++/Qt6 终端 | **17,800** | 技术栈不匹配，仅参考 UI |
| **last30days-skill** | 30 天热点研究 | **12,500** | 仅辅助研究，非交易信号 |
| **scientific-agent-skills** | Agent Skills 标准 | **16,400** | SKILL.md 格式参考 |

---

## 二、总体架构：基于 Hermes 的 Agent OS

```
┌─────────────────────────────────────────────────────────────────┐
│                     TQuant Agent OS                              │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Web 前端 │  │ 移动 App │  │ 飞书 Bot │  │ Hermes 对话   │  │
│  │ React 18 │  │ Capacitor│  │ Webhook  │  │ 外部编排      │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬───────┘  │
│       └──────────────┴─────────────┴─────────────────┘          │
│                          │ FastAPI                               │
│  ┌───────────────────────┼───────────────────────────────────┐  │
│  │         现有 Agent Safe API (/api/agent/*) — 已完成 ✓      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │  │
│  │  │Token Auth│ │Policy    │ │Audit Log │ │10 Tools     │ │  │
│  │  │(双重认证)│ │(read/write│ │(agent_    │ │(registry.py)│ │  │
│  │  │          │ │ /notify)  │ │ audit_    │ │             │ │  │
│  │  │          │ │          │ │ enabled)  │ │             │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └─────────────┘ │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                          │                                       │
│  ┌───────────────────────┼───────────────────────────────────┐  │
│  │     Phase 2 新增：Multi-Agent 研究流 (Hermes 编排)        │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │  │
│  │  │市场状态│ │板块热点│ │技术分析│ │策略验证│ │组合经理│ │  │
│  │  │Analyst │ │Analyst │ │Analyst │ │Validator│ │  PM    │ │  │
│  │  └────┬───┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ │  │
│  │       └──────────┴──────────┴──────────┴──────────┘       │  │
│  │                          │                                  │  │
│  │              已有 10 个 Tools 作为共享工具层               │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                          │                                       │
│  ┌───────────────────────┼───────────────────────────────────┐  │
│  │              策略引擎 (现有)                               │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────────────┐ │  │
│  │  │12 策略 │ │市场状态│ │风控系统│ │模拟盘 (T+1 规则)   │ │  │
│  │  └────────┘ └────────┘ └────────┘ └────────────────────┘ │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                          │                                       │
│  ┌───────────────────────┼───────────────────────────────────┐  │
│  │              数据层                                       │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────────────┐ │  │
│  │  │AkShare │ │东方财富│ │Tushare │ │OpenBB Adapter(P2)  │ │  │
│  │  │(主)    │ │(补)    │ │(备)    │ │海外/宏观 扩展      │ │  │
│  │  └────────┘ └────────┘ └────────┘ └────────────────────┘ │  │
│  └───────────────────────┬───────────────────────────────────┘  │
│                          │                                       │
│  ┌───────────────────────┼───────────────────────────────────┐  │
│  │              qlib 离线研究环境 (P2)                        │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────────────┐ │  │
│  │  │因子挖掘│ │模型训练│ │标准化  │ │RD-Agent            │ │  │
│  │  │Alpha158│ │LightGBM│ │回测    │ │自动因子→模型联合   │ │  │
│  │  └────────┘ └────────┘ └────────┘ └────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**关键原则**：所有 Agent 功能基于现有 Hermes 基础设施扩展。不引入新的 Agent 框架。Hermes 负责外部 prompt 编排，TQuant 负责工具执行和安全边界。

---

## 三、Phase 1：安全加固 + Hermes 能力扩展（本周，P0）

### 3.1 安全修复（5 项，来自最终裁定 P0）

| # | 文件 | 当前代码 | 修改 | 验证 |
|---|------|---------|------|------|
| S1 | `feishu/feishu_app.py:14-17` | `if not expected: return True` | → `return False` | 空 token 时 webhook POST → 401 |
| S2 | `Dockerfile:34` | `CMD ["python", "-m", "uvicorn", ...]` | → `RUN useradd -m tquant && USER tquant` + gunicorn 4 workers | `id` → uid≠0；wrk 压测 |
| S3 | `core/admin_auth.py:24` | `HTTP_500_INTERNAL_SERVER_ERROR` | → `HTTP_503_SERVICE_UNAVAILABLE` | 无 token 调 admin → 503 |
| S4 | `market/intraday.py:73-79` | f-string 构建 Python 脚本无校验 | → `re.match(r'^[A-Za-z0-9]+$', symbol)` 前置 | 特殊字符 → ValueError |
| S5 | `core/rate_limit.py` | InMemorySlidingWindow | → 文件锁计数器短期方案；长期 Redis | 俩 worker 各 50 请求 → 总量 60 限 |

### 3.2 Hermes 工具扩展：从 10 个工具扩展到 16 个

当前已有 10 个工具（`registry.py`）。新增 6 个工具，补齐策略研究和模拟盘操作能力：

```python
# 新增工具（添加至 registry.py 的 _tool_registry()）

# 11. 策略回测（新增）
ToolDefinition(
    name="backtest_strategy",
    description="对指定策略执行指定周期的回测，返回绩效摘要",
    method="POST",
    path="/api/agent/context/backtest",
    input_schema={
        "type": "object",
        "required": ["strategy_key"],
        "properties": {
            "strategy_key": {"type": "string"},
            "lookback_days": {"type": "integer", "default": 60, "minimum": 20, "maximum": 250},
        },
    },
    permission="read",
    timeout_seconds=60,  # 回测可能较慢
),

# 12. 策略对比（新增）
ToolDefinition(
    name="compare_strategies",
    description="对比多个策略在相同周期内的绩效差异",
    method="POST",
    path="/api/agent/context/compare-strategies",
    input_schema={
        "type": "object",
        "required": ["strategy_keys"],
        "properties": {
            "strategy_keys": {"type": "array", "items": {"type": "string"}},
            "lookback_days": {"type": "integer", "default": 60},
        },
    },
    permission="read",
    timeout_seconds=90,
),

# 13. 模拟盘下单（新增，write 权限，默认禁用）
ToolDefinition(
    name="create_paper_order",
    description="创建模拟盘订单（不执行实盘交易）",
    method="POST",
    path="/api/agent/paper/order",
    input_schema={
        "type": "object",
        "required": ["symbol", "side", "quantity", "price"],
        "properties": {
            "symbol": {"type": "string"},
            "side": {"type": "string", "enum": ["buy", "sell"]},
            "quantity": {"type": "integer", "minimum": 100, "maximum": 1000000},
            "price": {"type": "number", "minimum": 0.01},
            "account_id": {"type": ["integer", "null"]},
        },
    },
    permission="write",
    timeout_seconds=30,
),

# 14. 市场情绪概览（新增）
ToolDefinition(
    name="get_market_sentiment",
    description="获取市场情绪摘要：涨停/跌停数、炸板率、连板高度、资金流向",
    method="GET",
    path="/api/agent/context/market-sentiment",
    input_schema={"type": "object", "properties": {}},
    permission="read",
    timeout_seconds=15,
),

# 15. 板块热度排行（新增）
ToolDefinition(
    name="get_sector_heatmap",
    description="获取板块涨跌幅排行、资金流向、涨停数分布",
    method="GET",
    path="/api/agent/context/sector-heatmap",
    input_schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 20, "minimum": 5, "maximum": 50},
        },
    },
    permission="read",
    timeout_seconds=15,
),

# 16. 持仓做T信号（新增）
ToolDefinition(
    name="get_position_t_signal",
    description="获取指定持仓的正T/反T信号和建议操作",
    method="POST",
    path="/api/agent/context/position-t-signal",
    input_schema={
        "type": "object",
        "required": ["symbol"],
        "properties": {
            "symbol": {"type": "string"},
            "shares": {"type": "integer"},
            "cost_basis": {"type": "number"},
        },
    },
    permission="read",
    timeout_seconds=15,
),
```

### 3.3 Per-Agent Scoped Token（扩展当前单一 agent_api_token）

当前只有全局 `agent_api_token`。新增 per-agent 独立 token + scope 限制：

```python
# backend/app/core/agent_auth.py（新增文件）

# 配置格式（环境变量或 .env）
# AGENT_TOKENS='{"agent-analyst":"tk_xxx:read","agent-trader":"tk_yyy:read,write_paper"}'

@dataclass
class AgentTokenConfig:
    token_hash: str
    scopes: list[str]
    rate_limit_per_hour: int = 100
    paper_only: bool = True  # 永远不能创建实盘订单

# 在 require_current_user_or_agent_token 中扩展：
# 1. 先尝试用户 token（现有逻辑）
# 2. 再尝试 agent token → 解析 scope → 注入 request.state.agent_scopes
# 3. 后续工具调用检查 scope
```

### 3.4 审计日志增强

审计已有 `agent_audit_enabled=True` 基础设施。增强为结构化记录：

```python
# 扩展 backend/app/agent_tools/audit.py

# 每次工具调用记录：
# - agent_id（从 token 解析）
# - tool_name + params_snapshot（脱敏后）
# - result_summary（前 200 字符）
# - outcome: success | denied | error
# - latency_ms
# - timestamp + ip_address

# 新增查询端点：
# GET /api/agent/audit?agent_id=xxx&tool=yyy&limit=50  → admin only
```

---

## 四、Phase 2：Hermes Multi-Agent 研究流 + 每日报告升级（本月，P1）

### 4.1 核心理念：Hermes 编排 + TQuant 工具层

```
外部 Hermes 实例（prompt 编排）
         │
         │ HTTP + agent_api_token
         ▼
┌────────────────────────────────────┐
│  TQuant Agent Safe API             │
│  /api/agent/* （已完成）            │
│                                    │
│  ┌──────────────────────────────┐ │
│  │ 新增：Research Orchestrator  │ │
│  │ (backend/app/services/       │ │
│  │  agent_research/)            │ │
│  │                              │ │
│  │ 这不是新的 Agent 框架。       │ │
│  │ 它是 5 个预设的分析上下文，   │ │
│  │ 每个上下文调用已有的 Tools。  │ │
│  │ Hermes 负责编排调用顺序。    │ │
│  └──────────────────────────────┘ │
└────────────────────────────────────┘
```

### 4.2 五个 Research Context（新增 API 端点）

在现有 `/api/agent/` 下新增 5 个复合端点，每个端点聚合多个底层数据的分析结果：

```python
# backend/app/api/routes/agent.py 新增路由

# 17. 市场状态分析上下文
@router.get("/context/market-state-analysis")
def agent_market_state_analysis(db: Session = Depends(get_db)):
    """聚合：市场状态(8分类) + 涨停/跌停/炸板 + 资金流向 + 情绪周期 + 仓位建议"""
    return AgentResearchService(db).market_state_analysis()

# 18. 板块主线分析上下文
@router.get("/context/sector-mainline-analysis")
def agent_sector_mainline_analysis(db: Session = Depends(get_db)):
    """聚合：板块涨跌排行 + 资金流向 + 涨停分布 + 主线持续性判断"""
    return AgentResearchService(db).sector_mainline_analysis()

# 19. 策略交叉验证上下文
@router.post("/context/strategy-cross-validation")
def agent_strategy_cross_validation(
    symbols: list[str], db: Session = Depends(get_db)
):
    """对给定股票列表，交叉验证所有策略的信号一致性"""
    return AgentResearchService(db).cross_validate(symbols)

# 20. 风控检查上下文
@router.post("/context/risk-check")
def agent_risk_check(
    proposals: list[dict], db: Session = Depends(get_db)
):
    """对候选订单做仓位上限、行业集中度、单票风险暴露检查"""
    return AgentResearchService(db).risk_check(proposals)

# 21. 综合决策上下文（Multi-Agent 研究的入口）
@router.post("/context/comprehensive-analysis")
def agent_comprehensive_analysis(
    symbols: list[str], db: Session = Depends(get_db)
):
    """一键执行完整研究链路：
    market_state → sector_heat → technical → cross_validation → risk → decision
    返回结构化决策报告
    """
    return AgentResearchService(db).comprehensive_analysis(symbols)
```

### 4.3 Multi-Agent 角色 Prompt 模板（给 Hermes 使用）

这些 prompt 不是代码——它们是给 Hermes 的 system prompt 模板，定义每个角色的分析职责。参考 TradingAgents 的分析师→辩论→决策三阶段流程。

```
## 市场状态分析师
你是一位专注A股市场状态的量化分析师。
可用工具：get_market_sentiment, get_priority_board, get_agent_health

分析流程：
1. 调用 get_market_sentiment 获取涨停/跌停/炸板率/成交额/连板高度
2. 基于 8 类市场状态分类器判定当前状态
3. 输出：
   - 市场状态 + 置信度（0-100%）
   - 建议仓位范围（15%-65%）
   - 3 个关键风险提示
   - 与上一交易日的变化趋势

## 板块热点分析师
你是一位专注A股板块轮动的量化分析师。
可用工具：get_sector_heatmap, get_priority_board

分析流程：
1. 调用 get_sector_heatmap 获取板块涨跌排行和资金流向
2. 识别主线板块（连续 3+ 日资金净流入 + 涨停数 > 3）
3. 输出：
   - TOP 3 主线板块 + 持续性评分
   - 各板块核心标的（含信号状态）
   - 板块轮动风险提示

## 技术面分析师
你是一位专注技术形态的量化分析师。
可用工具：analyze_stock, get_priority_board, get_position_t_signal

分析流程：
1. 对每个给定标的调用 analyze_stock
2. 检查：均线位置、量能结构、支撑/压力、回调天数
3. 输出：
   - 每只标的的技术评分 + 买点区
   - 正T/反T信号 + 建议操作
   - 止损位和止盈位

## 策略验证员
你是一位负责交叉验证的分析师。
可用工具：compare_strategies, backtest_strategy

分析流程：
1. 对比市场状态分析师、板块分析师、技术分析师的结论
2. 标记三方结论一致的标的（高置信度）
3. 标记存在矛盾的标的（需人工判断）
4. 输出：
   - 高置信度候选列表
   - 矛盾信号列表 + 矛盾原因

## 组合经理
你是一位负责最终决策的组合经理。
可用工具：recommend_orders, get_paper_portfolio, create_paper_order

分析流程：
1. 接收策略验证员的输出
2. 对高置信度候选执行仓位分配（单票 ≤ 20%，总仓位 ≤ 市场状态建议上限）
3. 生成模拟委托建议
4. 输出：
   - 最终决策报告（含操作检查清单）
   - 模拟委托列表（不自动执行）
```

### 4.4 Hermes 编排配置

```yaml
# hermes_orchestration.yaml （Hermes 端的配置，非 TQuant 代码）

research_workflow:
  name: "tquant_daily_research"
  schedule: "0 15 * * 1-5"  # 每个交易日 15:00

  phases:
    - phase: parallel_analysis
      agents: [market_state_analyst, sector_heat_analyst, technical_analyst]
      parallel: true

    - phase: cross_validation
      agent: strategy_validator
      depends_on: [parallel_analysis]

    - phase: decision
      agent: portfolio_manager
      depends_on: [cross_validation]

  output:
    format: "markdown"
    push_channels: ["feishu"]
```

### 4.5 每日决策报告升级

当前 `GET /api/agent/reports/daily` 已返回规则化报告。升级为 Multi-Agent 综合报告：

```markdown
# TQuant 每日决策报告
## {date} {weekday}

### 📊 市场概览（市场状态分析师）
- 市场状态：{state}（置信度 {confidence}%）| 昨日：{yesterday_state}
- 涨停 {up} 家 | 跌停 {down} 家 | 炸板率 {break}%
- 成交额 {amount} 亿 | 较昨日 {delta}%
- 建议仓位：{min}% - {max}%
- 风险等级：{risk_level}

### 🔥 板块主线（板块热点分析师）
| 排名 | 板块 | 涨幅 | 涨停数 | 净流入(亿) | 持续性 | 核心标的 |
|------|------|------|--------|-----------|--------|---------|
| 1 | {s1} | {p1}% | {c1} | {f1} | {d1} | {sym1}({sig1}) |

### 📈 持仓做T信号
| 代码 | 名称 | 持仓 | 成本 | 现价 | 浮动盈亏 | T信号 | 建议 |
|------|------|------|------|------|---------|-------|------|
| ... | ... | ... | ... | ... | ...% | 正T/反T | 买点区/观望 |

### 🎯 选股宝典 TOP 10
| 排名 | 代码 | 策略 | 评分 | 买点区 | 信号 | 三方一致 |
|------|------|------|------|--------|------|---------|
| 1 | {sym} | {strategy} | {score} | {zone} | {signal} | ✅/⚠️ |

### 🛡️ 风控检查（策略验证员）
- ⚠️ 行业集中度：{sector} 占比 {pct}%（上限 25%）
- ⚠️ 单票风险暴露：{symbol} 仓位 {pct}%（上限 20%）
- ✅ 总仓位 {total}% 在市场建议范围 {min}%-{max}% 内

### 📋 操作检查清单（组合经理）
- [ ] 市场状态是否允许开仓？
- [ ] 目标标的是否在主线板块？
- [ ] 三方分析师结论是否一致？
- [ ] 价格是否已进入买点区？
- [ ] 单票仓位是否 ≤ 20%？
- [ ] 止损位是否已设定？
- [ ] 是否为 T+1 买入日（卖出需检查可用股数）？
```

### 4.6 大文件拆分（与 4.1-4.5 并行）

| 文件 | 当前行数 | 拆分方案 | 目标 |
|------|---------|---------|------|
| `MobileApp.tsx` | 1059 | → `MobileAuthScreen` + 4 tab 组件 + editor sheet | 各 <250 |
| `PaperTradingPage.tsx` | 687 | → 提取 `OrderEntryModal`/`PositionTable`/`TradeHistory` | 主文件 <300 |
| `priority_board.py` | 906 | → `priority_merging` + `priority_ranking` + `priority_performance` | 各 <350 |
| `signals.py` | 855 | → `signal_rules/hard_buy` + `soft_buy` + `signal_state` | 各 <350 |

---

## 五、Phase 3：离线研究 + 数据扩展 + Skill 化（下月，P2-P3）

### 5.1 qlib 离线研究环境（P2）

```
research/                     ← 新建目录（独立于 backend/）
├── requirements.txt          ← qlib, lightgbm, pandas, ...
├── data_sync/
│   └── tquant_to_qlib.py     ← TQuant DB → qlib 格式
├── factor_research/
│   └── alpha_exploration.py  ← 因子探索
├── backtest/
│   ├── strategy_validation.py ← 3 个新策略标准化回测
│   └── benchmark.py          ← 基准对比
└── reports/                  ← 回测报告输出
```

**关键约束**：qlib 完全离线运行。结果人工审核后才可能影响策略参数。**永远不直接修改生产策略阈值。**

### 5.2 OpenBB 数据扩展适配器（P2）

```python
# backend/app/services/market/openbb_adapter.py

class OpenBBDataAdapter:
    """仅在 AkShare 不覆盖的领域使用：
    - 海外市场行情（港股/美股）
    - 宏观经济指标（GDP/CPI/利率）
    - 基本面数据（财报/分析师评级）

    A 股核心数据仍使用 AkShare/东方财富。
    """
```

### 5.3 Agent Skills 沉淀（P3）

参考 scientific-agent-skills 的 SKILL.md 标准：

```
skills/
├── tquant-strategy-review/SKILL.md     ← 策略审查流程
├── tquant-backtest-analysis/SKILL.md   ← 回测结果解读
├── tquant-daily-report/SKILL.md        ← 每日报告生成
└── tquant-code-review/SKILL.md         ← 代码审查清单
```

### 5.4 基础设施补齐（P2-P3）

| 任务 | 说明 |
|------|------|
| Prometheus `/metrics` | 请求量、延迟分布、错误率、策略信号数、Agent 工具调用量 |
| 慢接口 trace_id | structured logs 默认开启 + correlation_id middleware |
| CI 覆盖率门禁 | coverage.py + `<70%` 不通过 |
| pytest 迁移 | 34 测试文件 → pytest（fixtures/parametrize） |
| JWT 标准化 | 自定义 token → PyJWT HS256（含 exp/iat/iss） |
| Agent provider 骨架清理 | Hermes/OpenClaw/LangGraph 中仅 Hermes 完整实现，其余标记为 planned |

---

## 六、分阶段执行路线图

```
Week 1-2 ────── Phase 1: 安全 + Hermes 扩展
  ├── S1-S5: 安全 5 项修复 (5h)
  ├── 新增 6 个 Agent Tools + API 端点 (12h)
  ├── Per-agent scoped token (4h)
  └── 审计日志结构化增强 (3h)
  Total: ~24h

Week 3-4 ────── Phase 2a: Multi-Agent 研究上下文
  ├── 5 个 Research Context 端点 (16h)
  ├── 5 个 Agent Role prompt 模板 (6h)
  ├── Hermes 编排配置 + 联调 (8h)
  └── 测试：研究流 + Agent Tools 集成 (8h)
  Total: ~38h

Week 3-4 ────── Phase 2b: 大文件拆分 + 每日报告升级（与 2a 并行）
  ├── MobileApp.tsx 拆分 (6h)
  ├── PaperTradingPage.tsx 拆分 (4h)
  ├── priority_board.py 拆分 (4h)
  ├── signals.py 拆分 (4h)
  ├── 每日报告模板升级 (4h)
  └── 前端关键路径测试扩展 (6h)
  Total: ~28h

Week 5-8 ────── Phase 3: 离线研究 + Skill 化
  ├── qlib 环境 + 数据同步 (16h)
  ├── 3 个新策略标准化回测 (12h)
  ├── OpenBB adapter (8h)
  ├── Agent Skills 沉淀 (8h)
  ├── Prometheus + trace_id + 结构化日志 (12h)
  ├── CI 覆盖率门禁 + pytest 迁移 (12h)
  └── JWT 标准化 (8h)
  Total: ~76h

───────────────────────────
总计: ~166 工程小时，约 4-6 周（单人）
```

---

## 七、验收标准

### Phase 1 验收
- [ ] 5 项安全修复全部通过验证（见 3.1）
- [ ] 6 个新 Agent Tool 在 `/api/agent/provider/status` 中可见
- [ ] Per-agent token 可用不同 scope 调用工具
- [ ] 审计日志记录每次工具调用（agent_id + tool + outcome + latency）

### Phase 2 验收
- [ ] 5 个 Research Context 端点返回结构化分析结果
- [ ] Hermes 编排的 daily_research workflow 对 10 只标的产出完整报告
- [ ] 每日报告通过飞书推送（格式含市场概览 + 板块 + 做T + TOP10 + 风控 + 检查清单）
- [ ] 4 个大文件拆分为子模块，功能回归通过
- [ ] 前端关键路径（登录/选股/模拟下单）有组件测试

### Phase 3 验收
- [ ] qlib 离线环境对 3 个 AUXILIARY 策略产出标准化回测报告（IC/IR/Sharpe/MaxDD/胜率）
- [ ] OpenBB adapter 可查美股行情和宏观指标
- [ ] 3 个 TQuant Agent Skills 的 SKILL.md 可被 Claude Code 加载使用
- [ ] Prometheus `/metrics` 端点可访问
- [ ] CI coverage > 70%

---

## 八、不做的事（边界声明）

| 不做 | 原因 |
|------|------|
| 引入新的 Agent 框架替代 Hermes | Hermes 已在生产运行，provider/tools/audit 体系完整 |
| 复制 TradingAgents-CN 代码 | `app/` + `frontend/` 专有授权 |
| 接入 FinceptTerminal | C++/Qt，技术栈不兼容 |
| 让 Agent 操作实盘 | 永远 paper-only（`agent_enable_write_tools` 仅控制模拟盘写入） |
| 让 qlib 阻塞线上请求 | 独立离线环境，结果人工审核 |
| 让 last30days-skill 产出交易信号 | 社交媒体热点 ≠ A 股有效信号 |
| 用 OpenBB 替代 AkShare | A 股数据覆盖不如东方财富/AkShare |
| 重写 Agent Gateway | `/api/agent/*` 路由已完整，只需扩展端点 |
