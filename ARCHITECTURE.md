# A股短线做T量化系统架构图

## 整体架构

```mermaid
flowchart LR
    U["用户 / 交易研究员"]

    subgraph FE["前端 Web 应用 (React + TypeScript + ECharts)"]
        FE1["实时监控页<br/>Watchlist Dashboard"]
        FE2["量化分析页<br/>Analysis Workbench"]
        FE3["研究复盘页<br/>Research & Backtest"]
        FE4["系统配置页<br/>Settings"]
    end

    subgraph API["后端 API 层 (FastAPI)"]
        API1["市场接口<br/>/api/instruments /quote /kline"]
        API2["分析接口<br/>/api/analyze /analyze/batch"]
        API3["研究接口<br/>/api/replays /backtests"]
        API4["配置接口<br/>/api/settings"]
        API5["自选池接口<br/>/api/watchlist"]
    end

    subgraph CORE["核心服务层"]
        S1["MarketDataService<br/>行情/标的/板块/事件"]
        S2["MarketRuleService<br/>交易制度识别<br/>T+0 / T+1 / 底仓做T"]
        S3["QuantEngine<br/>可交易性过滤<br/>多周期共振<br/>VWAP量价结构<br/>正T/反T建议"]
        S4["AiService<br/>OpenAI兼容大模型接入"]
        S5["ResearchService<br/>信号日志 / 复盘 / 回测"]
        S6["SettingsService<br/>运行配置读写"]
    end

    subgraph DATA["数据源层"]
        D1["免费实时行情<br/>Eastmoney Quote / Kline"]
        D2["股票列表源<br/>交易所官方清单 / AkShare"]
        D3["ETF列表源<br/>Sina ETF / AkShare"]
        D4["行业/事件源<br/>东财个股资料 / 新闻 / 公告"]
        D5["自定义数据源接口<br/>可扩展"]
        D6["大模型服务<br/>OpenAI兼容 API"]
    end

    subgraph DB["持久化层"]
        DB1["SQLite 默认库<br/>backend/data/t_quant.db"]
        DB2["可切换外部数据库<br/>MySQL / PostgreSQL"]
        DB3["核心表<br/>instruments<br/>instrument_rules<br/>watchlist<br/>system_settings<br/>analysis_logs<br/>signal_replays<br/>backtest_runs<br/>market_events"]
    end

    U --> FE
    FE --> API

    API1 --> S1
    API1 --> S2
    API2 --> S1
    API2 --> S2
    API2 --> S3
    API2 --> S4
    API2 --> S5
    API3 --> S5
    API4 --> S6
    API5 --> S1
    API5 --> S5

    S1 --> D1
    S1 --> D2
    S1 --> D3
    S1 --> D4
    S1 --> D5
    S4 --> D6

    S1 --> DB
    S2 --> DB
    S5 --> DB
    S6 --> DB
```

## 核心分析链路

```mermaid
flowchart TD
    A["用户选择标的并发起分析"] --> B["/api/analyze"]
    B --> C["读取系统配置"]
    C --> D["获取标的基础信息"]
    D --> E["获取实时行情 + 分钟K线"]
    E --> F["识别交易制度<br/>股票T+1 / ETF T+0或T+1"]
    F --> G["计算量化特征<br/>MA / RSI / MACD / ATR / VWAP / 量比"]
    G --> H["可交易性过滤<br/>流动性 / 振幅 / 风险事件"]
    H --> I["做T策略判断<br/>正T / 反T / 观望"]
    I --> J["动态仓位 / 止损 / 止盈 / 风险评级"]
    J --> K["可选AI增强解释"]
    K --> L["结果写入分析日志与复盘表"]
    L --> M["返回前端展示"]
```

## 部署结构

```mermaid
flowchart LR
    B["浏览器"]
    V["前端静态站点<br/>Vercel / CDN"]
    F["FastAPI 后端服务<br/>云主机 / 容器 / Serverless"]
    C["Docker 持久部署<br/>单容器 / 双容器"]
    S["SQLite 或 外部数据库"]
    M["外部行情源 / 大模型源"]

    B --> V
    V --> F
    B --> C
    C --> S
    C --> M
    F --> S
    F --> M
```

## 架构说明

- 前端负责展示、交互、图表和配置输入，不直接处理策略判断。
- 后端负责统一接入行情、制度识别、量化引擎、AI增强、研究回测。
- 数据源层采用“默认免费接口 + 可配置扩展”的设计，保证开箱即用。
- 数据库默认使用 SQLite，便于本地运行；生产环境可切换为外部数据库。
- 分析结果和回测结果都持久化，便于复盘和后续策略优化。
