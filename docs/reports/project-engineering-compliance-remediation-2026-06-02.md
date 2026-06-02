# 工程规范整改报告 - 2026-06-02

状态：整改进行中；G1 清理、G2 后端测试拆分、前端 CSS 拆分与前端 smoke 脚本拆分已完成，全量目标未完成
最后核验日期：2026-06-02
适用范围：`backend/`、`frontend/`、`scripts/`、`deploy/`、`docs/`、`tests/`、`data/generated`

## 1. 当前 git 状态摘要

本轮重新核验的 `git status --short --branch`：

```text
## codex/phase4-phase5-architecture...origin/codex/phase4-phase5-architecture [ahead 34]
 M backend/tests/test_backtest_v2_api_contract.py
 M backend/tests/test_backtest_v2_engine_contract.py
 M backend/tests/test_low_buy_read_paths.py
 M backend/tests/test_paper_auto_trading.py
 M backend/tests/test_phase4_phase5_foundation.py
 M docs/README.md
 M docs/reports/README.md
 M docs/reports/project-engineering-compliance-remediation-2026-06-02.md
 M frontend/scripts/smoke-responsive.mjs
 M frontend/src/styles/workspace/workspace-login.css
 M frontend/src/styles/workspace/workspace-primitives.css
 D frontend/tsconfig.node.tsbuildinfo
?? backend/tests/test_backtest_v2_execution_components.py
?? backend/tests/test_backtest_v2_worker_persistence.py
?? backend/tests/test_low_buy_runtime_seams.py
?? backend/tests/test_low_buy_trade_date_read_paths.py
?? backend/tests/test_paper_auto_trading_runtime_config.py
?? backend/tests/test_phase4_runtime_worker_tasks.py
?? docs/a-share-strong-stock-trading-requirements-2026-06-02.md
?? docs/reports/artifact-manifest-2026-06-02.md
?? docs/reports/zhangmengzhu-16-articles-analysis-2026-06-02.md
?? docs/reports/zhangmengzhu-16-articles-source-2026-06-02.md
?? docs/trading-experience-observation-suite-requirements-2026-06-02.md
?? frontend/scripts/smoke-responsive-fixtures.mjs
?? frontend/src/styles/workspace/workspace-login-card.css
?? frontend/src/styles/workspace/workspace-login-motion.css
?? frontend/src/styles/workspace/workspace-login-scene.css
?? frontend/src/styles/workspace/workspace-login-shell.css
?? frontend/src/styles/workspace/workspace-primitives-base.css
?? frontend/src/styles/workspace/workspace-primitives-intro.css
?? frontend/src/styles/workspace/workspace-primitives-stock.css
```

说明：

- 分支：`codex/phase4-phase5-architecture`
- 跟踪关系：`origin/codex/phase4-phase5-architecture`，本地 ahead 34。
- 开始前未提交改动：未跟踪 Markdown 文档；本轮未回滚或覆盖既有改动。
- 本轮新增改动：文档索引补齐、历史机器产物 manifest、超长后端测试拆分、前端超长 CSS 拆分、前端 smoke 脚本拆分、报告刷新、删除已跟踪 TypeScript 增量缓存。
- 未执行提交：本轮仅完成整改与验证，未执行 `git add` 或提交。
- 未部署：本轮整改不部署；部署脚本还要求 `CLOUD_HOST` 与 `CLOUD_SSH_KEY`。

## 2. 整改覆盖范围

| 区域 | 本轮覆盖动作 |
|---|---|
| backend | 拆分超长测试文件；未改后端业务代码 |
| frontend | 删除已跟踪的 `frontend/tsconfig.node.tsbuildinfo` 构建缓存；拆分 `workspace-login.css`、`workspace-primitives.css` 与 `frontend/scripts/smoke-responsive.mjs` |
| scripts/deploy | 只确认部署脚本入口和环境要求；未改部署配置 |
| scripts/cleanup | 复用既有 `scripts/clean_local_artifacts.sh` 作为本地缓存治理入口 |
| docs | 补齐新增需求文档、资料整理报告和 artifact manifest 索引，刷新本整改报告 |
| tests | 拆分 runtime worker、low-buy、backtest、paper trading 测试，运行相关 pytest 与前端结构测试 |
| data/generated | 不迁移历史回测和审计产物；仅删除误跟踪的前端构建缓存 |

## 3. 发现的不合规项清单

