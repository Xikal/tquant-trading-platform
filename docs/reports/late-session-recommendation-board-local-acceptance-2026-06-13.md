# 尾盘推荐榜本地验收报告

- 检查时间：2026-06-13 01:31:58 CST
- 项目路径：`/Users/j/Documents/gupiao`
- 分支：`codex/phase4-phase5-architecture`
- 基准提交：`34a14af3`
- 范围：独立“尾盘推荐榜 / late session recommendation board”本地开发、测试和验收文档
- 生产动作：未部署、未切流、未重启、未改 `.env`、未改 nginx、未改数据库、未清理磁盘

## 实现概览

| 模块 | 文件 | 结果 |
| --- | --- | --- |
| 后端契约 | `backend/app/models/schema_defs/late_session_board.py` | 新增 slot/status/state/degradation/item/response schema |
| 策略口径 | `backend/app/services/low_buy/late_session_policy.py` | 只允许 `first_board`、`volume_shrink`、`late_session_strong_support` 进入正式尾盘确认；低样本策略限权 |
| 低吸派生服务 | `backend/app/services/low_buy/late_session_board.py` | 从已物化 priority board、quote、分钟线、市场状态派生，不改原榜 |
| 快照缓存 | `backend/app/services/low_buy/late_session_cache.py` | 支持内存测试缓存与现有分布式缓存 fail-open 读写 |
| runtime task | `backend/app/services/low_buy/late_session_tasks.py`、`backend/app/workers/runtime_worker.py`、`backend/app/services/tasks/registry.py` | 新增 `late_session_recommendation_refresh` |
| API | `backend/app/api/routes/screeners.py` | 新增 `GET /api/screeners/low-buy/late-session-board` |
| 前端 | `frontend-next/src/features/monitor-action/LateSessionBoardPanel.tsx`、`lateSessionBoardModel.ts` | `/next/monitor` 增加尾盘模块，保留原 priority board 主榜 |
| 研究脚本 | `backend/scripts/late_session_board_backtest.py` | 新增本地研究报告 CLI，对比 priority board top N / late_confirmed / late_watch / late_rejected |
| 运行手册 | `docs/operations/late-session-board-runbook.md` | 记录 slot、payload、幂等键、本地验收与授权项 |

## API 契约

| 参数 | 默认 | 行为 |
| --- | --- | --- |
| `limit` | `12` | 返回数量，限制在 3-30 |
| `slot` | `latest` | 支持 `preview_1450`、`snapshot_1455`、`final_1457`、`latest` |
| `refresh` | `cache` | `cache` 只读；`async` 只入队 `late_session_recommendation_refresh`；非管理员 `sync` 降级为 `async` |
| `strategy_variant` | `baseline` | 保持 priority board 现有变体参数，不重算生产排序 |

`cache` 模式优先读取 runtime task 写入的尾盘快照；缓存 miss 时只从已物化 priority board 派生降级响应。Web 请求不触发全市场低吸扫描、24M 回测、DuckDB 报告或重分析任务。

## 策略与降级

| 场景 | 结果 |
| --- | --- |
| `first_board` / `volume_shrink` 且尾盘确认成立 | 可进入 `late_confirmed` |
| `late_session_strong_support` 且尾盘确认成立 | 可进入 `late_confirmed`，但分数上限 72 |
| research/factor 策略 | 仅 `late_watch`，带 `research_only` 标签 |
| 缺 quote | 不输出正式确认，记录 `quote_unavailable` |
| 缺分钟线 | `late_unavailable`，记录 `minute_data_missing` |
| 缺 VWAP | `late_unavailable`，记录 `vwap_unavailable` |
| 缺市场状态 | `partial_data`，记录 `market_context_missing` |
| 市场状态 block | 不输出 `late_confirmed`，记录 `market_block` |

## 前端验收

| 项 | 结果 |
| --- | --- |
| `/next/monitor` 集成 | 新增 `LateSessionBoardPanel`，原 priority board 主榜仍保留 |
| 顺序口径 | 前端只使用后端返回顺序，不重算生产排序 |
| 状态口径 | 前端只展示后端 `late_session_state` |
| 文案 | 新尾盘模块使用“尾盘确认 / 尾盘观察 / 不满足尾盘确认 / 数据不足”等观察语义 |
| 禁止短语扫描 | 新模块及 monitor 相关生产文件未出现 `必涨`、`建议买入`、`立即买入` |

## 测试结果

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_late_session_board_policy.py backend/tests/test_late_session_board_service.py backend/tests/test_late_session_board_cache.py backend/tests/test_late_session_board_api.py backend/tests/test_late_session_runtime_task.py backend/tests/test_late_session_board_backtest.py backend/tests/test_priority_board_cache_fast_path.py backend/tests/test_priority_board_read_model.py backend/tests/test_strategy_engine_production_gate_guards.py` | 40 passed，1 个本地 LibreSSL/urllib3 warning |
| `npm --prefix frontend-next test -- --run src/features/monitor-action/lateSessionBoardModel.test.ts` | 1 file passed，4 tests passed |
| `npm --prefix frontend-next run typecheck` | passed |
| `npm --prefix frontend-next run build` | passed |
| `PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/late_session_board_backtest.py --help` | passed |
| `docs/operations/late-session-board-runbook.md` 静态检查 | passed |
| `git diff --check` | passed |
| `git diff -- backend/app/services/low_buy/strategy_policy.py` | empty |
| `git diff -- backend/app/services/low_buy/priority_board.py backend/app/services/low_buy/priority_scoring.py backend/app/services/low_buy/production_scoring.py backend/app/services/low_buy/priority_response.py backend/app/services/low_buy/strategy_policy.py` | empty |

说明：用户给出的 `python -m pytest` 在本机系统 Python 下缺少 pytest，因此按项目既有方式使用 `backend/.venv/bin/python -m pytest` 执行。

## 未执行的生产操作

- 未部署。
- 未切流。
- 未重启任何生产服务。
- 未执行 Docker up/down/restart。
- 未清理磁盘、日志、镜像或缓存。
- 未修改 `.env`、nginx 或数据库结构/数据。
- 未改 `backend/app/services/low_buy/strategy_policy.py`。
- 未改 `production_score`、生产策略准入、priority board 默认排序或默认字段语义。
- 未启用线上 14:50/14:55/14:57 自动调度。

## 剩余授权项

| 项 | 是否阻塞本地验收 | 需要授权原因 |
| --- | --- | --- |
| 线上调度接入 14:50 / 14:55 / 14:57 自动入队 | 否 | 会改变线上 runtime scheduler 行为 |
| 生产环境快照持久化策略确认 | 否 | 当前已接现有分布式缓存，是否另建表需产品/运维确认 |
| 线上 API 冒烟与页面截图 | 否 | 本轮边界禁止部署和切流 |
| 真实历史样本回放 | 否 | 研究脚本已具备 CLI 和报告框架，仍需接入历史 priority board/分钟线样本 |

## 结论

本轮已完成本地独立尾盘推荐榜的后端契约、低吸领域派生逻辑、缓存、API、runtime task、前端展示、研究脚本、运行手册和验收报告。核心回归显示 priority board 与生产策略 gate 未回退，`strategy_policy.py` 无 diff。

当前功能可进入本地代码审查阶段；上线前仍需单独授权生产调度启用、生产冒烟和线上观测。
