# Project Engineering Compliance Remaining Remediation Plan - 2026-06-02

状态：待执行计划
最后核验日期：2026-06-02
权威前置报告：`docs/reports/project-engineering-compliance-remediation-2026-06-02.md`

## 1. 目标

把上一轮工程规范整改中明确暂缓的项目继续收口，分 6 批完成历史产物治理、超长测试拆分、响应式 smoke 脚本拆分、根目录历史文档归档、Go/Rust/native 实验链路审计、`ARCHITECTURE.md` 策略事实源同步。

本计划只处理工程规范和文档/测试/产物治理，不新增业务功能，不改策略计算，不改回测口径，不改生产排序，不部署上线。

## 2. 当前未完成项

| 编号 | 未完成项 | 当前证据 | 风险 |
|---|---|---|---|
| R1 | `docs/reports/` 存量机器产物治理 | 历史 `json/jsonl/zip/parquet` 类产物约 377 个 | 混入手写报告区，后续容易继续提交大型机器产物 |
| R2 | 后端超长测试继续拆分 | 多个测试文件仍超过 800 行 | 综合测试继续膨胀，失败定位成本高 |
| R3 | `frontend/scripts/smoke-responsive.mjs` 拆分 | 当前约 939 行 | 响应式 smoke 难维护，mock 数据和断言耦合 |
| R4 | 根目录历史文档归档 | 多个计划/交付文档仍在根目录且存在引用 | 根目录入口不清晰，历史文档容易被误当当前事实源 |
| R5 | Go/Rust/native 实验链路审计 | 可选增强链路仍保留源码、文档和入口 | 主路径与实验链路边界不够清晰 |
| R6 | `ARCHITECTURE.md` 策略矩阵漂移 | 需要与 `strategy_policy` 唯一事实源同步 | 文档误导生产/研究/观察分层 |

## 3. 全局硬边界

1. 不改生产策略计算、策略分层事实源、回测收益口径、生产排序逻辑。
2. 不删除数据库迁移、历史回测报告、生产部署配置、契约文件、关键数据产物。
3. 删除前必须做引用检查：文件名、basename、导入路径、脚本调用、路由入口、部署配置、测试引用、文档链接。
4. 每批独立验证，独立提交；不得把历史迁移、测试拆分和策略文档同步混在一个提交。
5. 不部署上线。

## 4. 执行顺序

建议顺序：

1. G4-2 后端超长测试拆分。
2. G4-3 响应式 smoke 脚本拆分。
3. G4-6 `ARCHITECTURE.md` 策略矩阵同步。
4. G4-1 历史机器产物治理。
5. G4-4 根目录历史文档归档。
6. G4-5 Go/Rust/native 实验链路审计。

理由：先处理测试和脚本可维护性，降低后续迁移风险；策略文档同步只改事实说明；历史产物和根目录文档引用面大，放在后面；实验链路涉及产品/部署边界，最后做审计决策。

## 5. G4-1 历史机器产物治理

### 范围

- `docs/reports/**/*.json`
- `docs/reports/**/*.jsonl`
- `docs/reports/**/*.zip`
- `docs/reports/**/*.parquet`

### 步骤

1. 新增 `docs/reports/artifact-manifest-2026-06-02.md`。
2. 列出所有候选产物：

```bash
git ls-files 'docs/reports/*' | rg '\.(json|jsonl|zip|parquet)$'
```

3. 对每个候选执行引用检查：

```bash
rg --fixed-strings "<basename>" .
```

4. 按结果分为三类：
   - `keep_in_place`：有活跃引用，迁移会破坏现有报告或审计链。
   - `move_to_artifacts`：无活跃代码/部署引用，但有审计价值，迁入 `backend/data/reports/`、`backend/data/analytics/reports/` 或外部 artifact。
   - `delete_candidate`：无引用、无审计价值、重复或临时产物。

5. 对 `move_to_artifacts` 先改引用，再移动文件。
6. 对 `delete_candidate` 再次运行引用检查后删除。
7. 更新 `docs/reports/README.md`，记录剩余历史产物和迁移策略。

### 验收

```bash
git diff --check
rg --fixed-strings "<deleted-basename>" .
```

通过条件：

- 每个仍留在 `docs/reports/` 的机器产物都在 manifest 中有保留理由。
- 每个删除项都有引用检查证据。
- 不删除关键回测、审计、部署或契约产物。

### 提交建议

`docs(artifacts): inventory historical report artifacts`

如有真实移动/删除，单独提交：

`chore(artifacts): move obsolete machine reports out of docs`

## 6. G4-2 后端超长测试拆分

### 范围

- `backend/tests/test_phase4_phase5_foundation.py`
- `backend/tests/test_backtest_v2_api_contract.py`
- `backend/tests/test_low_buy_read_paths.py`
- `backend/tests/test_backtest_v2_engine_contract.py`