| 编号 | 分类 | 发现 | 风险 | 本轮处理 |
|---|---|---|---|---|
| G1-1 | 生成产物位置 | `frontend/tsconfig.node.tsbuildinfo` 仍被 Git 跟踪；`.gitignore` 和 `docs/README.md` 均要求 `frontend/*.tsbuildinfo` 不应跟踪 | 构建缓存污染提交，造成无意义 diff | 已删除 |
| G1-2 | 文档索引 | `docs/a-share-strong-stock-trading-requirements-2026-06-02.md` 未进入 `docs/README.md` | 当前需求文档不可从文档入口追踪 | 已补索引 |
| G1-3 | 报告索引 | `docs/reports/zhangmengzhu-16-articles-source-2026-06-02.md` 未进入 `docs/README.md` 和 `docs/reports/README.md` | 人读资料整理与 reports 治理入口脱节 | 已补索引 |
| G1-4 | 报告漂移 | 原整改报告仍写 ahead 33、377 个历史机器产物、已完成状态，与当前工作区不一致 | 后续审计会依据过期结论误判 | 已刷新 |
| G1-5 | 文档索引 | `docs/trading-experience-observation-suite-requirements-2026-06-02.md` 与 `docs/reports/zhangmengzhu-16-articles-analysis-2026-06-02.md` 未进入文档索引 | 新增 PRD 与分析报告不可从文档入口追踪 | 已补索引 |
| G2-1 | 历史机器产物 | `docs/reports/` 顶层仍有 43 个历史 JSON/JSONL/zip 机器产物 | 与新增产物治理规范冲突，但有审计价值 | 已建 manifest，暂缓迁移 |
| G2-2 | 超长文档 | 新增 `a-share...` 791 行、`zhangmengzhu...` 661 行，超过 Markdown 目标上限 500 行 | 长文维护成本较高 | 暂缓拆分，记录职责单一 |
| G2-3 | 超长测试 | `backend/tests/test_phase4_phase5_foundation.py` 1074 行，超过后端测试 800 行必须拆分阈值 | 综合测试继续膨胀，定位成本高 | 已拆到 797 行 |
| G2-4 | 超长测试 | `backend/tests/test_backtest_v2_api_contract.py` 882 行，超过后端测试 800 行必须拆分阈值 | API 契约、worker、persistence 职责混杂 | 已拆到 549 行 |
| G2-5 | 超长测试 | `backend/tests/test_paper_auto_trading.py` 801 行，超过后端测试 800 行必须拆分阈值 | runtime/config helper 与自动交易行为测试混在一起 | 已拆到 743 行 |
| G2-6 | 超长测试 | `backend/tests/test_low_buy_read_paths.py` 860 行，超过后端测试 800 行必须拆分阈值 | materialized read path 与交易日 fallback 混在一起 | 已拆到 716 行 |
| G2-7 | 超长测试 | `backend/tests/test_backtest_v2_engine_contract.py` 849 行，超过后端测试 800 行必须拆分阈值 | engine 集成、data provider、broker、portfolio component 测试混杂 | 已拆到 501 行 |
| G2-8 | 超长 CSS | `frontend/src/styles/workspace/workspace-login.css` 1273 行，超过 CSS 700 行必须拆分阈值 | 登录页 shell、金融场景、卡片、动画/响应式样式混在单文件 | 已拆到 4 行聚合入口 |
| G2-9 | 超长 CSS | `frontend/src/styles/workspace/workspace-primitives.css` 881 行，超过 CSS 700 行必须拆分阈值 | 通用面板、intro、股票卡片样式混在单文件 | 已拆到 3 行聚合入口 |
| G2-10 | 超长前端检查脚本 | `frontend/scripts/smoke-responsive.mjs` 939 行，超过前端脚本 650 行必须拆分阈值 | 响应式冒烟运行流程与大块 mock fixtures 混在单文件 | 已拆到 396 行 |
| G2-11 | 其他超长代码/文档 | 扫描仍发现多处历史超长文件，如 generated API types、历史计划、后端回测脚本 | 大范围拆分可能改变行为或破坏审计材料 | 暂缓，后续按领域分批 |

## 4. 已整改项清单

### G1：低风险清理

- 删除 `frontend/tsconfig.node.tsbuildinfo`。该文件是 TypeScript incremental build cache，已被 `.gitignore` 忽略，不应入库。
- 更新 `docs/README.md`：
  - 将 `docs/a-share-strong-stock-trading-requirements-2026-06-02.md` 加入当前产品与策略参考。
  - 将 `docs/trading-experience-observation-suite-requirements-2026-06-02.md` 加入当前产品与策略参考。
  - 将 `docs/reports/zhangmengzhu-16-articles-analysis-2026-06-02.md` 加入报告与证据索引。
  - 将 `docs/reports/zhangmengzhu-16-articles-source-2026-06-02.md` 加入报告与证据索引。
