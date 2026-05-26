# 盘中节奏增强与基础设施演进执行计划（2026-05-25）

关联需求文档：`docs/market-trading-enhancement-requirements-2026-05-25.md`

本文把需求拆成可排期的里程碑和开发任务清单。所有任务默认遵守以下约束：

- 不改变原有策略结果口径。
- 不绕过现有权限、风控、模拟盘账本和回测一致性。
- Go/Rust 新能力在验收前可用 shadow 或受控开关隔离；验收完成后只能接入非策略权威主路径，并保留一键回退 Python 的能力。
- 策略、筛选、风控、回测、模拟盘决策只依赖 Python reference；Go 不实现独立策略公式，Rust 不决定策略结果。
- 每个里程碑必须有可运行测试或可复现验收证据。

## 1. 里程碑总览

| 里程碑 | 名称 | 优先级 | 目标 | 依赖 | 建议周期 |
|---|---|---|---|---|---|
| M0 | 基线与契约冻结 | P0 | 固定当前接口、测试、数据口径，避免开发中误伤原功能 | 无 | 1-2 天 |
| M1 | 盘中 pulse 闭环 | P1 | 小时快照、宽度、情绪、龙头强度合成首屏可执行摘要 | M0 | 3-5 天 |
| M2 | 实时监控复盘可见 | P1 | 午盘/收盘复盘进入实时监控页面和盘中工作流 | M0 | 3-5 天 |
| M3 | Go 服务生产化 | P1 | bff-gateway 聚合、market-read 批量读、scan-worker 扫描编排、性能门禁、非策略主路径接入 | M0 | 1-2 周 |
| M4 | 数据迁移与 settings 原子化 | P1/P2 | 迁移 scope 明确，settings 持久化避免半状态 | M0 | 1 周 |
| M5 | Rust 内核生产化 | P2 | RSI/VWAP/RankIC、wheel、CI 验收、fallback、Python 指标加速路径接入 | M0/M3 | 1-2 周 |
| M6 | 历史表、CI 与可观测性 | P2/P3 | 历史留痕、Go/Rust 门禁、可观测降级与回滚 | M1-M5 | 持续迭代 |

## 2. 责任角色

| 角色 | 责任 |
|---|---|
| `trading-quant-lead` | 确认 pulse、复盘、指标计算不改变策略语义和风控口径 |
| `stock-analysis-specialist` | 确认市场强弱、情绪、龙头、板块轮动的解释口径 |
| `product-strategist` | 定义页面信息层级、用户动作路径和验收标准 |
| `ui-designer` | 保证桌面与移动端信息紧凑、可读、无遮挡 |
| `fullstack-builder` | 实现前后端、Go/Rust、数据持久化与接口兼容 |
| `qa-tester` | 回归测试、异常场景、性能门禁 |
| `devops-operator` | CI、Docker、运行手册、发布回滚和可观测性 |

## 3. M0：基线与契约冻结

### 目标

在功能开发前先冻结关键接口、测试入口和回归基线，避免后续任务把审查发现的问题与新改动混在一起。

### 开发任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M0-1 | 建立接口契约清单 | `product-strategist` / `fullstack-builder` | `APP_API_SPEC.md`、`docs/` | 列出 pulse、monitor review、Go BFF/read/scan、settings、migration 的字段契约 | 字段名、类型、兼容策略明确 |
| M0-2 | 固定测试命令 | `qa-tester` | `Makefile`、CI 文档 | 明确 backend/frontend/go/rust 的标准测试命令 | 本地和 CI 命令一致 |
| M0-3 | 标记现有失败基线 | `qa-tester` | `docs/reports/` | 记录当前后端全量测试失败项及归因 | 不能把旧失败当新回归 |
| M0-4 | 建立禁止变更清单 | `trading-quant-lead` | `docs/` | 列出低吸、风控、回测、模拟盘账本不可变口径 | 策略结果变更必须单独审批 |

### 必跑测试

- `python -m compileall backend/app`
- `pytest` 或项目最终确定的后端标准命令
- `npm run lint`
- `npm test -- --run`
- `npm run build`
- `go test ./...` for each Go service
- `cargo test --no-default-features`

## 4. M1：盘中 pulse 闭环

