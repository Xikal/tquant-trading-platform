# 平台优化收口开发计划（2026-06-10）

状态：待执行  
需求来源：`docs/platform-optimization-requirements-2026-06-10.md`  
适用仓库：`/Users/j/Documents/gupiao`  
执行策略：本地可验证项先行；线上资源操作、部署、切流必须单独授权  
最后核验日期：2026-06-10

## 1. 执行目标

把平台体检后的收口需求转成可落地开发批次，优先恢复测试基线和工程门禁，再治理测试漂移与热读性能守卫，最后把线上资源/性能优化保留为授权执行包。

本计划不扩功能、不改策略语义、不做架构重写。所有改动围绕以下结果：

1. `frontend-next` data/settings e2e 恢复全绿。
2. CI 与本地检查顺序固定，避免瘦身/重构类提交假绿。
3. 日期窗口测试不再依赖当前日期。
4. priority board 热读路径有查询计数与 golden 守卫。
5. 旧前端退役相关项成对收尾，不出现半套状态。
6. 线上资源与性能动作有清晰授权、验收和回滚路径。

## 2. 硬边界

1. 不修改 `backend/app/services/low_buy/strategy_policy.py`。
2. 不改变 `production_score`、priority board 排序语义、生产策略公式、风控阈值、交易日发布门控。
3. `strategy_engine` 继续 shadow-only，`replacement_enabled=false`。
4. 不把研究、ML、因子、重分析任务放回 Web 主进程。
5. 不回滚当前在途旧前端退役工程改动。
6. 不执行服务器写操作、不部署、不切流、不停容器、不清 Docker cache，除非用户另行明确授权。
7. 当前工作树很可能有并行改动；每批开始和结束都必须 `git status --short`，只处理本批相关文件。

## 3. 分支与提交建议

建议新分支：

```bash
git switch -c codex/platform-optimization-closure
```

若当前线程已在用户指定分支或存在未提交在途改动，不强制切分支，先报告当前分支和工作树状态。

提交拆分建议：

1. `test: align data settings e2e guards`
2. `ci: enforce platform closure regression gates`
3. `test: add stable export-window fixture time helpers`
4. `test: guard priority board hot-read query budget`
5. `docs: record optional resource and performance execution gates`

如果 R8 发现并修复真实 N+1，再单独提交：

```text
perf: batch priority board hot-read context lookup
```

## 4. 执行批次

### D0. 开工基线

目的：保护当前脏工作树，确认事实基线。

命令：

```bash
git status --short
git branch --show-current
rg -n "令牌验证未通过|管理员权限校验通过|需要先校验管理令牌|管理授权缺失|已使用当前管理员账号解锁本地编辑" frontend-next/tests frontend-next/src
rg -n "pytest backend/tests|api:check|npm test -- --run|npm run build|playwright" .github/workflows/ci.yml frontend-next/package.json docs/engineering-conventions.md
```

产出：列出本批可触碰文件；与本任务无关的已有改动全部保护。

### D1. 修复 data/settings e2e 断言

优先级：P0  
需求来源：R1  
预计文件：

- `frontend-next/tests/e2e/backtest-data-settings.spec.ts`
- `frontend-next/tests/e2e/data-settings-error-states.spec.ts`
- `frontend-next/tests/e2e/interaction-parity.spec.ts`
- `frontend-next/tests/e2e/cutover-fixtures.ts`（仅在确实缺 mock 时改）

动作：

1. 将旧文案断言改成当前 UX 文案。
2. 更新 `/next/data`、`/next/settings` 的 heading 或面板选择器。
3. 复用 `installDataSettingsFixtures`，减少单个 spec 内重复 mock。
4. 保留 `writes() === []`、非 admin 403/权限不足、503 错误态和 admin 守卫断言。

验收：

```bash
cd frontend-next
npx playwright test tests/e2e/backtest-data-settings.spec.ts tests/e2e/data-settings-error-states.spec.ts tests/e2e/interaction-parity.spec.ts --project=chromium
npm run e2e
```

不可接受：为了变绿删除 no-write、403/503、admin guard 核心断言。

### D2. 固化 CI 与本地串行检查

优先级：P0/P1  
需求来源：R2、R3  
预计文件：

- `.github/workflows/ci.yml`
- `frontend-next/package.json`
- `docs/engineering-conventions.md`

动作：

