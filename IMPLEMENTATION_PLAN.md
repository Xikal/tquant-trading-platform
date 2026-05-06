# TQuant 全系统整改执行计划

## 当前需求来源
- `docs/TQuant-全系统整改需求-终版-2026-05-06.md`

## 当前执行清单
- [done] P0-1 通知未配置时不再返回假成功，失败不写入通知冷却账本。
- [done] P0-2 `main.py` 定时归档、日报推送和快照 freshness 统一使用北京时间。
- [done] P0-3 Android Release 禁止明文 HTTP，Debug 保留本地明文调试能力。
- [done] P1-1 `_rebuild_materialized_snapshot` 不再提交外部 session，修复路径使用独立事务。
- [done] P1-2 前端策略入口优先使用后端 `/strategies/meta`，本地只保留集中 fallback。
- [done] P1-3 Paper API `LookupError -> 404`、`ValueError -> 400` 边界补齐。
- [done] P1-4 飞书/Hermes/HTTP Gateway 通知成功语义改为业务成功才计数。
- [done] 运行后端/前端相关验证并记录结果。

## 当前决策
- 仅实现文档确认 Bug 的 P0/P1；P2 产品增强和长期架构按文档不纳入本轮。
- 不执行生产发布、真实密钥改动或破坏性数据操作。
- Android Release 使用 `weisilianghua.cloud` HTTPS-only network security config；Debug resource 同名覆盖为 cleartext true。

## 当前验证命令
- [pass] `python3 -m compileall backend/app backend/tests`
- [pass] `PYTHONPATH=/Users/j/Documents/gupiao/backend backend/.venv/bin/python -m unittest backend/tests/test_notification_events.py backend/tests/test_agent_provider.py backend/tests/test_main_timezone.py backend/tests/test_paper_routes.py`
- [pass] `PYTHONPATH=/Users/j/Documents/gupiao/backend backend/.venv/bin/python -m unittest backend/tests/test_agent_routes.py backend/tests/test_agent_tool_registry.py`
- [pass] `cd frontend && npm run build`

## 当前下一步
- 本轮 P0/P1 整改已完成，等待人工复核或后续发布指令。

---

# 历史计划：TQuant Phase 3 差距修复

## 历史需求来源
- `docs/TQuant-Phase3-差距修复需求-终版-2026-05-05.md`

## 历史执行清单
- [done] P0-1 修复 `/backtests` 老路由 tab 兼容。
- [done] P0-2 修复 owner_user_id NULL 任务隔离，增加迁移和 fail-closed。
- [done] P0-3 加固 WebSocket 进度流，前端 5 次指数重连后降级轮询。
- [done] P0-4 明确回测/优化/验证权限矩阵，前后端一致。
- [done] P1-1 策略工作台 5 Tab 状态流统一，去桥接文案，共享 backtest dashboard hook。
- [done] P1-2 信号回放增加交易日窗口、粒度、空态、错误态。
- [done] P1-3 修复 symbol search total、LIKE 转义、前端搜索错误提示。
- [done] P1-4 useStrategyHub 初始化改 allSettled + 请求序列保护。
- [done] P1-5 风控参数从 preset/form 读取，不再硬编码。
- [done] P1-6 StrategyPreset 增加 preset_key，前端不依赖 key 分支。
- [done] P1-7 Research 页术语中文化和反馈组件统一。
- [done] P1-8 Paper Trading 委托两步式。
- [done] P1-9 Settings 保存反馈和校验。
- [done] P2-1 移动端策略工作台关键路径补齐。
- [done] P2-2 可访问性补齐。
- [done] 运行后端/前端相关验证并记录结果。

## 决策
- 不做生产发布或真实生产数据操作。
- Alembic 迁移只做 additive/backfill；同时更新 schema_compat，兼容未跑迁移的自托管环境。
- WS 仍按文档要求保持 polling-based progress stream over WebSocket，不引入事件队列。

## 验证命令
- 待实现后执行：`python3 -m compileall backend/app backend/tests`
- 待实现后执行：后端相关 unittest/pytest 子集
- 待实现后执行：`npm run build`

## 当前下一步
- 已完成实现与验证，等待人工复核或后续发布指令。