### 目标

把市场宽度、情绪温度、龙头强度、小时全市场快照合成一个统一对象，并展示到实时监控页和市场情绪页。

### 后端任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M1-BE-1 | 定义 `IntradayMarketPulse` schema | `fullstack-builder` | `backend/app/models/schema_defs/market.py` 或相关 schema | 新增 pulse response model | OpenAPI / 类型稳定 |
| M1-BE-2 | 聚合市场宽度与小时快照 | `fullstack-builder` | `backend/app/api/routes/market.py`、`backend/app/services/market/` | `/market/pulse` 或嵌入 BFF workspace | 缺小时快照时返回 partial/stale |
| M1-BE-3 | 加入龙头强度和情绪温度摘要 | `stock-analysis-specialist` / `fullstack-builder` | market service | 输出 `leader_strength_text`、`emotion_text`、`market_strength_text` | 文案口径清晰，不构成收益承诺 |
| M1-BE-4 | 数据质量聚合 | `fullstack-builder` | market service | `data_quality=fresh/stale/partial/unavailable` | 任一 stale 不得标成 fresh |
| M1-BE-5 | BFF 接入 pulse | `fullstack-builder` | `backend/app/api/routes/bff.py` | monitor workspace 直接返回 pulse | partial_errors 不白屏 |

### 前端任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M1-FE-1 | 扩展 market 类型 | `fullstack-builder` | `frontend/src/types/market.ts` | `MarketPulse`、`HourlyAllMarketSnapshot` 类型 | 不使用隐式 any |
| M1-FE-2 | 监控页 pulse 条 | `ui-designer` / `fullstack-builder` | `frontend/src/features/monitor/` | 首屏 pulse strip/card | 关键字段完整可读 |
| M1-FE-3 | 情绪页 pulse 摘要 | `ui-designer` / `fullstack-builder` | `frontend/src/features/market-emotion/` | 情绪温度、龙头强度、数据质量可见 | 空状态清晰 |
| M1-FE-4 | 降级状态展示 | `fullstack-builder` | shared components | stale/partial/unavailable badge | 不把降级误当正常结果 |

### 测试任务

| ID | 测试 | 覆盖 |
|---|---|---|
| M1-T-1 | 后端 pulse 聚合单测 | fresh/stale/partial/unavailable |
| M1-T-2 | BFF partial response 测试 | 子源失败不白屏 |
| M1-T-3 | 前端组件测试 | pulse 正常、空状态、stale badge |

### Definition of Done

- 监控页首屏能看到一条明确的盘中 pulse。
- 情绪页能看到情绪温度、龙头强度和数据质量。
- 小时快照缺失时页面不白屏，并明确提示 stale/partial。

## 5. M2：实时监控复盘可见

### 目标

把全市场 `review_reports` 中的午盘与收盘复盘显示进实时监控页面，形成可执行的下午/次日约束。复盘对象是整个 A 股市场，不是模拟盘账户；模拟盘只保留账本、委托、成交、绩效明细和复盘历史辅助入口，不作为复盘主承载页。

### 后端任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M2-BE-1 | 固定市场复盘字段 | `fullstack-builder` | `backend/app/services/market/review.py`、schema | 市场级 `review_reports` 字段稳定 | midday/close 可同时存在，不依赖模拟盘账户 |
| M2-BE-2 | 监控 BFF 接入复盘摘要 | `product-strategist` / `fullstack-builder` | `backend/app/api/routes/bff.py`、monitor workspace | `review_status`、`review_reports` 或等价 summary 字段 | 实时监控页面不需自行推断 |
| M2-BE-3 | 修正午盘时间窗口 | `trading-quant-lead` / `fullstack-builder` | `backend/app/runtime/market_review_jobs.py` | 市场午盘只在合理窗口生成 | 避免下午/收盘后误生成午盘 |