1. 确认 CI backend 保留 `pytest backend/tests`。
2. 确认 frontend-next CI 顺序为 `api:check -> typecheck -> lint -> test -> build`。
3. 增加关键 e2e job 或 step，至少覆盖 `monitor-workflows` 和 `monitor-live-readiness`。
4. 在 `frontend-next/package.json` 增加 `check:all`：

```json
"check:all": "npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build"
```

5. 在 `docs/engineering-conventions.md` §6.11 补充：删除/瘦身/迁移/退役/重构类提交必须贴全量回归结果。

验收：

```bash
python - <<'PY'
from pathlib import Path
ci = Path('.github/workflows/ci.yml').read_text()
for needle in ['pytest backend/tests','npm run api:check','npm run typecheck','npm run lint','npm test -- --run','npm run build']:
    assert needle in ci, needle
pkg = Path('frontend-next/package.json').read_text()
assert 'check:all' in pkg
PY
cd frontend-next && npm run check:all
```

建议连续跑 3 次 `npm run check:all`；如果耗时过长，至少跑 1 次并记录未跑满 3 次的原因。

### D3. 日期窗口测试工具

优先级：P2  
需求来源：R6  
预计文件：

- `backend/tests/support/timefreeze.py` 或 `backend/tests/support/export_time.py`
- `backend/tests/test_analytics_layer.py`
- `backend/tests/test_low_buy_read_paths.py`

动作：

