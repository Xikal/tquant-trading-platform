# TQuant Claude 审查问题提取与实施整改方案

来源报告：`/Users/j/Downloads/TQuant_策略优化与ETF做T增强方案.html`

生成日期：2026-05-27

## 背景与目标

本文件将 Claude HTML 报告《TQuant · 策略优化与 ETF 做T增强完整方案》中提到的所有问题、风险、优化方向、改进建议、策略缺陷、工程缺陷、产品建议、测试建议和上线约束，整理成可执行整改方案。

本轮只做分析与实施规划，不修改业务代码。所有策略收益相关结论均按“概率改善方向”处理，不承诺固定收益，不把回测最优参数直接作为生产参数。

## 覆盖性说明

已完整覆盖原报告以下章节：

- 策略体系全维度优化总览。
- 当前策略体系完整盘点：16 个生产/研究策略、11 个策略族、24 个月回测数据口径。
- 当前策略核心问题诊断：5 个核心问题。
- 策略优化建议：P0/P1/P2 优先级清单。
- 可新增策略设计：7 个高潜力策略方向。
- ETF 与做T模块全方位增强方案：ETF 分类、4 个核心增强、UI 要求。
- 回测与验收标准：五类市场状态、上线必达标准、参数稳定性测试。
- 开发任务拆分、风险清单、不能做事项、验收命令参考。

原报告关键数字口径：

- 24 个月回测只覆盖 `ma_channel_band` 和 `leader_pullback_band` 两个策略，其他 14 个生产策略无数字回测记录。
- 全局接近买点样本成交 6250 笔，净胜率 50.74%，均净收益 0.54%，止损率 38.06%，执行盈亏比 1.44x。
- 5 日冲高 3% 命中率 57.47%。
- T+1 高点平均收益 2.3159%，T+1 收盘平均收益 -0.0028%，高峰衰减约 2.32%。
- `buy_now / soft_buy_now` 确定买入路径成交样本为 0。

## 问题总览表

| ID | 严重程度 | 原始问题/建议 | 影响范围 | 所属角色 | 处理结论 |
|---|---|---|---|---|---|
| Q-001 | P0 | `buy_now / soft_buy_now` 确定买入成交样本为 0，最强信号无历史验证 | 自动交易、模拟盘、低吸策略、回测 | trading-quant-lead / qa-tester | 必须补专项回测 |
| Q-002 | P0 | 止损率 38.06%，中位数收益为负，固定 -3% 止损不适配波动差异 | 动态退出、风控、收益回撤比 | trading-quant-lead / fullstack-builder | 必须回测 ATR 动态止损 |
| Q-003 | P0 | T+1 日内冲高明显，但收盘回吐，出口结构不匹配短线收益窗口 | 止盈、做T、持仓周期、模拟盘执行 | trading-quant-lead / stock-analysis-specialist | 必须调整并验证出口结构 |
| Q-004 | P1 | 14 个生产策略无独立 24M 回测数据，策略权重缺乏数字依据 | 策略治理、优先级榜、上线信心 | trading-quant-lead / qa-tester | 必须补全策略级回测 |
| Q-005 | P1 | ETF 做T依赖低吸榜映射，无 ETF 独立分时信号 | ETF 做T、sector_etf_t0、scheduler_etf | stock-analysis-specialist / fullstack-builder | 必须建设 ETF 独立信号 |
| Q-006 | P1 | 市场退潮/高位分化时缺少强制降分或阻断 | 低吸、模拟盘、账户回撤 | trading-quant-lead / fullstack-builder | 增加市场状态过滤 |
| Q-007 | P1 | 首板策略出货风险阈值需要优化 | 首板回踩策略 | stock-analysis-specialist / trading-quant-lead | 专项回测后调阈值 |
| Q-008 | P2 | 策略家族权重未按近 20 日表现动态调整 | 优先级榜、策略治理 | trading-quant-lead / fullstack-builder | A/B 后接入 |
| Q-009 | P2 | 多周期共振分数使用不够积极 | 候选排序、低吸评分 | trading-quant-lead | 单独回测共振样本 |
| Q-010 | P2 | 涨停回调类策略缺少板块活跃度过滤 | 涨停回调、主线策略 | stock-analysis-specialist | 退潮期对照验证 |
| Q-011 | P1 | ETF T+0 能力需要按规则分类，不能假设所有 ETF 可做T | ETF 池、自动交易约束 | product-strategist / fullstack-builder | 规则化品种能力 |
| Q-012 | P1 | 个股只能基于底仓做T，不能新建仓做T | smart_t、交易风控 | trading-quant-lead / fullstack-builder | 保持硬约束 |
| Q-013 | P1 | ETF 做T回测必须纳入手续费和滑点 | 回测、ETF 做T | qa-tester / trading-quant-lead | 回测框架补费用模型 |
| Q-014 | P2 | ETF 做T UI 缺少独立展示、失败暂停提示和历史统计 | 模拟盘、实时监控、策略工作台 | ui-designer / product-strategist | 前端展示增强 |
| Q-015 | P2 | 高股息防守策略依赖外部股息率等因子数据 | 因子数据、退潮期策略 | stock-analysis-specialist / fullstack-builder | 需确认数据源后实施 |
| Q-016 | P3 | ETF 动态网格属于高风险研究策略，不能直接接自动交易 | ETF 做T、研究策略治理 | trading-quant-lead / qa-tester | 研究模式 60 日观察 |
| Q-017 | P1 | 参数调整必须可配置，不能硬编码 | 设置、策略参数、回滚 | fullstack-builder / devops-operator | 配置化和 A/B flag |
| Q-018 | P1 | 所有优化必须并行新增，不删除或弱化现有策略逻辑 | 策略一致性、验收 | trading-quant-lead / qa-tester | 最小破坏原则 |
| Q-019 | P1 | 研究策略不得直接升生产，需 30 笔模拟盘验证 | 策略治理、自动交易 | trading-quant-lead / qa-tester | 增加上线门槛 |
| Q-020 | P2 | 需要策略、ETF、风控和数据质量可观测指标 | 监控、运维、回归 | devops-operator / qa-tester | 补 metrics 和告警 |

