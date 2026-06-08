# Frontend Next Parity Completion Implementation Prompt - 2026-06-06

把下面提示词复制给执行 Agent 使用。正文控制在 4000 字以内。

```text
你在 /Users/j/Documents/gupiao 工作。目标：按多 Agent 并行方案补齐 frontend-next/，使 /next/* 从 shadow shell 达到 cutover 评审前的完整 parity 状态。本轮不部署、不切流。

开始前执行：
cd /Users/j/Documents/gupiao && git status --short

必须阅读：
AGENTS.md、docs/engineering-conventions.md、docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md、docs/architecture/current-boundary-map.md、docs/frontend-next-solid-parallel-development-plan-2026-06-05.md、docs/frontend-next-architecture-design-2026-06-05.md、docs/frontend-next-feature-parity-matrix-2026-06-05.md、docs/reports/frontend-next-gap-audit-2026-06-06.md、docs/frontend-next-parity-completion-requirements-2026-06-06.md、docs/frontend-next-parity-completion-development-doc-2026-06-06.md、docs/frontend-next/style-specs/*.md。

硬边界：
1. 不部署、不切流。
2. 不改 strategy_policy.py。
3. 不改变生产策略语义、生产排序、production_score、priority_board。
4. 不改旧 frontend/ 生产代码；旧前端只作对照和验证。
5. 后端默认不动；缺安全写 API 时写契约需求，新前端保持 shadow-only。
6. 不伪造写入成功；写入默认 shadow，live-smoke 必须隔离且可回滚。
7. UI 必须经 frontend-next/src/shared/ui wrapper，不直接用第三方默认样式。
8. Worker/WASM 只做显示层 sort/filter/derive/downsample，不做策略判断。
9. 机甲头像/特效只用于 /next/paper display/review，不影响生产排序或信号。
10. 沿用旧前端风格、密度、文案语气；旧实现不合理处可优化，但只能提升易用性、可用性、稳定性，并证明业务口径不变。

并行分工：
A 架构：Auth、route guard、AppShell、Command Palette、兼容跳转、移动导航、error boundary、telemetry。主改 src/app、features/auth、shared/telemetry。
B 契约/API：OpenAPI types、shared/api operations、queryKeys、mutation 状态机、auth adapter、contract smoke。页面不得拼 URL。
C UI：shared/ui/form/motion wrapper，DataTable、VirtualCardList、Modal、Drawer、ConfirmAction、Toast、FormField、响应式、a11y。
D 实时/图表：SSE、Solid signals、Worker fallback、Lightweight Charts、ECharts adapter、资源释放、perf telemetry。
E 核心页：/next/monitor、/next/monitor/market、/next/paper、/next/strategy-tracking。
F 次级页：/next/analysis、/next/playbook、/next/backtest、/next/data、/next/settings。
G QA：traceability、optimization、permissions 矩阵，E2E、截图、性能、acceptance/open items。

共享规则：
shared/api 由 B 统一改；shared/ui 由 C 统一改；realtime/workers/charts 由 D 统一改；routeTree 由 A 合并；docs/frontend-next/*matrix* 和 acceptance/open items 由 G 汇总。改共享文件前先看 diff，禁止覆盖他人改动。

必须补文档：
docs/frontend-next/traceability-matrix-2026-06-06.md、optimization-registry-2026-06-06.md、permissions-matrix-2026-06-06.md，并更新 parity matrix、acceptance、open items。

必须补齐：
1. 基础：login/register/refresh/logout/me/MFA，session restore，paper/admin/live-smoke guard，Cmd/Ctrl+K，Cmd/Ctrl+1~8，/next/emotion/low-buy/strategy/performance 兼容跳转，401/403/429/5xx 处理，SSE/Worker/chart/timer/listener 离页释放。
2. analysis：单票/批量分析、关键位、盘中异常、Worker 排序、K 线、模拟下单联动。
3. playbook：真实策略 meta、生产/观察 tabs、候选分层、绩效归因、报价刷新、详情/分析/选择。
4. paper：完整委托、推荐导入、买卖/数量快捷、暂停恢复、风险/绩效/标签、自动交易、对账 dry-run/apply、机甲 display/review。
5. strategy-tracking：列表/分页/排序、筛选/详情抽屉、表现/持有/漂移/诊断、复盘中心、交易日志 CRUD、relative strength。
6. monitor/market：生产优先榜服务端顺序、strategy lane、risk badges、自选/持仓、观察池增删改、关键位、AI 解读、market gate、breadth、pulse、sector、ETF T0、review、runtime/data quality。
7. backtest/data/settings：回测提交/详情/取消/图表/验证优化对比；data admin、SLA、source、coverage、tasks、repair、inspector；settings MFA、风控、行业排除、LLM/factor/quant、策略治理、feature flags/audit。

保护与稳定：
priority_board 只按后端顺序；production_score 只展示后端字段；near_entry 仅 watch-only；research-only 不进生产排序。mutation 统一状态机，防重复提交，危险操作二次确认。空/加载/错误/权限不足/partial error/断网/SSE 断连/Worker crash 都有恢复路径。支持 reduced motion；截图覆盖 1440x900、1280x800、768x1024、390x844；token/账号/密钥/堆栈脱敏。

最终运行：
cd /Users/j/Documents/gupiao/frontend-next && npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build && npm run e2e && npm run perf:compare && npm run screenshot:parity
cd /Users/j/Documents/gupiao/frontend && npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build
cd /Users/j/Documents/gupiao && git diff --check && git status --short

最终报告必须写：初始/最终 git status，新建/修改文件，完成 Agent/阶段，新旧 parity，样式图/截图/响应式，API/data parity，权限/异常/写入/稳定性，SSE/请求，性能，测试结果，是否改旧 frontend/，是否改后端，是否影响平台功能，回滚方式，未完成项，是否需用户授权 cutover。
```
