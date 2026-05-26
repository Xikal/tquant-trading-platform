# 全项目审查报告 · 2026-05-25

## 测试范围
- 前端页面：登录、监控、情绪、分析、选股宝典、策略工作台、模拟盘、设置。
- 后端主链路：认证、工作台 BFF、行情、低吸筛选、模拟盘、复盘、调度器。
- 新增 Go / Rust：`go-services/*`、`rust/tquant-rs`。
- 运行时与部署：`/healthz`、`/readyz`、`make qa`、`ui_smoke`、前端构建。

## 测试环境
- 仓库：`/Users/j/Documents/gupiao`
- 日期：2026-05-25
- 运行环境：本地开发机
- 后端：FastAPI + SQLite 本地烟测库
- 前端：Vite + React + Ant Design
- Go：`go test ./...`
- Rust：`cargo test`

## 执行命令与结果摘要
- `./scripts/qa_smoke.sh`：通过
- `./scripts/ui_smoke.sh http://127.0.0.1:18080`：通过
- `cd frontend && npm run build`：通过，存在大 chunk 警告
- `cd backend && .venv/bin/python -m pytest -q tests/test_go_bff_shadow.py tests/test_finance_performance_math.py tests/test_performance_regression.py tests/test_backend_refactor_foundation.py tests/test_auth_cookie_security.py`：通过
- `cd go-services/market-read-service && go test ./...`：通过
- `cd go-services/bff-gateway && go test ./...`：通过
- `cd go-services/scan-worker && go test ./...`：通过
- `cd rust/tquant-rs && cargo test`：通过

## 总体结论
- 不建议直接按“完整需求”上线到正式生产。
- 现有主功能基本可用，UI 冒烟通过，核心后端烟测通过。
- 但两个新业务需求缺失，且有一个工作台聚合路径存在运行时异常。
- Go / Rust 当前仍是影子或可选增强路径，未达到“正式生产主路径可用 + 性能验收完成”的标准。

## 通过项
1. 前端主页面可加载，登录、导航、工作台切换正常。
2. UI 冒烟未发现明显遮挡、弹层残留或控制台致命错误。
3. 后端健康检查、就绪检查、认证、设置持久化、低吸筛选、回测烟测通过。
4. Go 三个服务单测通过。
5. Rust 计算内核单测通过。
6. 关键回归测试覆盖了权限、性能数学、分钟线持久化、Go 客户端与扫描影子逻辑。

## 缺陷清单

### 1. 新增“小时级全市场拉取”未落地
- 严重级别：P1
- 模块：`backend/app/runtime/background_jobs.py`、`backend/app/services/market_quote_cache_refresh.py`、`backend/app/workers/runtime_worker.py`
- 标题：交易时段内没有“每隔一个小时拉取全 A 股市场数据”的专用任务
- 影响范围：市场强弱判断、盘中节奏反馈、全市场行情缓存
- 复现步骤：查看运行时调度与任务队列，没有发现按小时触发的全市场拉取任务；现有缓存刷新仅覆盖自选和高流动性前 200 标的。
- 期望结果：交易时段内按小时拉取全市场 A 股快照，并产出可供页面/策略消费的强弱摘要。
- 实际结果：现有 `market_quote_cache_refresh` 只刷新自选 + 高流动性样本，且调度间隔为 30 秒，不是“每小时全市场”。
- 初步原因：调度器没有独立的全市场小时任务，任务目标也不是全市场。
- 修复建议：新增独立的小时级调度任务，拉取全市场 A 股快照，落库/缓存市场广度与强弱摘要，并在工作台暴露最新状态。
- 是否阻塞上线：是