## 按严重程度分类的问题清单

### P0：必须先做的策略与风险基础

#### Q-001：确定买入路径无历史验证

- 原始问题描述：`buy_now / soft_buy_now` 成交样本为 0。报告引用 `research/reports/low_buy_new_strategies_24m_20260506.json`，其中 `confirmed_result.filled_count=0`、`evaluated_count=0`。24 个月回测没有一笔“确定买入”状态被执行和评估，所有数据来自“接近买点 near_entry”。
- 影响范围：低吸生产策略、自动交易触发、模拟盘执行、回测可信度。
- 严重程度：P0。
- 所属角色：`trading-quant-lead`、`qa-tester`、`fullstack-builder`。
- 实施建议：新增 `buy_now` 专项回测，只评估 `buy_signal_state == "buy_now"` 或 `soft_buy_now` 的样本；同时对照执行层 `execution_ready`、`min_score`、价格触达窗口和 isolated/fast 回测口径。
- 可能涉及模块或文件：
  - `backend/app/services/low_buy/execution_backtest.py`
  - `backend/app/services/low_buy/execution_simulation.py`
  - `backend/app/services/low_buy/candidate_scoring.py`
  - 新增 `research/scripts/run_confirmed_buy_backtest.py` 或并入统一回测脚本。
- 验收标准：输出 `buy_now` 与 `near_entry` 对照 JSON；至少包含样本数、成交数、净胜率、均净收益、最大回撤、Profit Factor、触发率、未触发原因分布。
- 依赖关系：先完成回测脚本增强，再决定是否调整 `min_score` 或触达窗口。

#### Q-002：固定 -3% 止损导致止损率过高

- 原始问题描述：24 个月回测止损率 38.06%，`median_return_5d=-0.64%`，`profit_factor_5d=1.056`，收益分布依赖少数大赢单。当前所有策略共享 `hard_stop_loss_pct=-3.0%`，未按 ATR 或策略族区分。
- 影响范围：动态退出、模拟盘自动止损、策略胜率、用户持仓体验、收益回撤比。
- 严重程度：P0。
- 所属角色：`trading-quant-lead`、`fullstack-builder`、`qa-tester`。
- 实施建议：引入 ATR 动态止损，报告建议公式为 `stop_loss = max(-3%, -(1.5 * ATR14 / close * 100))`；同时按策略族差异化，例如 mainline 类约 -2.5%，trend_pullback 类约 -3.5%。注意报告公式里 `max(-3%, -ATR止损)` 的含义需要进一步确认：若目标是避免高波动标的过密止损，可能应允许更宽止损，不能直接机械套用。
- 可能涉及模块或文件：
  - `backend/app/services/paper/dynamic_exit.py`
  - `backend/app/services/paper/trailing_stop_decision.py`
  - `backend/app/services/low_buy/candidate_types.py`
  - `backend/app/services/low_buy/candidate_metrics.py`
  - `backend/app/models/schema_defs/paper.py`
- 验收标准：固定 -3% vs ATR 动态止损对比回测；目标为止损率下降、Profit Factor 提升或不下降、最大回撤不扩大；关键参数 ±20% 稳定性通过。
- 依赖关系：需要下单时把 `atr14` 写入 `signal_snapshot`，并保证老订单无 ATR 时有兼容 fallback。

#### Q-003：T+1 利润窗口集中在日内高点，收盘回吐严重

- 原始问题描述：`avg_t1_high_return_pct=2.3159%`，`avg_t1_close_return_pct=-0.0028%`，高峰衰减约 2.32%。策略更像 1-2 天短线，但 `take_profit_pct=5%` 目标过高，`first_take_profit_pct=2%` 只减仓 30%，`trailing_stop_trigger_pct=3%` 可能偏高。
- 影响范围：动态止盈、移动止损、做T、持仓周期、资金效率。
- 严重程度：P0。
- 所属角色：`trading-quant-lead`、`stock-analysis-specialist`、`fullstack-builder`。
- 实施建议：先回测 T+1 出口结构，再考虑将 2% 首次止盈减仓比例从 30% 提到 50%，将 `trailing_stop_trigger_pct` 从 3% 下调到 2%，将 `trailing_stop_pct` 从 2% 下调到 1.5%，5% 目标保留但触发后全清。
- 可能涉及模块或文件：
  - `backend/app/services/paper/dynamic_exit.py`
  - `backend/app/services/paper/trailing_stop_decision.py`
  - `backend/app/services/paper/smart_t_exit.py`
  - `backend/app/services/paper/scheduler_exit.py`
- 验收标准：T+1/T+2/T+3 分持仓周期回测；比较平均净收益、收益回吐、最大回撤、单笔期望收益和换手率；模拟盘观察至少 1 个月。
- 依赖关系：依赖 Q-001、Q-002 的回测框架和参数配置化。

### P1：近期应完成的策略、ETF 与工程落地项

#### Q-004：14 个生产策略缺少独立 24M 回测数据

- 原始问题描述：附件回测 JSON 仅包含 `ma_channel_band` 与 `leader_pullback_band`，其他 14 个生产策略没有策略级数字支撑。
- 影响范围：策略治理、优先级榜排序、策略权重、上线验收。
- 严重程度：P1。
- 所属角色：`trading-quant-lead`、`qa-tester`。
- 实施建议：对全部 16 个策略分别运行 24 个月回测，输出按策略、市场状态、季度分段的统计；形成策略基线表。
- 可能涉及模块或文件：
  - `backend/app/services/low_buy/execution_backtest.py`
  - `backend/app/services/low_buy/candidate_rules.py`
  - `backend/app/services/low_buy/strategy_families.py`
  - 新增 `research/scripts/run_all_strategy_backtest.py`
- 验收标准：每个策略有独立 JSON，包含样本数、成交数、净胜率、均净收益、止损率、PF、最大回撤、分市场状态表现。
- 依赖关系：先完成统一回测任务和报告格式。

