# TQuant 策略与工作台优化方案 v9 执行计划

## 需求来源

- `/Users/j/Documents/gupiao/docs/TQuant-策略与工作台优化方案-终版-2026-05-06.md`
- 标题：`TQuant 策略与工作台优化方案（v9·开发执行版）`
- 本轮追加：用户列出的 P0/P1/P2 语义、权限、feature flag、迁移 backfill、fallback 校验和探针补齐问题。

## 执行状态

- [x] 定位需求文档并核对当前项目基线。
- [x] Phase 0：策略工作台 UX 清理、一键回测、预设卡片、结果摘要、懒加载。
- [x] Phase 1：做 T 成本闭环、`effective_action/is_actionable`、模拟盘过滤。
- [x] Phase 2：策略元数据 4 字段、治理表、resolver、权限过滤、默认预设过滤。
- [x] Phase 3：新增研究策略 `ma_channel_band` / `leader_pullback_band`、样本池、规则、fallback。
- [x] Phase 4：Feature Flag 服务/API/前端入口、弹性缓存与预热脚本。
- [x] 验证：后端测试、前端构建、生成文件同步。
- [x] P0：统一 `visibility` 语义，`hidden` 只允许 admin + `include_hidden=true` 查看。
- [x] P0：factor/backtest_only 策略增加后端回测权限阻断，不再只靠前端隐藏。
- [x] P0：明确 quick backtest 只由前端展开 preset 到现有 `strategies` 数组，不新增 `preset_key` 提交接口。
- [x] P0：补齐 `StrategySuggestion` 唯一字段表和新策略可用指标说明。
- [x] P0：迁移和 schema_compat 显式 backfill `enabled/probe_status/probe_summary/visibility`。
- [x] P1：feature flag 60 秒进程缓存、标准响应字段、operator_ip 审计和前端审计入口。
- [x] P1：fallback 由后端生成并新增 `--check` 校验脚本。
- [x] P1：弹性缓存质量统一为 `fresh/stale/estimated/unavailable`。
- [x] P1：`probe_leader_pullback_data.py` 扩展为四维 JSON 探针。

## 关键实现决策

- 不修改 `trade_levels()` 返回结构。
- 不把 DB session 注入 `strategy_policy.py`、`candidate_rules.py`、`base_strategy.py`。
- `visibility=hidden` 采用安全语义：普通用户不可见；admin 仅通过显式 `include_hidden=true` 可见。
- `visibility=backtest_only` 仅研究/优化/admin 可见和可回测。
- Factor 策略在 meta API 按角色隐藏，并在回测创建/优化/样本外验证接口做后端权限阻断。
- 新字段全部提供默认值，旧客户端继续兼容。

## 验证命令

- 后端：`cd backend && python -m pytest ...`
- 前端：`cd frontend && npm run build`
- 生成：`python scripts/sync_strategy_meta_fallback.py`

## 本轮验证结果

- `backend/.venv/bin/python -m py_compile ...`：通过。
- `backend/.venv/bin/python -m pytest backend/tests/test_strategy_metadata_service.py backend/tests/test_strategy_meta_routes.py backend/tests/test_feature_flags_service.py`：13 passed，1 个 urllib3/OpenSSL 环境警告。
- `cd frontend && npm run build:web`：通过。
- `cd frontend && npm run check:strategy-meta`：通过，1 个 urllib3/OpenSSL 环境警告。
- `backend/.venv/bin/python scripts/probe_leader_pullback_data.py --dry-run --min-count 1 --output /tmp/leader_probe_report.json`：本地 MySQL 未启动，脚本按预期输出 failed JSON，不再抛出堆栈。