### 前端任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M2-FE-1 | 监控页面加载复盘摘要 | `fullstack-builder` | `frontend/src/features/monitor/`、workspace props | 复盘报告进入监控页 props/store | 不破坏现有监控加载 |
| M2-FE-2 | 实时监控复盘卡片 | `ui-designer` / `fullstack-builder` | `frontend/src/features/monitor/` | 午盘、收盘、风险提示、建议动作 | 关键结论、风险提示和建议动作完整可读 |
| M2-FE-3 | 复盘与 pulse 组合展示 | `ui-designer` | monitor page | 复盘摘要靠近 pulse 和今日动作 | 不挤压优先榜、自选扫描、告警 |
| M2-FE-4 | 空状态与下一次触发提示 | `product-strategist` | monitor page | 今日暂无复盘时提示 | 用户知道等待什么 |
| M2-FE-5 | 模拟盘降为辅助入口 | `fullstack-builder` | `frontend/src/features/paper/` | 仅保留历史入口或跳转实时监控 | 不再要求进入模拟盘才能看复盘 |

### 测试任务

| ID | 测试 | 覆盖 |
|---|---|---|
| M2-T-1 | 后端 dashboard shape 测试 | `review_reports`、midday、close |
| M2-T-2 | 午盘窗口测试 | 11:35 后合理窗口、收盘后不误判 |
| M2-T-3 | 前端实时监控渲染测试 | 午盘/收盘卡片、风险提示、建议动作 |
| M2-T-4 | 自动交易冲突测试 | 复盘展示不能阻断自动交易 |
| M2-T-5 | 模拟盘辅助入口测试 | 模拟盘不再是复盘唯一入口 |

### Definition of Done

- 午盘后实时监控页能看到午盘复盘。
- 收盘后实时监控页能看到收盘复盘。
- 自动交易、委托、持仓、风险日志原功能未回归。

## 6. M3：Go 服务生产化

### 目标

把 Go 三个服务做成生产可用的非策略主路径能力。验收完成后，`bff-gateway` 承担 workspace/monitor 聚合主路径，`market-read-service` 承担监控、情绪、选股的行情读取主路径，`scan-worker` 只承担扫描触发、调度编排、状态观测和 fallback 协调；候选排序、策略公式、风控判断和 snapshot 写入语义仍由 Python reference 负责。

### Go 服务任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M3-GO-1 | `bff-gateway` workspace 聚合主路径 | `fullstack-builder` | `go-services/bff-gateway` | workspace/monitor 聚合、partial response、字段兼容 | BFF 启用时页面请求命中 Go |
| M3-GO-2 | `bff-gateway` 超时与缓存 | `fullstack-builder` / `devops-operator` | `go-services/bff-gateway` | 子请求 timeout、cache、fallback reason | 子源失败不拖垮整体 |
| M3-GO-3 | `market-read-service` 批量 quote cache 接口 | `fullstack-builder` | `go-services/market-read-service` | 一次 MGET / 批量 fallback | 不再每个 symbol 单独连缓存 |
| M3-GO-4 | `market-read-service` MySQL fallback 批量查询 | `fullstack-builder` | Go cache layer | 一次查询多个 symbol | Redis miss 不放大 DB 查询 |
| M3-GO-5 | 顶层 data_quality 聚合 | `fullstack-builder` | quote/sector/key-level response | `fresh/stale/partial/unavailable` | 全 stale 不得标 fresh |
| M3-GO-6 | 连接复用 | `devops-operator` / `fullstack-builder` | Redis/MySQL client | 长连接或连接池 | 压测无短连接风暴 |
| M3-GO-7 | `scan-worker` 生产扫描编排 | `fullstack-builder` / `stock-analysis-specialist` | `go-services/scan-worker` | 触发 Python reference 全市场扫描、暴露状态、记录 fallback | 策略计算来源明确为 Python reference |
| M3-GO-8 | `scan-worker` 启用与回退 | `devops-operator` / `fullstack-builder` | scheduler/config/runtime | Go 扫描启用状态、fallback reason | 失败时回退 Python 扫描或停止写入 |
| M3-GO-9 | internal token 生产强校验 | `devops-operator` | Go main + Python security config | token 为空生产启动失败 | P0 安全项关闭 |
| M3-GO-10 | 生产路径启用标识 | `devops-operator` / `fullstack-builder` | Go metrics/logs | 输出 bff/read/scan hit、miss、fallback 指标 | 能证明生产请求命中 Go |