#### Q-005：ETF 做T缺少独立分时信号

- 原始问题描述：`SectorEtfT0Service.build_from_priority_board()` 从低吸优先榜取行业信号，通过 `SECTOR_ETF_PROXIES` 映射 ETF；ETF 本身无分时 VWAP 偏离、折溢价、盘口或分钟级量价评估。
- 影响范围：ETF 做T入场时机、信号质量、模拟盘执行、实时监控展示。
- 严重程度：P1。
- 所属角色：`stock-analysis-specialist`、`fullstack-builder`、`qa-tester`。
- 实施建议：新增 ETF 独立 VWAP 偏离信号和布林带均值回归信号；低吸榜映射只能作为协同信号，不作为唯一触发源。
- 可能涉及模块或文件：
  - `backend/app/services/sector_etf_t0.py`
  - `backend/app/services/paper/scheduler_etf.py`
  - `backend/app/services/paper/smart_t_entry_gate.py`
  - `backend/app/services/paper/smart_t_backtest.py`
  - `backend/app/services/market/minute_bar_store.py`
- 验收标准：ETF 分时回测覆盖 2023-2025 年，费用含买入万 0.5、卖出万 1.5、无印花税，宽基滑点 0.01%、行业 ETF 滑点 0.02%；VWAP 做T目标 PF > 1.4。
- 依赖关系：需要分钟线、VWAP、成交额、流动性检查和 T+0 品种分类。

#### Q-006：市场退潮/高位分化过滤不足

- 原始问题描述：报告建议在 `risk_release`、`high_flyer_retreat` 等退潮或高位分化状态下自动降分或阻断，降低回撤期误信号。
- 影响范围：低吸策略、涨停回调、模拟盘新开仓、账户回撤。
- 严重程度：P1。
- 所属角色：`trading-quant-lead`、`stock-analysis-specialist`、`fullstack-builder`。
- 实施建议：新增 `market_retreat_cash_protect` 控制策略；当 `market_state == high_flyer_retreat` 连续 2 日、大盘 3 日跌幅合计 > 5%、炸板率 > 40% 且涨停数 < 15 时暂停新开仓；解除时要求市场连续修复并延迟 1 天观察。
- 可能涉及模块或文件：
  - `backend/app/services/paper/scheduler.py`
  - `backend/app/services/market/regime.py`
  - `backend/app/services/market/pulse.py`
  - `backend/app/services/low_buy/candidate_prefilters.py`
  - `backend/app/services/low_buy/candidate_scoring.py`
- 验收标准：退潮期新开仓数显著下降，止损逻辑不放宽，现有持仓仍按止盈止损规则退出；触发/解除状态在模拟盘运行记录可见。
- 依赖关系：依赖市场状态数据质量和小时快照评分。

#### Q-007：首板策略出货风险阈值需要优化

- 原始问题描述：报告建议 `first_board.max_distribution_risk_score` 从 5.8 下调到 5.2，减少出货板误伤。
- 影响范围：`first_board` 首板回踩策略。
- 严重程度：P1。
- 所属角色：`stock-analysis-specialist`、`trading-quant-lead`。
- 实施建议：先做首板策略专项回测，比较阈值 5.8、5.5、5.2、5.0 对样本数、胜率、PF、错杀率的影响，再决定配置值。
- 可能涉及模块或文件：
  - `backend/app/services/low_buy/strategy_parameter_defaults_parts/low_buy_prefilters.py`
  - `backend/app/services/low_buy/candidate_prefilters.py`
  - `backend/app/services/low_buy/candidate_rules_mainline.py`
- 验收标准：阈值调整后首板策略 PF 提升或回撤下降，样本数不能过度塌缩；配置可回滚。
- 依赖关系：依赖 Q-004 策略级回测。

#### Q-011：ETF T+0 能力必须规则化

- 原始问题描述：核心约束要求 ETF T+0 能力必须基于规则分类，不能假设所有 ETF 都支持 T+0；债券 ETF、货币 ETF 不做T；跨境、黄金、商品 ETF 即使具备 T+0 也因数据依赖暂不自动化。
- 影响范围：ETF 池、做T执行、风控、产品展示。
- 严重程度：P1。
- 所属角色：`product-strategist`、`fullstack-builder`、`qa-tester`。
- 实施建议：建立 ETF 能力表：宽基指数 ETF、行业主题 ETF 可纳入自动化候选；跨境 ETF、黄金 ETF、商品 ETF 先只提示或研究；债券 ETF、货币 ETF 禁止做T。
- 可能涉及模块或文件：
  - `backend/app/services/sector_etf_t0.py`
  - `backend/app/services/paper/smart_t_strategy_scope.py`
  - `backend/app/services/paper/scheduler_etf.py`
  - 前端 ETF 做T展示组件。
- 验收标准：不同 ETF 类型返回明确 `t0_allowed`、`automation_allowed`、`reason`；不允许品种不会生成自动交易建议。
- 依赖关系：需要 ETF 标的池和分类维护机制。

#### Q-012：个股只能基于底仓做T

- 原始问题描述：个股不能新建仓做T，只能基于已有底仓执行 smart_t；ETF 做T与个股做T需分开处理。
- 影响范围：smart_t、订单执行、风控边界。
- 严重程度：P1。
- 所属角色：`trading-quant-lead`、`fullstack-builder`。
- 实施建议：保留并强化底仓检查，任何个股做T加仓必须绑定现有持仓和可用 T+1 数量，不允许把做T信号升级成新开仓。
- 可能涉及模块或文件：
  - `backend/app/services/paper/smart_t.py`
  - `backend/app/services/paper/smart_t_entry_gate.py`
  - `backend/app/services/paper/order.py`
  - `backend/app/services/paper/risk_control.py`
- 验收标准：无底仓个股 smart_t 返回禁止原因；有底仓时仓位不超过做T上限。
- 依赖关系：依赖持仓、可用数量和订单校验准确。

#### Q-013：ETF 做T回测必须包含手续费和滑点

