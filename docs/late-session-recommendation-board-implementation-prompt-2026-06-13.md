# 尾盘推荐榜实施提示词（2026-06-13）

下面提示词用于继续实现“尾盘推荐榜 / late session recommendation board”。可直接复制给主 agent，也可拆给多个 agent 并行开发。

## 主提示词

```text
你在 /Users/j/Documents/gupiao 项目中工作。目标：按已确认需求实现独立“尾盘推荐榜 / late session recommendation board”，只做本地开发、测试和验收文档，不部署、不切流、不重启生产服务、不改生产配置。

开始前必须执行：
1. cd /Users/j/Documents/gupiao && git status --short
2. 阅读 AGENTS.md、docs/engineering-conventions.md、docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md
3. 阅读需求文档 docs/late-session-recommendation-board-requirements-2026-06-13.md
4. 阅读开发计划 docs/superpowers/plans/2026-06-13-late-session-recommendation-board.md

硬边界：
- 禁止修改 backend/app/services/low_buy/strategy_policy.py
- 禁止改变 production_score、生产策略准入、priority_board 默认排序和默认字段语义
- 禁止让 Web 请求触发全市场低吸扫描、24M 回测、DuckDB 报告或重分析任务
- 禁止部署、切流、重启、清理磁盘、改 .env、改 nginx、改数据库
- 禁止自动下单；所有前端文案只能是“尾盘确认/尾盘观察/不满足尾盘确认/数据不足”等观察语义
- 前端不得重算生产排序或尾盘状态，必须以后端返回顺序和状态为准

实现范围：
1. 新增后端契约：
   - backend/app/models/schema_defs/late_session_board.py
   - 包含 snapshot_slot、status、late_session_state、degradation_reason、item、response schema
2. 新增低吸领域逻辑：
   - backend/app/services/low_buy/late_session_policy.py
   - backend/app/services/low_buy/late_session_board.py
   - backend/app/services/low_buy/late_session_cache.py
   - backend/app/services/low_buy/late_session_tasks.py
3. 新增 API：
   - GET /api/screeners/low-buy/late-session-board
   - 参数：limit=12、slot=latest、refresh=cache|async|sync、strategy_variant=baseline
   - 默认 cache 只读；async 只排队 late_session_recommendation_refresh；sync 仅管理员/内部允许，否则降级 async
4. 新增 runtime task：
   - late_session_recommendation_refresh
   - 只读取已物化 priority board 候选、quote cache、分钟线、市场状态
   - 不做全市场扫描，不重算生产分，不修改原 priority board 快照
5. 新增前端展示：
   - frontend-next/src/features/monitor-action/lateSessionBoardModel.ts
   - frontend-next/src/features/monitor-action/LateSessionBoardPanel.tsx
   - 集成到 /next/monitor 的 MonitorActionPage，保留现有 priority board 主榜
6. 新增研究脚本：
   - backend/scripts/late_session_board_backtest.py
   - 对比 priority board top N、late_confirmed、late_watch、late_rejected
7. 输出验收报告：
   - docs/reports/late-session-recommendation-board-local-acceptance-2026-06-13.md

策略口径：
- 正式尾盘候选只允许 first_board、volume_shrink、late_session_strong_support
- late_session_strong_support 低样本限权，不能高于核心策略
- research/factor 策略只能观察或研究标签，不能进入 late_confirmed
- 缺 quote、分钟线、VWAP、市场状态时必须显式降级，不能输出正式尾盘推荐
- 市场状态 block 时不能输出 late_confirmed

开发方式：
- 使用 TDD：先写失败测试，再实现，再跑测试
- 按 docs/superpowers/plans/2026-06-13-late-session-recommendation-board.md 的 Task 1-10 顺序推进
- 每个任务完成后运行对应测试；如要提交，按任务小提交，不混入无关改动
- 如果发现必须写生产配置、部署、重启或清理才能继续，停止并写入阻塞说明，不执行

必须新增/覆盖的测试：
- backend/tests/test_late_session_board_policy.py
- backend/tests/test_late_session_board_service.py
- backend/tests/test_late_session_board_cache.py
- backend/tests/test_late_session_board_api.py
- backend/tests/test_late_session_runtime_task.py
- frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts
- 可选：backend/tests/test_late_session_board_backtest.py

关键验收命令：
PYTHONPATH=backend:. python -m pytest -q \
  backend/tests/test_late_session_board_policy.py \
  backend/tests/test_late_session_board_service.py \
  backend/tests/test_late_session_board_cache.py \
  backend/tests/test_late_session_board_api.py \
  backend/tests/test_late_session_runtime_task.py \
  backend/tests/test_priority_board_cache_fast_path.py \
  backend/tests/test_priority_board_read_model.py \
  backend/tests/test_strategy_engine_production_gate_guards.py

npm --prefix frontend-next test -- --run frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts
npm --prefix frontend-next run typecheck
npm --prefix frontend-next run build
git diff -- backend/app/services/low_buy/strategy_policy.py
git status --short

验收标准：
- /api/screeners/low-buy/late-session-board 可返回完整 schema
- cache 模式不触发全量扫描
- async 模式只排队 late_session_recommendation_refresh
- runtime task 只从已物化 priority board 候选派生
- 14:50、14:55、14:57 slot 可区分
- missing quote/minute/VWAP/market context 都有明确 degradation_reason
- 原 /api/screeners/low-buy/priority-board 行为不回退
- frontend-next /next/monitor 显示尾盘模块，同时保留现有 priority board
- 前端不出现“必涨”“建议买入”“立即买入”
- strategy_policy.py 无 diff
- 明确记录本轮未部署、未重启、未切流、未改生产配置
```

