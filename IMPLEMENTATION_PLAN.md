# TQuant 实施计划

## 2026-05-29 策略跟踪易用性增强

需求来源：

- 用户目标：严格按 `docs/strategy-tracking-usability-enhancement-development-plan-2026-05-29.md` 落地，把 `/strategy-tracking` 优化为普通用户也能看懂的推荐结果追踪看板。

### 执行边界

- [x] 新增能力只做展示、筛选、复盘和只读聚合，不改变策略推荐、策略排序、回测、模拟盘或真实交易。
- [x] 小白模式默认启用，默认屏蔽创业板和科创板；专业模式可展示完整审计字段。
- [x] 最优持有天数只作为后验复盘统计；短线转波段/中长线资格判断只读取推荐日及以前可见行情。
- [x] 列表继续后端分页，详情懒加载，持有分析后端聚合，前端不拉全量历史，不新增重型图表库。

### TODO

- [x] 后端列表新增 `board_type`、`board_type_text`、`industry_sectors`、`concept_sectors`、`display_sectors`、`user_friendly_status*`、`plain_language_summary`、`sector_detail`。
- [x] 后端支持 `exclude_chinext`、`exclude_star`、`board_filter`、`user_status`，并新增只读 `GET /api/strategy-tracking/holding-analysis`。
- [x] 板块来源按 payload 与 `Instrument.sector_name` 合并，缺失时降级为市场板标签或空板块提示，不阻塞列表。
- [x] 前端新增小白/专业模式、板块标签、状态卡、普通语言总结、创业板/科创板过滤、持有分析 tab 和单票详情时间线。
- [x] Go BFF 聚合接入 holding-analysis，并透传创业板/科创板过滤参数；partial response 仍由既有 `fetchSources` 降级逻辑处理。
- [x] 测试覆盖后端板块识别/过滤/持有聚合/只读边界、前端模式/文案/板块/持有分析/参数、Go BFF 参数透传。

### 验证

- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_tracking.py backend/tests/test_bff_routes.py -q` 通过，27 passed / 1 warning。
- [x] `cd frontend && npm test -- StrategyTrackingPage --run` 通过，9 passed。
- [x] `cd frontend && npm test -- webRoutes --run` 通过，10 passed。
- [x] `cd frontend && npm run build:web` 通过，包含 lint、TypeScript 与 Vite build。
- [x] `cd go-services/bff-gateway && go test ./...` 通过。
- [x] `cd rust/tquant-rs && cargo test` 通过，10 passed。
- [x] `git diff --check` 通过。

## 2026-05-29 平台瘦身与策略跟踪落地

需求来源：

- 用户目标：严格按 `docs/platform-slimming-and-strategy-tracking-development-plan-2026-05-29.md` 完整开发。
- 当前状态：指定开发文档已补齐并作为权威需求源；本轮已完成前端瘦身、策略跟踪页、Go 读聚合边界和验证闭环。

### 执行边界

- [x] 删除前端“策略工作台”真实入口和独立代码，保留后端策略、回测、选股宝典、模拟盘、设置页能力。
- [x] 删除前端“市场情绪”独立页签和页面代码，保留实时监控页中的市场宽度、情绪温度、龙头强度、data_quality、pulse。
- [x] 新增 `/strategy-tracking`，只做观察、复盘、统计，不影响生产策略排序、模拟盘交易或真实交易。
- [x] `/strategy` 重定向 `/backtest`，`/emotion` 重定向 `/monitor`。
- [x] 列表接口后端分页，默认 limit 不超过 50；前端详情走势懒加载。
- [x] 后验统计与信号日隔离：信号特征读取截至推荐日，后验行情只用于 tracking/evaluation 展示。
- [x] Go/Rust 按现有基础设施预留或接入：Go BFF 读聚合已接入，Rust wrapper/fallback 已用于最大回撤数值统计。

### TODO

- [x] 后端新增 strategy-tracking schema/service/routes，复用 `LowBuyResultSnapshot`、`LowBuyTradeLifecycleSnapshot`、`DailyBarSnapshot`。
- [x] 后端测试覆盖生产策略过滤、首次推荐、生命周期结束、最大涨幅、最大回撤、买点触达、止损触发、数据缺失降级、分页、刷新只读约束和路由鉴权。
- [x] 前端新增 strategy-tracking API/types/hooks/page/detail drawer，列表分页，详情懒加载和一键复盘摘要。
- [x] 前端路由、导航、命令面板、快捷键改造；删除旧策略工作台和市场情绪页面引用。
- [x] 删除确认未复用的旧前端页面代码和旧页面测试，保留共享策略元数据 API 与 monitor 情绪数据。
- [x] Go/Rust 边界测试与说明：Go BFF 接入只读聚合并保持缓存/partial response，Rust wrapper 用于最大回撤并保留 Python fallback。
- [x] 运行前端 lint/test/build、后端 pytest、Go test、Rust cargo test、diff 检查。

### 验证

- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/scripts/strategy_tracking_daily_refresh.py backend/app/services/strategy_tracking.py backend/app/services/strategy_tracking_builders.py backend/app/services/strategy_tracking_helpers.py backend/app/api/routes/strategy_tracking.py backend/tests/test_strategy_tracking.py` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_tracking.py backend/tests/test_finance_performance_math.py` 通过，16 passed / 1 warning。
- [x] `cd frontend && npm test -- StrategyTrackingPage webRoutes --run` 通过，2 files / 16 tests。
- [x] `cd frontend && npm run build:web` 通过，包含 lint、TypeScript 与 Vite build；`StrategyTrackingPage` chunk 约 14.64 kB gzip 4.94 kB，`LazyKlineChart` 独立懒加载。
- [x] `cd frontend && SMOKE_MOCK_AUTH=1 npm run smoke:responsive` 通过，27 个路径/视口组合均 ok；`/strategy-tracking` 在 375 / 768 / 1440 宽度下 `overflow_x=0`。
- [x] `cd go-services/bff-gateway && go test ./...` 通过。
- [x] `cd rust/tquant-rs && cargo test` 通过，10 passed。
- [x] 旧页面引用审计通过：`features/strategy`、`features/market-emotion` 已删除，剩余 `strategy` 字符串均为业务字段、纸面绩效或命令类型。

## 2026-05-29 ETF T0 24 个月分钟级与执行元数据补齐

需求来源：

- 用户目标：补 ETF T0 24 个月分钟级与执行元数据。
- 当前执行边界：只能写真实远端数据和可由 ETF universe / 成交额推导的元数据；禁止伪造分钟线、盘口价差、折溢价或 fresh/verified 状态；30m 只能作为探针，不能计入 5m 生产验收。

### 本轮完成

- [x] ETF 分钟线补数脚本改为遍历所有 provider 后选择交易日覆盖最宽的真实候选，避免 Eastmoney/AkShare 短窗口数据提前截断更长的 Sina 数据。
- [x] 新增 `backend/scripts/etf_minute_backfill_helpers.py`，统一 provider candidate、ETF bar enrichment、流动性分层和执行元数据质量判断。
- [x] 新增 `backend/scripts/backfill_etf_execution_metadata.py`，只回填跟踪指数和基于成交额的流动性等级；不伪造 `bid_ask_spread`、`premium_discount_pct` 或 `fresh/verified`。
- [x] 重跑 T0 ETF 5m 真实近端补数：`docs/reports/etf-minute-backfill-t0-5m-refresh-2026-05-29.json`，22 个 T0 ETF 均返回 Sina 真实 5m 数据，单标的 1,055-1,067 条，窗口仍仅 24 个交易日。
- [x] 重跑 T0 ETF 30m 覆盖探针：`docs/reports/etf-minute-backfill-t0-30m-best-provider-2026-05-29.json`，22 个 T0 ETF 均返回 Sina 真实 30m 数据，合计 39,976 条，228 个交易日，实际范围 2025-05-22 至 2026-04-28；该周期不计入 5m 生产验收。
- [x] 执行元数据回填报告已落盘：`docs/reports/etf-execution-metadata-backfill-t0-5m-2026-05-29.json` 与 `docs/reports/etf-execution-metadata-backfill-t0-30m-2026-05-29.json`。5m 扫描 24,344 行，跟踪指数和流动性覆盖 100%，盘口价差、折溢价、fresh/verified 覆盖仍为 0。
- [x] 生产门禁已锁定 5m 口径：`minute_coverage.bar_period=5m`，`etf_t0.bar_period=5m`，ETF 执行元数据门禁也跟随 5m；新增测试防止 30m 分钟线或 30m 元数据通过 5m 验收。
- [x] 刷新闭环、24M、优化和总验收报告：整体仍为只读 / 研究态，生产交易未放行。

### 当前仍阻断

- [ ] 24 个月 5m 分钟线不足：闭环报告 `window_bar_count=24344`，22 个 ETF 均只有 24 个交易日，按 466 个验收交易日计算覆盖率 5.15%，达标 ETF 0 / 22。
- [ ] 真实执行元数据不足：5m 盘口正价差覆盖 0.0%、折溢价覆盖 0.0%、fresh/verified 覆盖 0.0%；跟踪指数和流动性已 100%，但不足以生产放行。
- [ ] 本地未配置 `TUSHARE_TOKEN` / `TUSHARE_API_TOKEN` / `TUSHARE_PRO_TOKEN`；免费公开源当前无法提供完整 24 个月 5m / 1m ETF 历史和真实盘口/折溢价。
- [ ] 生产结论保持不变：`strategy-improvement-closed-loop-2026-05-28` 为 `blocked_or_research_only`，`formal_backtest_allowed=false`，`walk_forward_allowed=false`；`strategy-system-acceptance-report-2026-05-28` 为 `readonly_shadow_loop_complete_production_blocked`，`production_trade_ready=false`。

### 验证

- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py --start-date 2024-05-28 --end-date 2026-04-28 --period 30m --scope t0-etf --workers 3 --sleep 0.05 --force --allow-partial --report-output docs/reports/etf-minute-backfill-t0-30m-best-provider-2026-05-29.json` 通过，22/22 ok。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py --start-date 2024-05-28 --end-date 2026-04-28 --period 5m --scope t0-etf --workers 3 --sleep 0.05 --force --allow-partial --report-output docs/reports/etf-minute-backfill-t0-5m-refresh-2026-05-29.json` 通过，22/22 ok。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_execution_metadata.py --start-date 2024-05-28 --end-date 2026-04-28 --period 5m --scope t0-etf --report-output docs/reports/etf-execution-metadata-backfill-t0-5m-2026-05-29.json` 通过，跟踪指数和流动性回填到 100%，真实价差/折溢价仍阻断。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 通过，ETF T0 仍 `blocked_by_data`。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_24m_backtest_report.py --start 2024-05-28 --end 2026-04-28 --refresh-sections-only --existing-report docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-24m-backtest-2026-05-28.json --markdown-output docs/reports/strategy-24m-backtest-2026-05-28.md` 通过，ETF T0 仍 `partial_minute_coverage`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/generate_strategy_24m_optimization_report.py --date 2026-05-28 --source-date 2026-05-28` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/strategy_system_acceptance_report.py --date 2026-05-28` 通过，输出 `readonly_shadow_loop_complete_production_blocked` / `completion_pct=100.0`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_etf_execution_metadata_backfill.py backend/tests/test_strategy_24m_report_sections.py backend/tests/test_etf_minute_backfill.py` 通过，35 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/scripts/backfill_etf_minute_history.py backend/scripts/etf_minute_backfill_helpers.py backend/scripts/backfill_etf_execution_metadata.py backend/app/services/strategy_improvement/coverage.py backend/app/services/strategy_improvement/quality.py backend/scripts/strategy_24m_report_sections.py backend/tests/test_etf_minute_backfill.py backend/tests/test_etf_execution_metadata_backfill.py backend/tests/test_strategy_24m_report_sections.py backend/tests/test_strategy_improvement_closed_loop.py` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_etf_execution_metadata_backfill.py backend/tests/test_strategy_24m_report_sections.py backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_system_acceptance_report.py` 通过，37 passed / 1 warning。
- [x] `git diff --check` 通过。
- [x] 报告抽查通过：闭环 `minute_coverage.bar_period=5m`、`status=blocked_by_data`、`window_bar_count=24344`、`expected_trade_day_count=466`；执行元数据门禁 `bar_period=5m`、跟踪指数/流动性 100%、盘口价差/折溢价/fresh 0%；总验收 `production_trade_ready=false`。

## 2026-05-29 策略体系归类与模型闭环最小收尾

需求来源：

- 用户目标：按 `docs/strategy-system-consolidation-and-enhancement-development-plan.md` 落地策略体系归类、主力观测模型、老鸭头结构因子、止盈止损辅助模型、模拟盘只读验证、回测与调参闭环。
- 已补齐 `docs/strategy-system-consolidation-and-enhancement-development-plan.md`，本轮以该文档、用户目标正文和既有 `IMPLEMENTATION_PLAN.md` 为需求源继续执行。

### 执行边界

- [x] 不新增重复策略入口，不修改低吸原始买卖口径、回测成交语义、模拟盘账本、风控和自动交易约束。
- [x] 主力观测、老鸭头、止盈止损辅助模型保持旁路 / Shadow / 只读建议。
- [x] 排序影响默认 `none`；主力排序 bonus 仍由开关与 Shadow 晋级门槛控制，默认不污染原排序。
- [x] 本轮不做无边界补数和长时间爬取，仅刷新已有 24M 报告结构。

### 本轮完成

- [x] P0：补齐 17 个低吸策略族元数据，`ma_channel_band` 归为 `trend_support_band` / 均线通道支撑，`leader_pullback_band` 显示为龙头回踩波段。
- [x] P0：前端/接口继续使用 `family_sections`、`strategy_family`、`strategy_family_text`，旧 `items` 接口保留兼容。
- [x] P1：复核主力观测模型已旁路接入候选并写 Shadow；`main_force_model_ranking_enabled=False`，未达 Shadow 门槛不加权。
- [x] P1：老鸭头结构保持 `old_duck_head_factor` 因子化接入，不新增独立策略入口。
- [x] P1：止盈止损辅助模型已接入模拟盘只读展示，`shadow_only=true`，不自动执行、不覆盖硬止损。
- [x] P2：24M 报告新增 `strategy_family_summary`，输出策略族维度胜率、收益率、最大回撤、PF、参数建议数量、验证状态和防未来函数/OOS 策略。
- [x] P2：总优化报告新增“策略族闭环”小节，明确覆盖 13 个策略族 / 17 个策略、排序影响 `none`、生产参数变更不允许。
- [x] P2：策略族报告新增 `time_series_splits`，按季度时间顺序区分 train / validation / OOS；当前证据为 `time_ordered_quarter_proxy`，`production_ready=false`，禁止随机切分。
- [x] P3：前端 `FamilyStrip` 新增策略族数据质量提示，聚合 `data_quality`、`missing_strategies`、`stale_strategies` 和主力模型 fallback，不改变候选排序或交易执行。
- [x] P3：`FamilyStrip` 拆成独立小组件，策略族条保持高密度概览，候选、表现、质量、fallback、弱数据和高分候选明细进入只读弹窗。
- [x] 验收：新增只读整体验收报告 `strategy-system-acceptance-report-2026-05-28`，统一证明 P0-P3 最小只读/Shadow 闭环已完成，同时明确真实交易生产仍被数据、walk-forward、purged-gap 和 Shadow settled 样本阻断。
- [x] 验收：整体验收报告已接入既有局部 walk-forward 证据，包括 P1 窄网格 21 个矩阵窗口、退出参数 7/7 OOS 窗口和市场状态 guard 2/7 窗口；这些证据仍只允许 Shadow/研究观察，不放行生产参数。
- [x] 验收：局部 walk-forward 证据已映射回 6 个策略族：`first_board_retest`、`trend_pullback`、`trend_support_band`、`leader_pullback_band`、`next_day_event`、`core_midcap_retrace`。其中 `first_board` / `volume_shrink` 有参数窄网格实跑证据，`ma_channel_band` / `leader_pullback_band` 仍只是计划级 OOS 证据，全部保持 `production_ready=false`。
- [x] 验收：整体验收报告新增 `requirement_audit`，逐条对应 P0/P1/P2/P3、执行边界和最终交付字段；16 项最小只读闭环要求为 `complete`，真实交易生产放行单独标记为 `blocked` 且不计入最小闭环完成度。
- [x] 验收：整体验收报告新增 `test_coverage_matrix`，把目标要求的测试覆盖显式固化为 6/6：策略归类、旁路信号、止盈止损建议、模拟盘展示/快照、回测指标输出、前端高密度展示。
- [x] 验收：整体验收报告新增 `promotion_action_plan`，将 20 条生产阻断归并为 6 类可执行动作：ETF T0 分钟线/执行元数据、策略族真实 walk-forward/purged-gap、主力模型 Shadow settled、退出模型 Shadow settled、重点策略参数稳定性、市场状态保护参数稳定性。
- [x] 验收：新增 `focus-strategy-purged-gap-audit-2026-05-28`，审计 P1 重点策略 21 个已落盘矩阵窗口；结论为时间顺序通过，并生成 365 天 train / 60 天 validation / 10 天 purged-gap / OOS 的建议切分计划和 21 条 `low_buy_execution_matrix.py` 复跑命令。
- [x] 验收：已定位上一轮 `dates=0` 根因：命令未显式指定 `DATABASE_URL` 时会误走未启动的本地 MySQL；现已将 21 条复跑 manifest 钉定到 `sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db`。
- [x] 验收：已执行 1 条 SQLite purged-gap 复跑 smoke 命令，确认复跑命令、`isolated` 输出目录和 `default_exit` / `quick_tp3_trailing1` 双变体结构可用；该窗口产出 576 个评估样本、554 笔成交，状态为 `executed_with_samples`，但覆盖率仍为 `partial`，不能替代全量 21 窗口 purged-gap 验收。
- [x] 验收：`focus-strategy-purged-gap-audit-2026-05-28` 新增本地日线覆盖审计，SQLite 日线覆盖 2024-05-28 至 2026-04-28 共 466 个交易日；21 个 manifest OOS 窗口全部有本地交易日覆盖，单窗口 50 至 58 个交易日。
- [x] 验收：21 条 SQLite purged-gap manifest 已全量复跑完成，正式矩阵目录落盘 21 个 JSON / 21 个 Markdown，`run-summary.json` 显示 `executed_or_existing_count=21`、`failed_count=0`；合计 6336 个评估样本、5964 笔成交，覆盖状态仍为 `partial`，因此只关闭“manifest 未执行”缺口，不关闭生产放行门禁。
- [x] 验收：`low_buy_execution_matrix.py` 已支持显式 `train/validation/purged-gap/OOS` 时间边界参数；21 条 manifest 已强制复跑，21/21 矩阵均写入 `split_plan_encoded=true`、`purged_gap_temporal_order_passed=true`、`purged_gap_days=10`。
- [x] 验收：刷新 `focus-strategy-purged-gap-audit-2026-05-28` 与 `strategy-system-acceptance-report-2026-05-28`，当前 purged-gap 阻断从“未编码/未执行”收敛为“执行矩阵覆盖仍为 partial、线上 Shadow settled 样本不足”。
- [x] 文档：补齐 `docs/strategy-system-consolidation-and-enhancement-development-plan.md`，固化 P0-P3、执行边界、验收交付和真实交易生产放行门禁；验收报告已将该文档纳入 source/evidence。

### 仍未完成 / 阻断

- [ ] 策略族维度仍是研究报告与 Shadow 候选，不是生产晋级；P1 重点策略 21 条 SQLite manifest 已全量复跑且显式编码 train/validation/purged-gap/OOS 边界，但所有矩阵覆盖状态仍为 `partial`，仍需完整覆盖数据、参数稳定性和真实 Shadow settled 样本后才能生产晋级。
- [ ] ETF T0 24 个月分钟线与执行元数据仍需要外部数据源或 Tushare token 才能推进；这是当前唯一明确依赖外部数据的生产放行动作。
- [ ] 主力模型和退出模型仍需要自然交易日/模拟盘继续积累 settled Shadow 样本；不能用回填样本冒充线上结算表现。
- [ ] P3：策略族局部高密度和弹窗已完成；全站级 UI 版式重排不属于本轮最小闭环，后续如需要可单独做视觉/信息架构优化。
- [x] 指定需求文档路径已补齐，并已重新纳入整体验收报告与逐项审计。

### 验证

- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_24m_backtest_report.py --start 2024-05-28 --end 2026-04-28 --refresh-sections-only --existing-report docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-24m-backtest-2026-05-28.json --markdown-output docs/reports/strategy-24m-backtest-2026-05-28.md` 通过，刷新策略族闭环报告。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/generate_strategy_24m_optimization_report.py --date 2026-05-28 ...` 通过，刷新总优化报告。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_priority_weighting.py::PriorityWeightingTests::test_all_low_buy_strategies_have_explicit_family_metadata backend/tests/test_strategy_24m_report_sections.py::test_strategy_family_summary_is_research_only_and_contains_parameter_changes backend/tests/test_strategy_24m_optimization_report.py::test_build_report_keeps_candidates_out_of_production backend/tests/test_strategy_24m_optimization_report.py::test_render_markdown_contains_required_sections` 通过，4 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_priority_weighting.py backend/tests/test_old_duck_head_factor.py backend/tests/test_main_force_model_enrichment.py backend/tests/test_main_force_model_ranking.py backend/tests/test_paper_exit_model_advisor.py backend/tests/test_paper_exit_model_shadow.py backend/tests/test_strategy_24m_report_sections.py backend/tests/test_strategy_24m_optimization_report.py` 通过，50 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/strategy_system_acceptance_report.py --date 2026-05-28` 通过，输出 `readonly_shadow_loop_complete_production_blocked` / `completion_pct=100.0`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_system_acceptance_report.py` 通过，2 passed / 1 warning。
- [x] `python3 ... docs/reports/strategy-system-acceptance-report-2026-05-28.json` 抽样核验通过：`family_evidence` 已覆盖 6 个策略族，`production_ready=false`，`ma_channel_band` / `leader_pullback_band` 标记为尚未实跑策略参数窗口。
- [x] `python3 ... docs/reports/strategy-system-acceptance-report-2026-05-28.json` 抽样核验通过：`requirement_audit.status=minimal_readonly_loop_complete_production_blocked`，最小只读闭环完成度 100.0%，生产交易放行 `false`。
- [x] `python3 ... docs/reports/strategy-system-acceptance-report-2026-05-28.json` 抽样核验通过：`test_coverage_matrix.status=covered`，覆盖项 6 / 6。
- [x] `python3 ... docs/reports/strategy-system-acceptance-report-2026-05-28.json` 抽样核验通过：`promotion_action_plan.status=blocked_by_production_gates`，动作数 6，需要外部数据动作数 1。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/focus_strategy_purged_gap_audit.py --date 2026-05-28` 通过，输出 `partial_oos_evidence_purged_gap_not_proven`。
- [x] `python3 ... docs/reports/strategy-system-acceptance-report-2026-05-28.json` 抽样核验通过：`purged_gap_audit.total_matrix_window_count=21`、`temporal_order_passed=true`、`proposed_split_plan_present=true`、`purged_gap_plan_ready=true`、`purged_gap_passed=false`。
- [x] `python3 ... docs/reports/focus-strategy-purged-gap-audit-2026-05-28/summary.json` 抽样核验通过：`rerun_manifest.status=ready_not_executed`、`command_count=21`、`variants=[default_exit, quick_tp3_trailing1]`。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py --start 2025-08-01 --end 2025-10-24 --strategies first_board,volume_shrink --states confirmed --engine fast --materialization-mode isolated --variants default_exit,quick_tp3_trailing1 --matrix-output-dir docs/reports/focus-strategy-purged-gap-rerun-2026-05-28/smoke --output-dir docs/reports/focus-strategy-purged-gap-rerun-2026-05-28/smoke` 通过，真实执行 50 个评估交易日，输出 1 个 smoke 矩阵文件、2 个变体。
- [x] `python3 ... docs/reports/focus-strategy-purged-gap-rerun-2026-05-28/smoke/low_buy_execution_matrix_24m_confirmed_first_board_volume_shrink_2025-08-01_2025-10-24.json` 抽样核验通过：`default_exit` 与 `quick_tp3_trailing1` 各 `evaluated_count=288`、`filled_count=277`；合计评估样本 576、成交 554，覆盖状态 `partial`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/focus_strategy_purged_gap_audit.py --date 2026-05-28` 通过，新增 `daily_data_coverage.status=covered`、`covered_window_count=21/21`、`min_window_trade_dates=50`，并将 `rerun_manifest.database_url` 钉定为 SQLite。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/strategy_system_acceptance_report.py --date 2026-05-28` 通过，总验收继续输出 `readonly_shadow_loop_complete_production_blocked` / `completion_pct=100.0`，并接入 `daily_data_*` 与 `rerun_smoke_*` 证据字段。
- [x] `python3 ... docs/reports/strategy-system-acceptance-report-2026-05-28.json` 抽样核验通过：`rerun_manifest_database_url=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db`、`daily_data_status=covered`、`daily_data_total_trade_dates=466`、`daily_data_covered_window_count=21`、`rerun_smoke_status=executed_with_samples`、`rerun_smoke_total_evaluated_count=576`、`rerun_smoke_total_filled_count=554`、`rerun_smoke_partial_coverage_only=true`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/run_focus_strategy_purged_gap_rerun.py --date 2026-05-28 --keep-going` 通过，`complete=true`、`executed_or_existing_count=21`、`failed_count=0`、总耗时约 1901 秒。
- [x] `python3 ... docs/reports/focus-strategy-purged-gap-rerun-2026-05-28/run-summary.json` 抽样核验通过：21 条 manifest 中 19 条本轮执行、2 条已有输出跳过，最后一条 `volume_shrink#7` 成功落盘。
- [x] `python3 ... docs/reports/focus-strategy-purged-gap-rerun-2026-05-28/matrix-windows/*.json` 汇总核验通过：矩阵文件 21 个，合计 `evaluated_count=6336`、`filled_count=5964`，所有矩阵覆盖状态仍为 `partial`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/focus_strategy_purged_gap_audit.py --date 2026-05-28` 通过，`rerun_manifest.status=executed_complete`、`rerun_full.complete=true`、`rerun_full.matrix_count=21`、`rerun_full.failed_count=0`、`rerun_full.partial_coverage_only=true`、`purged_gap_passed=false`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/strategy_system_acceptance_report.py --date 2026-05-28` 通过，总验收继续输出 `readonly_shadow_loop_complete_production_blocked`，并接入 `rerun_full_*` 证据字段。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/run_focus_strategy_purged_gap_rerun.py --date 2026-05-28 --force --keep-going` 通过，21/21 复跑完成，`complete=true`、`executed_or_existing_count=21`、`failed_count=0`、总耗时约 1993 秒。
- [x] `python3 ... docs/reports/focus-strategy-purged-gap-rerun-2026-05-28/matrix-windows/*.json` 抽样核验通过：矩阵文件 21 个，21/21 `split_plan_encoded=true`，21/21 `purged_gap_temporal_order_passed=true`，`purged_gap_days=10`，合计 `evaluated_count=6336`、`filled_count=5964`，覆盖状态仍为 `partial`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/focus_strategy_purged_gap_audit.py --date 2026-05-28` 通过，`explicit_train_validation_split_present=true`、`explicit_purged_gap_encoded=true`、`production_blockers=[execution_matrix_coverage_partial_only, online_shadow_settled_sample_lt_required]`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python scripts/strategy_system_acceptance_report.py --date 2026-05-28` 通过，总验收继续输出 `readonly_shadow_loop_complete_production_blocked` / `production_trade_ready=false`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/scripts/low_buy_execution_matrix.py scripts/focus_strategy_purged_gap_audit.py scripts/strategy_system_acceptance_walk_forward.py scripts/strategy_system_acceptance_report.py scripts/run_focus_strategy_purged_gap_rerun.py backend/tests/test_strategy_system_acceptance_report.py` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_priority_weighting.py backend/tests/test_old_duck_head_factor.py backend/tests/test_main_force_model_enrichment.py backend/tests/test_main_force_model_ranking.py backend/tests/test_paper_exit_model_advisor.py backend/tests/test_paper_exit_model_shadow.py backend/tests/test_strategy_24m_report_sections.py backend/tests/test_strategy_24m_optimization_report.py backend/tests/test_strategy_system_acceptance_report.py` 通过，52 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_system_acceptance_report.py` 通过，2 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile scripts/focus_strategy_purged_gap_audit.py scripts/strategy_system_acceptance_walk_forward.py scripts/strategy_system_acceptance_report.py backend/tests/test_strategy_system_acceptance_report.py` 通过。
- [x] `python3 ... docs/reports/strategy-system-acceptance-report-2026-05-28.json` 抽样核验通过：`walk_forward_evidence_snapshot` 已包含 P1 窄网格、退出参数和市场状态 guard，`production_trade_ready=false`。
- [x] `cd frontend && npm test -- workspaceFamilyQuality PaperTradingPerformance StrategyImprovementSummary StrategyImprovementGatePanel --run` 通过，4 files / 6 tests。
- [x] `cd frontend && npm test -- FamilyStrip workspaceFamilyQuality PaperTradingPerformance StrategyImprovementSummary StrategyImprovementGatePanel MonitorPage --run` 通过，6 files / 12 tests。
- [x] `cd frontend && npx tsc -b --pretty false` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile scripts/strategy_system_acceptance_report.py scripts/strategy_system_acceptance_walk_forward.py scripts/strategy_system_requirement_audit.py backend/tests/test_strategy_system_acceptance_report.py` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/low_buy/strategy_families.py backend/scripts/strategy_24m_report_metrics.py backend/scripts/strategy_24m_backtest_report.py backend/scripts/strategy_24m_report_markdown.py scripts/generate_strategy_24m_optimization_report.py scripts/strategy_24m_optimization_markdown.py backend/tests/test_priority_weighting.py backend/tests/test_strategy_24m_report_sections.py backend/tests/test_strategy_24m_optimization_report.py` 通过。
- [x] `git diff --check` 通过。

## 2026-05-28 主力模型生产化 P0/P1/P2

需求来源：

- `docs/main-force-model-production-development-plan-2026-05-28.md`
- 当前目标：将“主力结构识别 + 买点分级 + 风险解释”从旁路组件升级为生产只读展示、Shadow 自动记录、受控排序加权和模拟盘只读/小仓建议灰度路径。

### 执行边界

- [x] 排序加权默认关闭，小仓建议默认关闭；首阶段不自动下单。
- [x] 复用 `MarketModelObservation`、低吸候选主路径、模拟盘风控和现有前端组件。
- [x] 不覆盖低吸原始分数、止损、止盈、硬风险或模拟盘准入。
- [x] fallback、blocked、data_quality 必须进入 advice/payload，可观测。
- [x] 单个新增或重构文件保持小于 500 行。

### TODO

- [x] Task 1：配置、schema、前端类型。
- [x] Task 2：候选 enrichment，只读接入并自动 fallback。
- [x] Task 3：Shadow upsert、summary、settle 和闭环报告状态。
- [x] Task 4：排序 bonus 受控接入，默认关闭且未达标不加权。
- [x] Task 5：选股宝典/策略工作台/移动端只读展示。
- [x] Task 6：防未来函数测试与 walk-forward 样本外脚本。
- [x] Task 7：管理/设置/监控状态入口。
- [x] Task 8：模拟盘只读展示、Shadow 对账和小仓建议灰度。
- [x] Task 9：本地验证、runbook、上线 smoke 准备。

### 当前结果

- [x] P0 已落地：低吸候选生产只读展示，`main_force_advice` 可见，`MarketModelObservation` 自动 Shadow 记录。
- [x] P1 路径已落地但默认关闭：`main_force_model_ranking_enabled=False`；即使打开，也要求 Shadow 达标、策略白名单、数据质量和 advice 条件全部通过才会加分。
- [x] P2 路径已落地但小仓建议默认关闭：模拟盘持仓/导入界面只读展示，建议只输出 `manual_import_only`，不创建订单。
- [x] Readiness 当前结论：OOS 小样本研究指标通过；本地已通过 `main_force_shadow_warmup.py` 将主力模型 Shadow 观察样本从 2 补到 10，但已结算仍为 0/120，最终 `promotion_ready=false`。
- [x] 报告：
  - `docs/reports/main-force-model-production-readiness-2026-05-28.json`
  - `docs/reports/main-force-model-production-readiness-2026-05-28.md`
  - `docs/main-force-model-production-runbook-2026-05-28.md`

## 2026-05-28 主力建仓-洗盘-拉升旁路模型

需求来源：

- 用户要求：落地主力入场建仓、洗盘、拉升买点模型，对已有相关策略起到上层过滤、买点分级和风险识别作用，但不要影响现有策略。
- 参考报告：`docs/reports/main-force-accumulation-washout-markup-model-report-2026-05-28.md`

### 执行边界

- [x] 本轮只新增旁路 Shadow/Advisor 能力，不接入生产候选排序、买卖、风控、模拟盘账本或自动交易。
- [x] 未来涨幅只允许用于标签/报告，不允许进入特征或买点评分。
- [x] 所有输出只读，默认作为后续模拟盘 Shadow 或前端展示的辅助解释。

### TODO

- [x] 读取现有低吸候选、策略治理、退出模型 Shadow 实现模式。
- [x] 新增主力结构 schema、特征生成、规则评分和 advisor。
- [x] 新增训练标签生成模块，未来收益只用于 labels，不进入 features。
- [x] 新增研究数据集 JSONL 脚本：`backend/scripts/main_force_model_dataset.py`，只读本地日线，不写库、不改生产参数。
- [x] 补齐测试：时序防未来函数、风险阻断、Shadow-only 不污染候选。
- [x] 运行针对性 pytest、现有低吸/N 字/交易控制回归、py_compile 和 diff 检查。

### 验证

- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_main_force_model_features.py backend/tests/test_main_force_model_labels.py -q` 通过，6 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/low_buy/main_force_model_schema.py backend/app/services/low_buy/main_force_model_features.py backend/app/services/low_buy/main_force_model_labels.py backend/app/services/low_buy/main_force_model_advisor.py backend/scripts/main_force_model_dataset.py` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/main_force_model_dataset.py --limit-symbols 5 --max-samples 20 --output docs/reports/main-force-model-dataset-smoke.jsonl` 通过，生成 20 条 smoke 样本。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_main_force_model_features.py backend/tests/test_main_force_model_labels.py backend/tests/test_low_buy_strategy_replacement.py -q` 通过，19 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_n_pattern_observe_confirmed.py backend/tests/test_low_buy_trade_controls.py -q` 通过，28 passed / 1 warning。
- [x] `git diff --check -- IMPLEMENTATION_PLAN.md backend/app/services/low_buy/main_force_model_schema.py backend/app/services/low_buy/main_force_model_features.py backend/app/services/low_buy/main_force_model_labels.py backend/app/services/low_buy/main_force_model_advisor.py backend/scripts/main_force_model_dataset.py backend/tests/test_main_force_model_features.py backend/tests/test_main_force_model_labels.py docs/reports/main-force-accumulation-washout-markup-model-report-2026-05-28.md` 通过。

## 2026-05-28 策略胜率/盈利率提升闭环

需求来源：

- 当前 Goal：建立“策略胜率/盈利率提升闭环”，基于最近两年真实完整 A 股数据做全策略回测、分层治理、Walk-forward 调参、约束增强、模型辅助过滤和止盈止损 Shadow 验证。
- 参考报告：`docs/reports/strategy-24m-backtest-2026-05-28.md`
- 参考边界：`docs/go-rust-migration-development-plan-2026-05-27.md`

### 执行边界

- [x] Python 继续作为策略、风控、回测语义和模拟盘账本真源；本轮新增闭环只读报告，不修改生产参数、订单、成交、持仓或账本。
- [x] Go/Rust 仍只承担读服务/编排和纯数值加速，不参与策略买卖决策。
- [x] 模型保持 Shadow/辅助建议定位；报告明确硬止损不可被模型覆盖。
- [x] 新增代码已拆分，单个新增代码文件均小于 500 行。

### 已完成

- [x] 阅读 `AGENTS.md`、24 个月回测报告、Go/Rust 迁移边界文档，并定位现有策略/回测/模拟盘/退出模型/ETF/OOS 代码。
- [x] 新增只读闭环 CLI：`backend/scripts/strategy_improvement_closed_loop.py`。
- [x] 新增闭环服务模块：`backend/app/services/strategy_improvement/*`，覆盖数据覆盖率、数据质量、策略治理、Walk-forward readiness、退出模型 Shadow、门禁和补数计划。
- [x] 生成报告：
  - `docs/reports/strategy-improvement-closed-loop-2026-05-28.json`
  - `docs/reports/strategy-improvement-closed-loop-2026-05-28.md`
- [x] 当前结论：`blocked_or_research_only`。全 A 日线 24 个月窗口已完整，日线质量已通过；ETF T0 分钟线仅有近端短窗口 5m 数据，24 个月验收覆盖仍为 0%，且 ETF 执行元数据实值覆盖不足，因此禁止正式两年验收、Walk-forward 晋级和生产参数变更。
- [x] 策略治理状态已输出：正期望候选 3、高收益高回撤 3、弱策略 5、样本不足 4、研究候选 2。
- [x] 补齐 `daily_bar_snapshots` / `minute_bar_snapshots` 数据血缘字段：`source`、`fetch_time`、`checksum`、`data_quality`，日线额外含 `adjusted_mode`。
- [x] `backfill_daily_history.py` 已写入 AkShare source、qfq 复权模式、fetch_time、data_quality 和 checksum。
- [x] 小批量真实补数探针通过：`000001` / `600000` 在 2024-05-28 至 2024-06-07 各写入 9 条，source=`akshare.stock_zh_a_hist`、adjusted_mode=`qfq`、data_quality=`fresh`、checksum 长度 64。
- [x] 修正覆盖率口径：正式门禁使用“全市场完整交易日覆盖率”，不能因少数标的补到两年前而误报完整覆盖。
- [x] `backfill_daily_history.py` 新增 `--report-output` 审计报告，记录 config、totals、逐 symbol 结果、source、adjusted_mode、data_quality 和 failed_symbols。
- [x] 第二次小批量探针通过：`000001` / `600000` 在 2024-06-11 至 2024-06-14 各写入 4 条，报告 `docs/reports/daily-history-backfill-probe-2026-05-28.json`，status=`completed`，failed_symbols 为空，实际 source=`akshare.stock_zh_a_daily` fallback。
- [x] 新增可恢复批量补数运行器：`backend/scripts/daily_history_backfill_runner.py`，按 batch 生成子报告和 `manifest.json`，支持 `--resume`。
- [x] runner 小批量真实验证通过：`docs/reports/daily-history-backfill-runs/probe-2026-05-28/manifest.json`，2 个 batch 全部 completed，totals ok=2；2024-06-17 至 2024-06-21 两个探针标的各写入 5 条。
- [x] runner 已支持 `--scope all-stock|pool|symbols` 和 `--limit`，可直接按全市场/低吸池/指定标的生成可恢复批次，不再依赖外部手工拆清单。
- [x] runner 范围解析真实验证通过：`docs/reports/daily-history-backfill-runs/probe-scope-2026-05-28/manifest.json`，2 个 batch 全部 completed，totals ok=2；2024-06-24 至 2024-06-28 两个探针标的各写入 5 条。
- [x] 闭环报告的数据补齐计划已切换为 `daily_history_backfill_runner.py --scope all-stock --batch-size 50 --workers 4 --resume`，避免全市场补数失败后从头开始。
- [x] 新增 ETF 分钟线补数脚本：`backend/scripts/backfill_etf_minute_history.py`，只补 ETF universe 中 `same_day_sell_allowed=true` 的标的，默认补 5m 历史分钟线，写入 `minute_bar_snapshots` 并保留 source/fetch_time/checksum/data_quality。
- [x] ETF 分钟线补数脚本已增加多源 fallback 与 provider 级失败审计：5m/15m/30m/60m 使用 Eastmoney 历史分钟线；1m 可 fallback 到 Tencent/Eastmoney 近端趋势源；全失败时记录每个 provider 的失败原因，不生成伪分钟线。
- [x] ETF 分钟线补数脚本已接入 Sina K 线 fallback；当前环境 Eastmoney 历史分钟线仍返回 `Remote end closed connection without response`，Sina 可提供真实近端 5m 数据，但只覆盖约 24 个交易日，不能冒充 24 个月历史分钟线。
- [x] ETF 分钟线补数脚本已新增 Tushare `stk_mins` 与 AkShare `fund_etf_hist_min_em` 历史分钟线 fallback，优先级为 Tushare -> Eastmoney -> AkShare -> Sina；Tushare token 从环境变量或 `backend/.env` / `backend/data/runtime.env` 读取，缺失时记录 `tushare token not configured`，不生成伪分钟线。
- [x] 修复 `MinuteBarSnapshotStore.persist()` 历史回填能力：默认实时路径仍跳过旧数据，补数脚本可显式 `skip_older_than_latest=False` 回填较早分钟线。
- [x] ETF 5m 历史失败探针已落审计报告：`docs/reports/etf-minute-backfill-probe-2026-05-28.json`，Eastmoney 返回 `Remote end closed connection without response`，status=`partial_data`，库内仍未写入伪分钟线。
- [x] ETF 5m AkShare 历史分钟线探针已落审计报告：`docs/reports/etf-minute-backfill-akshare-probe-2026-05-28.json`，`510300` 在 `2024-05-28` 至 `2024-05-29` 的 Eastmoney、AkShare、Sina 均返回 empty，status=`partial_data`，库内未写入伪分钟线。
- [x] ETF 5m Tushare 优先探针已落审计报告：`docs/reports/etf-minute-backfill-tushare-probe-2026-05-28.json`，当前本地未配置 `TUSHARE_TOKEN` / `TUSHARE_API_TOKEN` / `TUSHARE_PRO_TOKEN`，Eastmoney 返回连接关闭，AkShare/Eastmoney 路径报 proxy/remote 错误，Sina 历史窗口 empty；status=`partial_data`，库内未写入伪分钟线。
- [x] ETF 1m 近端 fallback 探针通过：`docs/reports/etf-minute-backfill-1m-probe-2026-05-28.json`，`510300` 写入 242 条 `tencent.minute` / `fresh` 分钟线。闭环报告将其标记为窗口外探针，不计入 24 个月验收。
- [x] 闭环报告已接入 ETF 分钟线 provider 诊断：`minute_coverage.provider_diagnostics` 指向最新 `etf-minute-backfill*.json`，展示 Tushare token 缺失、Eastmoney/AkShare/Sina 失败样本、写入效果和 `fake_minute_bars_forbidden`，便于区分真实阻断与代码失败。
- [x] ETF T0 分钟线不足已按目标要求机器可读标记为 `blocked_by_data`：`minute_coverage.status=blocked_by_data`，同时保留 `raw_data_status=partial/empty` 与 `blocked_reason`，gate evidence 也携带同样字段。
- [x] 闭环报告的数据补齐计划已增加 `backfill_etf_minute_history.py --scope t0-etf --period 5m --allow-partial`；报告继续提示 1m 免费接口通常只返回近 5 个交易日，不能伪造 24 个月 1m 验收。
- [x] 闭环覆盖率报告新增缺口样本：日线输出薄交易日、当前 symbol 数、阈值、估算缺失标的数、缺失字段和原因；ETF 分钟线输出白名单逐 symbol 样本、行数、实际起止日期和缺失原因，并区分窗口内分钟线与窗口外探针数据。
- [x] 闭环报告新增交易元数据门禁：涨跌停、停牌/ST/退市/上市日期、行业/概念历史、ETF 盘口价差/折溢价/跟踪指数/流动性、持久化 T0 规则缺失时，`market_metadata_coverage` 阻断正式回测与 Walk-forward 晋级，避免 OHLCV 通过被误判为可验收。
- [x] ETF 执行元数据门禁已从“字段存在”升级为“窗口内实值覆盖”：`etf_intraday_execution_metadata_coverage` 要求正盘口价差、折溢价、跟踪指数、流动性等级和 fresh/verified 分钟执行元数据达到覆盖阈值；默认 0、`unknown` 或 `partial_metadata` 不再通过正式验收。
- [x] 新增交易元数据承载结构：`daily_bar_snapshots` 支持涨跌停价、停牌/ST/退市；`instruments` 支持上市/退市/ST/状态；`minute_bar_snapshots` 支持盘口价差、折溢价、跟踪指数、流动性等级；新增行业/概念历史表。
- [x] 新增 Alembic 迁移 `backend/alembic/versions/20260528_0001_market_metadata_fields.py`，并扩展本地 SQLite 兼容修复，旧库可自动补齐上述字段和历史表。
- [x] 日线/ETF 分钟补数链路已接入交易元数据字段；缺少真实涨跌停/盘口/折溢价时标记 `partial_metadata`，不冒充完整 `fresh`。
- [x] 当前本地闭环报告刷新后，`market_metadata_coverage=fail`，阻断缺口来自 ETF 分钟执行元数据实值覆盖不足；涨跌停价、行业覆盖、active/listed 股票上市日期和持久化 T0 规则已通过，但 ETF T0 仍不可验收。
- [x] 新增 ETF T0 规则持久化服务和脚本：`backend/app/services/etf/rule_sync.py`、`backend/scripts/sync_etf_t0_rules.py`，只同步 ETF universe 中 `same_day_sell_allowed=true` 的白名单，不提升未知 ETF 或股票。
- [x] 已对本地库执行 ETF T0 规则同步，报告 `docs/reports/etf-t0-rule-sync-2026-05-28.json`，持久化 T0 标的 22 个；闭环报告中 `persisted_t0_rule_coverage=pass`，`market_metadata_coverage` 阻断缺口从 4 个降为 3 个。
- [x] 新增 instruments 元数据补齐脚本：`backend/scripts/backfill_instrument_metadata.py`，支持从 AkShare/Eastmoney 批量 spot 数据提取行业、上市日期、状态和 ST 标记；缺失字段不硬填，失败源写入 provider_errors。
- [x] 已对当前环境执行 instruments 元数据补齐，报告 `docs/reports/instrument-metadata-backfill-2026-05-28.json`，状态 `partial_data`；AkShare/Eastmoney 当前均因连接/代理失败未返回数据，因此行业覆盖仍 7.11%、上市日期覆盖仍 0%。
- [x] instruments 元数据补齐已接入非 Eastmoney 源：深交所/上交所/北交所基础表与申万行业历史；本地执行后行业覆盖 100.0%，active/listed 股票上市日期覆盖 99.95%，行业和生命周期门禁已通过。
- [x] 新增日线涨跌停价规则推导脚本：`backend/scripts/backfill_daily_limit_prices.py`，按 `pre_close`、板块代码、上市日期、ST 标记推导涨跌停价；启用 `--derive-pre-close` 时只使用同一标的上一条已落库真实 `close_price` 补 `pre_close`，不生成/插值 OHLCV。
- [x] 已对本地库执行涨跌停价补齐，最新报告 `docs/reports/daily-limit-price-backfill-2026-05-28.json`：扫描 966,047 行，更新 468,529 行，跳过无上一收盘 2,351 行、上市豁免 118 行；覆盖率 963,578 / 966,047 = 99.74%，`market_metadata_coverage` 已通过。
- [x] 修正 `backfill_daily_history.py` 的覆盖完整判定：不再只看单标的 min/max 日期，必须窗口内达到最低交易日密度且 lineage 字段完整，避免后续 `--resume` 将中间缺口误判为 complete。
- [x] 全 A 日线真实补数已从探针推进到前 2,000 个标的：`docs/reports/daily-history-backfill-runs/all-stock-probe-2000-2026-05-28/manifest.json`，totals ok=1022、skip=975、empty=3、error=0；闭环报告窗口内股票数 2,351，日线 966,047 条，交易日 466。
- [x] 全 A 日线真实补数已完成全量窗口：`docs/reports/daily-history-backfill-runs/all-stock-full-2026-05-28/manifest.json`，totals ok=1549、skip=3399、empty=321、error=0；闭环报告窗口内股票数 4,967，日线 2,266,166 条，466 / 466 个交易日完整，`daily_24m_coverage=pass`。
- [x] 清理日线质量异常：首次执行 `clean_invalid_daily_bars.py` 删除 3 条 2024-11-06 零开高低但有收盘价的无效 K 线；后续闭环报告 `daily_quality=pass`，重复 K 线 0、非法 OHLC 0、负成交 0。
- [x] 全量涨跌停价补齐后元数据门禁通过：`docs/reports/daily-limit-price-backfill-2026-05-28.json`，全量窗口涨跌停覆盖约 99.75%，行业覆盖 100.0%，上市/退市生命周期覆盖 99.95%，持久化 T0 规则 22 个，`market_metadata_coverage=pass`。
- [x] ETF T0 白名单已补入真实 Sina 5m 近端数据：`docs/reports/etf-minute-backfill-t0-5m-2026-05-28.json`，22 个 T0 ETF 均写入 `sina.kline`，窗口内 24,344 条、每标的 1,106 条、24 个交易日；闭环验收按 466 个交易日覆盖率判定，所有 ETF 仅 5.15%，`etf_t0_minute_coverage=fail`。
- [x] ETF 分钟线门禁已强化为交易日覆盖口径：即使窗口内存在近端真实分钟线，也必须达到 24 个月交易日覆盖阈值，避免短窗口数据误放行正式回测。
- [x] 24 个月全策略报告脚本已按当前需求拆分：`strategy_24m_backtest_report.py` 保留主流程，指标、ETF/SmartT/sector section、Markdown 渲染分别拆到 `strategy_24m_report_metrics.py`、`strategy_24m_report_sections.py`、`strategy_24m_report_markdown.py`，当前相关文件均小于 500 行。
- [x] 24 个月全策略报告已刷新：`docs/reports/strategy-24m-backtest-2026-05-28.json` / `.md`。日线覆盖 `complete`、实际评估窗口 `2024-05-28` 至 `2026-04-21` 共 461 个交易日；ETF T0 正确标记为 `partial_minute_coverage`，窗口内分钟线 24,344 条，验收交易日 466，达标 ETF 0 / 22。
- [x] 闭环报告已引用修正后的 24M 报告重刷：`docs/reports/strategy-improvement-closed-loop-2026-05-28.json` / `.md`。`daily_24m_coverage=pass`、`daily_quality=pass`、`market_metadata_coverage=fail`、`etf_t0_minute_coverage=fail`，整体仍 `blocked_or_research_only`，`formal_backtest_allowed=false`、`walk_forward_allowed=false`。
- [x] Walk-forward readiness 已从“准备度”扩展为只读执行蓝图：报告生成 12m 训练 / 3m 验证 / 3m OOS 月度滚动窗口，本地完整日线窗口可形成 7 个时间顺序窗口；明确 `random_split_allowed=false`、禁止随机切分，受控参数网格仅包含目标允许的 min_score、持仓天数、止损、止盈、移动止盈、仓位、市场状态、板块强度和流动性阈值。
- [x] Walk-forward 蓝图已列出过拟合/稳定性必检项：`parameter_stability_pm_10pct`、`parameter_stability_pm_20pct`、`pbo_or_equivalent`、`deflated_sharpe_or_equivalent`、`market_state_pass_rate`。当前仍只是执行蓝图，不写生产参数，也不绕过 ETF T0 门禁。
- [x] 新增防未来函数门禁：`backend/app/services/strategy_improvement/temporal_guard.py` 检查 Walk-forward 窗口必须 `train < validation < OOS`、`random_split_allowed=false`，并扫描退出模型 Shadow `feature_snapshot`，禁止 `future` / `next` / `outcome` / `t_plus` / `t+` 等未来字段进入特征。闭环报告新增 `temporal_no_future_function` blocking gate。
- [x] 新增约束增强审计：`backend/app/services/strategy_improvement/constraint_policy.py` 把弱市/市场宽度/板块强度/流动性/ST/涨跌停/连续止损/近 20 笔胜率/data_quality 等要求汇总成 `constraint_policy_coverage` blocking gate。当前真实报告 `constraint_policy.status=pass`，`issue_count=0`，生产影响为 `audit_only_no_parameter_write`。
- [x] 退出模型 Shadow 闭环报告已增强：`backend/app/services/strategy_improvement/model_shadow.py` 输出模型动作相对规则动作的一致/更激进/更保守/fallback 分布、硬止损覆盖风险、5 日后验收益/最大不利/卖飞率、晋级阻断原因。当前真实库 `record_count=0`、`settled_count=0`，因此 `promotion_ready=false`，仍只允许继续积累 Shadow 样本。
- [x] 新增只读后端 API：`GET /api/backtests/strategy-improvement-report`，复用闭环报告构建逻辑，需 research 权限，不触发补数、不改生产参数。
- [x] 回测页“研究闭环”新增上线门禁面板，展示正式回测/Walk-forward 阻断原因、全市场覆盖、完整交易日、ETF 任意分钟线覆盖、ETF 验收分钟线覆盖、日线/ETF 缺口样本和门禁表。
- [x] 回测页“研究闭环”面板已继续接入 Walk-forward 窗口、受控参数网格、稳定性/过拟合检查、约束审计、防未来函数门禁、Shadow-only 状态、动作差异和晋级阻断原因；仅展示报告结论，不写生产参数。
- [x] 回测页“研究闭环”面板已接入 ETF 分钟线补数诊断，展示报告路径、写入效果、禁止伪造分钟线策略和 provider 失败样本，避免用户只能在 JSON/Markdown 中排查 Tushare/公开源问题。
- [x] 回测页“研究闭环”面板已展示 ETF 分钟线 `blocked_by_data`、原始数据状态和阻断原因，避免把短窗口真实分钟线误读为验收通过。
- [x] 回测页“研究闭环”面板已展示交易元数据阻断数量和缺口样本，当前可直接看到 ETF 折溢价、盘口价差和 fresh/verified 执行元数据覆盖不足。
- [x] 策略工作台“快速体检”侧栏已接入闭环治理摘要，展示生产候选、高收益高回撤、暂停/降权、Walk-forward、约束审计、防未来函数和 ETF T0 门禁阻断；组件只读调用闭环报告 API，不新增参数写入。
- [x] 模拟盘“策略绩效”页已接入止盈止损模型 Shadow 总览，展示 Shadow 样本/已结算、动作差异、fallback、卖飞率、晋级阻断和硬止损不可覆盖，明确不下单、不改账本、不取消硬止损。
- [x] 前端回测类型定义已拆分为 `backtestBaseTypes.ts`、`backtestResearchTypes.ts`、`etfT0BacktestTypes.ts` 和兼容导出 `backtestTypes.ts`，保持单文件小于 500 行。

### 未完成 / 阻断

- [ ] 涨跌停价覆盖门禁已通过，但 ST 使用当前 `instruments.is_st` 与名称识别，尚缺历史 ST 状态快照源；正式回测报告需继续把 `st_current_only_rows` 作为审计 caveat。
- [ ] 尚未补齐 ETF T0 两年历史分钟线、折溢价和真实盘口/流动性字段；当前只有 Sina 近端 5m 真数据，ETF T0 为 `blocked_by_data` / `partial_minute_coverage`，不能作为 24 个月 T0 验收。
- [ ] P1 `first_board` / `volume_shrink` 参数窄网格已实跑 21 个矩阵窗口；`first_board` 7/7 通过、`volume_shrink` 6/7 通过，整体仍需补 purged-gap、稳定性和 Shadow settled 后才能生产晋级。
- [ ] 主力模型 Shadow warmup 路径已补齐并验证，本地 `market_model_observations` 观察样本为 10；已结算仍为 0，不能评估真实成功率、PF 或生产晋级。
- [ ] 退出模型 Shadow 当前本地 settled 样本不足，不能评估是否降低回吐/止损率；`quick_tp3_trailing1` 只能作为 Shadow 候选，不允许写生产参数。

### 验证

- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 通过，输出 `formal_backtest_allowed=false` / `walk_forward_allowed=false`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py -q` 通过，5 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_data_lineage.py backend/tests/test_strategy_improvement_closed_loop.py -q` 通过，7 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_data_lineage.py -q` 通过，4 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_daily_history_backfill_runner.py backend/tests/test_market_data_lineage.py -q` 通过，7 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_daily_history_backfill_runner.py -q` 通过，5 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_etf_minute_backfill.py backend/tests/test_market_data_lineage.py -q` 通过，9 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_etf_minute_backfill.py -q` 通过，12 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py -q` 通过，4 passed / 1 warning；覆盖缺口样本和 ETF 缺口样本输出。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_requires_research_permission backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_returns_gate_summary_for_research_user backend/tests/test_strategy_improvement_closed_loop.py -q` 通过，6 passed / 1 warning。
- [x] `cd frontend && npm test -- StrategyImprovementGatePanel BacktestDashboard --run` 通过，2 files / 2 tests。
- [x] `cd frontend && npm run lint:state -- --quiet` 通过。
- [x] `cd frontend && npx tsc -b --pretty false` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/sync_etf_t0_rules.py --report-output docs/reports/etf-t0-rule-sync-2026-05-28.json` 通过，`t0_enabled_count=22`。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 通过，仍为 `blocked_or_research_only`，但 `instrument_rules.same_day_sell_allowed_rows` 已不再阻断。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_rules.py backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_market_data_lineage.py backend/tests/test_daily_history_backfill_runner.py backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_requires_research_permission backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_returns_gate_summary_for_research_user -q` 通过，35 passed / 1 warning。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_instrument_metadata.py --report-output docs/reports/instrument-metadata-backfill-2026-05-28.json` 通过并产出 `partial_data`；provider_errors 记录 AkShare proxy failure 与 Eastmoney remote closed。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_data_lineage.py backend/tests/test_market_rules.py backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_daily_history_backfill_runner.py backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_requires_research_permission backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_returns_gate_summary_for_research_user -q` 通过，37 passed / 1 warning。
- [x] 修正 `backend/scripts/backfill_instrument_metadata.py` 后重跑：`docs/reports/instrument-metadata-backfill-2026-05-28.json`，`sector_coverage_pct=100.0`，`listing_date_coverage_pct=99.95`；闭环报告中 `static_sector_coverage=pass`、`instrument_lifecycle_coverage=pass`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_data_lineage.py backend/tests/test_market_rules.py backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_daily_history_backfill_runner.py backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_requires_research_permission backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_returns_gate_summary_for_research_user -q` 通过，39 passed / 1 warning。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_daily_limit_prices.py --start-date 2024-05-28 --end-date 2026-04-28 --derive-pre-close --report-output docs/reports/daily-limit-price-backfill-2026-05-28.json` 通过，更新 75,603 行，涨跌停价覆盖 99.13%。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/daily_history_backfill_runner.py --scope all-stock --limit 300 --start-date 2024-05-28 --end-date 2026-04-28 --batch-size 25 --workers 3 --sleep 0.08 --resume --run-id all-stock-probe-300-2026-05-28 --run-dir docs/reports/daily-history-backfill-runs` 通过，totals ok=270 / skip=30 / empty=0 / error=0。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/daily_history_backfill_runner.py --scope all-stock --limit 1000 --start-date 2024-05-28 --end-date 2026-04-28 --batch-size 50 --workers 4 --sleep 0.06 --resume --run-id all-stock-probe-1000-2026-05-28 --run-dir docs/reports/daily-history-backfill-runs` 通过，totals ok=698 / skip=299 / empty=3 / error=0。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/daily_history_backfill_runner.py --scope all-stock --limit 2000 --start-date 2024-05-28 --end-date 2026-04-28 --batch-size 50 --workers 4 --sleep 0.06 --resume --run-id all-stock-probe-2000-2026-05-28 --run-dir docs/reports/daily-history-backfill-runs` 通过，totals ok=1022 / skip=975 / empty=3 / error=0。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_daily_limit_prices.py --start-date 2024-05-28 --end-date 2026-04-28 --derive-pre-close --report-output docs/reports/daily-limit-price-backfill-2026-05-28.json` 重跑通过，更新 468,529 行，涨跌停价覆盖 99.74%。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 重跑通过，`market_metadata_coverage=pass`，整体仍 `blocked_or_research_only`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_daily_limit_price_backfill.py backend/tests/test_market_data_lineage.py backend/tests/test_daily_history_backfill_runner.py backend/tests/test_strategy_improvement_closed_loop.py -q` 通过，29 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/scripts/backfill_daily_history.py backend/scripts/daily_history_backfill_runner.py backend/scripts/backfill_daily_limit_prices.py backend/scripts/strategy_improvement_closed_loop.py` 通过。
- [x] `git diff --check` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 通过，`market_metadata_coverage=pass`，整体仍 `blocked_or_research_only`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_daily_limit_price_backfill.py backend/tests/test_market_data_lineage.py backend/tests/test_market_rules.py backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_daily_history_backfill_runner.py backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_requires_research_permission backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_returns_gate_summary_for_research_user -q` 通过，45 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/scripts/backfill_daily_limit_prices.py backend/scripts/strategy_improvement_closed_loop.py backend/scripts/backfill_daily_history.py backend/scripts/daily_history_backfill_runner.py backend/scripts/backfill_etf_minute_history.py backend/scripts/sync_etf_t0_rules.py backend/scripts/backfill_instrument_metadata.py` 通过。
- [x] `git diff --check` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py --scope symbols --symbols 510300 --start-date 2026-04-28 --end-date 2026-04-28 --period 5m --workers 1 --force --allow-partial --report-output docs/reports/etf-minute-backfill-probe-2026-05-28.json` 产出 partial_data 报告；Eastmoney 连接关闭，totals empty=1，未写入伪分钟线。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py --scope symbols --symbols 510300 --start-date 2026-05-27 --end-date 2026-05-27 --period 1m --workers 1 --force --allow-partial --report-output docs/reports/etf-minute-backfill-1m-probe-2026-05-28.json` 通过，totals ok=1，写入 242 条窗口外近端分钟线。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/daily_history_backfill_runner.py --scope symbols --symbols 000001,600000 --start-date 2024-06-24 --end-date 2024-06-28 --batch-size 1 --workers 1 --sleep 0.1 --force --run-id probe-scope-2026-05-28 --run-dir docs/reports/daily-history-backfill-runs` 通过，totals ok=2。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 通过，仍为 `blocked_or_research_only`。
- [x] 闭环报告刷新后 `market_metadata_coverage=fail`，当前阻断缺口 17 个；`daily_quality=pass` 只代表 OHLC/重复/负成交检查通过，不再被用作完整验收依据。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_market_data_lineage.py backend/tests/test_daily_history_backfill_runner.py backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_requires_research_permission backend/tests/test_backtest_v2_api_contract.py::test_strategy_improvement_report_returns_gate_summary_for_research_user -q` 通过，28 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/scripts/backfill_etf_minute_history.py backend/scripts/daily_history_backfill_runner.py backend/scripts/backfill_daily_history.py backend/scripts/strategy_improvement_closed_loop.py backend/app/services/strategy_improvement/quality.py backend/app/services/strategy_improvement/report.py backend/app/services/strategy_improvement/gates.py backend/alembic/versions/20260528_0001_market_metadata_fields.py` 通过。
- [x] `cd backend && ../backend/.venv/bin/python -m alembic heads` 输出 `20260528_0001 (head)`。
- [x] `cd frontend && npm test -- StrategyImprovementGatePanel BacktestDashboard --run` 通过，2 files / 2 tests。
- [x] `cd frontend && npm run lint:state -- --quiet` 通过。
- [x] `cd frontend && npx tsc -b --pretty false` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_paper_exit_model_advisor.py backend/tests/test_paper_exit_model_shadow.py backend/tests/test_etf_t0_oos_validation.py backend/tests/test_low_buy_backtest_isolation.py -q` 通过，16 passed / 1 warning。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_24m_backtest_report.py --start 2024-05-28 --end 2026-04-28 --refresh-sections-only --existing-report docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-24m-backtest-2026-05-28.json --markdown-output docs/reports/strategy-24m-backtest-2026-05-28.md` 通过，ETF T0 修正为 `partial_minute_coverage`，达标 ETF 0 / 22。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 通过，整体 `blocked_or_research_only`，`formal_backtest_allowed=false` / `walk_forward_allowed=false`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_24m_report_sections.py backend/tests/test_strategy_improvement_closed_loop.py -q` 通过，8 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/scripts/strategy_24m_backtest_report.py backend/scripts/strategy_24m_report_metrics.py backend/scripts/strategy_24m_report_sections.py backend/scripts/strategy_24m_report_markdown.py backend/tests/test_strategy_24m_report_sections.py` 通过。
- [x] `git diff --check -- backend/scripts/strategy_24m_backtest_report.py backend/scripts/strategy_24m_report_metrics.py backend/scripts/strategy_24m_report_sections.py backend/scripts/strategy_24m_report_markdown.py backend/tests/test_strategy_24m_report_sections.py docs/reports/strategy-24m-backtest-2026-05-28.json docs/reports/strategy-24m-backtest-2026-05-28.md docs/reports/strategy-improvement-closed-loop-2026-05-28.json docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 重跑通过，Walk-forward 蓝图输出 7 个 12/3/3 月度滚动窗口。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_strategy_24m_report_sections.py -q` 通过，9 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/strategy_improvement/coverage.py backend/app/services/strategy_improvement/walkforward.py backend/app/services/strategy_improvement/report.py backend/tests/test_strategy_improvement_closed_loop.py` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 重跑通过，`temporal_no_future_function=pass`，`etf_t0_minute_coverage=fail`，整体仍 `blocked_or_research_only`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_strategy_24m_report_sections.py -q` 通过，10 passed / 1 warning；新增用例验证含 `future_return_5d` 的 Shadow 特征会被 temporal gate 阻断。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/strategy_improvement/temporal_guard.py backend/app/services/strategy_improvement/gates.py backend/app/services/strategy_improvement/report.py backend/tests/test_strategy_improvement_closed_loop.py` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 重跑通过，`constraint_policy_coverage=pass`、`temporal_no_future_function=pass`、`etf_t0_minute_coverage=fail`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_strategy_24m_report_sections.py -q` 通过，12 passed / 1 warning；新增用例验证缺基础约束、缺高风险约束、弱策略未暂停会被约束审计阻断。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/strategy_improvement/constraint_policy.py backend/app/services/strategy_improvement/gates.py backend/app/services/strategy_improvement/report.py backend/tests/test_strategy_improvement_closed_loop.py` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 重跑通过，`auxiliary_model_shadow.status=insufficient_shadow_samples`，`shadow_only=true`，`hard_stop_override_allowed=false`，`promotion_ready=false`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_paper_exit_model_shadow.py backend/tests/test_strategy_24m_report_sections.py -q` 通过，17 passed / 1 warning；新增用例覆盖 Shadow 动作差异、fallback、硬止损覆盖风险和后验摘要。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/strategy_improvement/model_shadow.py backend/app/services/strategy_improvement/gates.py backend/app/services/strategy_improvement/report.py backend/tests/test_strategy_improvement_closed_loop.py` 通过。
- [x] `cd frontend && npm test -- StrategyImprovementGatePanel --run` 通过，1 file / 1 test；新增断言覆盖 Walk-forward、防未来函数、约束审计、Shadow-only、动作差异和晋级阻断原因。
- [x] `cd frontend && npx tsc -b --pretty false` 通过。
- [x] `cd frontend && npm run lint:state -- --quiet` 通过。
- [x] `git diff --check -- frontend/src/api/backtestBaseTypes.ts frontend/src/features/backtest/StrategyImprovementGatePanel.tsx frontend/src/features/backtest/StrategyImprovementGatePanel.test.tsx` 通过。
- [x] `wc -l frontend/src/api/backtestBaseTypes.ts frontend/src/features/backtest/StrategyImprovementGatePanel.tsx frontend/src/features/backtest/StrategyImprovementGatePanel.test.tsx` 确认分别为 334 / 111 / 128 行，均小于 500 行。
- [x] `cd frontend && npm test -- StrategyImprovementSummary StrategyImprovementGatePanel PaperTradingPerformance --run` 通过，3 files / 4 tests；新增断言覆盖策略治理分层、参数晋级阻断、模拟盘 Shadow-only、硬止损不可覆盖。
- [x] `cd frontend && npx tsc -b --pretty false` 通过。
- [x] `cd frontend && npm run lint:state -- --quiet` 通过。
- [x] `git diff --check -- frontend/src/api/backtestBaseTypes.ts frontend/src/features/backtest/StrategyImprovementSummary.tsx frontend/src/features/backtest/StrategyImprovementSummary.test.tsx frontend/src/features/strategy/StrategyHubDetailTabs.tsx frontend/src/features/paper/PaperDetailTabs.tsx` 通过。
- [x] `wc -l frontend/src/features/backtest/StrategyImprovementSummary.tsx frontend/src/features/backtest/StrategyImprovementSummary.test.tsx frontend/src/features/strategy/StrategyHubDetailTabs.tsx frontend/src/features/paper/PaperDetailTabs.tsx frontend/src/api/backtestBaseTypes.ts` 确认分别为 134 / 130 / 187 / 455 / 351 行，均小于 500 行。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py --scope symbols --symbols 510300 --start-date 2024-05-28 --end-date 2024-05-29 --period 5m --workers 1 --force --allow-partial --report-output docs/reports/etf-minute-backfill-akshare-probe-2026-05-28.json` 通过，totals empty=1；provider_errors 包含 `eastmoney.etf_minute`、`akshare.fund_etf_hist_min_em`、`sina.kline`，未写入伪分钟线。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py --scope symbols --symbols 510300 --start-date 2024-05-28 --end-date 2024-05-29 --period 5m --workers 1 --force --allow-partial --report-output docs/reports/etf-minute-backfill-tushare-probe-2026-05-28.json` 通过，totals empty=1；provider_errors 包含 `tushare.stk_mins=tushare token not configured`、`eastmoney.etf_minute`、`akshare.fund_etf_hist_min_em`、`sina.kline`，未写入伪分钟线。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 重跑通过，仍为 `blocked_or_research_only`，`etf_t0_minute_coverage=fail`。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_strategy_24m_report_sections.py -q` 通过，26 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/scripts/backfill_etf_minute_history.py backend/scripts/etf_minute_akshare_provider.py backend/tests/test_etf_minute_backfill.py` 通过。
- [x] `git diff --check -- backend/scripts/backfill_etf_minute_history.py backend/scripts/etf_minute_akshare_provider.py backend/tests/test_etf_minute_backfill.py docs/reports/etf-minute-backfill-akshare-probe-2026-05-28.json docs/reports/strategy-improvement-closed-loop-2026-05-28.json docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 通过。
- [x] `wc -l backend/scripts/backfill_etf_minute_history.py backend/scripts/etf_minute_akshare_provider.py backend/tests/test_etf_minute_backfill.py` 确认分别为 488 / 66 / 148 行，均小于 500 行。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/strategy_improvement/provider_diagnostics.py backend/app/services/strategy_improvement/coverage.py backend/app/services/strategy_improvement/report.py backend/tests/test_strategy_improvement_closed_loop.py` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_24m_report_sections.py -q` 通过，27 passed / 1 warning。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 重跑通过，`provider_diagnostics` 指向 Tushare 探针，整体仍 `blocked_or_research_only`。
- [x] `jq '{overall_status:.summary.overall_status,minute_status:.minute_coverage.status,provider_diagnostics:.minute_coverage.provider_diagnostics}' docs/reports/strategy-improvement-closed-loop-2026-05-28.json` 确认 Tushare token 缺失、公开源失败样本和 `no_bars_written` 已进入闭环 JSON。
- [x] `rg -n "ETF 分钟线补数诊断|Provider 失败样本|分钟线造数策略" docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 确认 Markdown 已展示 provider 诊断和禁止造数策略。
- [x] `cd frontend && npm test -- StrategyImprovementGatePanel --run` 通过，1 file / 1 test；新增断言覆盖 ETF 补数诊断、Tushare token 缺失和 `fake_minute_bars_forbidden`。
- [x] `cd frontend && npx tsc -b --pretty false` 通过。
- [x] `cd frontend && npm run lint:state -- --quiet` 通过。
- [x] `git diff --check -- backend/app/services/strategy_improvement/provider_diagnostics.py backend/app/services/strategy_improvement/coverage.py backend/app/services/strategy_improvement/report.py backend/tests/test_strategy_improvement_closed_loop.py frontend/src/api/backtestBaseTypes.ts frontend/src/features/backtest/StrategyImprovementGatePanel.tsx frontend/src/features/backtest/StrategyImprovementGatePanel.test.tsx docs/reports/strategy-improvement-closed-loop-2026-05-28.json docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 通过。
- [x] `wc -l backend/app/services/strategy_improvement/provider_diagnostics.py backend/app/services/strategy_improvement/coverage.py backend/app/services/strategy_improvement/report.py backend/tests/test_strategy_improvement_closed_loop.py frontend/src/api/backtestBaseTypes.ts frontend/src/features/backtest/StrategyImprovementGatePanel.tsx frontend/src/features/backtest/StrategyImprovementGatePanel.test.tsx` 确认分别为 88 / 231 / 312 / 399 / 360 / 121 / 141 行，均小于 500 行。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/strategy_improvement/coverage.py backend/app/services/strategy_improvement/gates.py backend/app/services/strategy_improvement/report.py backend/tests/test_strategy_improvement_closed_loop.py` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_24m_report_sections.py -q` 通过，27 passed / 1 warning；新增断言覆盖 `minute_coverage.status=blocked_by_data`、`raw_data_status` 和 `blocked_reason`。
- [x] `cd frontend && npm test -- StrategyImprovementGatePanel StrategyImprovementSummary BacktestDashboard --run` 通过，3 files / 4 tests。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 重跑通过，JSON/Markdown 均显示 ETF 分钟线 `blocked_by_data`、原始状态 `partial`、原因 `insufficient_window_trade_day_coverage`。
- [x] `cd frontend && npx tsc -b --pretty false` 通过。
- [x] `cd frontend && npm run lint:state -- --quiet` 通过。
- [x] 真实库 ETF 执行元数据抽查：窗口内 ETF 分钟线 24,344 条，`premium_discount_pct` 覆盖 0.0%，正 `bid_ask_spread` 覆盖 0.0%，fresh/verified 覆盖 0.0%，`data_quality=partial_metadata` 24,344 条。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/strategy_improvement/quality.py backend/tests/test_strategy_improvement_closed_loop.py` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_improvement_closed_loop.py backend/tests/test_etf_minute_backfill.py backend/tests/test_strategy_24m_report_sections.py -q` 通过，28 passed / 1 warning；新增用例验证有字段但缺真实 ETF 执行元数据时 `market_metadata_coverage` 失败。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/strategy_improvement_closed_loop.py --start 2024-05-28 --end 2026-04-28 --existing-backtest docs/reports/strategy-24m-backtest-2026-05-28.json --json-output docs/reports/strategy-improvement-closed-loop-2026-05-28.json --markdown-output docs/reports/strategy-improvement-closed-loop-2026-05-28.md` 重跑通过，`market_metadata_coverage=fail`，缺口为 ETF 盘口价差、折溢价、跟踪指数、流动性等级、fresh/verified 覆盖不足。
- [x] `cd frontend && npm test -- StrategyImprovementGatePanel StrategyImprovementSummary BacktestDashboard --run` 通过，3 files / 4 tests；新增断言覆盖交易元数据缺口展示。
- [x] `cd frontend && npx tsc -b --pretty false` 通过。
- [x] `cd frontend && npm run lint:state -- --quiet` 通过。
- [x] `cd frontend && npm test -- StrategyImprovementGatePanel StrategyImprovementSummary BacktestDashboard --run` 重跑通过，3 files / 4 tests；真实研究闭环路由现会在参数优化/样本外验证子页签展示上线门禁。
- [x] `cd frontend && npx tsc -b --pretty false` 重跑通过。
- [x] `cd frontend && npm run lint:state -- --quiet` 重跑通过。
- [x] Playwright 浏览器联调通过：`http://127.0.0.1:5173/backtest` -> “研究闭环”，桌面 1440x960 与移动 390x844 均命中 `正式回测已阻断`、`blocked_by_data`、`insufficient_window_trade_day_coverage`、`交易元数据：fail`、`premium_discount_coverage_lt_95pct`、`ETF补数诊断`、`Provider失败`；无 console/page error，横向溢出 0。
- [x] 浏览器联调截图：
  - `/tmp/tquant-ui-qa/backtest-research-loop-desktop.png`
  - `/tmp/tquant-ui-qa/backtest-research-loop-mobile.png`

## 2026-05-28 Go/Rust 迁移深化与止盈止损辅助模型

需求来源：

- `docs/go-rust-migration-development-plan-2026-05-27.md`
- 当前 Goal：一次性尽可能完整落地 Go/Rust 迁移深化与“止盈止损辅助模型”，Go/Rust 不接管策略真源，Python 继续作为策略/风控/回测/账本真源，退出模型只能 Shadow 建议。

### 执行边界

- [x] Go 只做高并发读服务、BFF 聚合、market-read、scan 编排、缓存、fallback、metrics、traceparent；当前测试覆盖 token、readyz、metrics、partial/fallback、traceparent 和 scan-worker `python_reference` 标注。
- [x] Rust 只做 ATR、RSI、VWAP、RankIC、rolling、回撤、回测/因子纯数值计算；当前 Rust/Python parity 和 wheel import smoke 已通过。
- [x] Python 继续作为策略、风控、回测语义、模拟盘账本、动态止盈止损规则真源；Go/Rust 未接管策略决策。
- [x] 止盈止损辅助模型第一阶段只做 Shadow：不下单、不开仓/补仓、不改账本、不放宽硬止损、不绕过权限/风控；advisor fallback 也保留规则动作下限。

### 需求清单

- [x] GO-001~008：审查现有 Go 三服务主路径、字段兼容、partial/fallback、metrics、traceparent、token/readyz；`go test ./...` 已通过。
- [x] RS-001~007：审查并补齐 Rust 指标、wrapper fallback/metrics、parity、wheel smoke；`cargo test`、wheel import smoke、Python parity 已通过。
- [x] PY-001~006：确认 Python reference 仍为策略/风控/账本真源，Go/Rust 开关和 fallback 可回滚。
- [x] ML-001：新增 `exit_model_schema.py`，定义特征、建议、fallback、Shadow schema。
- [x] ML-002：新增 `exit_model_features.py`，生成持仓、行情、市场、风控、ETF 特征快照。
- [x] ML-003：新增 `exit_model_shadow.py`，记录 rule_action/model_action/feature_snapshot/model_version/后验字段；本轮改为直接按 `as_of` 交易日 upsert。
- [x] ML-004：新增 `exit_model_advisor.py`，模型加载、预测、低置信度降级、不可用 fallback，硬止损不可覆盖；本轮修复低置信度/模型不可用不能弱化规则动作。
- [x] ML-005：新增 `exit_model_dataset.py`，训练样本、标签和时间切分。
- [x] ML-006：新增 `research/scripts/train_exit_model.py` CPU smoke 训练脚本。
- [x] ML-007：新增 `research/scripts/evaluate_exit_model_shadow.py` Shadow 评估脚本。
- [x] ML-008：模拟盘只读展示模型建议和 Shadow 状态，`PaperPositionsPanel` 展示 `exit_model_shadow`。
- [x] ML-009：补 `test_paper_exit_model_*.py`，覆盖特征、标签、fallback、硬止损不可覆盖、Shadow 记录。
- [x] ML-010：训练配置、模型版本、特征版本审计，训练脚本输出 `training_config.json`、`evaluation_report.json` 和模型产物。

### 当前状态

- [x] 已阅读 `AGENTS.md` 与开发文档。
- [x] 已审查当前 Go/Rust/Python/前端实现和调用链。
- [x] 本轮补齐 `research/scripts/evaluate_exit_model_shadow.py`。
- [x] 本轮修复 `record_exit_model_shadow` 的非原子“先按今天写入再回填 as_of 日期”路径，改为直接按 `as_of` 交易日 upsert。
- [x] 本轮修复 `ExitModelAdvisor` 的 fallback/低置信度路径，确保模型不可用、低置信度或硬止损场景都不会弱化规则系统动作。
- [x] CI 已确认覆盖本轮改动：backend job 执行 `pytest backend/tests`，go-rust job 执行 Go 三服务测试、Rust tests、wheel smoke 和 Rust benchmark gate。
- [x] 云端 verify-only 验收通过：`scripts/quick_cloud_deploy.sh --verify-only --performance-verify --host 43.143.243.97 --user ubuntu --key /Users/j/Downloads/gupiao.pem --port 18090`，报告 `docs/reports/gupiao-cloud-performance-2026-05-28-022048.json`，`ok=true`。

### 验证计划

- [x] `cd go-services/bff-gateway && go test ./...` 通过。
- [x] `cd go-services/market-read-service && go test ./...` 通过。
- [x] `cd go-services/scan-worker && go test ./...` 通过。
- [x] `cd rust/tquant-rs && PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 cargo test --no-default-features` 通过，10 tests。
- [x] `cd rust/tquant-rs && cargo test` 通过，10 tests。
- [x] Rust wheel import smoke 通过：`import tquant_rs`，确认 `rsi_wilder` / `rank_ic` 可见。
- [x] Rust hit smoke 通过：`rust_max_drawdown` 命中后 metrics `hits=1/fallbacks=0/errors=0`。
- [x] Python parity：`backend/tests/test_finance_performance_math.py backend/tests/test_factor_mining.py backend/tests/test_backend_refactor_foundation.py::test_rust_math_can_be_disabled_by_config -q` 通过，23 passed。
- [x] Go fallback / route：`backend/tests/test_go_bff_shadow.py backend/tests/test_go_scan_worker_async.py backend/tests/test_market_routes.py -q` 通过，14 passed。
- [x] Exit model：`backend/tests/test_paper_exit_model_features.py backend/tests/test_paper_exit_model_advisor.py backend/tests/test_paper_exit_model_shadow.py -q` 通过，10 passed。
- [x] 模拟盘退出回归：`backend/tests/test_paper_auto_trading.py backend/tests/test_paper_dynamic_exit.py -q` 通过，39 passed。
- [x] `backend/.venv/bin/python research/scripts/train_exit_model.py --smoke --output /tmp/tquant-exit-model-goal-rerun` 通过，输出模型、训练配置和评估报告。
- [x] `backend/.venv/bin/python research/scripts/evaluate_exit_model_shadow.py --smoke --model /tmp/tquant-exit-model-goal-rerun --output /tmp/tquant-exit-model-goal-rerun/shadow_eval.json` 通过。
- [x] 前端模拟盘展示 smoke：`cd frontend && npm test -- PaperTradingPerformance PaperTradingSections --run` 通过，1 file / 1 test。
- [x] 前端全量 `npm run lint` 通过。
- [x] 前端全量 `npm run build:web` 通过。
- [x] 前端全量 `npm test -- --run` 通过，20 files / 56 tests。
- [x] 后端全量 `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q` 通过，780 passed / 1 warning。
- [x] Go/Rust 性能验收：`BACKEND_PYTHON=backend/.venv/bin/python python scripts/verify_go_rust_performance_acceptance.py` 通过，报告 `docs/reports/go-rust-performance-acceptance-2026-05-27.json`，Go benchmark 与 Rust speedup hard gates 均通过。
- [x] 云端 verify-only + performance verify 通过：readyz、protected API、frontend、MySQL、Go BFF/market-read/scan-worker health、scan-worker accept、Rust finance math hit/fallback metrics 均通过；线上报告 `docs/reports/gupiao-cloud-performance-2026-05-28-022048.json`。
- [x] 云端可观测性：Go BFF partial timeout、market-read fallback/unresolved miss 以 warning 输出并进入报告；未被当作正常结果吞掉，`failures=[]`。

## 2026-05-27 TQuant Claude 审查整改与策略回测证据链

需求来源：

- `docs/TQuant_Claude审查问题提取与实施整改方案.md`
- 当前 Goal：落地整改方案全部可实施项，并对所有策略执行最近 24 个月回测、根据结果继续调整策略参数/过滤/风控/信号逻辑。

### 本轮执行顺序

- [x] `trading-quant-lead`：先处理策略可交易性、信号规则、仓位、风控、回测基线。
- [ ] `stock-analysis-specialist`：继续补市场退潮、板块轮动、情绪周期、龙头识别过滤。
- [ ] `product-strategist`：把策略优化结果转成配置项、页面能力和验收标准。
- [ ] `ui-designer`：补信号/风险/仓位/止损展示。
- [ ] `fullstack-builder`：落地前后端、数据链路、配置持久化、容错。
- [ ] `qa-tester`：补回归、异常场景、策略一致性测试。
- [ ] `devops-operator`：补部署、监控、回滚和运行手册。

### 当前完成项

- [x] Q-001：`low_buy_market_backtest.py` 增加 `--states`，支持 `confirmed` / `buy_now,soft_buy_now` 专项回测。
- [x] Q-001：报告增加 `selected_signal_states`、全量信号状态分布、状态过滤跳过分布、未成交原因、退出原因。
- [x] Q-001：Markdown 报告增加“策略诊断”表，避免只看收益指标而无法定位样本丢失/未成交原因。
- [x] Q-004：全 17 个低吸策略已跑一次当前本地数据可覆盖范围内的 confirmed 专项基线。
- [x] 回测脚本增加 `--start` / `--end`，报告增加数据覆盖率，明确本地数据不足 24 个月时不能作为完整验收。
- [x] Q-002：新增 `backend/scripts/low_buy_execution_matrix.py`，可复现固定止损、ATR 动态止损和出口模型矩阵。
- [x] Q-003：`low_buy_market_backtest.py` 增加研究态执行模型 override：固定止损、ATR 止损、首次止盈、移动防守、最大持有、强制 T+1/T+2 退出。
- [ ] Q-002/Q-003：全 17 个低吸策略已在当前本地数据可覆盖范围内完成 6 个 confirmed 执行模型阶段矩阵；`fixed_stop_m3p5`、`atr_stop_0p8`、`atr_stop_1p2` 尚未跑完。结果只作为部分区间研究证据，不直接切生产参数。
- [x] Q-006：新增研究态市场保护 A/B 回测入口，支持 `risk_release`、`high_flyer_retreat` 等市场状态下对 `buy_now` / `soft_buy_now` 降级或阻断；默认关闭，不改变生产策略真源。
- [x] Q-007：新增首板出货风险阈值研究矩阵，支持以研究态 prefilter override 比较 5.8 / 5.5 / 5.2 / 5.0，不直接修改生产默认值。

### 当前基线结果

- 报告路径：
  - `backend/data/reports/low_buy_market_backtest_24m_confirmed_2025-10-09_2026-04-20.json`
  - `backend/data/reports/low_buy_market_backtest_24m_confirmed_2025-10-09_2026-04-20.md`
- 数据覆盖：请求 24 个月，当前本地 SQLite 实际可评估 `2025-10-09` 至 `2026-04-20`，约 6.26 个月，覆盖率 26.08%，因此只能作为部分区间基线。
- 全策略 confirmed 汇总：评估 205，成交 202，净胜率 44.55%，均净收益 -0.0982%，总收益 -32.9389%，最大回撤 -58.8845%，Sharpe -0.3482，Profit Factor 0.9495。
- 信号分布：`watch=7276`、`avoid=4053`、`near_entry=2380`、`buy_now=176`、`soft_buy_now=29`。
- 过滤诊断：本次只评估 confirmed，状态过滤跳过 13709 条；未成交原因全部为“信号后 2 日未出现可成交买点。”共 3 条。
- 退出诊断：移动防守线 65、首次止盈 64、止损 46、最长持有 26、开盘跳空止损 1。
- 当前含 confirmed 成交的策略：`first_board`、`volume_shrink`、`late_session_strong_support`、`core_midcap_vwap_ma5_retrace`、`n_pattern_long_wash`、`n_pattern_short_wash`。

### Q-002/Q-003 执行模型矩阵结果

- 报告路径：
  - `backend/data/reports/execution_matrix_full/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.json`
  - `backend/data/reports/execution_matrix_full/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.md`
- 命令：
  - `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py --start 2025-10-09 --end 2026-04-28 --months 24 --strategies all --states confirmed --engine fast --materialization-mode isolated --scan-limit 480 --limit 80 --variants default_exit,fixed_stop_m2p5,atr_stop_1p0,force_t1_close,force_t2_close,quick_tp3_trailing1 --resume-existing --resume-search-dir backend/data/reports/execution_matrix --output-dir backend/data/reports/execution_matrix_full --matrix-output-dir backend/data/reports/execution_matrix_full`
- 数据覆盖：请求 24 个月，实际覆盖率 26.08%，仍然只能作为部分区间研究基线。
- 默认退出模型：成交 202，净胜率 44.55%，均净收益 -0.0982%，止损率 23.27%，执行 PF 0.9495，总收益 -32.9389%，最大回撤 -58.8845%，Sharpe -0.3482，平均持仓 2.45 天。
- 固定 -2.5% 止损：成交 202，净胜率 31.68%，均净收益 -0.346%，止损率 63.86%，执行 PF 0.8027，总收益 -56.1869%，最大回撤 -68.8534%，Sharpe -1.5397，平均持仓 2.72 天。当前部分区间证据显示更紧固定止损显著恶化，不能推广。
- ATR 1.0x 动态止损：成交 202，净胜率 43.56%，均净收益 -0.3358%，止损率 30.2%，执行 PF 0.8448，总收益 -59.1805%，最大回撤 -70.8719%。当前部分区间证据显示 ATR 1.0x 变差，不能推广。
- 强制 T+1 收盘退出：成交 202，净胜率 45.54%，均净收益 0.3029%，止损率 19.8%，执行 PF 1.1893，总收益 51.7536%，最大回撤 -42.7195%，平均持仓 1.36 天。该模型改善资金效率和净收益，但仍需完整 24M/OOS 验证。
- 强制 T+2 收盘退出：成交 202，净胜率 43.56%，均净收益 0.1075%，止损率 22.28%，执行 PF 1.0575，总收益 -0.2683%，最大回撤 -45.9759%，平均持仓 1.91 天。
- `3% 首次止盈 + 1% 移动防守 + 最多 3 天`：成交 202，净胜率 82.67%，均净收益 0.826%，止损率 17.33%，执行 PF 2.0085，总收益 384.6271%，最大回撤 -27.1855%，Sharpe 4.5913，平均持仓 1.3 天。该模型在部分区间显著优于默认，但盈亏比仅 0.4209，且收益可能受高频小止盈路径影响，必须补完整 24M、样本外和模拟盘观察后再考虑配置化灰度。
- 收尾说明：本轮按用户要求停止长跑，未遗留后台进程。`backend/scripts/low_buy_execution_matrix.py` 已支持 `--resume-existing`，后续可从已落盘变体继续补跑 `fixed_stop_m3p5`、`atr_stop_0p8`、`atr_stop_1p2`。

### Q-006 市场退潮/高位分化保护 A/B

- 代码入口：
  - `backend/scripts/low_buy_market_backtest_market_guard.py`
  - `backend/scripts/low_buy_market_backtest.py --market-guard-mode`
  - `backend/scripts/low_buy_market_backtest_runner.py`
  - `backend/scripts/low_buy_market_backtest_reporting.py`
  - `backend/scripts/low_buy_market_backtest_markdown.py`
- 参数：
  - `--market-guard-mode none|degrade_retreat|block_retreat`
  - `--market-guard-states high_flyer_retreat,risk_release`
  - `--market-guard-degrade-to near_entry|watch|avoid`
  - `--market-guard-min-strength`
- 设计边界：该能力仅用于研究态回测 A/B，默认 `none`；生产低吸信号、优先榜、模拟盘自动交易不因本入口改变。
- 真实退潮/风险释放 smoke：
  - 报告：`backend/data/reports/smoke/market_guard/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_high_flyer_retreat-risk_release_to_avoid_min_0_2026-04-09_2026-04-20.md`
  - 结果：8 个评估交易日、9 个 confirmed 信号，市场保护触发 0。该窗口内没有 `high_flyer_retreat` / `risk_release` confirmed 信号，不能说明保护无效，只说明本地样本未覆盖触发场景。
- 强制机制 smoke：
  - 报告：`backend/data/reports/smoke/market_guard_forced/low_buy_market_backtest_24m_confirmed_default_exit_guard_block_retreat_broad_rally-repair-low_volume_wait-weight_support-weight_support_active-fast_rotation-high_flyer_retreat-risk_release_to_avoid_min_0_2026-04-09_2026-04-20.md`
  - 结果：市场保护触发 9 次，分布为 `fast_rotation=4`、`repair=2`、`weight_support_active=2`、`broad_rally=1`，所有 actionable confirmed 信号被降级为 `avoid`，报告中已写入 `market_guard_count` 和各策略诊断。
- 阶段结论：Q-006 的 A/B 回测入口、诊断字段和单元测试已完成；尚未完成完整 24M 退潮样本验证，也没有把该规则切入生产主路径。

### Q-007 首板出货风险阈值矩阵

- 代码入口：
  - `backend/app/services/low_buy/candidate_rule_params.py`
  - `backend/scripts/low_buy_market_backtest.py --prefilter-override`
  - `backend/scripts/low_buy_first_board_distribution_matrix.py`
- 设计边界：研究态 prefilter override 使用上下文变量临时生效；退出上下文后默认参数恢复，不写运行时参数、不改生产默认值。
- 报告路径：
  - `backend/data/reports/first_board_distribution_matrix/first_board_distribution_matrix_24m_confirmed_2025-10-09_2026-04-28.json`
  - `backend/data/reports/first_board_distribution_matrix/first_board_distribution_matrix_24m_confirmed_2025-10-09_2026-04-28.md`
- 命令：
  - `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_first_board_distribution_matrix.py --start 2025-10-09 --end 2026-04-28 --months 24 --states confirmed --scan-limit 480 --limit 80 --thresholds 5.8,5.5,5.2,5.0 --output-dir backend/data/reports/first_board_distribution_matrix --matrix-output-dir backend/data/reports/first_board_distribution_matrix`
- 当前本地数据覆盖：请求 24 个月，实际覆盖约 6.26 个月，覆盖率 26.08%，仍然只能作为部分区间研究基线。
- 结果：
  - 阈值 5.8：命中候选 1178，confirmed 39，成交 39，净胜率 43.59%，均净收益 -0.1564%，PF 0.91，最大回撤 -33.9743%。
  - 阈值 5.5：命中候选 1176，confirmed 39，成交 39，净胜率 43.59%，均净收益 -0.1564%，PF 0.91，最大回撤 -33.9743%。
  - 阈值 5.2：命中候选 1176，confirmed 39，成交 39，净胜率 43.59%，均净收益 -0.1564%，PF 0.91，最大回撤 -33.9743%。
  - 阈值 5.0：命中候选 1176，confirmed 39，成交 39，净胜率 43.59%，均净收益 -0.1564%，PF 0.91，最大回撤 -33.9743%。
- 阶段结论：仅下调 `first_board` 预筛 `max_distribution_risk_score` 在当前可用样本中几乎不影响 confirmed 成交和绩效；执行确认层已经有 `first_board.max_distribution_risk_score=5.2`，因此没有证据支持把生产预筛默认值从 5.8 直接下调到 5.2。Q-007 应保留为完整 24M/OOS 后复核项。

### 验证记录

- [x] `python -m py_compile backend/scripts/low_buy_market_backtest.py backend/scripts/low_buy_market_backtest_runner.py backend/scripts/low_buy_market_backtest_reporting.py backend/scripts/low_buy_market_backtest_markdown.py backend/tests/test_n_pattern_observe_confirmed.py`
- [x] `python -m py_compile backend/scripts/low_buy_execution_matrix.py backend/scripts/low_buy_market_backtest.py backend/app/services/low_buy/execution_simulation.py backend/tests/test_low_buy_trade_controls.py`
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_n_pattern_observe_confirmed.py backend/tests/test_low_buy_next_day_event_model.py -q` 通过，11 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_trade_controls.py::LowBuyTradeControlTests::test_execution_override_can_apply_atr_stop_without_changing_candidate_plan backend/tests/test_low_buy_trade_controls.py::LowBuyTradeControlTests::test_execution_override_can_force_t1_exit_for_research_matrix backend/tests/test_low_buy_trade_controls.py::LowBuyTradeControlTests::test_execution_override_can_force_t2_exit_without_manual_holding_days -q` 通过，3 passed / 1 warning。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_market_backtest.py --start 2025-10-09 --end 2026-04-28 --months 24 --strategies all --states confirmed --engine fast --materialization-mode isolated --scan-limit 480 --limit 80 --output-dir backend/data/reports` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py --start 2025-10-09 --end 2026-04-28 --months 24 --strategies all --states confirmed --engine fast --materialization-mode isolated --scan-limit 480 --limit 80 --variants default_exit,atr_stop_1p0,force_t1_close,force_t2_close,quick_tp3_trailing1 --output-dir backend/data/reports/execution_matrix --matrix-output-dir backend/data/reports/execution_matrix` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_trade_controls.py -q` 通过，19 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/scripts/low_buy_market_backtest.py backend/scripts/low_buy_market_backtest_runner.py backend/scripts/low_buy_market_backtest_reporting.py backend/scripts/low_buy_market_backtest_markdown.py backend/scripts/low_buy_market_backtest_market_guard.py backend/tests/test_low_buy_trade_controls.py` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_market_backtest.py --start 2026-03-01 --end 2026-04-28 --months 24 --strategies first_board,volume_shrink,n_pattern_long_wash,n_pattern_short_wash --states confirmed --engine fast --materialization-mode isolated --scan-limit 160 --limit 40 --max-dates 8 --market-guard-mode block_retreat --market-guard-states high_flyer_retreat,risk_release --output-dir backend/data/reports/smoke/market_guard` 通过，市场保护触发 0。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_market_backtest.py --start 2026-03-01 --end 2026-04-28 --months 24 --strategies first_board,volume_shrink,n_pattern_long_wash,n_pattern_short_wash --states confirmed --engine fast --materialization-mode isolated --scan-limit 160 --limit 40 --max-dates 8 --market-guard-mode block_retreat --market-guard-states broad_rally,repair,low_volume_wait,weight_support,weight_support_active,fast_rotation,high_flyer_retreat,risk_release --output-dir backend/data/reports/smoke/market_guard_forced` 通过，市场保护触发 9。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_trade_controls.py -q` 通过，20 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/low_buy/candidate_rule_params.py backend/scripts/low_buy_market_backtest.py backend/scripts/low_buy_market_backtest_reporting.py backend/scripts/low_buy_market_backtest_markdown.py backend/scripts/low_buy_first_board_distribution_matrix.py backend/tests/test_low_buy_trade_controls.py` 通过。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_first_board_distribution_matrix.py --start 2026-03-01 --end 2026-04-28 --months 24 --states confirmed --scan-limit 160 --limit 40 --max-dates 8 --thresholds 5.8,5.5,5.2,5.0 --output-dir backend/data/reports/smoke/first_board_distribution_matrix --matrix-output-dir backend/data/reports/smoke/first_board_distribution_matrix` 通过，生成 smoke 报告。
- [x] `DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/low_buy_first_board_distribution_matrix.py --start 2025-10-09 --end 2026-04-28 --months 24 --states confirmed --scan-limit 480 --limit 80 --thresholds 5.8,5.5,5.2,5.0 --output-dir backend/data/reports/first_board_distribution_matrix --matrix-output-dir backend/data/reports/first_board_distribution_matrix` 通过，生成当前本地可覆盖区间矩阵报告。

### 下一步

- [x] 2026-05-28 收尾：新增主力模型 Shadow warmup 只读脚本并刷新报告，本地观察样本 2 -> 10，`production_effect=readonly_shadow`，`production_parameter_change=false`。
- [x] 2026-05-28 收尾：P1 `first_board` / `volume_shrink` 参数窄网格已完成 21 个矩阵窗口，结论写入 `docs/reports/focus-strategy-parameter-walk-forward-2026-05-28/summary.md` 和总报告；收益主要来自 3% 首次止盈与 1% 移动防守的冲高兑现。
- [x] 2026-05-28 收尾：夸张收益口径已在总报告中区分为研究指标、诊断复利和待补 Paper 账户曲线，禁止当作生产收益或参数晋级证据。
- [ ] Q-002：继续补完整固定止损 3.5、ATR 0.8/1.2 矩阵，并在 24M 数据补齐后复跑；当前固定 -2.5% 和 ATR 1.0x 部分区间未通过。
- [ ] Q-003：将 `3% 首次止盈 + 1% 移动防守 + 最多 3 天` 作为研究候选配置化，不直接上线；补 OOS、分市场状态和模拟盘观察。
- [ ] Q-006：基于完整 24M 数据复跑退潮/高位分化保护 A/B，验证新开仓减少、回撤改善和非退潮样本不过度流失后，再决定是否进入可审计配置。
- [ ] Q-007：完整 24M/OOS 数据补齐后复跑首板出货风险阈值矩阵；当前部分区间无证据支持直接下调生产默认值。
- [ ] Q-017：把通过验证的策略参数接入可审计配置和 feature flag，未验证参数只保留研究模式。

## 2026-05-27 ETF Universe 管理与真实 OOS 数据集增强

需求来源：

- `docs/etf-universe-oos-enhancement-plan-2026-05-27.md`
- 用户 Goal：完整实现 ETF universe 专用管理 UI / 修复向导、admin-only 后端管理接口、校验/diff/审计/回滚链路、真实标注 OOS dataset manifest 与验证服务、回测页 OOS 验证入口、策略工作台和模拟盘阶段门槛展示。

### 总体目标

- [x] 后端：ETF universe admin 服务，支持 baseline/current/override diff、校验、修复草稿、apply、rollback。
- [x] 后端：admin-only API，所有 mutation 写 quant audit 与 operation audit，校验 error 时禁止激活。
- [x] 后端：真实标注 OOS manifest loader、dataset quality 校验、真实 regime segments 注入 ETF T0 research。
- [x] 后端：OOS validate 和 promote-check 接口，结果只读，不自动改生产策略或绕过模拟盘风控。
- [x] 前端：设置页 ETF Universe 管理 UI / 修复向导 / diff / 审计回滚入口。
- [x] 前端：回测页 ETF T0 OOS 数据集选择、质量、覆盖、验证结果、门槛结论。
- [x] 前端：策略工作台和模拟盘展示 ETF T0 阶段、最新 OOS 结论和未满足门槛原因。
- [x] 测试：补后端、前端、权限、审计、回滚、OOS 质量、Go/Rust 不承载策略决策等测试。

### 本轮边界

- [x] 不修改低吸策略、候选生成、策略排序、风控阈值和自动交易策略公式。
- [x] ETF universe 只定义品种能力与交易约束，不生成策略信号。
- [x] ETF T0 策略真源仍为 Python；Go 只读行情/data quality，Rust 只做指标加速。
- [x] OOS 通过只生成 `paper_small` / `candidate_production` 建议，不自动启用生产交易。
- [x] 第一阶段复用 quant parameter 版本、审计、回滚链路，不新增破坏性迁移。

### 当前执行计划

- [x] M1：Universe 管理只读与校验。
- [x] M2：Universe 修复向导与可审计保存/回滚。
- [x] M3：OOS Manifest 与只读验证。
- [x] M4：OOS 结果沉淀与上线门槛展示。

### 验证计划

- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_etf_universe_admin.py backend/tests/test_etf_t0_oos_dataset.py backend/tests/test_etf_t0_oos_validation.py -q` 通过，11 passed。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_etf_universe_admin.py backend/tests/test_etf_t0_oos_dataset.py backend/tests/test_etf_t0_oos_validation.py backend/tests/test_etf_t0_backtest.py -q` 通过，19 passed。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q` 通过，757 passed / 1 warning。
- [x] `cd frontend && npm test -- EtfUniverseAdminCard EtfT0OosPanel EtfT0BacktestPanel EtfT0StrategyStatusPanel PaperTradingPerformance --run` 通过，5 files / 5 tests。
- [x] `cd frontend && npm run lint` 通过。
- [x] `cd frontend && npx tsc -b --pretty false` 通过。
- [x] `cd frontend && npm run build:web` 通过。
- [x] `cd go-services/bff-gateway && go test ./...` 通过。
- [x] `cd go-services/market-read-service && go test ./...` 通过。
- [x] `cd go-services/scan-worker && go test ./...` 通过。
- [x] `cd rust/tquant-rs && PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 cargo test --no-default-features` 通过，7 tests。
- [x] `BACKEND_PYTHON=backend/.venv/bin/python python scripts/verify_go_rust_performance_acceptance.py` 通过，`docs/reports/go-rust-performance-acceptance-2026-05-27.json` hard gates ok。
- [x] `git diff --check` 通过。
- [x] `./scripts/quick_cloud_deploy.sh --performance-verify` 通过，已部署到 `http://43.143.243.97:18090`，线上报告 `docs/reports/gupiao-cloud-performance-2026-05-27-155515.json` hard gates ok。

### 上线验证记录

- [x] ETF Universe admin 后端接口和设置页 UI 已进入部署包，mutation 仍要求 admin 权限并写 quant audit / operation audit。
- [x] OOS manifest、OOS validate、promote-check 和 latest 阶段展示已进入部署包，验证结果只读，不自动启用生产交易。
- [x] 策略工作台、回测页、模拟盘已展示 ETF T0 OOS 阶段、数据集版本、门槛结论和失败原因。
- [x] Go/Rust 边界已锁定：Python 仍是 ETF T0 策略真源；Go 只承担 BFF、market-read、scan-worker 编排和只读数据质量；Rust 只承担指标加速。
- [x] 部署性能门禁中 `monitor_bff p95=17.974ms`、`scan_worker_accept p95=114.144ms`、Rust 指标 `hits=6/fallbacks=0`、失败项为空。
- [x] Go BFF 对监控页重源 `market_breadth`、`sector_relative_strength`、`paired_hedge` 增加源级短超时和分类 partial error，避免重源拖慢实时监控主入口。

## 2026-05-27 策略优化与 ETF 做T 增强

需求来源：

- `docs/strategy-etf-t0-enhancement-plan-2026-05-27.md`
- 用户补充约束：不可以影响已有策略。

### 总体目标

- [x] 补齐 ETF universe 与 T+0 eligibility，禁止继续用“所有 ETF 前缀默认 T+0”作为生产判断。
- [x] 增加 ETF 分钟级信号与 ETF T0 回测。
- [x] 增强模拟盘 ETF T0 执行、风控暂停、失败原因和复盘归因的最小执行门禁。
- [x] 在实时监控展示 ETF 做T机会、分钟信号、风险、阻断原因和验收结果。
- [x] Go 只做批量读取和 data quality 聚合；Rust 只做指标计算加速；策略真源仍为 Python。
- [x] 补齐本轮后端、前端、Go、Rust、回测、模拟盘测试和验收命令。
- [x] 策略工作台、模拟盘、回测页增加 ETF 专区、执行门禁、分钟快照诊断和五类市场状态验收入口。
- [x] ETF T0 参数热力图批量计算、五类市场状态自动分段验证和模拟盘逐笔复盘归因面板已完成最小可运行闭环。

### 本轮边界

- [x] 实现 ETF universe / T+0 eligibility 基础层。
- [x] 不修改低吸策略、候选生成、策略排序、风控阈值和自动交易策略公式。
- [x] 保留现有 510300 等既有测试路径兼容，同时让未知 ETF 默认不具备 T+0 执行资格。
- [x] 用测试锁住：ETF 识别、T+0 eligibility、模拟盘可卖日期、现有 ETF 同日卖出不回归。
- [x] 新增 ETF 分钟信号服务，复用现有 Python 指标入口；Rust 仅作为 RSI/VWAP 等指标加速，不承载策略真源。
- [x] 新增 ETF T0 分钟回测服务和 `/api/backtests/etf-t0-minute` 研究权限接口；回测只读，不写模拟盘账本。
- [x] 模拟盘自动 ETF T0 下单要求 `t0_eligible=true` 且分钟信号为 `positive_t_buy`，避免把临时降级或观察信号当作可执行结果。
- [x] 新增 `/api/market/etf-universe` 研究权限接口，暴露 ETF universe 版本、审计路径、T+0 eligibility 和交易约束。
- [x] 新增 `/api/market/etf-minute-snapshots` 研究权限诊断接口，经 Go market-read-service 只读分钟快照和数据质量。
- [x] Go market-read-service 新增 `/api/market-read/v1/etf-minute-snapshot-batch`，只读 Redis/MySQL 分钟快照，不输出策略决策。
- [x] 前端状态遵守当前 lint 约束，新面板状态进入 Zustand store，不在业务组件中使用 `useState`。

### 当前决策

- Python 仍是策略和交易规则真源。
- `is_etf` 继续表示基金/ETF 类识别，用于手续费、报价精度、基金类限价规则等。
- 新增独立的 `is_t0_eligible_etf` / `same_day_sell_allowed` 表达“是否允许按 T+0 执行”，避免把 ETF 识别等同于 T+0。
- 第一阶段使用代码内置 ETF universe 和规则兜底，不做破坏性数据库迁移；后续再扩展为可审计、可回滚的持久化配置。
- ETF 分钟信号只对 universe 放行、数据 fresh、流动性/价差/量能/趋势风险不过线的标的产生正T或反T候选。
- 自动交易当前只允许正T买入候选进入模拟盘自动订单，反T卖出候选先作为展示/研究信号，不自动卖出底仓。

### 验证计划

- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_rules.py backend/tests/test_paper_routes.py backend/tests/test_backtest_v2_engine_contract.py -q`
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_rules.py backend/tests/test_paper_routes.py backend/tests/test_backtest_v2_engine_contract.py backend/tests/test_etf_t0_signal.py backend/tests/test_etf_t0_backtest.py backend/tests/test_phase4_phase5_foundation.py::test_sector_etf_validation_reports_acceptance_from_current_opportunities backend/tests/test_paper_auto_trading.py::PaperAutoTradingTest::test_auto_trader_builds_sector_etf_t0_order backend/tests/test_paper_auto_trading.py::PaperAutoTradingTest::test_auto_trader_skips_sector_etf_without_intraday_positive_t_signal backend/tests/test_paper_auto_trading.py::PaperAutoTradingTest::test_auto_trader_skips_sector_etf_without_t0_eligibility backend/tests/test_market_routes.py -q` 通过，78 passed。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_etf_t0_backtest.py backend/tests/test_etf_t0_signal.py backend/tests/test_market_rules.py backend/tests/test_market_routes.py backend/tests/test_paper_routes.py::PaperRouteTests::test_sector_etf_t0_performance_includes_trade_review_attribution backend/tests/test_paper_auto_trading.py::PaperAutoTradingTest::test_auto_trader_builds_sector_etf_t0_order backend/tests/test_paper_auto_trading.py::PaperAutoTradingTest::test_auto_trader_skips_sector_etf_without_intraday_positive_t_signal backend/tests/test_paper_auto_trading.py::PaperAutoTradingTest::test_auto_trader_skips_sector_etf_without_t0_eligibility -q` 通过，33 passed。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q` 通过，746 passed。
- [x] `cd frontend && npm test -- --run src/features/trading-workspace/MonitorPage.test.tsx` 通过，5 passed。
- [x] `cd frontend && npm test -- --run src/features/backtest/BacktestDashboard.test.tsx src/features/backtest/EtfT0BacktestPanel.test.tsx src/features/trading-workspace/MonitorPage.test.tsx src/features/trading-workspace/PaperTradingPage.test.tsx src/features/strategy/EtfT0StrategyStatusPanel.test.tsx src/features/paper/PaperTradingPerformance.test.tsx` 通过，15 passed。
- [x] `cd frontend && npm run lint -- --max-warnings=0` 通过。
- [x] `cd frontend && npm test -- --run` 通过，18 files / 54 tests。
- [x] `cd frontend && npm run build` 通过。
- [x] `cd go-services/market-read-service && go test ./...` 通过。
- [x] `cd go-services/bff-gateway && go test ./...` 通过。
- [x] `cd go-services/scan-worker && go test ./...` 通过。
- [x] `cd rust/tquant-rs && cargo test --no-default-features` 通过，7 tests。
- [x] `BACKEND_PYTHON=backend/.venv/bin/python PYTHONPATH=backend:. backend/.venv/bin/python scripts/verify_go_rust_performance_acceptance.py` 通过，刷新 `docs/reports/go-rust-performance-acceptance-2026-05-27.json`。
- [x] `git diff --check` 通过。

### 后续未完成项

- [x] 参数热力图已接入 `/api/backtests/etf-t0-research` 后端批量网格计算，前端回测页可一键运行；结果仍为只读研究报告，不写生产参数。
- [x] 五类市场状态已接入自动分段验证输出，覆盖牛市、震荡、熊市、退潮、强反弹；后续可替换为真实标注 OOS 数据集。
- [x] 模拟盘 ETF 复盘归因已在 `/api/paper/performance/sector-etf-t0` 返回 `review_trades`，前端绩效面板展示逐笔“原因/执行/风险提示”。
- [x] ETF universe 已经接入运行时参数覆盖、量化参数审计/回滚链路，并补齐专用管理 UI 和修复向导。

## 2026-05-26 上线前审查报告采纳计划落地

需求来源：

- `docs/prelaunch-review-adoption-plan-2026-05-26.md`

### 本轮目标

- [x] 修正 Go scan-worker status/health 语义，明确 Go 是生产编排层、策略引擎为 Python reference，并补测试。
- [x] 为 Rust 增加 criterion benchmark、Makefile 入口和 CI artifact，保持生产默认启用但用 wheel/metrics/fallback 验收。
- [x] 扩展 Go BFF：strategy/settings/factor 聚合、workspace/source 维度指标、cache size/ttl/hit rate。
- [x] 补前端路由 cold navigate 测试和开发期一致性 warning；保留实时监控作为全市场复盘主入口。
- [x] 强化运行手册：RL 可选依赖、Redis 限速、内部 token、Rust wheel、Go fallback 指标、复盘口径。
- [x] 对 trade_date 字符串迁移做兼容设计和测试边界，不破坏低吸、回测、策略结果口径。
- [x] 标注 agent benchmark 样本不足，避免被误用为策略收益证据。

### 当前决策

- 复盘仍作为全市场复盘在实时监控主展示，模拟盘只保留辅助入口。
- Rust 不因 wheel 风险改回默认关闭；生产镜像必须预装 wheel，fallback 必须可观测。
- 15:00 收盘快照不替换为 14:57；如需要尾盘信号，新增 late-session slot。
- Go scan-worker 不宣传为独立策略内核，当前准确口径是 Go 编排 Python reference。
- 策略、筛选、风控、回测、模拟盘决策只依赖 Python reference；Go/Rust 只做非策略主路径、扫描编排、读服务或指标加速。

### 验证计划

- [x] `cd go-services/scan-worker && go test ./...`
- [x] `cd go-services/bff-gateway && go test ./...`
- [x] `cd go-services/market-read-service && go test ./...`
- [x] `cd rust/tquant-rs && cargo test && cargo bench --features extension-module --bench finance`
- [x] `cd frontend && npm run lint && npm test -- --run && npm run build`
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q`
- [x] `BACKEND_PYTHON=backend/.venv/bin/python PYTHONPATH=backend:. backend/.venv/bin/python scripts/verify_go_rust_performance_acceptance.py`

## 2026-05-26 未完成/部分完成项最终收尾与上线验证

需求来源：

- 用户明确列出的“未完成 / 部分完成”清单。

### 本轮决策

- [x] `trade_date` 字段真实迁移：本轮放弃，不做破坏性迁移。当前仅保留审计和兼容测试；真实迁移必须单独设计 SQLite/MySQL 双端 Alembic、索引/唯一约束、历史字符串兼容和策略回归。
- [x] MarketEmotionPage：已拆分为情绪仪表盘和龙头强度表组件。
- [x] 15:00 快照替换为 14:57/14:55：本轮放弃，保留 15:00 作为收盘快照；尾盘预警应新增 `late_session` slot，不替换收盘口径。
- [x] 响应式 smoke 登录态：新增 `SMOKE_MOCK_AUTH=1` 模式，用 mock 登录态/API 覆盖登录后的 `/monitor`、`/emotion`、`/paper`、`/backtest`、`/settings`。
- [x] 云端部署验收：已部署到 `http://43.143.243.97:18090`，并完成 readyz、Go health、前端未登录/登录态 smoke。

### 本轮验证

- [x] `cd frontend && npm run lint` 通过。
- [x] `cd frontend && npm test -- --run` 通过，13 files / 46 tests。
- [x] `cd frontend && npm run build` 通过。
- [x] `cd frontend && SMOKE_MOCK_AUTH=1 npm run smoke:responsive` 通过，375/768/1440 的 `/monitor`、`/emotion`、`/paper`、`/backtest`、`/settings` 均无横向溢出和 JS 错误。
- [x] 首次云端部署发现 `rust:1.82` 无法解析锁定依赖 `clap_lex 1.1.0` 的 edition 2024 manifest，已将生产 Rust builder 升级到 `rust:1.95-bookworm`，保持 wheel 作为镜像产物。
- [x] `scripts/quick_cloud_deploy.sh --key /Users/j/Downloads/gupiao.pem` 已完成部署；过程中修复一键部署脚本，确保 Python app/runtime/backtest 容器强制替换到新 `tquant-web:mysql` 镜像，避免“镜像构建成功但线上仍服务旧前端”。最终完整脚本复跑通过，输出 `web_image:updated` 与 `web_image:ok`。
- [x] `scripts/quick_cloud_deploy.sh --key /Users/j/Downloads/gupiao.pem --verify-only` 通过，包含 `web_image:ok`、readyz、受保护 API、前端入口和三个 Go 服务 readyz。
- [x] 线上 `FRONTEND_SMOKE_URL=http://43.143.243.97:18090 npm run smoke:responsive` 通过，最大横向溢出 0。
- [x] 线上 `FRONTEND_SMOKE_URL=http://43.143.243.97:18090 SMOKE_MOCK_AUTH=1 npm run smoke:responsive` 通过，最大横向溢出 0。

## 2026-05-26 M0-M6 未完成项继续收敛

需求来源：

- `docs/market-trading-enhancement-requirements-2026-05-25.md`
- `docs/market-trading-enhancement-execution-plan-2026-05-25.md`
- 用户要求继续完成上一轮明确的未完成/部分完成项，必要时部署到云服务器验收。

### 本轮目标

- [x] Go market-read-service 不只停留 quote batch，继续接入 sector strength、key levels、intraday latest 到 Python 主读路径。
- [x] Go scan-worker 尽量补强生产扫描证据：状态、排序一致性、失败不污染 latest、benchmark/acceptance 证据；如仍依赖 Python reference，必须明确为业务真源 fallback 而非 shadow。
- [x] pulse / 复盘补历史查询与可回放入口，满足 M6 历史留痕的最小闭环。
- [x] settings/db migration 补运行时诊断与 UI 可见性，减少“后端有报告但页面不可见”的缺口。
- [x] Rust 补完整 Python parity 证据，避免只靠 wheel smoke 和性能脚本。
- [ ] 如果本地验收受限，使用现有 `scripts/deploy_cloud_server.sh` 部署到云服务器并执行 readyz、Go/Rust metrics、关键页面/API smoke。

### 当前风险

- Go scan-worker 已从 shadow 变成生产编排主路径并受 Go 状态/失败不污染 latest 测试保护；低吸策略计算、候选排序和 snapshot 写入语义仍调用 Python reference 作为业务真源，不规划在本阶段迁移为纯 Go 内核。
- 云端部署阻塞：本机 `ssh -o BatchMode=yes ubuntu@43.143.243.97` 返回 `Permission denied (publickey,password)`，未提供 `CLOUD_SSH_KEY` / `CLOUD_PASSWORD`，无法执行部署脚本。本轮已完成线上只读 readyz 和响应式 smoke。

### 本轮验证

- [x] `git diff --check` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m compileall backend/app -q` 通过。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q` 通过，668 passed / 47 warnings。
- [x] `cd frontend && npm run lint` 通过。
- [x] `cd frontend && npm test -- --run` 通过，13 files / 37 tests。
- [x] `cd frontend && npm run build` 通过。
- [x] `cd go-services/bff-gateway && go test ./...` 通过。
- [x] `cd go-services/market-read-service && go test ./...` 通过。
- [x] `cd go-services/scan-worker && go test ./...` 通过。
- [x] `cd rust/tquant-rs && cargo test` 通过，6 tests。
- [x] `cd rust/tquant-rs && cargo test --no-default-features` 通过，6 tests。
- [x] `BACKEND_PYTHON=backend/.venv/bin/python PYTHONPATH=backend:. backend/.venv/bin/python scripts/verify_go_rust_performance_acceptance.py` 通过，Go quote benchmark 7612 ns/op，Rust speedup max_drawdown 6.988 / rolling_mean 11.862 / atr_wilder 9.408。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python - <<'PY' ... rust_math.rust_available()` 通过，Rust extension available=true。
- [x] Alembic 空库 `DATABASE_URL=sqlite:///$tmp/app.db backend/.venv/bin/alembic upgrade head` 通过，包含 `20260526_0001`。
- [x] 本地 `FRONTEND_SMOKE_URL=http://127.0.0.1:4173 npm run smoke:responsive` 通过，375/768/1440、`/monitor` `/emotion` `/backtest` `/settings` 无横向溢出和 JS 错误；未登录态被记录为 `authenticated=false`。
- [x] 线上只读 `curl http://43.143.243.97:18090/readyz` 通过，database/frontend_dist 均 true。
- [x] 线上只读 `FRONTEND_SMOKE_URL=http://43.143.243.97:18090 npm run smoke:responsive` 通过，未登录态记录为 `authenticated=false`。
- [ ] 云端部署未执行：缺 SSH 凭据，无法上传和重建容器。

## 2026-05-23 全模块代码审查报告整改

需求来源：`TQuant_全模块代码审查报告_2026-05-23.md`

### 已完成

- [x] `VERSION.json` 从正式 1.0.0 改为 `0.9.0` + `release_stage=stabilization`，避免在关键问题未完全验收前误标正式版。
- [x] 2026-05-21 后端/前端旧重构方案文档增加归档/历史状态说明，避免多份方案并行造成执行口径冲突。
- [x] `DailyBarSnapshot.trade_date` 模型改为 DATE 语义，OHLCV 改为 `Numeric` 精度列，并新增 Alembic 迁移 `20260523_0001_daily_bar_snapshot_decimal_date.py`。
- [x] 日线仓库增加 ISO 日期归一化，兼容既有字符串调用方和迁移后的 DATE 返回值。
- [x] 模拟盘持仓与批次建立 ORM relationship，并在 `PaperPositionService.get_positions/get_position` 使用 `selectinload`，避免批次访问退化为 N+1。
- [x] 生产环境 `GLOBAL_RATE_LIMIT_BACKEND=memory` 已在 `security_config.py` 中 fail-fast；MySQL compose 默认注入 Redis 限流。
- [x] 前端 `antd` / `antd-mobile` 依赖改为精确版本锁定，避免 clean install 被范围版本漂移影响。
- [x] RL 研究依赖保持可选 requirements 文件，并在 `position_shadow.py` 中显式 ImportError 降级说明，默认生产镜像不加载 PyTorch。
- [x] 部署/清理/监控脚本移除默认公网 IP，要求显式传入 `CLOUD_HOST`；HTTPS 脚本要求显式传入 `DOMAIN`/`EMAIL`。
- [x] `PRODUCTION_RUNBOOK.md` 示例改为占位符，不再写死公网 IP 和生产域名。
- [x] MySQL compose 增加 `/var/lib/mysql/mysql-slow.log` 显式路径，慢日志随 `mysql_data` volume 持久化，避免 `/var/log/mysql` 权限风险。
- [x] Web Router 从单一 workspaceElement 改为每条业务路由显式传入页面标识，`useWorkspaceNavigation` 改用 React Router `navigate/location`，不再手写 `window.history.pushState` / `popstate`。
- [x] 新增后端回归测试锁住 `DailyBarSnapshot` 类型和模拟盘持仓批次 eager load 查询上限。

### 核验说明

- [x] 报告中 “antd 6 不存在” 与当前 npm registry 状态不符：`npm view antd version` 为 `6.4.3`。本轮采用精确锁定而非降级到旧大版本，避免破坏现有 AntD 6 组件实现。
- [x] 报告提到的 watchlist/latest_signal 与 low_buy/signal_detail N+1 关系在当前模型中是 JSON 快照/批量仓库读取，不存在可 `selectinload` 的 ORM relation；本轮对真实存在的 paper position lots N+1 风险做硬修复和测试。

### 本轮验证

- [x] `npm view antd version --silent` 返回 `6.4.3`。
- [x] `cd frontend && npm ci --ignore-scripts` 通过。
- [x] `cd frontend && npm run build:web` 通过。
- [x] `backend/.venv/bin/python -m compileall backend/app backend/tests/test_backend_refactor_foundation.py -q` 通过。
- [x] `cd backend && .venv/bin/python -m pytest tests/test_backend_refactor_foundation.py tests/test_bff_routes.py tests/test_performance_regression.py -q` 通过，27 passed。
- [x] SQLite Alembic 空库 `upgrade head`、新增迁移 `downgrade`、再 `upgrade head` 均通过。
- [x] `backend/.venv/bin/python` 静态解析 `docker-compose.mysql.yml`，确认 MySQL slow log 与 Redis 限流配置存在。
- [x] `make qa` 通过。
- [x] `make prod-preflight` 通过。
- [x] `git diff --check` 通过。

## 后端 Go/Rust 重构最终方案落地

需求来源：`docs/backend-go-rust-refactor-final-plan-2026-05-22.md`

### 执行约束

- [x] 不修改任何策略公式、策略阈值、选股规则、自动交易规则。
- [x] 历史阶段采用 Go/Rust 默认不启用；截至 2026-05-27，Go 已升级为非策略生产主路径，Rust 已升级为 Python 调用的指标加速生产路径。
- [x] 先完成 Phase 0 基础加固，再补 Phase 1-4 的可插拔骨架。

### 已完成

- [x] DB 连接池配置化：新增 `DB_POOL_SIZE`、`DB_MAX_OVERFLOW`、`DB_POOL_TIMEOUT`、`DB_POOL_RECYCLE`，MySQL engine 不再硬编码连接池参数。
- [x] BFF Redis 短缓存：新增 `workspace_cache.py`，支持 monitor/paper/strategy/settings 按用户和参数缓存，partial response 不缓存。
- [x] BFF 缓存配置化：新增 `BFF_WORKSPACE_CACHE_ENABLED` 和各 workspace TTL。
- [x] Docker Compose MySQL 生产参数补齐：连接数、buffer pool、redo log、slow query、long query time 可配置。
- [x] Docker Compose Redis 持久化补齐：AOF everysec、AOF rewrite、RDB save 策略。
- [x] Docker Compose 应用/worker 注入 DB 连接池环境变量。
- [x] Docker Compose 增加可选 `mysql-backup` profile，不默认启动，避免影响现有部署。
- [x] Go BFF Gateway 骨架：健康检查、metrics、内部 token 校验、manifest/workspace 只读透传、`X-TQuant-Bff-Hop` 防循环。
- [x] Go BFF 影子校验接入 Python BFF：可选 `TQUANT_BFF_GATEWAY_URL` + `TQUANT_BFF_SHADOW_ENABLED`，对 manifest / workspace 做后台契约比对，不影响现有响应。
- [x] Go Market Read Service 骨架：健康检查、metrics、批量报价只读 Redis 本地行情缓存，未命中时返回 partial/unavailable，不接外部源、不写数据库。
- [x] Go Market Read Service 补齐只读聚合能力：基于 Redis 本地行情快照计算板块内相对强度和分时关键位，Redis 未命中时可只读 MySQL 最新日线快照兜底，接口均受内部 token 保护。
- [x] Python 行情批量读取增加可选 Go market-read seam：配置 `TQUANT_MARKET_READ_SERVICE_URL` 后先读 Go 本地快照，失败或未配置时回退现有 Python Provider Router。
- [x] Go Scan Worker 骨架：shadow 状态接口，明确 production write 禁止。
- [x] Go Scan Worker 增加影子触发 seam：`/api/scan-worker/v1/shadow/run` 仅接受请求并返回只读状态，不写生产快照。
- [x] Python 低吸物化刷新接入 Go Scan Worker 影子触发：新增 `TQUANT_GO_SCAN_WORKER_URL` / `TQUANT_GO_SCAN_SHADOW_ENABLED`，默认关闭；开启后只触发 shadow run，不改变 Python 策略结果。
- [x] Go Market / Scan 内部接口增加 `X-Internal-Service-Token` 校验，健康检查不受影响，避免 profile 启用后裸读内部接口。
- [x] Python BFF 远端适配补齐 `X-Request-ID` 透传，跨服务调用可按 request_id 串联日志。
- [x] Python BFF 远端适配指标接入 `/metrics`：calls/successes/failures/circuit_short_circuits/credentials_suppressed。
- [x] Go BFF 生成缺失 `X-Request-ID` 时同步写入上游请求头和响应头，保证 Python 上游和客户端看到同一链路 ID。
- [x] 历史阶段 Docker Compose 曾使用可选 `go-bff`、`go-market`、`go-scan` profiles；当前 MySQL compose 已默认启动 Go 三服务。
- [x] Docker Compose 为 app/worker 注入 `TQUANT_INTERNAL_SERVICE_TOKEN` 和远端服务 URL 开关，默认空值保持当前 Python 路径。
- [x] Rust PyO3 `tquant-rs` 骨架：`max_drawdown`、`rolling_mean`、`atr_wilder`。
- [x] Python Rust 可选入口：`rust_math.py` 默认关闭，包装 `max_drawdown`、`rolling_mean`、`atr_wilder`，失败自动回退，不影响现有计算。
- [x] 新增测试覆盖配置化、BFF cache 和 Rust 默认关闭。
- [x] BFF 缓存指标接入 `/metrics`：reads/hits/writes/skips/schema_misses。
- [x] BFF 本地聚合统一超时：monitor/paper/strategy/settings 均通过 `run_workspace_with_timeout`，慢数据源返回 partial response，避免拖住前端请求。
- [x] 清理未跟踪 `output/` 本地产物，并将 `output/` 加入 `.gitignore`。
- [x] Go/Rust 骨架补测试源码并已本地执行：Go BFF/Market/Scan 与 Rust `tquant-rs` 基础单元测试均通过。
- [x] 新增 `scripts/verify_backend_refactor_foundation.sh`，统一验证 Python、Compose、Go、Rust 基础骨架。
- [x] 验证脚本无 Docker 时仍解析 `docker-compose.mysql.yml`，至少校验关键服务存在，避免本地完全跳过 Compose 结构检查。
- [x] 新增运行手册：`docs/backend-refactor-runtime-runbook-2026-05-22.md`；该手册已在 2026-05-27 更新为 Go 非策略生产主路径、Rust 指标加速生产路径口径。

### 历史阶段说明

- [x] 2026-05-22 的默认关闭 / shadow 口径已被 2026-05-27 方案取代，不再作为当前生产目标。
- [x] Go BFF、Go market-read-service、Go scan-worker 在 MySQL compose 中默认启动；Python 保留可观测 fallback。
- [x] Go scan-worker 只编排 Python reference，不实现独立策略公式；策略计算、候选排序和 snapshot 写入语义仍由 Python reference 负责。
- [x] Rust `tquant_rs` 在生产镜像中作为 wheel 产物安装，`RUST_FINANCE_MATH_ENABLED=true` 默认启用；导入或计算失败时回退 Python 并暴露 metrics。
- [x] MinuteBar 时序库升级不在本轮执行：文档定义为条件触发，当前不做破坏性数据迁移；后续只有分钟数据规模真实触发阈值后再进维护窗口。

### 本轮验证

- [x] Python 编译：`backend/.venv/bin/python -m compileall backend/app backend/tests/test_backend_refactor_foundation.py -q` 通过。
- [x] 后端针对性 pytest：`cd backend && .venv/bin/python -m pytest tests/test_backend_refactor_foundation.py tests/test_bff_routes.py tests/test_performance_regression.py -q` 通过，23 passed。
- [x] 统一验证脚本：`scripts/verify_backend_refactor_foundation.sh` 通过，Python `34 passed`，Go BFF/Market/Scan `go test` 通过，Rust `cargo test` 通过；Compose YAML 静态解析通过。
- [x] Go scan shadow 新增测试：`backend/tests/test_backend_refactor_foundation.py` 覆盖默认关闭和多策略触发；统一验证脚本更新为 Python `34 passed`。
- [x] `make qa` 通过。
- [x] `make prod-preflight` 通过。
- [x] Compose YAML 解析：`backend/.venv/bin/python - <<'PY' ... yaml.safe_load(...)` 通过，识别 10 个 services。
- [x] diff 检查：`git diff --check` 通过。
- [x] 新增文件行数检查：本轮新增 Go/Rust/Python 文件均小于 500 行。
- [x] Compose 结构静态检查替代验证：本机未安装 Docker，无法执行 `docker compose config`；统一验证脚本已用 YAML 静态解析覆盖关键服务存在性。
- [x] Go/Rust 编译测试：本机已安装 Go/Rust 后补跑通过；Rust 使用 ABI3 兼容环境变量执行测试。
- [x] `make runtime-snapshot`：本地 SQLite 临时后端启动后通过 healthz/readyz，runtime 详情因端点要求登录态返回“请先登录”，符合当前安全设计。
- [x] 云端部署：`scripts/deploy_cloud_server.sh` 已完成，远端 migration/app/runtime-worker/backtest-worker 重建成功。
- [x] 云端验收：`http://43.143.243.97:18090/readyz`、`https://43.143.243.97/readyz -k` 均返回 ok；远端 Compose profile 识别 `go-bff-gateway`、`go-market-read-service`、`go-scan-worker`。
- [x] 最新数据闭环验收：云端 `latest_data_acceptance.py` 返回 ok，预期/发布交易日均为 `2026-05-22`，日线 5208 条，8 个生产策略快照齐全，无失败和警告。
- [x] HTTPS 本机回环验收：服务器本机通过 `--resolve weisilianghua.cloud:443:127.0.0.1` 访问 `/readyz` 返回 ok；外网直连域名当前 TLS 握手被重置，属于域名/SNI/云网络层问题，IP HTTPS 和 HTTP 服务正常。

## 前端重构 Codex 版报告核验与落地

需求来源：`/Users/j/Downloads/TQuant_前端重构完整方案_Codex版.html`

### 核验结论

- 报告中的基础设施建议大部分已在当前项目落地：Ant Design / antd-mobile、React Router、TanStack Query、按 feature 拆目录、因子实验室均已存在。
- 当前最有价值、低风险的剩余建议：路由直达与 404 明确化、统一状态页组件命名、保留旧路由兼容。

### 本轮落地范围

- [x] Web Router 从单一 `*` 捕获改为白名单路由：`/monitor`、`/emotion`、`/analysis`、`/playbook`、`/low-buy`、`/strategy`、`/paper`、`/performance`、`/settings`。
- [x] 根路径 `/` 重定向到 `/monitor`，保留旧 `/low-buy` 与 `/performance` 兼容。
- [x] 未知路径不再静默显示监控页，改为明确的 404 状态页并提供返回实时监控按钮。
- [x] `PAGE_PATHS` 增加报告建议的规范 URL：监控 `/monitor`，选股宝典 `/playbook`。
- [x] 新增 `StateViews.tsx`，提供报告要求的 `TqEmpty` / `TqPageLoading` / `TqErrorResult` / `TqForbidden` 统一状态组件。
- [x] 旧 `EmptyState` / `LoadingState` / `ErrorState` 改为兼容包装，避免大范围改动调用点。

### 暂不落地项

- [ ] Zustand 全量迁移：当前 auth 与业务数据流运行稳定，若强行迁移会扩大鉴权回归风险。

### 验证

- [x] `cd frontend && npm run build:web` 通过。
- [x] `cd frontend && npm test` 通过，12 files / 33 tests。
- [x] `npm run preview -- --host 127.0.0.1 --port 4173` + Playwright 冒烟通过：`/` 跳 `/monitor`，`/monitor` 与 `/playbook` 可直达，未知路径显示 404。

## 前端最终重构优化基础层

需求来源：`docs/frontend-final-refactor-optimization-plan-2026-05-21.md`

### 本轮执行范围

- [x] 安装第一批基础依赖：Ant Design、Ant Design Icons、antd-mobile、TanStack Query、TanStack Virtual、React Router。
- [x] 新增 `frontend/src/app` 基础层：通用 Providers、Web/Native Router、QueryClient、Query Keys、权限 Guard。
- [x] 新增 `frontend/src/ui` 设计系统基础层：AntD 主题、Shell、反馈态、数据展示、表单、图表容器。
- [x] 重构 Web 入口：`main.tsx` 接入 AppProviders、WebUiProviders、React Router。
- [x] 重构 Native 入口：`main-native.tsx` 接入 AppProviders、Memory Router，并避免引入桌面 AntD Provider。
- [x] 新增 Query seam：monitor / playbook / holdings / paper / settings 查询或 mutation 包装，供后续页面迁移复用。
- [x] Web 工作台顶部 Shell 导航迁移到 Ant Design `Menu` / `Badge` / `Dropdown`，保留现有页面状态和权限逻辑。
- [x] Web 核心页面第一批控件迁移：系统配置分类、选股宝典策略切换、模拟盘详情切换统一改为 Ant Design `Tabs`。
- [x] 交易工作台共享动作控件迁移：股票卡片操作、设置卡保存、错误弹窗、股票详情弹窗改用 Ant Design `Button` / `Modal`。
- [x] 实时监控和系统配置主操作按钮改用 Ant Design `Button`，保留原有回调和 loading 语义。
- [x] App 壳层第一批迁移：底部导航改用 `antd-mobile` `TabBar`，状态提示改用 `NoticeBar`。
- [x] 回测页面大文件拆分：`BacktestDashboard.tsx` 降到 471 行，新增纯 helper 文件；`api/backtests.ts` 降到 496 行，新增 API helper 文件。
- [x] 系统配置页继续拆分：校验/dirty state helper 独立，页面降到 396 行；修复旧 `.settings-tabs button` 规则误伤 AntD Tabs 的风险。
- [x] 系统配置管理操作继续迁移 Ant Design：板块过滤清空、策略治理操作、功能开关切换改用 `Button` / `Switch`。
- [x] App 端继续拆分：`MobileDesignCards.tsx` 格式化逻辑独立，策略切换改用 `antd-mobile` `CapsuleTabs`，板块偏好逻辑独立为 hook。
- [x] 实时监控页继续拆分：盘面摘要、今日动作、数据质量、榜单提示等纯逻辑抽入 helper，页面降到 320 行。
- [x] 回测页面继续拆分：任务进度、PanelHeader、Metric、EmptyLine 独立组件化，页面保持 437 行。
- [x] 回测 API 层继续拆分：响应归一化逻辑独立到 `backtests.normalizers.ts`，`api/backtests.ts` 降到 219 行。
- [x] 回测页面常用控件继续迁移 Ant Design：刷新、快速/专家切换、策略多选、提交、取消任务改用 `Button` / `Segmented` / `Checkbox`。
- [x] 策略工作台继续迁移 Ant Design：刷新、一键体检、策略确认弹窗和确认摘要按钮改用 `Button` / `Modal`。
- [x] 因子实验室继续迁移 Ant Design：刷新、生成假设、合成代码、保存草稿、评估、晋级和激活开关改用 `Button` / `Input` / `Checkbox` / `Switch`。
- [x] 系统配置继续迁移 Ant Design：板块过滤多选改用 `Checkbox`，因子权重输入改用 `InputNumber`。
- [x] 模拟盘盘中确认弹窗按钮改用 Ant Design `Button`。
- [x] 回测研究区剩余控件迁移 Ant Design：优化、样本外验证、对比、归因导出、ML/容量面板和任务列表统一改用 `Button` / `Checkbox`。
- [x] 策略工作台剩余控件迁移 Ant Design：健康摘要、流程步骤、预设选择、因子库列表统一改用 `Button`。
- [x] 工作台剩余通用控件迁移 Ant Design：命令面板、账本修复、个股详情切换、ETF 参数开关、页面错误重试、成交标签、机甲委托入口统一改用 `Button` / `Input` / `Checkbox`。
- [x] App / App Preview 剩余控件迁移 antd-mobile：账户菜单、候选详情、更新弹窗、行业偏好、持仓搜索、持仓编辑、候选/持仓操作统一改用 `Button` / `Input`。
- [x] App 壳层补齐 `PullToRefresh`：按当前 Tab 触发对应刷新，低吸 Tab 支持强制刷新候选池。
- [x] App 持仓编辑 Sheet 改为 `antd-mobile` `Popup`，保留原有表单语义。
- [x] Vitest 增加 `antd-mobile` 测试轻量 mock；生产和 Native 构建仍使用真实 `antd-mobile`。
- [x] Web/Native 根路由改为 `React.lazy`：`TradingWorkspace` 和 `MobileApp` 从入口同步包中拆出，降低首屏同步加载压力。
- [x] 核心页面新增 feature 入口并完成真实实现搬迁：`analysis`、`market-emotion`、`playbook`、`paper`、`monitor`、`settings` 页面实现已在对应 feature 目录，`trading-workspace` 旧兼容 re-export 已删除。
- [x] 删除根路由懒加载后不再被引用的旧 `frontend/src/App.tsx`。
- [x] 删除前端可确认无引用的占位/废弃组件、旧策略交通灯组件、空目录；保留 `vite-env.d.ts`、测试 mock 等必要基础文件。
- [x] 目标范围内不再存在原生 `button` / checkbox / select / textarea 残留：`frontend/src/features/backtest`、`strategy`、`factor-mining`、`trading-workspace`、`mobile`、`app-preview` 扫描为 0。
- [x] 保留现有页面业务行为，不在本批次直接替换核心交易页面，避免影响策略与模拟盘逻辑。

### 已验证

- [x] `cd frontend && npm run build:web` 通过。
- [x] `cd frontend && npm run build:native` 通过；Native 构建未引入桌面 AntD 大包。
- [x] `cd frontend && npm test` 通过，12 files / 33 tests。
- [x] `cd frontend && npm audit --audit-level=moderate` 通过，0 vulnerabilities；曾发现的 `brace-expansion` moderate 已通过 `npm audit fix` 修复。
- [x] `git diff --check` 通过。
- [x] `rg -n "<button|<input\\s+type=\\\"checkbox\\\"|<select|<textarea" frontend/src/features/backtest frontend/src/features/strategy frontend/src/features/factor-mining frontend/src/features/trading-workspace frontend/src/mobile frontend/src/features/app-preview` 无结果。
- [x] 新增 `frontend/src/app` / `frontend/src/ui` 文件均小于 500 行。
- [x] 本轮新增/拆分文件均小于 500 行；搬迁后的 `features/settings/SettingsPage.tsx` 400 行、`features/monitor/MonitorPage.tsx` 320 行、`features/paper/PaperTradingPage.tsx` 288 行、`features/playbook/PlaybookPage.tsx` 241 行。
- [x] `api/backtests.ts` 从 496 行降到 219 行，归一化文件 305 行。
- [x] `trading-workspace` 旧 re-export wrappers 已清理，测试与业务引用改为直接指向目标 feature / shared 模块。
- [x] 前端无引用文件启发式扫描仅剩 `vite-env.d.ts`，该文件为 Vite 类型声明，需保留。

### 保留项与原因

- [x] 第一批核心页面实现已从 `trading-workspace` 搬迁到业务 feature 目录；旧兼容 re-export wrappers 已删除，避免继续扩大 shell 目录职责。
- [x] 共享业务 UI 组件 `WorkspaceComponents` 搬迁到 `features/workspace-shared`，旧路径兼容 re-export 已删除。
- [x] 共享格式化、类型、视图模型和工作台常量 `workspaceFormatters` / `workspaceTypes` / `workspaceViewModels` / `workspaceConstants` 搬迁到 `features/workspace-shared`。
- [x] 模拟盘主要子组件 `PaperDetailTabs`、`PaperTradingSections`、`PaperTradingSummaryBar`、`PaperTodayActionPanel` 搬迁到 `features/paper`。
- [x] 模拟盘详情与委托组件 `PaperTradingPerformance`、`PaperLedgerRepairPanel`、`PaperPositionDetailsPanel`、`PaperOrderEntryModal` 搬迁到 `features/paper`，旧路径兼容 re-export 已删除。
- [x] 模拟盘日期/状态工具与机甲舱组件、动画资产搬迁到 `features/paper`，旧路径兼容 re-export 已删除。
- [x] 设置页主要子组件 `SettingsPagePanels`、`SettingsPageTabs`、`AuthSecurityCard`、`LatestDataStatusCard` 搬迁到 `features/settings`。
- [x] 设置页量化参数卡片 `QuantParameter*` 与 `quantParameterCardUtils` 搬迁到 `features/settings`，旧路径兼容 re-export 已删除。
- [x] 监控页小组件 `InstrumentSyncProgress`、`MonitorHoldingWizard` 搬迁到 `features/monitor`，旧路径兼容 re-export 已删除。
- [x] K 线通用 ECharts 渲染器搬迁到 `ui/charts`，工作台业务包装搬迁到 `features/workspace-shared`，旧路径兼容 re-export 已删除。
- [x] `requestCached` 保留兼容函数名，但底层已迁移为 TanStack Query `fetchQuery`，鉴权/管理令牌变化和显式 invalidation 会清理 Query cache。
- [x] ECharts 与专家面板已按需加载；后续优化应基于真实首屏 profiling 决定是否进一步替换组件。

## Auth 安全整改核验与补强

需求来源：用户 2026-05-20 直接给出的 AUTH-C/AUTH-H 安全问题清单。

### 核验结论

- [x] `JWT_SECRET` 硬编码/弱默认：当前后端使用 `AUTH_SECRET_KEY`，无源码默认密钥；启动期 `main.py` 调用 `ensure_auth_secret_configured()`，生产安全配置拒绝弱密钥。
- [x] Token 吊销：access token 带 `sid` 和 `token_version`；logout、refresh replay、管理员禁用/降权都会吊销 session 或提升 token_version。
- [x] API Key/敏感配置明文：系统配置中的 `llm_api_key`、`database_url` 走 Fernet 派生加密，公开响应只返回脱敏值；审计日志会脱敏 token/secret/api_key；运行时配置不再把 `LLM_API_KEY` 写入 `runtime.env`。
- [x] 登录/注册暴力破解：登录 IP + 账号维度限流、账号失败锁定和注册限流均已存在。
- [x] RBAC/归属：策略治理、参数、回测/优化/验证、模拟盘、Agent 写工具均有登录、角色或管理员校验；正式回测任务和旧兼容研究回测列表/详情均按 owner_user_id 隔离。
- [x] 密码哈希：当前为 `scrypt_sha256`，旧 `pbkdf2_sha256` 登录时自动升级；未发现 MD5 密码哈希。
- [x] Refresh Token：httpOnly Cookie、7 天有效期、每次 refresh 轮换，旧 token 重放会吊销用户全部会话。
- [x] MFA：模拟盘下单默认要求 TOTP；本轮补齐 Agent 模拟盘下单同样必须使用已登录用户会话并通过 paper_trade/MFA 门禁，Agent token 不能直接下单。

### 本轮修改

- [x] `/api/agent/paper/order` 在工具写权限之外追加用户会话、模拟盘权限和 MFA 校验。
- [x] 增加回归测试：Agent scoped token 即使有 write_paper scope 也不能直接创建模拟盘委托；写工具打开时未开启 MFA 的用户会被拒绝。
- [x] 旧兼容 `/api/backtests/runs` 和 `/api/backtests/runs/{id}` 增加 owner_user_id 过滤；旧 `/api/backtests` 创建的回测记录写入当前用户 ID。
- [x] 系统设置保存时清理历史 `runtime.env` 中的 `LLM_API_KEY`，后续只允许从数据库加密字段读取/更新 API Key；保留旧环境变量读取兼容但不再持久化。

### 验证结果

- [x] `backend/.venv/bin/python -m compileall backend/app backend/tests/test_agent_routes.py backend/tests/test_research_route_ownership.py -q` 通过。
- [x] `backend/.venv/bin/python -m compileall backend/app/services/settings_service.py backend/tests/test_low_buy_trade_controls.py -q` 通过。
- [x] `PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_trade_controls.py::LowBuyTradeControlTests::test_settings_public_payload_masks_secrets_and_preserves_masked_updates -q` 通过，1 passed。
- [x] `cd backend && .venv/bin/python -m pytest tests/test_auth_routes.py tests/test_auth_hardening.py tests/test_auth_cookie_security.py tests/test_login_lockout.py tests/test_agent_routes.py tests/test_paper_routes.py tests/test_research_route_ownership.py -q` 通过，55 passed。
- [x] `PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_trade_controls.py::LowBuyTradeControlTests::test_settings_public_payload_masks_secrets_and_preserves_masked_updates backend/tests/test_security_quant_extensions.py backend/tests/test_totp_secret_crypto.py backend/tests/test_security_hardening.py -q` 通过，9 passed。

## 量化增强闭环：Kelly+ATR、Regime、实盘回测监控、BL、另类数据、在线学习、执行算法、套利研究

需求来源：用户 2026-05-20 直接需求。

### 执行口径

- 不接真实券商和真实交易所下单。
- 现有 Kelly+ATR、市场状态、Markowitz、在线学习、真实撮合滑点已有基础实现，本轮只补缺口和生产接入。
- “多交易所套利”在 A 股平台中按研究/诊断能力落地，不进入自动交易。
- 新增文件保持 500 行以内，不改变现有策略买卖语义。

### TODO

- [x] P0：核实并补强 Kelly+ATR 仓位管理在模拟盘自动下单链路中的结构化输出与测试。
- [x] P0：核实并补强市场状态识别对策略参数/仓位缩放的生产链路。
- [x] P0：新增实盘/模拟盘 vs 回测表现对比监控，输出策略失效和滑点损耗告警。
- [x] P1：补齐 Black-Litterman 组合优化方法，并接入现有 portfolio-optimization API。
- [x] P1：新增另类数据情绪/事件评分服务，作为研究信号和候选加权输入，不直接自动交易。
- [x] P1：核实在线学习闭环已由 paper trade 样本、warm_start、人工审批构成，并补测试/报告字段。
- [x] P1：扩展回测执行算法：TWAP、VWAP、Implementation Shortfall 语义明确，成交假设写入输出。
- [x] P1：新增多市场/多交易所套利研究诊断接口，默认只报告不可交易/需人工确认。
- [x] 最终运行编译、针对性测试和前端构建。

### 当前发现

- `PositionSizer` 已读取 `kelly_position`、`final_position_cap_pct`、`volatility_position_pct`、`validation_position_scale`、`portfolio_weight_scale`。
- 市场状态、分市场参数晋级和自进化调度已有实现。
- Markowitz 已用共同成交日和 NaN 协方差，缺 Black-Litterman。
- ML 在线学习已有 paper sample、warm_start、时序验证、artifact hash 和人工审批。
- Backtest broker 已支持 VWAP、保守滑点、市场冲击，缺 TWAP/IS 枚举和成交假设。

### 本轮落地

- 新增 `black_litterman_optimizer.py`，`/api/backtests/{run_id}/portfolio-optimization?method=black_litterman` 可返回 BL 权重和有效前沿。
- 新增 `/api/backtests/live-comparison`，比较模拟盘真实平仓收益与最近回测收益差，发现策略实盘损耗。
- 新增 `/api/market/alternative-sentiment`，基于缓存新闻/公告/社交事件源输出研究层情绪分，不进入自动交易。
- 新增 `/api/market/multi-exchange-arbitrage/research`，明确多交易所套利当前为研究边界，不把 Provider 价差误当可交易机会。
- Backtest execution model 新增 `twap` 和 `implementation_shortfall`，并写入前端选项和执行假设。

### 本轮验证

- `backend/.venv/bin/python -m compileall backend/app backend/tests/test_quant_enhancement_completion.py -q` 通过。
- `cd backend && .venv/bin/python -m pytest tests/test_quant_enhancement_completion.py tests/test_ml_markowitz_regime_rl.py tests/test_bff_routes.py -q` 通过，18 passed。
- `cd frontend && npm run build` 通过。

## 因子挖掘系统落地计划

需求来源：`/Users/j/Downloads/TQuant_因子挖掘系统规划方案.html`

### 目标

1. 建立因子库、因子沙盒计算、因子评估、LLM/本地假设生成、代码合成、解释与迭代闭环。
2. 新增后端 API 与数据库表，支持候选因子从 `candidate` 到 `validated/production/rejected/archived` 的生命周期。
3. 在策略工作台新增“因子实验室”入口，支持假设生成、因子创建、评估、晋级查看。
4. 所有新增文件保持 500 行以内，不改动现有策略买卖语义。

### TODO

- [x] 新增 FactorDefinition / FactorEvalRun / FactorApproval 数据模型与 Alembic 迁移。
- [x] 新增 factor_mining 服务包：模型、因子库、沙盒计算、评估、假设生成、代码合成、结果解释、迭代循环、生产集成。
- [x] 新增 `/api/factor-mining/*` 路由，覆盖列表、创建、假设生成、代码合成、评估、迭代、晋级和异步评估入队。
- [x] 策略工作台增加“因子实验室”Tab 与前端 API。
- [x] 增加后端单元测试，覆盖 AST 安全、假设生成数量、评估指标和 API 基础契约。
- [x] 运行 Python 编译、针对性 pytest、前端构建验证。

### 已验证

- `backend/.venv/bin/python -m compileall backend/app backend/alembic/versions -q` 通过。
- `backend/.venv/bin/python -m pytest backend/tests/test_factor_mining.py backend/tests/test_factor_registry.py backend/tests/test_strategy_evolution_scheduler_tasks.py -q` 通过，11 passed。
- `PYTHONPATH=backend DATABASE_URL=sqlite:////tmp/... AUTH_SECRET_KEY=test-secret backend/.venv/bin/alembic -c backend/alembic.ini upgrade head` 通过。
- `npm run build` 通过。
- `make qa` 通过。

### 实施说明

- DeepSeek 适配器固定默认模型 `deepseek-v4-flash`；未配置或接口失败时自动使用本地结构化模板，确保功能不中断。
- 生产晋级只允许评估结果达到 production gate 后执行，并记录操作审计；动态因子先注册到因子库和 FactorSpec 元数据，不会静默改变现有策略评分。

## v4 五大整改包剩余项实施计划

需求来源：`docs/TQuant-v4-五大整改包整改需求计划-2026-05-09.md`

### 当前批次目标

1. P1：补齐 UserSession refresh hash 唯一索引迁移检查、操作审计覆盖、自动退出行情质量结构化、Provider 自适应排序。
2. P2：补齐优先榜 Redis 分布式缓存、Walk-forward 按市场状态输出最佳参数。
3. P2/P3：补齐 RBAC/MFA、外部因子多 Provider、本地数据优先、组合优化/RL 研究、Web/Native API Client 解耦、个性化 SSE、审计入口和验收测试。

### 实施约束

- 单文件保持 500 行以内。
- 新功能优先新建小文件。
- 不改变核心策略阈值和买卖逻辑。
- 数据库结构调整必须通过 Alembic 迁移。

### TODO

- [x] UserSession refresh_token_hash 迁移前重复校验 + 显式唯一索引。
- [x] 高风险 mutating API 自动写 operation_audit_log。
- [x] 自动退出计划返回结构化行情质量，不使用旧价兜底。
- [x] Provider Router 根据成功率和延迟做自适应排序。
- [x] 优先榜响应缓存支持 Redis 跨 worker 共享，Redis 不可用降级进程缓存。
- [x] Walk-forward by_market_state 输出最佳参数和窗口详情。
- [x] SSE 增加事件 id / Last-Event-ID 兼容。
- [x] 统一 RBAC helper，模拟盘权限支持动态验证码强制策略。
- [x] 外部因子支持 Local + AkShare 多 Provider 降级链路。
- [x] 市场状态、热点行业和优先榜支持 Redis 跨 worker 缓存。
- [x] Local Provider 补齐行业映射、行业资金流、本地涨停快照和热点板块降级。
- [x] Backtest 增加策略组合 HRP/均值方差优化研究接口。
- [x] Backtest 增加离线仓位策略研究接口，明确不进入自动交易。
- [x] Web / Native API 增加 IApiClient 注入抽象，桌面与 App API 包装层复用。
- [x] 系统配置页增加操作审计入口。
- [x] 补充/运行针对性测试。

### 已验证

- `make qa` 通过。
- `backend/.venv/bin/python -m compileall backend/app backend/alembic/versions -q` 通过。
- `backend/.venv/bin/python -m pytest backend/tests/test_v4_remaining_contracts.py backend/tests/test_security_quant_extensions.py backend/tests/test_phase4_phase5_foundation.py backend/tests/test_pkg02_pkg04_contracts.py backend/tests/test_market_provider_contract.py -q` 通过，45 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_auth_cookie_security.py backend/tests/test_login_lockout.py backend/tests/test_security_headers.py backend/tests/test_v4_completion_contracts.py backend/tests/test_v4_remaining_contracts.py -q` 通过，10 passed。
- `npm run build` 通过。
- 生产代码文件未发现超过 500 行；现存超过 500 行的是既有测试文件。

## v7 全界面易用性优化执行计划

来源：`/Users/j/Downloads/TQuant_v7_深度报告_含UX优化.html`

### 目标

- 所有核心页面优先展示“现在该做什么 / 买卖边界 / 错了怎么办”。
- 减少英文和不必要专业术语，保留必要金融指标但增加中文解释。
- 不修改策略计算、交易规则、后端权限和数据库结构。
- 以低风险前端整改为主，保证现有功能可回归。

### 实施项

1. 登录页：补齐登录中/验证成功反馈、MFA 明确说明、错误处理下一步提示。
2. 实时监控页：增加“今天我该做什么”摘要；录入字段增加示例；持仓和榜单卡片突出当前动作、风险和失效条件。
3. 选股宝典：策略页签增加用途说明；分层文案改为“现在可买 / 等确认 / 继续观察”；评分用星级辅助表达。
4. 模拟盘：增加“系统今日动作日志 / 需要处理 / 分时确认”顶部操作区；保留自动交易与风险说明。
5. 个股分析：增加综合判断大卡片；把 AI 和复杂指标放在次级说明。
6. 回测页面：增加快速/专家模式、结果自然语言判断、进度等待说明。
7. 策略工作台：增加四步流程导览和红黄绿健康语义。
8. 研究复盘：把复盘样本改成案例故事式展示，强调样本量可信度。
9. 系统配置：补充“我的账户 / 交易参数 / 系统管理”分区提示。
10. 绩效看板：增加自然语言总结和策略赚钱/亏钱排行条。
11. 移动端：首页增加“今天最重要一件事”；选股宝典默认聚焦可执行候选；登录支持 MFA 数字输入。
12. 移动登录：补齐动态验证码字段和清晰的错误提示。

### 验证

- 已通过 `npm run build`。
- 本轮只涉及前端易用性和移动端登录参数，不改动策略计算、交易规则和数据库。

### 完成状态

- 12 项界面易用性整改均已落地到对应页面或移动端入口。
- 生物识别快速登录未接入原生插件，本轮以“后续可接入”的安全提示呈现，避免伪造不可用功能。

## SmartT 成功率、防过拟合与情绪温度计闭环

来源：用户 2026-05-14 需求。

### 目标

1. 做T 入场必须同时满足缩量、低点不破、时间窗口、VWAP 折价、市场状态和盈利持仓条件。
2. 做T 仓位必须有止盈、止损、时间退出和冲高回落退出计划。
3. 市场状态增加情绪温度计，用于“冷 / 温 / 热 / 过热”更细粒度入场判断。
4. 新策略引入 Phase 1/2/3 渐进验证，避免未经验证策略直接放大。
5. ML 晋级增加 Bootstrap 置信区间、AUC gap、特征集中度和漂移监控。
6. 选股质量增强以因子加分方式落地，不直接改变原策略买点阈值。

### TODO

- [x] SmartT 加仓门槛：volume_release_ratio、low_rising、VWAP 折价、时间过滤、市场状态过滤、盈利持仓过滤。
- [x] SmartT 动态参数：市场状态自适应 expected_rebound_pct、账户盈亏自适应 cash_pct、单轮标的数上限。
- [x] SmartT T 仓退出：止盈、0.6% 止损、60 分钟时间退出、冲高回落退出。
- [x] 情绪温度计：冷 / 温 / 热 / 过热分类，并接入市场快照、优先榜和 App 投影。
- [x] Phase 1/2/3 渐进验证：影子观察、小仓验证、标准执行字段接入策略治理。
- [x] ML 防过拟合：Bootstrap CI、训练/验证 AUC gap、特征重要性集中度晋级阻断。
- [x] ML 漂移监控：近期样本 vs 基线样本 KL 散度，输出漂移告警。
- [x] 选股质量因子：连续缩量、健康回踩、启动动能、派发风险和假突破惩罚接入因子注册表与参数版本系统。

### 已验证

- `backend/.venv/bin/python -m pytest backend/tests/test_paper_smart_t.py backend/tests/test_paper_dynamic_exit.py backend/tests/test_paper_smart_t_backtest.py backend/tests/test_market_regime_strategy_p2.py backend/tests/test_market_routes.py backend/tests/test_ml_markowitz_regime_rl.py -q` 通过，41 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_phase4_phase5_foundation.py backend/tests/test_pkg02_pkg04_contracts.py -q` 通过，31 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_factor_registry.py backend/tests/test_paper_smart_t.py backend/tests/test_paper_dynamic_exit.py backend/tests/test_paper_smart_t_backtest.py -q` 通过，18 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_market_regime_strategy_p2.py backend/tests/test_market_routes.py backend/tests/test_phase4_phase5_foundation.py backend/tests/test_pkg02_pkg04_contracts.py backend/tests/test_ml_markowitz_regime_rl.py -q` 通过，57 passed。

## 策略自进化与在线学习闭环

来源：用户 2026-05-15 需求。

### 目标

1. 每笔模拟盘平仓继续写入 `MLSignalSample`，作为在线学习样本。
2. 每周五收盘后自动编排“增量训练 → 显著性验证 → 参数晋级草案 → Phase 评估”。
3. 训练结果达到门槛后只生成晋级候选，必须管理员审批后才进入 production。
4. 每月执行特征漂移监控，输出漂移告警。

### TODO

- [x] 新增 `StrategySelfEvolutionOrchestrator`，串联增量训练、在线学习状态、漂移监控、分市场状态参数晋级草案和 Phase 评估。
- [x] 新增 APScheduler 调度，每周五 16:05 入队策略自进化任务，每月 1 日 16:35 入队漂移监控任务。
- [x] runtime worker 支持 `strategy_self_evolution` 与 `ml_feature_drift_monitor` 任务。
- [x] 增量训练默认 `promote=False`，训练达标后标记 `promotion_candidate/approval_required`。
- [x] 新增管理员审批接口 `/api/ml/signals/models/{model_key}/approve-promotion`。
- [x] 保留 runtime loop 兜底调度，APScheduler 不可用时不影响系统启动。

### 验证

- 本轮将运行 Python 编译和针对性 pytest。

## 2026-05-26 市场复盘数据自动补全

需求来源：用户要求“数据不全的时候自动补全”。

### 本轮目标

- [x] 新增市场复盘/pulse 前置自动补全服务。
- [x] 情绪温度缺失时使用市场涨跌面派生保守情绪，不伪装为真实涨停情绪。
- [x] 板块/龙头强度缺失时优先使用既有行业/日线排行，仍缺时用全市场强势扩散代理。
- [x] 全市场快照缺失时优先保留同桶/同日最近有效样本，禁止 0 样本污染。
- [x] 复盘风险提示列出仍未补齐项，并输出已补齐项审计信息。
- [x] 补测试并部署云端验证。

### 结果

- [x] 自动补全服务已接到 `market/pulse` 与 `market/review` 生成链路。
- [x] `market_breadth`、`market_pulse`、`review_reports` 的返回 schema 均增加了 `autofill_details`，复盘同时携带 `missing_data`。
- [x] 监控页与市场情绪页显示自动补全审计文案，用户可直接看到补齐项和剩余缺口。
- [x] 本地相关后端/前端测试通过，云端部署由现有脚本执行与验证。

### 当前决策

- 自动补全只能降低 `unavailable`，不能把派生数据标成 `fresh`。
- 派生情绪、强势扩散代理都标记为 `partial`，并写入 `autofill_details`。
- 午盘复盘只允许使用午盘截止前数据；收盘复盘使用全天最新可用数据。

### 验证计划

- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_review.py backend/tests/test_market_hourly_snapshot.py backend/tests/test_market_routes.py backend/tests/test_market_pulse_cache_fast_path.py backend/tests/test_bff_routes.py -q`
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q`
- [x] 本轮不执行生产发布；云端重新生成当日午盘/收盘复盘保留为发布后运营验收项。

## 2026-05-27 六大整改包审查采纳开发

来源：Claude 审查报告 `TQuant_六大整改包审查报告_2026-05-27.md` 与用户指定的长期方向收敛。

### 本轮目标

- [x] 市场午盘/收盘复盘从模拟盘归档开关中解耦。
- [x] Go BFF / market-read / scan-worker 在 MySQL 生产 compose 中作为主路径默认启动，并保留可观测 fallback。
- [x] Go BFF 先接入 `traceparent` 透传，不引入高成本 trace 存储。
- [x] Redis/MySQL 行情缓存覆盖率、TTL 和 fallback 指标可观测。
- [x] Rust finance benchmark 增加基线和 CI 退化门禁。
- [x] 生产手册密码占位符、结构化日志、MySQL 慢查询验收补齐。
- [x] 前端路由错误边界补齐，实时监控复盘继续作为全市场午盘/收盘主入口。
- [x] 模拟盘 dashboard 只保留全市场复盘历史入口元信息，不再携带复盘正文、建议或风险提示。

### 非目标

- 不做生产发布、不触碰真实生产数据。
- 不做大范围 `trade_date` 真实迁移。
- 不做 CSS 重构、CSS Split、页面级样式清理或 inline style 收口。
- 长期演进只保留“自动止损实盘化”和“OpenTelemetry 链路”，其余报告中的中长期方向本轮不采纳。

### 验证计划

- [x] `backend/.venv/bin/python -m pytest backend/tests/test_ml_online_learning_schedule.py backend/tests/test_bff_routes.py backend/tests/test_market_quote_cache_coverage.py backend/tests/test_logging_config.py -q`
- [x] `cd go-services/bff-gateway && go test ./...`
- [x] `cd go-services/market-read-service && go test ./...`
- [x] `cd go-services/scan-worker && go test ./...`
- [x] `cd rust/tquant-rs && cargo test`
- [x] `BACKEND_PYTHON=backend/.venv/bin/python PYTHONPATH=backend:. backend/.venv/bin/python scripts/verify_go_rust_performance_acceptance.py`
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_review.py backend/tests/test_market_hourly_snapshot.py backend/tests/test_market_routes.py backend/tests/test_market_pulse_cache_fast_path.py backend/tests/test_bff_routes.py -q`
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_paper_performance_archive.py -q`
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_paper_routes.py backend/tests/test_paper_performance_archive.py backend/tests/test_market_routes.py -q`
- [x] `cd frontend && npm test -- --run PaperTradingPage MonitorPage`
- [x] `python scripts/check_rust_bench_baseline.py docs/reports/rust-bench-baseline.json /tmp/tquant_bench_sample.txt`
- [x] `cd frontend && npm test -- webRoutes`
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q` 通过，709 passed / 47 warnings。
- [x] `cd frontend && npm run lint && npm test -- --run && npm run build` 通过，14 files / 48 tests。
- [x] `git diff --check` 通过。

### 结果

- 市场复盘开关已独立为 `MARKET_REVIEW_ENABLED`，模拟盘归档关闭时不再影响全市场午盘/收盘复盘。
- Go 三服务在 MySQL compose 中默认进入生产主路径；生产部署 smoke 会校验 Go readyz、MySQL 慢查询和结构化日志配置。
- Go BFF / Python remote BFF 已透传 `traceparent`，Go BFF 缺失时会生成 W3C traceparent。
- Go market-read 增加 Redis hit、cache miss、MySQL fallback 指标；Python 本地行情缓存暴露 TTL 常量并补测试。
- Rust bench 增加 `docs/reports/rust-bench-baseline.json` 与 `scripts/check_rust_bench_baseline.py`，CI 退化超阈值失败。
- Go/Rust 接受度报告已刷新：Go quote benchmark `8199 ns/op`、`11239 B/op`、`212 allocs/op`，Rust speedup `max_drawdown=7.056`、`rolling_mean=12.844`、`atr_wilder=9.636`。
- 前端路由增加错误边界；实时监控页继续作为全市场午盘/收盘复盘主展示入口，模拟盘只保留入口元信息。
- 纸面交易 dashboard、`/api/paper/performance/review-summary`、`/api/paper/performance/review-history` 均只返回全市场复盘入口元信息；复盘正文、建议、风险提示只由实时监控/market review 接口承载。

## 2026-05-27 全平台稳定性与可用性治理

需求来源：Codex Goal `全平台稳定性与可用性治理`。

### 硬性边界

- 不删除已有功能，不改变策略、筛选、风控、回测、模拟盘既有业务口径。
- 策略相关决策继续以 Python reference 为准；Go 只承担 BFF 聚合、行情读取、scan-worker 编排。
- Rust 只承担 Python 调用的金融指标加速，不作为策略结果真源。
- 不做无关大重构，不做 CSS 重构，不做视觉风格重写。

### 本轮检查项

- [x] 登录、权限、Cookie/Token、持久化登录、失效处理。
- [x] 前端核心页面入口、路由、移动端和关键交互可用性。
- [x] 实时监控、行情、market pulse、复盘、缓存降级和调度任务。
- [x] 模拟盘订单、持仓、成交、盈亏、自动交易、风险、对账和标签。
- [x] 回测、参数优化、walk-forward、归因、ML 容量和策略结果一致性。
- [x] Provider、缓存、并发、数据库会话、N+1、慢查询、重复请求、锁竞争。
- [x] 部署、健康检查、日志、metrics、限流、异常降级、迁移、备份恢复、settings 持久化。

### 验证计划

- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q` 通过，709 passed / 47 warnings。
- [x] `cd frontend && npm run lint` 通过。
- [x] `cd frontend && npm test -- --run` 通过，15 files / 50 tests。
- [x] `cd frontend && npm run build` 通过。
- [x] `cd go-services/bff-gateway && go test ./...` 通过。
- [x] `cd go-services/market-read-service && go test ./...` 通过。
- [x] `cd go-services/scan-worker && go test ./...` 通过。
- [x] `cd rust/tquant-rs && cargo test` 通过，7 tests。
- [x] `BACKEND_PYTHON=backend/.venv/bin/python PYTHONPATH=backend:. backend/.venv/bin/python scripts/verify_go_rust_performance_acceptance.py` 通过，报告写入 `docs/reports/go-rust-performance-acceptance-2026-05-27.json`。
- [x] `git diff --check` 通过。

### 当前发现

- [x] 已修复午盘复盘 cutoff 过宽问题：午盘复盘现在只取 12:00 及以前的快照/盘中 pulse，避免延迟补跑时混入下午 13:00 以后数据。
- [x] 已补 `test_market_review_midday_ignores_late_session_snapshots` 等复盘回归，确认午盘与收盘复盘分别使用午盘/全天口径。
- [x] 已修复 native HTTP bridge 错误状态丢失问题：移动端 401/403/5xx 错误保留 `status`，避免登录失效被误判为可离线降级的普通异常。
- [x] 已补 `frontend/src/api/nativeHttp.test.ts`，覆盖 native JSON/plain text 错误状态。
- [x] 静态审计确认实时监控仍是全市场午盘/收盘复盘主展示入口；模拟盘只保留入口元信息。
- [x] 静态审计确认 Go BFF、Go market-read-service、Go scan-worker 已进入非策略生产主路径；Python reference 仍是策略真源和 fallback。
- [x] 静态审计确认 Rust `tquant_rs` 已接入 RSI、ATR、VWAP、RankIC、max drawdown 等 Python 调用路径，并保留 Python fallback。
- [x] 剩余风险：本轮为本地全量验收，未执行真实云端发布和真实交易日盘中数据拉取；生产上线前仍需按 runbook 做云端 smoke、日志/metrics 观测和当日复盘人工抽检。

## 2026-05-29 策略跟踪增强开发

需求来源：`docs/platform-slimming-and-strategy-tracking-development-plan-2026-05-29.md` 与当前 Goal。

### 硬性边界

- `/strategy-tracking` 继续只做观察、复盘和统计，不自动影响策略排序、模拟盘交易或真实交易。
- 后验表现和最优持有期统计必须与推荐当日信号隔离，不允许未来函数污染策略。
- Shadow 观测闭环只能展示真实观测状态和阻塞原因，不伪造样本。
- Shadow 无样本原因自动识别没有模型观测记录、没有符合条件信号、数据缺失、策略未启用、时间窗口未到、任务未运行、写入失败和 schema mismatch。
- 前端继续使用后端分页、详情懒加载和现有 query/cache 模式。

### 本轮开发 TODO

- [x] 后端扩展策略跟踪 schema：失败归因、市场分层、健康度、Shadow 诊断、防未来函数审计、持有期优化、报告摘要。
- [x] 后端实现纯计算模块：持有期最优窗口、收益/回撤比、利润回吐、短线转中长线资格、异常收益标记。
- [x] 后端新增诊断/聚合接口：review、failure-attribution、market-segments、health、shadow-observations、leakage-audit、reports。
- [x] 前端扩展策略跟踪类型、列表、详情和复盘/诊断展示。
- [x] Go BFF 聚合透传新增策略跟踪接口或补充测试说明边界。
- [x] 验证后端 pytest、前端测试/构建、Go test、Rust test、diff check。
- [x] 拆分 `strategy_tracking.py` 中的 Shadow/报告辅助逻辑到 `strategy_tracking_reports.py`，主服务文件降至 472 行，避免超过 500 行的代码坏味道。
- [x] 前端增加策略跟踪周报 query/API 封装，并在复盘诊断 tab 展示报告摘要。
- [x] 周报请求改为仅在复盘诊断 tab 启用，避免策略跟踪首屏额外请求；日报/周报接口均补只读回归断言。

### 验证计划

- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_tracking.py -q` 通过，8 passed / 1 warning。
- [x] `cd frontend && npm test -- StrategyTrackingPage --run` 通过，7 passed。
- [x] `cd frontend && npm test -- webRoutes --run` 通过，10 passed。
- [x] `cd frontend && npm test -- StrategyTrackingPage webRoutes --run` 通过，17 passed。
- [x] `cd frontend && npm test -- --run` 通过，23 files / 69 tests。
- [x] `cd frontend && npm run build:web` 通过；StrategyTrackingPage chunk 22.20 kB / gzip 6.71 kB。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_tracking.py backend/tests/test_bff_routes.py -q` 通过，25 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_tracking.py backend/tests/test_bff_routes.py backend/tests/test_backtest_v2_api_contract.py backend/tests/test_agent_research_contexts.py backend/tests/test_agent_report_and_local_invoker.py -q` 通过，49 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_monitor_routes.py backend/tests/test_market_routes.py backend/tests/test_bff_monitor_workspace.py backend/tests/test_settings_routes.py -q` 通过，19 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_paper_routes.py backend/tests/test_paper_performance_archive.py -q` 通过，40 passed / 1 warning。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_backtest_v2_api_contract.py backend/tests/test_backtest_phase2_research_tasks.py backend/tests/test_low_buy_positioning.py backend/tests/test_low_buy_standardization.py -q` 通过，37 passed / 1 warning。
- [x] `cd go-services/bff-gateway && go test ./...` 通过。
- [x] `cd rust/tquant-rs && cargo test` 通过，10 passed。
- [x] `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/app/services/strategy_tracking.py backend/app/services/strategy_tracking_builders.py backend/app/services/strategy_tracking_helpers.py backend/app/services/strategy_tracking_enhancements.py backend/app/services/strategy_tracking_reports.py backend/app/api/routes/strategy_tracking.py backend/app/models/schema_defs/strategy_tracking.py` 通过。
- [x] `git diff --check` 通过。

### 本轮结果

- 策略跟踪增强已落地为只读链路：列表/详情/复盘/归因/市场分层/健康度/Shadow/审计/报告接口均不写生产策略排序、模拟盘交易或真实交易。
- 每条跟踪记录已补充买点触达、最高涨幅、最大回撤、止损、冲高回落、失败归因、市场状态、数据质量、异常收益和未来函数审计字段。
- Shadow 观测为 0 时返回 `no_sample_reason` 与中文原因，默认覆盖没有模型观测记录等原因，不再只显示数字 0。
- 持有期优化只作为后验复盘指标展示，短线转波段/中长线观察资格按信号日前可见趋势/均线/市场状态约束计算。
- Go BFF 已将策略跟踪 summary/items/performance/detail 扩展到 market-segments 和 shadow-observations 读聚合路径。
- Rust 当前通过既有数值测试保障最大回撤等基础指标边界；策略跟踪本轮仍以 Python 编排为主，保留数值迁移边界。
- 静态审查确认 `/strategy` 重定向 `/backtest`，`/emotion` 重定向 `/monitor`，前端不存在旧 StrategyRoute/EmotionRoute 独立页面文件。
- 代码质量审查：新增/大改文件均小于 500 行，未发现未使用旧页面、console log、TODO/FIXME 或明显重复大块逻辑。