- 原始问题描述：ETF 做T回测必须包含手续费：买入万 0.5、卖出万 1.5、无印花税；滑点：宽基 ETF 0.01%、行业 ETF 0.02%。
- 影响范围：ETF 做T策略可信度、上线门槛。
- 严重程度：P1。
- 所属角色：`qa-tester`、`trading-quant-lead`。
- 实施建议：扩展 `smart_t_backtest.py` 支持 ETF 分时回测，费用模型按 ETF 类型区分。
- 可能涉及模块或文件：
  - `backend/app/services/paper/smart_t_backtest.py`
  - `backend/app/services/shared/trading_costs.py`
  - 新增 `research/scripts/run_etf_vwap_t0_backtest.py`
- 验收标准：输出 gross/net 收益、手续费、滑点损耗、成交次数、PF、最大单次亏损。
- 依赖关系：依赖分钟线和 ETF 分类。

#### Q-017：参数必须可配置并支持 A/B flag

- 原始问题描述：报告约束所有优化必须独立回测后上线；参数调整必须在设置页可配置，不硬编码；优化逻辑与原逻辑并行，通过 A/B flag 控制。
- 影响范围：策略参数、回滚、灰度发布。
- 严重程度：P1。
- 所属角色：`fullstack-builder`、`devops-operator`、`qa-tester`。
- 实施建议：新增参数版本/feature flag，默认保持现有逻辑，灰度用户或模拟盘启用新版。
- 可能涉及模块或文件：
  - `backend/app/services/strategy_metadata_service.py`
  - `backend/app/services/low_buy/strategy_parameter_defaults_parts/*`
  - `backend/app/services/settings_service.py`
  - `frontend/src/features/settings/*`
- 验收标准：参数可审计、可回滚、不会污染旧回测结果。
- 依赖关系：依赖现有设置持久化和策略元数据系统。

#### Q-018：所有优化必须并行新增，不能删除或弱化现有策略

- 原始问题描述：报告明确要求按最小破坏原则实现，不删除或弱化现有 16 个策略的任何逻辑；新增策略、新参数、新出口结构必须并行运行并通过 flag 控制。
- 影响范围：策略一致性、回测口径、模拟盘账本、生产回滚。
- 严重程度：P1。
- 所属角色：`trading-quant-lead`、`fullstack-builder`、`qa-tester`、`devops-operator`。
- 实施建议：任何策略变更都采用“旧逻辑保留 + 新逻辑新增 + 参数版本记录 + A/B flag”方式；新策略单独输出结果，不覆盖旧策略 key；回测报告按策略版本隔离。
- 可能涉及模块或文件：
  - `backend/app/services/low_buy/candidate_rules.py`
  - `backend/app/services/low_buy/strategy_families.py`
  - `backend/app/services/strategy_metadata_service.py`
  - `backend/app/services/low_buy/priority_board.py`
  - `backend/app/services/paper/scheduler.py`
- 验收标准：旧策略回测结果可复现；新旧策略结果可并排比较；关闭 flag 后系统回到旧行为；无已有策略 key 被删除或语义替换。
- 依赖关系：依赖参数版本、策略元数据、回测输出命名规范。

#### Q-019：研究策略不得直接升为生产策略

- 原始问题描述：报告明确禁止把研究策略直接升为生产策略，必须经过回测、样本外验证和模拟盘至少 30 笔；ETF 动态网格等高风险策略还需更长观察。
- 影响范围：策略治理、自动交易、用户风险、产品承诺边界。
- 严重程度：P1。
- 所属角色：`trading-quant-lead`、`product-strategist`、`qa-tester`、`devops-operator`。
- 实施建议：建立策略生命周期：research -> watch -> paper_verified -> production_advisory；只有 `paper_verified` 后才能进入生产建议，自动交易还需额外审批或开关。
- 可能涉及模块或文件：
  - `backend/app/services/strategy_metadata_service.py`
  - `backend/app/services/low_buy/strategy_governance_health.py`
  - `backend/app/services/paper/performance.py`
  - `frontend/src/features/strategy/StrategyHubPage.tsx`
  - `frontend/src/features/backtest/ValidationPanel.tsx`
- 验收标准：策略元数据中可见阶段、验证笔数、回测报告、样本外结果和模拟盘结果；未达标策略无法被自动交易调度选中。
- 依赖关系：依赖策略回测报告、模拟盘执行归因、策略元数据状态。

### P2：增强优化与产品展示

#### Q-008：策略家族权重动态调整

- 原始问题描述：报告建议基于近 20 日窗口动态调整策略家族权重，让近期有效策略族获得更高权重。
- 影响范围：优先级榜、候选排序。
- 严重程度：P2。
- 所属角色：`trading-quant-lead`、`fullstack-builder`。
- 实施建议：以 A/B 测试方式接入，动态权重只作为排序加分，不改变策略命中原始结果。
- 可能涉及模块或文件：
  - `backend/app/services/low_buy/factor_functions.py`
  - `backend/app/services/low_buy/priority_board.py`
  - `backend/app/services/strategy_self_evolution.py`
- 验收标准：动态权重组优先级榜收益/回撤优于静态组，且换手率不过度上升。
- 依赖关系：需要策略级历史表现数据。

#### Q-009：多周期共振分数使用不足

- 原始问题描述：报告建议更积极使用 `multi_timeframe_resonance_score`，加分上限从 5.0 提高到 8.0。
- 影响范围：低吸评分、日/周共振样本排序。
- 严重程度：P2。
- 所属角色：`trading-quant-lead`。
- 实施建议：先对 resonance ≥ 3 分样本单独回测，验证其独立增益，再决定是否调高加分上限。
- 可能涉及模块或文件：
  - `backend/app/services/low_buy/candidate_scoring.py`
  - `backend/app/services/low_buy/multi_timeframe.py`
- 验收标准：高共振组胜率、PF、回撤显著优于低共振组。
- 依赖关系：需要 Q-004 统一回测框架。

#### Q-010：涨停回调类策略缺少板块活跃度过滤

