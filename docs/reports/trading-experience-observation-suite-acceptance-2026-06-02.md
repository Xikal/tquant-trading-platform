# A 股交易经验观察与复盘套件验收报告

生成日期：2026-06-02

## 范围

本轮按 `docs/trading-experience-observation-suite-final-execution-plan-2026-06-02.md` 落地 G0-G6：

1. Feature flags、API/schema、禁词守卫、生产隔离守卫。
2. 每日复盘池与交易纪律日志。
3. 量价-位置风险标签与相对强度事实榜。
4. 模拟盘持仓纪律助手。
5. 涨停后形态研究门，由 runtime task 物化 24M 回测门；数据不足输出 `blocked`，未达标输出 `research_only`。
6. 做 T 效果归因，分钟数据不足输出 `no_data`，成交字段不完整输出 `insufficient`。
7. OpenAPI/generated 同步与 flag 回退验证。

## 生产隔离结论

- 未修改 `strategy_policy`。
- 未替换 low-buy、priority board、front-row weighted 或任何现有生产排序。
- 新增 response 和 UI 不输出 `production_score`。
- `watch_score` 未被改写为生产分。
- 涨停后形态只读 `trading_experience_snapshots` 中的 24M 回测门；门禁 `failed` 时仅 `research_only`，`blocked` 时明确原因；不会进入观察排序或生产排序。

## Feature Flag 回退

默认新增 flags 全部为 `false`：

- `TRADING_EXPERIENCE_SUITE_ENABLED=false`
- `TRADE_REVIEW_SUITE_ENABLED=false`
- `VP_POSITION_TAGS_ENABLED=false`
- `RELATIVE_STRENGTH_BOARD_ENABLED=false`
- `HOLDING_DISCIPLINE_ASSISTANT_ENABLED=false`
- `LIMIT_UP_FOLLOWTHROUGH_ENABLED=false`
- `T_TRADE_DISCIPLINE_ENABLED=false`

关闭全部 flags 后：

- 策略跟踪不显示复盘、纪律日志、抗跌事实入口。
- 模拟盘不显示持仓纪律和 T 归因面板。
- 监控、策略跟踪、模拟盘、回测和生产排序保持既有行为。
- runtime task 仍受研究任务门控，不由 Web 请求启动后台 loop。
- 关闭量价标签 flag 后，监控页、策略详情、关键位区域不请求 `/trading-experience/volume-position-tags/*`。

## 数据质量与文案

- 所有新增 API response 带 `data_quality`、`as_of`、`engine_version`、`source`、`research_only` 或等价字段。
- 缺数据或研究门未满足时显式返回 `insufficient`、`no_data`、`blocked`、`stale` 或 `research_only`。
- 量价标签和持仓纪律复用 AKeyLevel 缓存；缺关键位数据时输出 `insufficient`，不使用近几日高低点替代。
- T 归因使用 `paired_cashflow_vs_hold` 对照算法，并展示成交完整性、分钟覆盖和 AKeyLevel 状态。
- “主力出货/洗盘/吸筹/对倒”未作为事实输出，相关经验转为可观测价量标签。
- 新增守卫阻断交易指令词和 `production_score`。

## 验收命令

- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_trading_experience_*.py -q`：40 passed，1 个 LibreSSL/urllib3 上游 warning。
- `cd frontend && npm run api:check`：通过，OpenAPI hash `6b778f722715bba6b1aba8378beb35aced215e4ba135b4f1d264027c394ad6e5`。
- `cd frontend && npm run lint`：通过。
- `cd frontend && npm test -- --run`：57 files / 170 tests passed。输出中的 state separation 失败文本来自负向 fixture，退出码为 0。
- `cd frontend && npm run build`：通过。
- `cd frontend && npm run analyze`：通过，写入 `frontend/dist/bundle-report.json`。
- `cd frontend && SMOKE_MOCK_AUTH=1 npm run smoke:responsive`：通过，写入 `frontend/dist/responsive-smoke-report.json`，覆盖 375px / 768px / 1440px。
- `git diff --check`：通过。

## G0-G6 完成情况

- G0：完成。新增 flags、schema/API、禁词守卫和生产隔离守卫。
- G1：完成。每日复盘池、交易纪律日志和前端快速记录已落地。
- G2：完成。量价-位置标签复用 AKeyLevel；相对强度/抗跌事实榜使用 `DataTable`。
- G3：完成。持仓纪律助手复用 AKeyLevel 和 paper 持仓，缺关键位输出 `insufficient`。
- G4：完成。`trading_experience_limit_up_backtest` 真实计算 24M 回测门，输出 winrate、PF、max drawdown、sample count、quarter stability；Web 读快照。
- G5：完成。T 归因覆盖成交完整性、分钟覆盖、配对现金流对照和关键位状态。
- G6：完成。OpenAPI/generated 已同步，全量验收命令与 `git diff --check` 已通过。

## 未完成/阻断项

- 当前无代码阻断项。
- 若生产或本地真实日线不足 24M，G4 会按设计输出 `blocked` / `insufficient_24m_daily_bars`，不会伪造指标。