- 更新 `docs/reports/README.md`：
  - 增加当前人读资料与审查记录清单。
  - 明确 `zhangmengzhu-16-articles-analysis-2026-06-02.md` 是经验分析报告。
  - 明确 `zhangmengzhu-16-articles-source-2026-06-02.md` 是人读资料整理，不是新增机器产物。
- 新增 `docs/reports/artifact-manifest-2026-06-02.md`：
  - 记录 `docs/reports/` 顶层 43 个历史 JSON/JSONL/zip 产物。
  - 按引用计数标记保留、迁移候选和外部归档候选。
  - 明确迁移或删除前仍需重新引用检查，不把 manifest 当作删除许可。
- 刷新本报告，移除旧的 ahead 33、377 个机器产物等过期状态。

### G2：中风险结构整改

- 拆分 `backend/tests/test_phase4_phase5_foundation.py`：
  - 新增 `backend/tests/test_phase4_runtime_worker_tasks.py`，承接 runtime worker task execution 测试。
  - 新增 `backend/tests/test_low_buy_runtime_seams.py`，承接 low-buy runtime cache/composition seam 测试。
  - 原文件从 1074 行降到 797 行，低于后端测试 800 行必须拆分阈值。
- 拆分 `backend/tests/test_backtest_v2_api_contract.py`：
  - 新增 `backend/tests/test_backtest_v2_worker_persistence.py`，承接 backtest worker、job service 和 persistence 测试。
  - 原 API contract 文件从 882 行降到 549 行，回归为路由/API 契约测试职责。
- 拆分 `backend/tests/test_paper_auto_trading.py`：
  - 新增 `backend/tests/test_paper_auto_trading_runtime_config.py`，承接 auto trader runtime config 和 trading-time helper 测试。
  - 原文件从 801 行降到 743 行，低于后端测试 800 行必须拆分阈值。
- 拆分 `backend/tests/test_low_buy_read_paths.py`：
  - 新增 `backend/tests/test_low_buy_trade_date_read_paths.py`，承接 low-buy 交易日解析和日历 fallback 测试。
  - 原文件从 860 行降到 716 行，低于后端测试 800 行必须拆分阈值。
- 拆分 `backend/tests/test_backtest_v2_engine_contract.py`：
  - 新增 `backend/tests/test_backtest_v2_execution_components.py`，承接 data provider、broker、portfolio execution component 测试。
  - 原文件从 849 行降到 501 行，低于后端测试 800 行必须拆分阈值。
- 当前扫描结果：`backend/tests/test_*.py` 已无文件达到 800 行必须拆分阈值。
- 拆分 `frontend/src/styles/workspace/workspace-login.css`：
  - 新增 `workspace-login-shell.css`、`workspace-login-scene.css`、`workspace-login-card.css`、`workspace-login-motion.css`。
  - 原文件保留为 4 行 `@import` 聚合入口，继续由 `workspace.css` 引用。
  - 已用 `diff` 校验：四个子文件串联内容与 HEAD 中原 `workspace-login.css` 完全一致。
- 拆分 `frontend/src/styles/workspace/workspace-primitives.css`：
  - 新增 `workspace-primitives-base.css`、`workspace-primitives-intro.css`、`workspace-primitives-stock.css`。
  - 原文件保留为 3 行 `@import` 聚合入口，继续由 `workspace.css` 引用。
  - 已用 `diff` 校验：三个子文件串联内容与 HEAD 中原 `workspace-primitives.css` 完全一致。
- 当前扫描结果：`frontend/src/styles/workspace/*.css` 已无文件达到 700 行必须拆分阈值。
- 拆分 `frontend/scripts/smoke-responsive.mjs`：
  - 新增 `frontend/scripts/smoke-responsive-fixtures.mjs`，承接响应式冒烟脚本的 mock payload fixtures。
  - 原文件从 939 行降到 396 行，只保留浏览器运行流程、API route mock 入口和结果写入逻辑。
  - 新 fixtures 文件 596 行，低于前端脚本 650 行必须拆分阈值。
  - 当前扫描结果：`frontend/scripts/*.mjs` 已无文件达到 650 行必须拆分阈值。