## 多 Agent 并行提示词

### Agent A：后端领域与策略边界

```text
你是 Agent A，负责尾盘推荐榜后端领域模型和只读派生逻辑。工作目录 /Users/j/Documents/gupiao。

先执行 git status --short，阅读 AGENTS.md、docs/engineering-conventions.md、docs/late-session-recommendation-board-requirements-2026-06-13.md、docs/superpowers/plans/2026-06-13-late-session-recommendation-board.md。

只实现计划 Task 1-2：
- backend/app/models/schema_defs/late_session_board.py
- backend/app/services/low_buy/late_session_policy.py
- backend/app/services/low_buy/late_session_board.py
- backend/tests/test_late_session_board_policy.py
- backend/tests/test_late_session_board_service.py

硬边界：
- 不改 backend/app/services/low_buy/strategy_policy.py
- 不改 production_score、priority_board 默认排序或准入口径
- 不写 API、runtime worker、前端和部署脚本

验收：
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_late_session_board_policy.py backend/tests/test_late_session_board_service.py
git diff -- backend/app/services/low_buy/strategy_policy.py 必须为空。
```

### Agent B：API、缓存与 Runtime Task

```text
你是 Agent B，负责尾盘推荐榜 API、缓存和 runtime task。工作目录 /Users/j/Documents/gupiao。

先执行 git status --short，阅读 AGENTS.md、docs/engineering-conventions.md、docs/late-session-recommendation-board-requirements-2026-06-13.md、docs/superpowers/plans/2026-06-13-late-session-recommendation-board.md。

在 Agent A 的 schema/service 可用后，只实现计划 Task 3-6：
- backend/app/services/low_buy/late_session_cache.py
- backend/app/services/low_buy/late_session_tasks.py
- backend/app/api/routes/screeners.py 新增 GET /low-buy/late-session-board
- backend/app/workers/runtime_worker.py 新增 late_session_recommendation_refresh 分发
- 如无稳定 scheduler registry，只写 docs/operations/late-session-board-runbook.md，不强行新增调度体系

硬边界：
- cache 默认只读，不触发全市场扫描
- refresh=async 只能排队 late_session_recommendation_refresh
- refresh=sync 仅管理员/内部允许，否则降级 async
- 不部署、不重启、不改生产配置

验收：
PYTHONPATH=backend:. python -m pytest -q \
  backend/tests/test_late_session_board_cache.py \
  backend/tests/test_late_session_board_api.py \
  backend/tests/test_late_session_runtime_task.py \
  backend/tests/test_priority_board_cache_fast_path.py \
  backend/tests/test_priority_board_read_model.py
git diff -- backend/app/services/low_buy/strategy_policy.py 必须为空。
```