- 原始问题描述：涨停回调类策略在板块已退潮时不应继续做；需要结合 MarketRegime 和 sector 热度判断。
- 影响范围：`limit_up_breakout_retrace`、`mainline_limitup_shrink_retrace_reclaim` 等策略。
- 严重程度：P2。
- 所属角色：`stock-analysis-specialist`、`trading-quant-lead`。
- 实施建议：新增板块活跃度过滤：板块连续两日平均下跌、龙头断板扩散、涨停家数不足时降分或屏蔽。
- 可能涉及模块或文件：
  - `backend/app/services/low_buy/candidate_prefilters.py`
  - `backend/app/services/market/sector_relative_strength.py`
  - `backend/app/services/market/regime.py`
- 验收标准：退潮期错误信号减少，非退潮期样本不过度流失。
- 依赖关系：依赖 sector 数据质量。

#### Q-014：ETF 做T UI 展示不足

- 原始问题描述：报告要求模拟盘“今日动作”区分个股做T和 ETF 做T；实时监控页增加“ETF做T机会”卡片；策略工作台新增“ETF做T分析”Tab；ETF 做T连续失败时模拟盘首屏显示暂停提示。
- 影响范围：模拟盘、实时监控、策略工作台。
- 严重程度：P2。
- 所属角色：`ui-designer`、`product-strategist`、`fullstack-builder`。
- 实施建议：新增 ETF 做T机会、执行记录、成功率、平均收益和暂停原因展示；颜色区分：蓝色 = ETF 做T，橙色 = 个股做T。
- 可能涉及模块或文件：
  - `frontend/src/features/paper/PaperTodayActionPanel.tsx`
  - `frontend/src/features/monitor/MonitorPage.tsx`
  - `frontend/src/features/strategy/EtfT0StrategyStatusPanel.tsx`
  - `frontend/src/features/strategy/StrategyHubDetailTabs.tsx`
- 验收标准：有 ETF 机会时可见，无机会时有空状态；失败暂停原因清晰；移动端不遮挡。
- 依赖关系：依赖后端 ETF 做T接口。

#### Q-015：高股息低波防守轮动依赖外部数据

- 原始问题描述：策略需要股息率、PE、市值、指数相对抗跌等数据；报告建议从 EastMoney 外部因子数据获取。
- 影响范围：防守策略、因子数据、退潮期轮动。
- 严重程度：P2。
- 所属角色：`stock-analysis-specialist`、`fullstack-builder`。
- 实施建议：先确认数据源稳定性和字段授权，再实现 `evaluate_high_dividend_factor()`，策略先作为研究策略。
- 可能涉及模块或文件：
  - `backend/app/services/low_buy/factor_external.py`
  - `backend/app/services/market/external_factors.py`
  - `backend/app/services/factor_mining/*`
- 验收标准：至少两年退潮期/熊市专项回测，胜率 ≥ 58% 才可进入模拟盘观察。
- 依赖关系：外部数据源稳定性需确认。

### P3 / 研究模式：长期增强

#### Q-016：ETF 动态网格做T只能研究模式验证

- 原始问题描述：ETF 动态网格适用于震荡区间明确的宽基 ETF，但趋势行情中可能失效；报告明确要求研究模式观察至少 60 个交易日，不建议验证充分前接入自动交易。
- 影响范围：ETF 做T研究模块、自动交易风险。
- 严重程度：P3。
- 所属角色：`trading-quant-lead`、`qa-tester`。
- 实施建议：作为独立研究模块，不接入自动交易；先做网格间距 × 最大层数参数热力图。
- 可能涉及模块或文件：
  - `backend/app/services/paper/smart_t_backtest.py`
  - 新增 `research/scripts/run_etf_grid_t0_backtest.py`
- 验收标准：完整季度模拟盘验证；单日最大亏损不超过账户净值 0.5%。
- 依赖关系：依赖 ETF 分时回测框架。

#### Q-020：策略、ETF、风控和数据质量需要可观测指标

- 原始问题描述：报告在上线与验收要求中强调需要对策略命中、回测、ETF 做T、data_quality、fallback、模拟盘执行失败等建立可观测证据；否则策略优化无法稳定验收和回滚。
- 影响范围：部署、监控、运维、回归验证、线上问题定位。
- 严重程度：P2。
- 所属角色：`devops-operator`、`qa-tester`、`fullstack-builder`。
- 实施建议：补充 Prometheus metrics 或结构化日志，包括策略命中/过滤/成交/止损率、`buy_now` 触发率、ETF 做T机会/执行/连续亏损、回测任务耗时、data_quality、Go/Rust hit/fallback。
- 可能涉及模块或文件：
  - `backend/app/main.py`
  - `backend/app/services/low_buy/priority_board.py`
  - `backend/app/services/paper/scheduler.py`
  - `backend/app/services/paper/scheduler_etf.py`
  - `go-services/market-read-service/cmd/market-read-service/main.go`
  - `go-services/bff-gateway/cmd/bff-gateway/main.go`
- 验收标准：线上或本地 `/metrics` 能看到新增指标；策略回测和模拟盘运行失败有结构化原因；data_quality 非 fresh 时可定位来源；发布报告能引用这些指标。
- 依赖关系：依赖现有 metrics 暴露、日志配置和部署监控栈。

## 按 Agent 角色拆分的执行清单

### trading-quant-lead

- 设计并验收 `buy_now` 专项回测。
- 建立 16 策略 24M 策略级基线。
- 评估 ATR 动态止损、策略族差异止损和 T+1 出口结构。
- 设计 7 个新策略的可交易性、持仓周期、仓位和上线门槛。
- 定义研究策略、观察策略、生产策略的晋级规则。

### stock-analysis-specialist

- 复核主线板块、龙头断板、N 字洗盘、涨停回调等主观逻辑是否可工程化。
- 定义板块热度、龙头持续性、退潮期、炸板率、弱转强等口径。
- 设计 ETF 品种分类、ETF 轮动和做T适用边界。
- 判断高股息防守轮动是否适合 A 股当前数据链路。

### product-strategist