### 2. 中午/下午复盘链路未完整实现
- 严重级别：P1
- 模块：`backend/app/services/paper/archive.py`、`backend/app/runtime/background_jobs.py`、`backend/app/services/latest_data_close_refresh.py`
- 标题：缺少中午复盘与下午收盘复盘两段式报告
- 影响范围：盘中决策指导、收盘复盘、模拟盘绩效总结
- 复现步骤：查看现有调度，只有 15:05 后的归档与 15:10 的日报推送，没有中午复盘报告，也没有“中午报告指导下午”的分发链路。
- 期望结果：中午收盘生成一份复盘报告，并能指导下午执行；下午收盘再生成最终复盘。
- 实际结果：只有收盘后归档和日报，没有中午复盘专用任务。
- 初步原因：复盘逻辑被收口到收盘后归档，缺少午盘时间窗。
- 修复建议：新增午盘复盘任务与午盘报告存储/推送，复盘内容至少包含市场强弱、主线、风险提示、下午执行建议。
- 是否阻塞上线：是

### 3. 工作台 BFF 的配对对冲聚合存在会话脱离异常
- 严重级别：P2
- 模块：`backend/app/api/routes/bff.py:369-410`、`backend/app/api/routes/market.py:136`、`backend/app/core/role_permissions.py:14-18`
- 标题：`paired_hedge` 聚合在 UI 冒烟中触发 `DetachedInstanceError`
- 影响范围：监控页的 BFF 聚合、配对对冲模块、部分工作台摘要
- 复现步骤：打开监控页时，后端日志出现 `bff source failed source=paired_hedge`，栈中报 `DetachedInstanceError`，但页面通过 partial error 继续返回。
- 期望结果：聚合路径稳定返回，不应因权限检查访问 detached ORM 对象。
- 实际结果：该源被降级为 partial error，相关数据不可用。
- 初步原因：`require_research_access(current_user)` 在 BFF 聚合上下文中访问了已脱离会话的 `User` 实体。
- 修复建议：在聚合路径里重新获取用户或只使用已加载字段；避免把 detached ORM 对象传入后续权限检查。
- 是否阻塞上线：否，但应修复

### 4. Go / Rust 仍是影子或可选增强路径，未达到“正式生产主路径可用”
- 严重级别：P2
- 模块：`go-services/README.md`、`rust/tquant-rs/README.md`、`backend/app/services/finance/rust_math.py`、`backend/app/services/market/go_read_client.py`
- 标题：新增 Go / Rust 还未切到生产主路径
- 影响范围：后端读服务、扫描 worker、计算内核
- 复现步骤：查看 README 和运行配置，Go 服务默认关闭，Rust 默认不加载，Python 仍是 source of truth。
- 期望结果：按需求文档，新增模块应满足正式可用标准并可进入受控生产路径。
- 实际结果：当前仍以影子模式或可选增强方式存在。
- 初步原因：实现策略刻意保守，尚未完成正式启用和验证闭环。
- 修复建议：补齐启用条件、灰度开关、回退路径和线上验证流程，明确何时可接入主链路。
- 是否阻塞上线：视生产目标而定；若必须以 Go / Rust 为正式能力，则是阻塞项

### 5. Go / Rust 缺少独立性能验收证据
- 严重级别：P2
- 模块：`go-services/*`、`rust/tquant-rs/*`
- 标题：没有看到可复用的性能基准脚本或 CI 门禁
- 影响范围：读服务、扫描 worker、计算内核的上线决策
- 复现步骤：仓库里只有单测，没有 Go benchmark / Rust benchmark / 压测脚本结果。
- 期望结果：能给出稳定的延迟、吞吐或数值误差指标。
- 实际结果：只能确认单测与构建通过，不能确认性能达标。
- 初步原因：缺少专门的 benchmark harness。
- 修复建议：补 Go/Rust 基准测试和门禁阈值，至少覆盖批量 quote 读取、扫描影子路径和 Rust 计算内核。
- 是否阻塞上线：是，若该能力要纳入生产验收

