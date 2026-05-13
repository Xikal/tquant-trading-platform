# TQuant 实施计划

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