### 拆分目标

| 原文件 | 建议新文件 |
|---|---|
| `test_phase4_phase5_foundation.py` | `test_runtime_worker_tasks.py`、`test_ml_signal_guards.py`、`test_decision_context_tasks.py`、`test_quant_parameters.py` |
| `test_backtest_v2_api_contract.py` | `test_backtest_v2_routes.py`、`test_backtest_v2_contract_errors.py`、`test_backtest_v2_data_quality.py` |
| `test_low_buy_read_paths.py` | `test_low_buy_priority_read_paths.py`、`test_low_buy_snapshot_read_paths.py`、`test_low_buy_data_quality_paths.py` |
| `test_backtest_v2_engine_contract.py` | `test_backtest_v2_engine_execution.py`、`test_backtest_v2_engine_risk_rules.py`、`test_backtest_v2_engine_reporting.py` |

### 步骤

1. 先跑原始相关测试，确认拆分前基线：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_phase4_phase5_foundation.py \
  backend/tests/test_backtest_v2_api_contract.py \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_backtest_v2_engine_contract.py -q
```

2. 按主题移动测试函数，不改断言语义。
3. 共享 fixture 只在确有重复时抽到 `backend/tests/helpers/` 或同目录 helper。
4. 拆分后确认旧文件不再承担无关领域测试。
5. 保持测试文件名 `test_<domain>_<behavior>.py`。

### 验收

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
git diff --check
find backend/tests -name 'test_*.py' -print0 | xargs -0 wc -l | sort -nr | head -20
```

通过条件：

- 被拆文件低于 800 行；目标尽量低于 500 行。
- 全量后端测试通过。
- 不改业务逻辑文件，除非是测试 helper 必需。

### 提交建议

`test(backend): split oversized compliance guard suites`

## 7. G4-3 响应式 smoke 脚本拆分

### 范围

- `frontend/scripts/smoke-responsive.mjs`

### 建议结构

```text
frontend/scripts/smoke-responsive.mjs
frontend/scripts/responsive-smoke/mockData.mjs
frontend/scripts/responsive-smoke/routes.mjs
frontend/scripts/responsive-smoke/browserRunner.mjs
frontend/scripts/responsive-smoke/assertions.mjs
frontend/scripts/responsive-smoke/reportWriter.mjs
```

### 步骤

1. 保留 `smoke-responsive.mjs` 作为 CLI 入口。
2. 将 mock API 响应迁入 `mockData.mjs`。
3. 将 path 和 viewport 配置迁入 `routes.mjs`。
4. 将 Playwright 启动、route mocking、page visiting 迁入 `browserRunner.mjs`。
5. 将 overflow、login gate、main region、visible text 等检查迁入 `assertions.mjs`。
6. 将 JSON report 生成迁入 `reportWriter.mjs`。
7. 保持环境变量兼容：
   - `FRONTEND_SMOKE_URL`
   - `SMOKE_REQUIRE_AUTH`
   - `SMOKE_MOCK_AUTH`

### 验收

```bash
cd frontend
npm run build:web
npm run smoke:responsive
node - <<'NODE'
const report=require('./dist/responsive-smoke-report.json');
const mobile=report.results.filter((item)=>item.viewport==='mobile');
console.log({
  ok: report.ok,
  failed: report.results.filter((item)=>!item.ok).length,
  maxMobileOverflowX: Math.max(...mobile.map((item)=>item.overflow_x || 0)),
});
NODE
```

通过条件：

- `npm run smoke:responsive` 输出路径不变。
- 375/768/1440 均通过。
- 375px `maxMobileOverflowX=0`。
- CLI 行为和报告 schema 不变。

### 提交建议

`refactor(frontend-smoke): split responsive smoke runner`

## 8. G4-4 根目录历史文档归档

### 候选文件

- `FINAL_DELIVERY.md`
- `IMPLEMENTATION_PLAN.md`
- `OPTIMIZATION_PLAN.md`
- `APP_API_SPEC.md`
- `ARCHITECTURE.md`
- `PROJECT_PLAN.md`
- `PRODUCT_STAGE_ACCEPTANCE.md`

### 步骤

1. 对每个候选跑引用检查：

```bash
for f in FINAL_DELIVERY.md IMPLEMENTATION_PLAN.md OPTIMIZATION_PLAN.md APP_API_SPEC.md ARCHITECTURE.md PROJECT_PLAN.md PRODUCT_STAGE_ACCEPTANCE.md; do
  echo "--- $f"
  rg --fixed-strings "$f" .
done
```

2. 新增归档目录：

```text
docs/archive/root-docs-2026-06-02/
```

3. 分类：
   - 当前事实源：保留根目录。
   - 当前入口但位置不合规：先更新入口，再迁移。
   - 纯历史材料：迁入归档。