### 6. 前端仍有较大的打包 chunk
- 严重级别：P3
- 模块：`frontend/dist/assets/*`
- 标题：`antd` / `echarts` chunk 仍然偏大
- 影响范围：首屏加载速度、低端机器体验
- 复现步骤：`npm run build` 输出 `antd-nfQAR0Y9.js` 803 kB、`echarts-DdeMZWpx.js` 595 kB，并给出 chunk 超限警告。
- 期望结果：更细的路由拆分或更小的按需加载 chunk。
- 实际结果：构建可用，但 chunk 仍明显偏大。
- 初步原因：公共依赖体积高，路由拆分已做但仍未进一步细分。
- 修复建议：继续拆分图表和高频页依赖，减少首屏公共包。
- 是否阻塞上线：否

## UI/UX 专项结论
- 登录页、监控页、选股页和工作台整体可用。
- UI 冒烟未见明显遮挡、空白块或弹层残留。

## 功能按钮专项结论
- 登录、刷新、切换、提交、注册、回测、分析等主按钮可用。
- 未发现明显的重复提交弹窗或按钮失效问题。
- 监控页的部分聚合源会降级为 partial error，需要修正，但按钮本身可用。

## 业务/领域专项结论
- 低吸、模拟盘、复盘、风控、权限边界基本保持原样。
- 现有策略筛选路径通过回归测试，没有看到策略逻辑被改坏的证据。
- 但新增的盘中小时级全市场反馈和午盘复盘缺失，属于业务需求缺口。

## Agent/通知专项结论
- Agent 报告、通知扫描、账本复核等调度已存在。
- 运行时能生成日报和复核任务，但没有新增的午盘指导报告链路。

## 安全性专项结论
- 认证、Cookie、安全头、管理令牌、内网服务 token 检查都在。
- 生产安全基线测试通过。
- 需要继续关注 BFF 聚合路径中的 detached user 问题，避免权限判断异常。

## 部署可用性专项结论
- `/healthz`、`/readyz`、前端静态托管、UI 冒烟都通过。
- 本地启动与单端口托管可用。
- 但 Go / Rust 仍不是默认生产主路径，正式部署策略还没收口。

## 性能与稳定性专项结论
- 后端烟测稳定。
- Go / Rust 单测通过，但没有独立 benchmark 结果。
- 前端构建存在较大 bundle 警告，说明包体积仍有优化空间。

## 上线前必须修复项
1. 补上交易时段内每小时全市场拉取与强弱反馈。
2. 补上中午复盘与下午收盘复盘的两段式报告。
3. 修复监控页 BFF 的 `paired_hedge` detached session 问题。
4. 若 Go / Rust 要进入正式可用范围，补性能基准和灰度启用策略。

## 建议补充的自动化测试
1. 小时级全市场拉取调度测试。
2. 中午复盘报告生成与下午指导内容测试。
3. BFF 聚合权限与 detached ORM 回归测试。
4. Go 读服务批量 quote 延迟基准测试。
5. Rust 计算内核基准与数值误差测试。
6. 前端关键页面 smoke 回归测试。

## 下一步测试计划
1. 先补两个业务缺口，再做一次完整回归。
2. 对 Go / Rust 补 benchmark 与启用条件。
3. 继续压缩前端公共包。
4. 再跑一次 UI 冒烟与后端烟测，确认没有回归。

## 整改进度（2026-05-25 更新）
- 项 2 已收尾：`paper_midday_review` 与 `paper_perf_archive` 已接入后台调度，午盘复盘与收盘归档的时间窗、幂等与测试都已通过。
- 项 3 已收尾：`paired_hedge` 聚合已通过 `_attached_user` 重新绑定会话对象，不再依赖脱离会话的 ORM 实体。
- 项 4 已收尾：Go / Rust 性能验收脚本已通过，`docs/reports/go-rust-performance-acceptance-2026-05-25.json` 已落盘，Go market-read benchmark 与 Rust seam benchmark 均达到门槛。
- 现阶段 Go / Rust 仍按运行手册保持受控启用，但已满足“正式可用 + 性能验收完成”的工程条件。