### Agent C：Frontend-next 展示

```text
你是 Agent C，负责 frontend-next 尾盘推荐榜展示。工作目录 /Users/j/Documents/gupiao。

先执行 git status --short，阅读 AGENTS.md、docs/engineering-conventions.md、docs/late-session-recommendation-board-requirements-2026-06-13.md、docs/superpowers/plans/2026-06-13-late-session-recommendation-board.md。

只实现计划 Task 7-8：
- frontend-next/src/features/monitor-action/lateSessionBoardModel.ts
- frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts
- frontend-next/src/features/monitor-action/LateSessionBoardPanel.tsx
- 修改 frontend-next/src/features/monitor-action/MonitorActionPage.tsx
- 修改 frontend-next/src/features/monitor-action/monitor-action.css
- 修改 frontend-next/src/shared/api/client.ts 和 queryKeys.ts

硬边界：
- 不改后端策略语义
- 不重排后端 items
- 不在前端计算 late_session_state
- 保留现有 priority board 主榜
- 禁止出现“必涨”“建议买入”“立即买入”

验收：
npm --prefix frontend-next test -- --run frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts
npm --prefix frontend-next run typecheck
npm --prefix frontend-next run build
如本地服务可启动，用 Playwright 检查 /next/monitor：尾盘模块可见、priority board 仍可见、无 chunk 404、无接口白屏。
```

### Agent D：研究脚本、回归与验收报告

```text
你是 Agent D，负责尾盘推荐榜研究脚本、回归检查和验收报告。工作目录 /Users/j/Documents/gupiao。

先执行 git status --short，阅读 AGENTS.md、docs/engineering-conventions.md、docs/late-session-recommendation-board-requirements-2026-06-13.md、docs/superpowers/plans/2026-06-13-late-session-recommendation-board.md。

实现计划 Task 9-10：
- backend/scripts/late_session_board_backtest.py
- 可测试逻辑写 backend/tests/test_late_session_board_backtest.py
- docs/reports/late-session-recommendation-board-local-acceptance-2026-06-13.md

研究报告必须对比：
- priority board top N
- late_confirmed
- late_watch
- late_rejected

指标必须包含：
- T+1 开盘、T+1 最高、T+1 10:30 前最高、T+1 收盘、T+2 收盘
- 胜率、PF、平均收益、最大回撤、样本留存率、数据缺失率

硬边界：
- 不用 max_gain 冒充可成交收益
- 不把 research/factor 策略升入生产
- 不部署、不改配置、不重启

最终验收报告必须列出：
- 已执行命令和结果
- API/前端/任务/缓存验收结果
- strategy_policy.py 无 diff 证据
- priority_board 回归证据
- 本轮未执行的部署、重启、切流、清理、生产配置写入
- 剩余需要用户授权的事项
```

## 停止条件

任一 agent 遇到以下情况必须停止并报告，不得自行绕过：

- 需要修改 `backend/app/services/low_buy/strategy_policy.py`
- 需要改变 `production_score` 或默认 `priority_board` 排序
- 需要 Web 请求触发全市场扫描才能实现
- 需要部署、切流、重启、改 `.env`、改 nginx、改数据库或清理生产资源
- 本地测试证明 priority board 现有行为发生回退
- 前端实现必须隐藏或替换现有 priority board 才能继续
