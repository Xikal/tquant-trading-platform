# TQuant 策略与工作台优化方案 v9 执行计划

## 需求来源

- `/Users/j/Documents/gupiao/docs/TQuant-策略与工作台优化方案-终版-2026-05-06.md`
- 标题：`TQuant 策略与工作台优化方案（v9·开发执行版）`

## 执行状态

- [x] 定位需求文档并核对当前项目基线。
- [x] Phase 0：策略工作台 UX 清理、一键回测、预设卡片、结果摘要、懒加载。
- [x] Phase 1：做 T 成本闭环、`effective_action/is_actionable`、模拟盘过滤。
- [x] Phase 2：策略元数据 4 字段、治理表、resolver、权限过滤、默认预设过滤。
- [x] Phase 3：新增研究策略 `ma_channel_band` / `leader_pullback_band`、样本池、规则、fallback。
- [x] Phase 4：Feature Flag 服务/API/前端入口、弹性缓存与预热脚本。
- [x] 验证：后端测试、前端构建、生成文件同步。

## 关键实现决策

- 不修改 `trade_levels()` 返回结构。
- 不把 DB session 注入 `strategy_policy.py`、`candidate_rules.py`、`base_strategy.py`。
- `visibility=hidden` 采用安全语义：普通用户不可见；admin 仅通过显式 `include_hidden=true` 可见。
- Factor 策略在 meta API 按角色隐藏；回测 API 保持现有能力，不额外拦截 strategy key。
- 新字段全部提供默认值，旧客户端继续兼容。

## 验证命令

- 后端：`cd backend && python -m pytest ...`
- 前端：`cd frontend && npm run build`
- 生成：`python scripts/sync_strategy_meta_fallback.py`

## 本轮验证结果

- `backend/.venv/bin/python -m py_compile ...`：通过。
- `backend/.venv/bin/python -m pytest backend/tests/test_strategy_meta_routes.py backend/tests/test_app_mobile_routes.py`：13 passed，1 个 urllib3/OpenSSL 环境警告。
- `cd frontend && npm run build:web`：通过。