1. 新增共享时间构造工具，返回稳定落在导出窗口内的 `datetime`。
2. 将 analytics/read path 中依赖窗口过滤的 fixture 改成显式时间。
3. 写注释说明：日期窗口测试禁止依赖 DB 默认当前时间。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_layer.py backend/tests/test_low_buy_read_paths.py -q
rg -n "datetime\\.utcnow\\(|datetime\\.now\\(" backend/tests/test_analytics_layer.py backend/tests/test_low_buy_read_paths.py
```

### D4. Priority board 热读查询预算守卫

优先级：P1  
需求来源：R8  
预计文件：

- `backend/tests/test_low_buy_read_paths.py` 或新增 `backend/tests/test_priority_board_query_budget.py`
- 如测出真实问题，再改 `backend/app/services/low_buy/*`

动作：

1. 先只写查询计数测试：构造 N=20 候选，用 SQLAlchemy `before_cursor_execute` 监听目标表查询。
2. 加 golden 输出一致性测试：序列化关键字段并 sha256。
3. 若测试显示查询随 N 线性增长，再批量化上下文读取。
4. 批量化只能减少 DB 往返，不能改排序、分数、lane、shadow 字段。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_production_scoring.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_read_paths.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

停止条件：如果 golden 不一致，必须回滚或继续定位，不能放松断言。

### D5. 旧前端退役收尾核对

优先级：P1  
需求来源：R5  
预计文件：只在当前退役工作面需要时改。

动作：

1. 扫描旧前端运行链路残留。
2. 只做成对收尾，不物理删除 `frontend/` 源码。
3. 若发现旧前端守卫/脚本/CI 半套状态，按当前退役工程作者改动协同修正。

验收：

```bash
rg -n "frontend-legacy|frontend-hot|frontend/dist|html-root|__legacy" Dockerfile deploy scripts backend .github Makefile
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py -q
```

### D6. TanStack chunk 评估

优先级：P2  
需求来源：R7  
预计文件：

- 一般只产出报告；除非收益明确，不改代码。

动作：

```bash
cd frontend-next
npm run build
npm run chunk:profile
```

判断：

1. 如果 table/virtual/misc 不在首屏或收益不足，写“不拆”结论。
2. 如果拆分收益明确，再做 lazy 拆分并跑完整前端验收。

验收：

```bash
cd frontend-next
npm run lint
npm test -- --run
npm run build
npm run chunk:profile
```

### D7. 线上资源与性能授权包

优先级：P1  
需求来源：R4、R9、R10  
默认动作：只整理脚本/Runbook/报告模板，不执行服务器写操作。

本地可做：

1. 确认 `docker-compose.mysql.yml` 保持 `APP_WORKERS=1`、`mem_limit/cpus`、logging、analytics profile、scheduler grey flag。
2. 确认 Runbook 写清楚 analytics 按需和 scheduler 灰度回滚。
3. 准备 `docs/reports/cloud-performance-recheck-YYYY-MM-DD.md` 模板。

必须单独授权后才能做：

1. `docker builder prune -af`
2. 停 separated 栈
3. 改 `vm.swappiness`
4. 灰度/停止 scheduler 容器
5. 线上性能复测
6. 部署或切流

线上授权后的验收目标：

- Swap < 300M。
- 空闲内存 > 1G。
- `/readyz` 全 true。
- `monitor_bff` p95 <= 500ms。
- `priority_board` p95 <= 500ms。
- `bff_partial_timeout=0`。
- market-read unresolved = 0。

## 5. 总体验收矩阵

| 批次 | 必跑命令 | 通过标准 |
|---|---|---|
| D1 | `npx playwright test ...data/settings...`、`npm run e2e` | data/settings spec 全绿；全量 e2e 无新增失败 |
| D2 | `npm run check:all` | api/type/lint/test/build 串行全绿 |
| D3 | `pytest test_analytics_layer.py test_low_buy_read_paths.py` | 日期窗口测试稳定 |
| D4 | 低吸/priority 相关 pytest + `pytest backend/tests` | 查询预算和 golden 守卫通过 |
| D5 | frontend cutover/deploy scope/cloud scripts pytest | 旧前端退役无半套状态 |
| D6 | `npm run chunk:profile` | 拆或不拆都有证据 |
| D7 | 授权后线上 raw command/result | 资源和 p95 达标或列明残差 |

## 6. Done 标准

1. 每批相关测试通过，失败项有根因与处理结果。
2. `git status --short` 中只出现本计划允许的改动和原有在途改动。
3. 未修改策略语义和生产排序核心文件。
4. 未执行未经授权的线上写操作。
5. 交付说明列出：改动文件、验证命令、通过/未跑原因、是否部署/切流。

## 7. 完整执行提示词

```text
你现在在 /Users/j/Documents/gupiao 仓库执行平台优化收口任务。请严格按 docs/platform-optimization-development-plan-2026-06-10.md 和 docs/platform-optimization-requirements-2026-06-10.md 实施。

开始前必须执行 git status --short 和 git branch --show-current，保护当前所有在途改动；不要回滚、删除或覆盖与本任务无关的改动。默认不部署、不切流、不执行服务器写操作、不停容器、不清 Docker cache、不改 sysctl；线上动作必须等我单独授权。

硬边界：不修改 backend/app/services/low_buy/strategy_policy.py；不改变 production_score、priority board 排序语义、生产策略公式、风控阈值、交易日发布门控；strategy_engine 保持 shadow-only，replacement_enabled=false；不把研究/ML/因子/重分析任务放回 Web 主进程；不物理删除 frontend/ 源码。

按批次执行：
1. D0 建立基线：记录 git 状态、相关旧文案断言、CI 与 package 脚本现状。
2. D1 修 frontend-next 的 data/settings e2e：只对齐当前 UX 文案、heading、fixture；保留 writes()===[]、403/503、admin guard 核心断言。验收：cd frontend-next && npx playwright test tests/e2e/backtest-data-settings.spec.ts tests/e2e/data-settings-error-states.spec.ts tests/e2e/interaction-parity.spec.ts --project=chromium；再跑 npm run e2e。
3. D2 固化 CI 与本地串行检查：确保 CI backend 保留 pytest backend/tests，frontend-next 顺序为 api:check -> typecheck -> lint -> test -> build；增加 check:all；docs/engineering-conventions.md 写入删除/瘦身/迁移/退役/重构类提交必须全量回归。验收：cd frontend-next && npm run check:all。
4. D3 增加日期窗口测试工具并改用显式 fixture 时间。验收：PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_analytics_layer.py backend/tests/test_low_buy_read_paths.py -q。
5. D4 为 priority board 热读加查询计数和 golden 输出一致性守卫。先测量，只有证明存在 N+1 才改生产代码；若改代码，必须保持 items 顺序、production_score、priority_score、lane、risk、strategy_engine_shadow 一致。验收：相关低吸测试 + PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q。
6. D5 核对旧前端退役收尾，只做成对收尾，不抢当前退役工作面，不删除 frontend/。验收 cutover/deploy scope/cloud scripts 相关 pytest。
7. D6 评估 TanStack chunk，先 npm run build && npm run chunk:profile；收益不足就写不拆结论，不为拆而拆。
8. D7 只准备线上资源/性能授权包和报告模板，不执行线上写操作。若我之后授权，再按 raw command/result 做资源和 p95 验收。

每完成一个批次，先跑该批验收；失败要定位并修复，不能通过删除核心断言或放松策略守卫来变绿。最终交付必须说明改了哪些文件、跑了哪些命令、结果如何、哪些未跑及原因，并明确没有部署/切流/线上写操作，除非我另行授权。
```