### Python 接入任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M3-PY-1 | 更新 Go read client | `fullstack-builder` | `backend/app/services/market/go_read_client.py` | 支持批量和质量字段 | Go 失败时 Python fallback |
| M3-PY-2 | BFF/market route 使用质量字段 | `fullstack-builder` | market routes/BFF | 前端拿到一致质量 | 降级可见 |
| M3-PY-3 | Go BFF client 接入 | `fullstack-builder` | backend workspace/BFF client | workspace 请求优先 Go BFF | 关闭后回退 Python BFF |
| M3-PY-4 | scan-worker 编排接入 | `fullstack-builder` | scan result repository / monitor API | 读取 Python reference 写入的 snapshot，并标注 Go 编排来源 | Go 启停不改变策略结果 |
| M3-PY-5 | 配置和 compose 对齐 | `devops-operator` | `docker-compose.mysql.yml`、`.env.docker.example` | Go DSN/token/URL 配置完整 | profile 启用即能工作 |
| M3-PY-6 | 非策略生产主路径切换 | `fullstack-builder` | market data service、BFF、settings、scheduler | 验收完成后默认优先调用 Go BFF/read/scan 编排路径 | 关闭 Go 配置可回退 Python |

### 性能和测试任务

| ID | 测试 | 覆盖 |
|---|---|---|
| M3-T-1 | BFF 聚合 benchmark | workspace payload、并发、P95、partial response |
| M3-T-2 | 500/1000 symbol benchmark | ns/op、B/op、allocs/op、P95 |
| M3-T-3 | stale 聚合测试 | 全 stale、部分 stale、fresh+missing |
| M3-T-4 | Redis miss + MySQL fallback | 批量 fallback 不 N+1 |
| M3-T-5 | scan-worker 策略真源测试 | 响应必须标注 `strategy_engine=python_reference` |
| M3-T-6 | scan-worker snapshot 写入测试 | Python reference 写入幂等、Go 编排失败不污染 latest |
| M3-T-7 | token 启动校验测试 | 生产 token 为空失败 |
| M3-T-8 | 生产路径命中测试 | Go 启用时 BFF/read/scan 实际命中 Go，Go 关闭时回退 Python |

### Definition of Done

- `bff-gateway` 支持 workspace/monitor 聚合主路径。
- `market-read-service` 支持真实批量读取。
- `scan-worker` 支持全市场扫描编排主路径，但不实现独立候选排序或策略公式。
- 质量字段可被前端正确消费。
- Go 关闭后 Python fallback 完整可用。
- 性能门禁进入 CI 或发布前脚本。
- 生产配置启用 Go 后，workspace/监控/情绪/选股读请求和扫描编排默认命中 Go；策略计算结果仍由 Python 产出。

## 7. M4：数据库迁移与 settings 原子化

### 目标

避免迁移和配置保存出现半状态。

### 数据库迁移任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M4-DB-1 | 明确迁移模式 | `product-strategist` / `devops-operator` | docs + API schema | `full` / `materialized_only` 或明确命名 | UI 不再误导为全量 |
| M4-DB-2 | 扩展全量表清单 | `fullstack-builder` | `db_admin_service.py` | 覆盖用户、会话、模拟盘、回测、runtime、审计等 | 关键业务表不丢 |
| M4-DB-3 | 单事务迁移 | `fullstack-builder` | migration service | 中途失败回滚 | 目标库不半成品 |
| M4-DB-4 | 迁移报告 | `devops-operator` | migration response/log | copied/skipped/failed 表清单 | 运维能定位问题 |

### settings 原子化任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M4-SET-1 | runtime.env 原子写 | `fullstack-builder` | `settings_service.py` | temp file + rename | 文件写失败不破坏旧文件 |
| M4-SET-2 | DB 与文件一致性语义 | `fullstack-builder` | settings service | 失败补偿或事务顺序重构 | 不出现 DB 更新但 runtime 未更新 |
| M4-SET-3 | 敏感字段保护 | `devops-operator` | settings service | 不回显、不误写 masked value | Key 不泄漏 |
| M4-SET-4 | 运行时诊断 | `devops-operator` | settings runtime diagnostics | 展示 DB/runtime 是否一致 | 用户知道是否需修复 |

### 测试任务