- 对超长 Markdown 文档先做职责判断：
  - `docs/a-share-strong-stock-trading-requirements-2026-06-02.md` 是单一需求文档，当前不拆，避免打断后续评审上下文。
  - `docs/reports/zhangmengzhu-16-articles-source-2026-06-02.md` 是 16 篇资料原文整理，当前不拆，避免破坏原文证据完整性。

### G3：高风险守卫整改

- 本轮未修改 feature flag、API 契约、生产排序、后台任务或部署配置。
- 原因：当前低风险问题集中在生成缓存和文档治理；高风险守卫改动需要单独需求、测试和部署前验收。

## 5. 已删除文件清单

| 路径 | 删除理由 | 引用检查证据 | 风险判断 |
|---|---|---|---|
| `frontend/tsconfig.node.tsbuildinfo` | TypeScript incremental build cache；`.gitignore` 已忽略 `frontend/*.tsbuildinfo`；`docs/README.md` 明确该类文件不得跟踪 | 删除前执行 `rg --fixed-strings "tsconfig.node.tsbuildinfo" .`，仅命中历史清理报告和本整改报告，无代码、脚本、部署、测试引用 | 低风险；前端构建可重新生成本地缓存，不影响源码、API 契约或部署 |

未删除：

- `frontend/tsconfig.app.tsbuildinfo`：未被 Git 跟踪，属于本地缓存。
- `docs/reports/` 历史机器产物：顶层 43 个，已建立 `docs/reports/artifact-manifest-2026-06-02.md`；涉及审计和回测证据，需引用迁移后再处理。
- 大型历史计划/报告：多数是审计材料，直接拆分会破坏原始证据。

## 6. 已移动/重命名文件清单

本轮没有移动或重命名文件。

原因：新增文档命名符合 kebab-case 和 `YYYY-MM-DD` 日期规则；现有历史机器产物和长文档迁移需要先建立引用清单。

## 7. 已拆分超长文件清单

| 原文件 | 新文件 | 整改内容 | 结果 |
|---|---|---|---|
| `backend/tests/test_phase4_phase5_foundation.py` | `backend/tests/test_phase4_runtime_worker_tasks.py` | 拆出 runtime worker `_execute_task` 任务执行守卫测试 | 原文件减少到 797 行；新文件 280 行 |
| `backend/tests/test_phase4_phase5_foundation.py` | `backend/tests/test_low_buy_runtime_seams.py` | 拆出 low-buy runtime cache 和 composition seam 测试 | 新文件 24 行；职责独立 |
| `backend/tests/test_backtest_v2_api_contract.py` | `backend/tests/test_backtest_v2_worker_persistence.py` | 拆出 backtest worker、job service 和 persistence 测试 | 原文件减少到 549 行；新文件 365 行 |
| `backend/tests/test_paper_auto_trading.py` | `backend/tests/test_paper_auto_trading_runtime_config.py` | 拆出 auto trader runtime config 和 trading-time helper 测试 | 原文件减少到 743 行；新文件 68 行 |
| `backend/tests/test_low_buy_read_paths.py` | `backend/tests/test_low_buy_trade_date_read_paths.py` | 拆出 low-buy 交易日解析和日历 fallback 测试 | 原文件减少到 716 行；新文件 155 行 |
| `backend/tests/test_backtest_v2_engine_contract.py` | `backend/tests/test_backtest_v2_execution_components.py` | 拆出 data provider、broker、portfolio execution component 测试 | 原文件减少到 501 行；新文件 391 行 |
| `frontend/src/styles/workspace/workspace-login.css` | `workspace-login-shell.css`、`workspace-login-scene.css`、`workspace-login-card.css`、`workspace-login-motion.css` | 拆出登录页 shell、金融场景、卡片与动画/响应式样式 | 原文件减少到 4 行聚合入口；新文件分别为 101、486、365、321 行 |
| `frontend/src/styles/workspace/workspace-primitives.css` | `workspace-primitives-base.css`、`workspace-primitives-intro.css`、`workspace-primitives-stock.css` | 拆出通用基础、intro/info、股票卡片/mini-kline 样式 | 原文件减少到 3 行聚合入口；新文件分别为 353、287、241 行 |
| `frontend/scripts/smoke-responsive.mjs` | `frontend/scripts/smoke-responsive-fixtures.mjs` | 拆出响应式冒烟脚本 mock payload fixtures | 原文件减少到 396 行；新文件 596 行 |

暂缓说明：