- 把策略状态拆成研究、观察、模拟盘、生产建议四个阶段。
- 设计 ETF 做T、个股做T、退潮空仓保护的产品展示和提示语。
- 明确“禁止做T/只提示/可模拟/可自动”的用户可见状态。
- 定义策略参数配置入口和灰度开关行为。

### ui-designer

- 模拟盘“今日动作”区分 ETF 做T与个股做T。
- 实时监控页增加 ETF 做T机会卡片和暂停状态。
- 策略工作台新增 ETF 做T分析 Tab，展示历史执行、成功率、平均收益。
- 所有新增展示保持紧凑、无重叠、移动端可用。

### fullstack-builder

- 回测脚本、参数配置、动态止损、市场状态过滤、ETF 分时信号、T+0 能力表落地。
- 确保旧策略逻辑并行保留，不污染已有结果口径。
- Go market-read-service 如新增 `sector_etf_rs()`，只做读服务和聚合，不承接策略真源。
- Rust 可复用 RSI 等指标加速，但策略语义仍由 Python reference 控制。

### qa-tester

- 建立策略级、市场状态级、参数稳定性、样本外、模拟盘观察的测试矩阵。
- 对新增策略要求 baseline 对比。
- 验证 ETF 做T费用、滑点、T+0 分类和禁止规则。
- 增加防未来函数、幸存者偏差、参数过拟合检查。

### devops-operator

- 策略、ETF 做T、数据质量、fallback、回测任务耗时、模拟盘执行失败要有 metrics。
- 新策略上线必须通过 feature flag 和回滚开关。
- 部署前必须跑回测/测试/前端构建/后端测试/Go/Rust smoke。
- 生产只启用已通过模拟盘观察的策略。

## 策略与量化层整改项

### 现有 16 策略盘点

| 策略键 | 策略名 | 家族 | 报告状态 | 整改要求 |
|---|---|---|---|---|
| `classic_retrace` | 经典回踩 | `trend_pullback` | 生产，无数字数据 | 补独立 24M 回测 |
| `ma_support` | 均线支撑 | `trend_pullback` | 生产，无数字数据 | 补独立 24M 回测 |
| `volume_shrink` | 缩量低吸 | `trend_pullback` | 生产，无数字数据 | 补独立 24M 回测 |
| `first_board` | 首板回踩 | `first_board_retest` | 生产，无数字数据 | 补回测并验证出货阈值 |
| `late_session_strong_support` | 尾盘强支撑 | `next_day_event` | 生产，无数字数据 | 补回测并关注 T+1 出口 |
| `core_midcap_vwap_ma5_retrace` | 主线中军 VWAP 回踩 | `core_midcap_retrace` | 生产，无数字数据 | 补回测并验证主线过滤 |
| `sector_mainline_first_divergence_low_buy` | 主线首分歧低吸 | `mainline_first_divergence` | 生产，无数字数据 | 补回测并验证退潮过滤 |
| `mainline_limitup_shrink_retrace_reclaim` | 主线涨停缩量回调复位 | `mainline_limitup_retrace` | 生产，无数字数据 | 增加板块活跃度验证 |
| `breakout_support` | 突破后回踩支撑 | `breakout_retest` | 生产，无数字数据 | 补独立回测 |
| `limit_up_breakout_retrace` | 涨停突破回踩 | `breakout_retest` | 生产，无数字数据 | 增加板块退潮过滤 |
| `divergence_consensus` | 右侧分歧共识 | `main_wave_confirmation` | 生产，无数字数据 | 补独立回测 |
| `deep_pullback` | 深回撤低吸 | `deep_pullback` | 生产，无数字数据 | 补独立回测 |
| `trend_rebound` | 趋势龙回头 | `trend_rebound` | 生产，无数字数据 | 补独立回测 |
| `n_pattern_long_wash` | N 字长洗盘 | `n_pattern_retrace` | 生产，无数字数据 | 与升级版对比 |
| `n_pattern_short_wash` | N 字短洗盘 | `n_pattern_retrace` | 生产，无数字数据 | 与升级版对比 |
| `ma_channel_band` | 均线通道波段 | 独立 | 研究，有回测数据 | 不直接升生产，继续验证 |
| `leader_pullback_band` | 龙头回踩波段 | 独立 | 研究，有回测数据 | 不直接升生产，继续验证 |

### 可新增策略设计整理

| 策略 | 严重程度 | 核心逻辑 | 实施文件 | 验收门槛 |
|---|---|---|---|---|
| `sector_mainline_double_confirm` 主线板块回踩二次确认低吸 | P1 | 板块连续热点，核心股二次缩量回踩，第二次回踩弱于首次，市场为进攻/权重支撑 | `candidate_rules_mainline.py`、`candidate_prefilters.py`、`strategy_families.py` | 24M 净胜率 ≥ 55%，PF ≥ 1.6，模拟盘 30 笔后胜率 ≥ 52% |
| `leader_broken_board_recovery` 龙头断板弱转强确认 | P1 | 炸板后缩量横盘，尾盘翘头或缩量阳线，站回 MA5，板块热度仍前列 | `candidate_rules_mainline.py` | 牛市/震荡均通过，净胜率 ≥ 53%，PF ≥ 1.8，最大回撤 < 15%，模拟盘 ≥ 20 笔 |
| `high_dividend_defensive` 高股息低波防守轮动 | P2 | 退潮/修复期选高股息、低 PE、大市值、相对抗跌个股 | `factor_external.py`、新增 defensive 规则 | 熊市/退潮专项回测 ≥ 2 年，胜率 ≥ 58% |
| `index_etf_trend_rotation` 指数 ETF 趋势轮动 | P2 | 沪深300/创业板/科创50 相对强度轮动，MA5 上穿 MA20，量能放大 | `sector_etf_t0.py`、`low_buy_screener.py` | 牛/震/熊三类市场 PF > 1.3 |
| `sector_etf_rs_rotation` 行业 ETF 相对强弱轮动 | P2 | 18 只行业 ETF 计算相对沪深300 5 日超额收益，选择 RS 最强 1-2 只 | `low_buy_screener.py`、Go `market-read-service` | 2022-2024 ETF 专项回测，换手率 < 150%/年 |
| `market_retreat_cash_protect` 退潮期空仓现金保护 | P1 | 退潮状态暂停新开仓，不强平，持仓止盈目标调低，止损不放宽 | `paper/scheduler.py`、`market_regime` | 触发/解除逻辑正确，不误触发 |
| N 字洗盘后龙头强势回踩升级版 | P2 | 在现有 N 字策略增加龙头验证、板块成交额放大、洗盘缩量质量和假突破过滤 | `candidate_rules_n_pattern.py`、`candidate_prefilters_n_pattern.py` | vs 现有 N 字策略净胜率提升 ≥ 3% |