| ID | 测试 | 覆盖 |
|---|---|---|
| M4-T-1 | 迁移失败回滚测试 | 单表失败、目标库状态 |
| M4-T-2 | overwrite 范围测试 | 清空范围和跳过范围 |
| M4-T-3 | runtime 写失败测试 | DB/runtime 一致性 |
| M4-T-4 | 迁移报告测试 | copied/skipped/failed 输出 |

### Definition of Done

- 迁移 scope 在 UI、API、文档中一致。
- settings 写失败不会留下半状态。
- 运维能看到可执行的恢复提示。

## 8. M5：Rust 内核生产化

### 目标

补齐核心指标、修复 Python wrapper、发布 wheel，把 Rust 验收纳入 CI，并在验收完成后作为 Python 调用的指标加速层接入。Rust 不作为策略、风控、回测或模拟盘结果的独立真源。

### Rust 任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M5-RS-1 | 实现 RSI | `fullstack-builder` / `trading-quant-lead` | `rust/tquant-rs` | `rsi_wilder` | 与 Python reference 误差达标 |
| M5-RS-2 | 实现 VWAP | `fullstack-builder` / `trading-quant-lead` | `rust/tquant-rs` | `vwap` | 支持分时/日线输入 |
| M5-RS-3 | 实现 RankIC | `fullstack-builder` / `trading-quant-lead` | `rust/tquant-rs` | `rank_ic` | 因子实验室可复用 |
| M5-RS-4 | 修复 wrapper warmup `None` | `fullstack-builder` | `backend/app/services/finance/rust_math.py` | 不因 `None` 触发无谓 fallback | rolling/ATR wrapper 可用 |
| M5-RS-5 | wheel 进入镜像 | `devops-operator` | Dockerfile/CI | 容器内可 import `tquant_rs` | 不依赖运行时编译 |
| M5-RS-6 | Rust 命中指标 | `devops-operator` / `fullstack-builder` | Rust wrapper/logs/metrics | 输出 rust hit/fallback 指标 | 能证明生产计算命中 Rust |

### 接入任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M5-PY-1 | Python reference parity | `qa-tester` | backend tests | Rust/Python 一致性测试 | 指标误差阈值明确 |
| M5-PY-2 | 生产 feature flag | `devops-operator` | config/settings | 验收前可关闭，验收后可受控启用 | 关闭即走 Python，开启也不得改变策略结果 |
| M5-PY-3 | 回测/因子实验室指标加速接入 | `fullstack-builder` | finance/backtest/factor services | 指标热点可走 Rust wrapper | Python reference parity 必须通过，策略语义不变 |

### 测试任务

| ID | 测试 | 覆盖 |
|---|---|---|
| M5-T-1 | Rust 单元测试 | 空数组、短数组、长数组、NaN/None 等 |
| M5-T-2 | Python parity | RSI/VWAP/RankIC/ATR/rolling/maxDD |
| M5-T-3 | wheel import smoke | Docker/CI 中导入 |
| M5-T-4 | fallback 测试 | Rust 不可用时 Python 结果不变 |
| M5-T-5 | 指标加速路径命中测试 | Rust 启用时指标 wrapper 可命中 Rust，关闭时回退 Python，策略输出不变 |

### Definition of Done

- Rust 指标覆盖目标集合。
- wheel 可发布、可导入、可回退。
- CI 能在干净环境复现验收。
- 生产配置启用后，目标指标可命中 Rust 加速路径；策略结果仍以 Python reference 为准。

## 9. M6：历史表、CI 与可观测性

### 目标

把已完成能力沉淀成可回放、可验证、可观测、可维护的长期基础。

### 数据历史任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M6-DATA-1 | 小时快照历史表 | `fullstack-builder` | models/migrations/service | 每小时保留历史 | 可按日期回放 |
| M6-DATA-2 | pulse 事件表 | `stock-analysis-specialist` / `fullstack-builder` | models/service | 强弱切换事件留痕 | 策略医生可引用 |
| M6-DATA-3 | 复盘历史查询接口 | `fullstack-builder` | monitor/paper routes | 查询历史复盘 | 实时监控可查看过去报告，模拟盘可做辅助入口 |