4. 修改所有引用链接。
5. 更新 `docs/README.md`，标注当前文档与历史文档。

### 验收

```bash
git diff --check
rg --fixed-strings "FINAL_DELIVERY.md" .
rg --fixed-strings "IMPLEMENTATION_PLAN.md" .
rg --fixed-strings "OPTIMIZATION_PLAN.md" .
rg --fixed-strings "APP_API_SPEC.md" .
rg --fixed-strings "ARCHITECTURE.md" .
rg --fixed-strings "PROJECT_PLAN.md" .
rg --fixed-strings "PRODUCT_STAGE_ACCEPTANCE.md" .
```

通过条件：

- 根目录只保留长期入口和仍被确认的事实源。
- 无悬空链接。
- 迁移清单写入本批报告或 `docs/README.md`。

### 提交建议

`docs: archive legacy root planning documents`

## 9. G4-5 Go/Rust/native 实验链路审计

### 范围

- `go-services/`
- `rust/`
- `frontend/android/`
- `frontend/ios/`
- `frontend/NATIVE_APP_SETUP.md`
- 相关 README、runbook、deploy 配置和 CI 引用

### 步骤

1. 列出入口：

```bash
rg -n "go-services|tquant-rs|NATIVE_APP_SETUP|android|ios|Capacitor|cargo|go build|go run" .
```

2. 标记每个入口状态：
   - `active optional`
   - `disabled by default`
   - `archived`
   - `unknown`

3. 检查是否默认进入 Web 主路径、生产排序或策略事实源。
4. 对保留链路补充说明：
   - 不作为策略事实源。
   - 不作为生产排序事实源。
   - 默认不影响 Web 主路径。
5. 对无入口链路，只归档文档，不删除源码。

### 验收

```bash
git diff --check
cd frontend && npm run build:web
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

通过条件：

- Web 主路径构建不受 Go/Rust/native 链路影响。
- 文档明确 optional/disabled 状态。
- 未删除可追溯源码或生产配置。

### 提交建议

`docs(platform): clarify optional native and go rust lanes`

## 10. G4-6 ARCHITECTURE 策略矩阵同步

### 范围

- `ARCHITECTURE.md`
- 可选：新增策略矩阵检查脚本或测试

### 步骤

1. 读取事实源：

```bash
sed -n '1,240p' backend/app/services/low_buy/strategy_policy.py
```

2. 从 `strategy_policy` 提取策略层级：
   - CORE
   - AUX
   - RESEARCH
   - FACTOR / optional research

3. 更新 `ARCHITECTURE.md`：
   - 生产榜只以 `participates_in_priority_board` 为准。
   - 研究策略不得获得 `production_score`。
   - N 字策略保持 research-only / observe-only。
   - 观察信号不是买入建议。

4. 避免写死易漂移数量；如必须写策略表，注明来源为 `strategy_policy`。
5. 可选新增脚本检查文档中列出的 strategy key 与 `strategy_policy` 一致。

### 验收

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_low_buy_production_scoring.py \
  backend/tests/test_low_buy_strategy_replacement.py -q
git diff --check
rg -n "n_pattern_long_wash|n_pattern_short_wash|production_score|priority board|观察|买入" ARCHITECTURE.md
```

通过条件：

- `ARCHITECTURE.md` 不再使用旧策略数量或旧生产层口径。
- N 字策略不出现生产推荐或买入建议口径。
- 策略守卫测试通过。

### 提交建议

`docs(architecture): align strategy matrix with policy source`

## 11. 总体验收

全部 6 批完成后运行：

```bash
git diff --check
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run api:check && npm run lint && npm test -- --run && npm run build:web && npm run analyze
cd frontend && npm run smoke:responsive
rg "\buseState\b|\buseReducer\b" frontend/src
rg "<Table" frontend/src
```

通过条件：

- 后端全量测试通过。
- 前端 api check、lint、test、build、analyze 通过。
- 375px 响应式 smoke 无横向溢出。
- `useState/useReducer` 无命中。
- raw `<Table>` 只在允许入口内。
- 未改策略逻辑、回测口径、生产排序。
- 未部署上线。

## 12. 最终交付

完成后新增报告：

```text
docs/reports/project-engineering-compliance-remaining-remediation-2026-06-02.md
```

报告必须包含：

1. 6 批实际执行结果。
2. 删除、移动、归档清单和引用检查证据。
3. 超长文件拆分前后行数。
4. 历史机器产物 manifest 摘要。
5. Go/Rust/native 链路状态。
6. `ARCHITECTURE.md` 与 `strategy_policy` 对齐证据。
7. 全量验证输出摘要。
8. 是否影响策略逻辑、回测口径、生产排序。
9. 是否部署，必须写“未部署”。