- `docs/a-share-strong-stock-trading-requirements-2026-06-02.md`：791 行，超过 Markdown 目标上限但未超过必须拆分阈值 1200 行；职责单一，作为需求评审材料保留。
- `docs/reports/zhangmengzhu-16-articles-source-2026-06-02.md`：661 行，超过 Markdown 目标上限但未超过必须拆分阈值 1200 行；作为原文资料证据保留。
- `frontend/src/generated/api-types.ts`：generated types，属于规范豁免文件，不按手写代码阈值处理。

## 8. 暂缓整改项和原因

| 暂缓项 | 原因 | 后续建议 |
|---|---|---|
| `docs/reports/` 43 个历史机器产物迁移 | 涉及回测、云性能、审计证据，不能直接删除或移动；本轮已先建 manifest | 按 `docs/reports/artifact-manifest-2026-06-02.md` 逐项复查后迁入 `backend/data/reports/` 或外部 artifact |
| 其他超长后端脚本拆分 | 后端测试必须拆分阈值已清零；后端脚本仍存在超长历史文件，继续拆会触及回测脚本和策略报告生成口径 | 按 backend scripts 单独批次拆，避免混入测试拆分 |
| 根目录历史文档迁移 | `docs/README.md` 已标记部分为历史决策记录，仍可能被报告引用 | 先做 `rg --fixed-strings <basename> .` 引用矩阵，再迁入 `docs/archive/` |
| 新增长文 Markdown 拆分 | 当前是需求与资料证据，拆分会影响评审上下文完整性 | 评审后可按章节拆为需求正文和 source appendix |
| 其他页面/浏览器深测 | 本轮已完成 responsive smoke 覆盖；未逐页人工截图审查所有交互分支 | 后续 UI 交互改动时再按页面补充截图和控制台检查 |

## 9. 风险判断

- 策略逻辑：未修改选股规则、策略阈值、信号计算或策略分层。
- 回测口径：未修改样本范围、费用、滑点、成交假设、回测脚本或报告计算。
- 生产排序：未修改 production scoring、priority board、生产候选准入或排序逻辑。
- API 契约：未修改路由、DTO、OpenAPI 或 generated types。
- 部署配置：未修改部署配置，未部署。

## 10. 验证命令和结果

本轮已执行的取证命令：

```bash
git status --short --branch
git ls-files | rg '(^|/)(__pycache__/|.*\.pyc$|frontend/.*\.tsbuildinfo$|frontend/dist/|rust/.*/target/|\.log$|\.zip$|\.parquet$)'
find docs/reports -maxdepth 1 -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.zip' -o -name '*.parquet' \) | wc -l
rg --fixed-strings "tsconfig.node.tsbuildinfo" .
rg -n "a-share-strong-stock-trading-requirements|trading-experience-observation-suite-requirements|zhangmengzhu-16-articles-analysis|zhangmengzhu-16-articles-source" docs README.md AGENTS.md
git check-ignore -v docs/a-share-strong-stock-trading-requirements-2026-06-02.md docs/trading-experience-observation-suite-requirements-2026-06-02.md docs/reports/zhangmengzhu-16-articles-analysis-2026-06-02.md docs/reports/zhangmengzhu-16-articles-source-2026-06-02.md
```

结果摘要：

- `frontend/tsconfig.node.tsbuildinfo` 被 Git 跟踪，已删除。
- `docs/reports/` 顶层历史机器产物当前为 43 个，暂缓迁移。
- 新增 Markdown 未被忽略，适合提交为人读资料。
- 删除引用检查未发现代码、脚本、部署或测试依赖。

已执行验证：

```bash
git diff --check
test ! -e frontend/tsconfig.node.tsbuildinfo
bash -lc 'diff -q <(git show HEAD:frontend/src/styles/workspace/workspace-login.css) <(cat frontend/src/styles/workspace/workspace-login-shell.css frontend/src/styles/workspace/workspace-login-scene.css frontend/src/styles/workspace/workspace-login-card.css frontend/src/styles/workspace/workspace-login-motion.css)'
bash -lc 'diff -q <(git show HEAD:frontend/src/styles/workspace/workspace-primitives.css) <(cat frontend/src/styles/workspace/workspace-primitives-base.css frontend/src/styles/workspace/workspace-primitives-intro.css frontend/src/styles/workspace/workspace-primitives-stock.css)'
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_cloud_deploy_scripts.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_phase4_phase5_foundation.py backend/tests/test_phase4_runtime_worker_tasks.py backend/tests/test_low_buy_runtime_seams.py backend/tests/test_runtime_task_queue.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_backtest_v2_api_contract.py backend/tests/test_backtest_v2_worker_persistence.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_paper_auto_trading.py backend/tests/test_paper_auto_trading_runtime_config.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_trade_date_read_paths.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_backtest_v2_engine_contract.py backend/tests/test_backtest_v2_execution_components.py -q
cd frontend && npm run lint
cd frontend && npm run build
cd frontend && npm test -- src/styles/workspace/workspaceStructure.test.ts
node --check frontend/scripts/smoke-responsive.mjs
node --check frontend/scripts/smoke-responsive-fixtures.mjs
cd frontend && npm run preview -- --host 127.0.0.1
cd frontend && SMOKE_MOCK_AUTH=1 npm run smoke:responsive
```