## 股票分析与选股逻辑整改项

- 主线板块回踩策略必须要求板块连续热点、板块内核心股、回踩缩量、市场进攻状态。
- 龙头断板弱转强必须排除持续放量下跌、连板崩盘扩散和大幅炸板后弱修复。
- 首板回踩必须重点过滤高换手、下影线、出货风险和板块退潮。
- 涨停回调类策略必须加入板块活跃度和龙头未破条件。
- 高股息防守轮动只允许在退潮/修复期触发，不能与进攻策略混用。
- N 字洗盘升级必须区分真洗盘与假突破，要求第三段站上第一段高点。

## 产品与交互整改项

- 模拟盘今日动作：增加 `smart_t` 个股做T与 `sector_etf_t0` ETF 做T的类型区分。
- 实时监控：增加 ETF 做T机会卡片，显示 ETF、信号类型、VWAP 偏离、预期价差、data_quality、暂停原因。
- 策略工作台：新增 ETF 做T分析 Tab，展示历史执行次数、成功率、平均收益、连续亏损和回测摘要。
- 风险提示：ETF 连续 3 次做T亏损时首屏显示“ETF做T暂停”，并说明暂停到何时解除。
- 参数设置：动态止损、移动止盈、ETF 做T阈值、市场退潮保护开关需要可配置且可回滚。

## 前后端与数据链路整改项

- 后端新增统一策略回测脚本，输出稳定 JSON，不污染已有回测结果。
- 动态止损需要在下单快照中保留 `atr14` 或可追溯计算源。
- ETF 分时 VWAP 依赖分钟线、成交额和成交量；数据缺失时必须返回 `partial/unavailable`，不能生成自动做T建议。
- ETF T+0 分类表要可维护，并在 API 返回中暴露是否可自动化。
- Go `market-read-service` 可新增 ETF RS 读接口，但不应成为策略真源。
- Rust 可复用 RSI/VWAP/rolling 等指标加速，但 fallback 必须保留。
- 前端新增展示时必须兼容空数据、partial 数据和暂停状态。

## 测试与验收整改项

### 新策略上线必达标准

- 24 个月回测样本数 ≥ 100 笔；样本不足时延长周期或降级为观察策略。
- 五类市场状态均单独通过验收，不能只看总收益。
- 关键参数 ±20% 时 PF 下降不超过 0.3。
- 最近 6 个月样本外验证 PF ≥ 1.1。
- 模拟盘跑满 30 笔，模拟盘胜率与回测胜率偏差不超过 10%。
- 必须有 baseline 对比，显著优于同市场随机选择基准。

### 市场状态验收标准

| 市场状态 | 参考区间 | 最低净胜率 | 最低 PF | 最大回撤 | 特殊要求 |
|---|---|---:|---:|---:|---|
| 强反弹/牛市 | 2024Q4-2025Q1 | ≥ 52% | ≥ 1.4 | < 15% | 不能只靠牛市贝塔 |
| 震荡分化 | 2024Q2-Q3 | ≥ 50% | ≥ 1.3 | < 12% | 真实质量测试 |
| 熊市下跌 | 2024 年 3-4 月反弹前 | ≥ 47% | ≥ 1.1 | < 20% | 可低胜率但不能大亏 |
| 退潮期 | `market_state == high_flyer_retreat` 持续期 | ≥ 45% 或暂停 | ≥ 1.0 | < 10% | 最好空仓 |
| 强反弹初期 | 情绪从极低快速反弹 | ≥ 55% | ≥ 1.6 | < 10% | 高概率期应更强 |

### 建议验收命令

以下命令为报告建议，部分脚本尚需新增：

```bash
python research/scripts/run_all_strategy_backtest.py \
  --start 2024-01-01 --end 2026-05-01 \
  --output research/reports/all_strategies_$(date +%Y%m%d).json

python research/scripts/run_etf_vwap_t0_backtest.py \
  --etf 510300,159915,512480 \
  --period 2023-2025 \
  --fee_buy 0.00005 --fee_sell 0.00015 \
  --slippage 0.0001

python research/scripts/compare_stop_loss.py \
  --mode_a fixed:-3.0 \
  --mode_b atr_dynamic:1.5x \
  --output atr_vs_fixed_$(date +%Y%m%d).json

python research/scripts/param_sensitivity.py \
  --param1 trailing_stop_trigger_pct:1.5,2.0,2.5,3.0,3.5 \
  --param2 hard_stop_loss_pct:-2.0,-2.5,-3.0,-3.5,-4.0

make qa-smoke
```

## 部署与监控整改项

- 新策略和参数调整必须通过 feature flag 灰度，不允许直接替换生产逻辑。
- 发布前必须保存旧参数版本，支持一键回滚。
- 监控指标建议：
  - 策略命中数、过滤数、成交数、胜率、PF、止损率。
  - `buy_now` 触发率、成交率、未成交原因。
  - ETF 做T机会数、执行数、成功率、连续亏损次数、暂停状态。
  - data_quality：fresh/stale/partial/unavailable。
  - 回测任务耗时、失败率、样本数不足告警。
  - Go/Rust hit/fallback 指标。
- 部署策略：先研究模式，再模拟盘，再小范围生产建议；自动交易接入需单独审批。