### CI 与观测任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M6-CI-1 | Go/Rust CI job | `devops-operator` | `.github/workflows/ci.yml` | Go test、bench、Rust test、wheel smoke | PR 自动拦截 |
| M6-OBS-1 | partial_errors 结构化日志 | `devops-operator` | BFF/market/paper | source、reason、request_id | 方便排障 |
| M6-OBS-2 | 迁移/settings 修复报告 | `devops-operator` | settings/db admin | recovery_hint | 运维知道下一步 |

### 移动端入口任务

| ID | 任务 | 责任角色 | 改动范围 | 产出 | 验收 |
|---|---|---|---|---|---|
| M6-MOB-1 | 移动端入口补齐 | `ui-designer` | mobile shell | 监控/情绪/模拟盘/设置入口一致 | 移动体验闭环 |

### Definition of Done

- 历史快照和复盘可查询。
- CI 覆盖 Go/Rust 与关键前后端基础测试。
- 降级、迁移、settings 失败都有结构化输出。

## 10. 跨里程碑依赖

| 依赖 | 说明 |
|---|---|
| M1 依赖 M0 | pulse 字段需要先冻结接口契约 |
| M2 依赖 M0 | 实时监控复盘不能改坏模拟盘账本和自动交易 |
| M3 依赖 M0 | Go BFF/read/scan 接口必须先明确兼容字段、生产命中指标和 fallback |
| M4 可与 M1/M2 并行 | 主要影响 settings/db admin，不直接改策略 |
| M5 依赖 M0，部分依赖 M3 | Rust 指标需要 Python reference 和 CI 验收 |
| M6 依赖 M1-M5 | 历史表和观测应基于稳定字段沉淀 |

## 11. 发布策略

### 阶段一：开发环境验证

- 功能开关默认用于开发隔离。
- Go/Rust 先在开发环境验证非策略主路径命中和 fallback。
- 前端页面先展示但不驱动交易动作。

### 阶段二：灰度验证

- 开启 pulse 和复盘展示。
- Go BFF/read/scan 编排接入一部分 workspace、监控、情绪、选股和扫描生产请求，并记录命中率。
- Rust 接入一部分回测/因子/性能评估指标热点，并记录命中率；策略输出必须与 Python reference 一致。

### 阶段三：生产启用

- 所有 P1 测试通过。
- CI 门禁稳定。
- 运行手册和回滚路径完整。
- 连续交易日无策略结果异常。
- Go BFF/read/scan 编排成为 workspace、监控、情绪、选股和扫描调度主路径。
- Rust 成为已迁移指标的生产加速路径，但不成为策略结果真源。

## 12. 回滚策略

| 模块 | 回滚方式 |
|---|---|
| pulse 前端展示 | 隐藏组件，保留旧监控指标 |
| monitor 复盘展示 | 隐藏实时监控复盘卡片，不影响账本 |
| Go BFF/read/scan 编排 | 清空服务 URL 或关闭 Go feature flag，回退 Python |
| Rust 指标加速 | 关闭 `RUST_FINANCE_MATH_ENABLED` |
| settings 原子化 | 保留旧 runtime.env，回滚 DB 设置 |
| 数据迁移 | 禁止自动 activate，先恢复备份 |

## 13. 统一验收清单

上线前必须确认：

- [ ] 前端 `lint/test/build` 通过。
- [ ] 后端标准测试命令通过，或已有失败项有明确豁免报告。
- [ ] Go 三服务测试通过。
- [ ] Rust 测试、wheel import、Python parity 通过。
- [ ] 盘中 pulse 在 fresh/stale/partial/unavailable 下都可展示。
- [ ] 午盘/收盘复盘在实时监控页可见。
- [ ] Go BFF/read/scan benchmark 达标。
- [ ] Go `bff-gateway`、`market-read-service`、`scan-worker` 已接入非策略生产主路径，并有命中/回退指标。
- [ ] Rust 已接入指标加速路径，并有命中/回退指标；策略结果只依赖 Python reference。
- [ ] settings 写失败不会留下半状态。
- [ ] 数据迁移失败能回滚或拒绝 activate。
- [ ] Docker/compose/env/runbook 与实现一致。
- [ ] 回滚开关验证通过。