结果摘要：

- `git diff --check`：通过。
- `test ! -e frontend/tsconfig.node.tsbuildinfo`：通过，工作区文件已删除。
- `git diff --name-status -- frontend/tsconfig.node.tsbuildinfo`：显示 `D frontend/tsconfig.node.tsbuildinfo`，删除等待提交。
- CSS 等价校验：通过；拆分后的 login/primitives 子文件串联内容分别与 HEAD 中原 CSS 完全一致。
- 后端脚本守卫测试：`10 passed, 1 warning in 1.53s`；warning 为本地 LibreSSL/urllib3 环境提示。
- 后端拆分相关测试：`39 passed, 1 warning in 3.15s`；warning 为本地 LibreSSL/urllib3 环境提示。
- Backtest API/worker 拆分测试：`19 passed in 2.79s`。
- Paper auto trading 拆分测试：`29 passed, 1 warning in 1.42s`；warning 为本地 LibreSSL/urllib3 环境提示。
- Low-buy read path 拆分测试：`19 passed, 1 warning in 1.57s`；warning 为本地 LibreSSL/urllib3 环境提示。
- Backtest engine/component 拆分测试：`19 passed, 1 warning in 0.97s`；warning 为本地 LibreSSL/urllib3 环境提示。
- 后端测试行数扫描：`backend/tests/test_*.py` 已无文件达到 800 行。
- 前端 lint：通过，包含 `lint:state`、`check:refactor`、`check:state-separation`、`check:css`。
- 前端 build：通过，执行 `lint && tsc -b && vite build`，构建完成。
- 前端结构测试：`src/styles/workspace/workspaceStructure.test.ts` 通过，`1 passed`。
- 前端 CSS 行数扫描：`frontend/src/styles/workspace/*.css` 已无文件达到 700 行。
- 前端 smoke 脚本语法检查：`node --check frontend/scripts/smoke-responsive.mjs` 与 `node --check frontend/scripts/smoke-responsive-fixtures.mjs` 均通过。
- 前端 smoke 脚本行数扫描：`frontend/scripts/*.mjs` 已无文件达到 650 行。
- 本地 preview：通过，`cd frontend && npm run preview -- --host 127.0.0.1` 启动 `http://127.0.0.1:4173/`。
- Responsive smoke：通过，`cd frontend && SMOKE_MOCK_AUTH=1 npm run smoke:responsive` 产出 `frontend/dist/responsive-smoke-report.json`；30 个路径/视口组合全部通过，覆盖 mobile 375px、tablet 768px、desktop 1440px，`failures=0`、`maxOverflow=0`。
- `frontend/dist/responsive-smoke-report.json` 位于被 `.gitignore` 忽略的 `frontend/dist/`，不纳入提交。

说明：本轮未改路由、API 或契约，因此不需要 OpenAPI/generated types 更新。CSS 拆分属于页面样式结构整改，已完成 lint/build/结构测试、内容等价校验和 375px responsive smoke 验证。

## 11. 后续建议

1. 按 `docs/reports/artifact-manifest-2026-06-02.md` 迁移候选清单逐项复核，不直接删除。
2. 为超长后端脚本建立单独拆分批次，优先处理不改变策略口径的 report writer / runner 分离。
3. 评审 `a-share-strong-stock-trading-requirements` 后，将原文资料作为 appendix 或 archive source 保存，需求正文保留在当前索引。
4. 后续若继续拆后端回测脚本，应先锁定 report writer / runner / domain helper 边界并保留回测口径守卫测试。
5. 当前仍未提交；提交前建议再跑一次 `git status --short --branch` 与受影响测试集合。