## 分阶段实施路线图

### 第一阶段：必须先做的策略与风险基础

目标：先补证据链，不急于改生产参数。

1. 新增全部 16 策略独立 24M 回测。
2. 新增 `buy_now / soft_buy_now` 专项回测。
3. 新增 ATR 动态止损对比回测，不直接改生产默认。
4. 新增 T+1 出口结构对比回测。
5. 建立五类市场状态分组统计。

阶段验收：

- 所有策略有独立 JSON。
- `buy_now` 是否有效有明确结论。
- 固定止损、ATR 止损、T+1 出口结构的收益/风险对比可复现。

### 第二阶段：产品与工程落地

目标：把通过验证的控制逻辑和低风险增强接入系统。

1. 接入 `market_retreat_cash_protect` 退潮期新开仓保护。
2. 接入 smart_t 3K 线趋势确认和大盘分时同步过滤。
3. 将止损、止盈、移动止盈参数配置化并支持 A/B。
4. 建设 ETF T+0 能力表。
5. 建设 ETF 独立 VWAP 偏离信号和布林带回测能力。
6. 前端增加 ETF 做T状态与暂停展示。

阶段验收：

- 不删除旧策略，所有新增逻辑可关闭。
- API 字段兼容，前端空状态/partial 状态可用。
- 模拟盘能记录新增策略、参数版本和触发原因。

### 第三阶段：测试、部署与监控

目标：建立上线门槛和回滚能力。

1. 建立策略上线 checklist。
2. 补齐回测、单测、API smoke、前端展示测试。
3. 增加 metrics 和告警。
4. 使用 feature flag 灰度发布。
5. 模拟盘观察不少于 30 笔，ETF 网格不少于 60 个交易日。

阶段验收：

- 测试与回测报告可在 CI 或发布流程复跑。
- 生产配置可回滚。
- 监控可看到命中、fallback、暂停、失败原因。

### 第四阶段：增强优化

目标：在证据足够后推进新策略和复杂 ETF 模块。

1. 实现并回测 `sector_mainline_double_confirm`。
2. 实现并回测 `leader_broken_board_recovery`。
3. 研究高股息防守轮动，确认数据源后再实现。
4. 研究 ETF RS 轮动和 Go 读接口。
5. ETF 动态网格仅保持研究模式，不接自动交易。

阶段验收：

- 每个新策略有 baseline 对比。
- 新策略至少经过模拟盘门槛。
- 高风险策略不会自动进入生产建议。

## 明确不能做的事项

原报告明确列出的禁止项必须保留为上线红线：

1. 不能把回测最优参数直接当生产参数，必须做 ±20% 稳定性测试。
2. 不能删除或弱化现有 16 个策略的任何逻辑，只能并行新增。
3. 不能假设个股可以新建仓做T，个股只有底仓才能做T。
4. 不能绕过 `scheduler_etf.py` 中的 `historical_acceptance()` 验收门槛。
5. 不能把研究策略直接升为生产策略，必须经过模拟盘至少 30 笔。
6. 不能承诺固定收益率，所有改进方向都是概率意义上的改善。
7. 债券 ETF / 货币 ETF 不能做T。
8. 不能在回测报告中污染已有策略结果口径，新策略必须单独输出 JSON。

## 待确认问题

- ATR 动态止损公式需确认方向：报告写 `max(-3%, -(1.5 * ATR14 / close * 100))`，但同时指出高波动标的固定 -3% 过密。若要给高波动标的更宽止损，公式可能需要按策略族或波动区间重新定义。
- `buy_now` 样本为 0 的根因需通过回测代码确认，可能是触达价格、`min_score`、`execution_ready` 或 isolated/fast 模式导致。
- 高股息防守轮动的数据源、刷新频率和字段授权需确认。
- ETF 折溢价、盘口数据、海外指数、黄金现货、商品期货数据是否可稳定获取需确认。
- Go `market-read-service` 新增 ETF RS 接口是否必要，或先由 Python 完成研究计算。
- ETF 动态网格是否符合用户风险偏好，建议先仅在研究页展示。

## 原报告覆盖检查清单

| 原报告信息点 | 本文位置 | 覆盖状态 |
|---|---|---|
| 16 个生产/研究策略盘点 | 现有 16 策略盘点 | 已覆盖 |
| 24M 回测只有 2 个策略有数据 | Q-004、覆盖性说明 | 已覆盖 |
| 全局回测关键数据 | 覆盖性说明 | 已覆盖 |
| buy_now 样本为 0 | Q-001 | 已覆盖 |
| 止损率 38.06%、中位数收益为负 | Q-002 | 已覆盖 |
| T+1 高点与收盘衰减 | Q-003 | 已覆盖 |
| ETF 做T依赖低吸榜映射 | Q-005 | 已覆盖 |
| P0/P1/P2 优化项 | 问题总览、严重程度清单 | 已覆盖 |
| ATR 动态止损实现方向 | Q-002、待确认问题 | 已覆盖 |
| 7 个新策略 | 可新增策略设计整理 | 已覆盖 |
| ETF T+0 分类表 | Q-011、ETF/数据链路整改 | 已覆盖 |
| ETF VWAP 偏离做T | Q-005、测试整改 | 已覆盖 |
| ETF 布林带做T | Q-005、ETF 相关条目 | 已覆盖 |
| smart_t 3K 线趋势确认 | 第二阶段路线图 | 已覆盖 |
| ETF 动态网格研究限制 | Q-016 | 已覆盖 |
| ETF 做T UI 增强 | Q-014 | 已覆盖 |
| 五类市场状态验收标准 | 测试与验收整改项 | 已覆盖 |
| 新策略上线必达标准 | 测试与验收整改项 | 已覆盖 |
| 开发任务拆分和工时风险 | 问题清单、路线图 | 已覆盖 |
| 立即可做/必须回测/长期验证 | 分阶段路线图 | 已覆盖 |
| 明确不能做事项 | 明确不能做的事项 | 已覆盖 |
| 验收命令参考 | 建议验收命令 | 已覆盖 |
