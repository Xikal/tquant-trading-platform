# Project Conventions Remediation

状态：已完成首轮整改
适用范围：工程结构、文档结构、命名、文件规模、生成产物、生产/研究边界
最后核验日期：2026-05-31

## 结论

已补齐缺失的工程规范文档，并把它纳入 AGENTS 与 docs 索引。随后将一批无活引用历史报告迁入 `docs/archive/reports/`，并将一批无活引用历史计划迁入 `docs/archive/plans/`；同时在 `README.md` 与 `docs/README.md` 中明确当前入口和 archive 边界。其余发现项以清单形式保留，不做高风险搬迁或业务重写。

## 数据范围

- 仓库根目录顶层文件
- `docs/README.md`
- `docs/reports/`
- `.gitignore`
- 前端源码的结构性扫描
- 后端脚本、后端服务、前端源码、契约生成文件的路径/体量扫描
- 生产/研究边界关键词扫描：`participates_in_priority_board`、`research_only`、`near_entry`、`production_score`

## 不可信或限制条件

- 仅覆盖当前工作区可见文件和可搜索到的文本引用。
- 未对业务代码、运行时效果或部署环境做变更验证。
- 结构扫描中的 `slice(...)` 结果仅作为代码形态记录，不代表一定是缺陷。

## 已整改文件

- `/Users/j/Documents/gupiao/AGENTS.md`
- `/Users/j/Documents/gupiao/docs/engineering-conventions.md`
- `/Users/j/Documents/gupiao/README.md`
- `/Users/j/Documents/gupiao/docs/README.md`
- `/Users/j/Documents/gupiao/.gitignore`
- `/Users/j/Documents/gupiao/docs/维斯量化平台-完整提升整改方案-2026-05-30.md`
- `/Users/j/Documents/gupiao/docs/reports/project-conventions-remediation-2026-05-31.md`
- `/Users/j/Documents/gupiao/docs/reports/repository-cleanup-2026-05-27.md`
- `/Users/j/Documents/gupiao/docs/archive/plans/backend-final-refactor-master-plan-2026-05-21.md`
- `/Users/j/Documents/gupiao/docs/archive/plans/backend-final-refactor-optimization-plan-2026-05-21.md`
- `/Users/j/Documents/gupiao/docs/archive/plans/backend-final-refactor-pragmatic-plan-2026-05-21.md`
- `/Users/j/Documents/gupiao/docs/archive/plans/frontend-bff-microservices-evolution-plan-2026-05-19.md`
- `/Users/j/Documents/gupiao/docs/archive/plans/microservices-independent-deployment-design-2026-05-20.md`
- `/Users/j/Documents/gupiao/docs/archive/plans/remaining-architecture-debt-executable-plan-2026-05-24.md`
- `/Users/j/Documents/gupiao/docs/archive/plans/策略体系重组方案.md`
- `/Users/j/Documents/gupiao/docs/archive/plans/系统级全方位提升方案-2026-05-30.md`
- `/Users/j/Documents/gupiao/docs/archive/reports/全方位评估报告-2026-05-01.md`

## P0

1. `docs/engineering-conventions.md` 在工作区缺失，但 `AGENTS.md` 已要求遵循它。已恢复到工作区。
2. `AGENTS.md` 未显式链接默认工程规范。已补。
3. `docs/README.md` 未把工程规范列入当前文档入口。已补。
4. `README.md` 仍把 `FINAL_DELIVERY.md`、`PROJECT_PLAN.md`、`OPTIMIZATION_PLAN.md` 作为主入口展示，容易把历史计划当作当前执行依据。已改为指向 `docs/README.md`、`docs/engineering-conventions.md` 和稳定运行文档。

## P1

1. 根目录仍保留多份历史计划/交付类文档，如 `IMPLEMENTATION_PLAN.md`、`OPTIMIZATION_PLAN.md`、`FINAL_DELIVERY.md`、`APP_API_SPEC.md`、`ARCHITECTURE.md`、`PROJECT_PLAN.md`、`PRODUCT_STAGE_ACCEPTANCE.md`。这些文件仍有入口或历史审查引用，未在本轮移动，以免破坏现有引用链。已归档 `全方位评估报告-2026-05-01.md`、`策略体系重组方案.md`、`系统级全方位提升方案-2026-05-30.md`。
2. `docs/reports/` 仍包含大量机器可读产物和大文件，例如 `front-row-weighted-production-scoring-backtest-2026-05-29.json`、`strategy-24m-backtest-2026-05-30.json`、`strategy-24m-optimization-report-2026-05-28.json`、`front-row-weighted-production-scoring-review-package-2026-05-30.zip`、`main-force-model-dataset-smoke.jsonl`。其中多个文件在计划、脚本或审查报告中存在引用，暂不移动。
3. 前端存在大量 `slice(...)` 截断用法，主要用于展示层的窗口裁剪或列表限长；本轮未改动业务 UI 逻辑，只做结构扫描记录。
4. 根目录仍有少量隐式配置文件（`.vercelignore`、`Dockerfile.prebuilt`、`pytest.ini`）没有文本引用，但属于工具/构建默认入口，未纳入本轮文档归档范围。
5. `docs/reports/` 下已有批量 walk-forward `windows/` 明细，按规范属于生成产物。现存文件因引用链和历史报告完整性暂保留，已通过 `.gitignore` 防止后续新增同类目录继续入库。
6. 多个手写文件超过 `docs/engineering-conventions.md` 的评审或必须拆分阈值。最高风险包括 `frontend/src/styles/workspace/workspace.css`(1261 行)、`backend/scripts/low_buy_market_backtest_reporting.py`(1180 行)、`backend/scripts/front_row_weighted_production_scoring_backtest.py`(1113 行)、`backend/tests/test_phase4_phase5_foundation.py`(1109 行)、`frontend/src/features/monitor/MonitorPage.tsx`(1094 行)。本轮不做行为拆分，只标注为“只小修，不扩写”。
7. 前端 raw `<Table>` 扫描只命中 `frontend/src/ui/table/DataTable.tsx`，属于封装组件；未发现新增业务页面直接使用 AntD raw Table。`slice(...)` 命中较多，其中 `MonitorPage.tsx` 仍有 `priorityCards.slice(0, 3)`、`watchCards...slice(0, 3)` 等首屏裁剪，需要在后续 UI 性能专项里判断是否业务截断。

## P2

1. 仍有历史文档散落在根目录，建议后续分批归档到 `docs/archive/` 或更清晰的历史索引。
2. `docs/reports/` 中的机器可读产物建议继续向 `backend/data/analytics/reports/` 和外部 artifacts 收敛。
3. `main-force-model-dataset-smoke.jsonl` 已通过 `.gitignore` 增加后缀屏蔽，防止新 `.jsonl` 继续误入报告目录。
4. `docs/contracts/openapi.json` 与 `frontend/src/generated/api-types.ts` 属于允许豁免的生成文件；当前未改 API，不重跑生成。后续凡涉及 schema/route 变更必须跑 `cd frontend && npm run api:check`。

## 超大文件清单

| 文件 | 规模观察 | 处理建议 |
|---|---:|---|
| `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` | 约 13 MB / 369k 行 | 必须拆分候选说明和机器数据，保留引用但不再膨胀 |
| `docs/reports/strategy-24m-backtest-2026-05-30.json` | 约 1.4 MB / 38k 行 | 只小修，继续作为机器产物 |
| `docs/reports/strategy-24m-optimization-report-2026-05-28.json` | 约 1.3 MB / 36k 行 | 只小修，后续优先归档到数据目录 |
| `docs/reports/strategy-24m-front-row-filter-backtest-2026-05-29.json` | 约 0.9 MB | 建议拆分摘要与机器数据 |
| `docs/reports/market-state-guard-walk-forward-2026-05-28/**/windows/*.json` | 多个约 0.62 MB 文件 | 已入库历史明细仅保留，不再新增；后续批量迁入 artifact |
| `docs/contracts/openapi.json` | 约 38k 行 | 允许豁免，但需保持与生成源同步 |
| `frontend/src/generated/api-types.ts` | 约 26k 行 | 允许豁免，避免人工编辑 |
| `frontend/src/styles/workspace/workspace.css` | 1261 行 | 必须拆分阈值；只小修，不再追加职责 |
| `backend/scripts/low_buy_market_backtest_reporting.py` | 1180 行 | 必须拆分阈值；新增报告逻辑应拆到 helper |
| `frontend/src/features/monitor/MonitorPage.tsx` | 1094 行 | 必须拆分阈值；后续 UI 性能/可维护性专项处理 |

## 生成产物清理建议

- 保留：当前仍被计划、脚本或报告引用的 JSON/ZIP 证据文件。
- 已移动：无代码、CI、测试或页面活引用的历史报告批次已迁入 `docs/archive/reports/`，无代码、CI、测试或页面活引用的历史计划批次已迁入 `docs/archive/plans/`。
- 仅加 ignore：`docs/reports/*.jsonl` 与 `docs/reports/**/windows/`，避免新生成物继续进入报告目录。
- 后续可迁移：未被引用、纯机器产出的新 JSON/Parquet/ZIP，优先放 `backend/data/analytics/reports/` 或 `artifacts/`。

## 生产/研究边界检查结论

- 本轮未改业务路径，因此未改变生产/研究门控。
- 结构扫描没有显示新增生产入口或后台 loop。
- `production_scoring.py` 使用 `participates_in_priority_board`，`near_entry` 在 production scoring 路径返回 `production_score=None`；`track_record/signal_ledger.py` 也以 `participates_in_priority_board` 控制生产分记录。
- `strategy_24m_duckdb_report.md` 已无裸“总收益”表头，使用“每日信号等权复利收益”，并列出真实组合 max5/max10、walk-forward、OOS、费用/滑点/T+1/涨跌停/停牌等假设。
- 研究型、回测型和报告型产物仍集中在报告与数据目录，边界总体清楚，但历史堆积仍需后续清理。

## 是否可作为生产依据

- 否。本文只记录工程结构整改结果与后续清理建议，不作为生产策略或收益判断依据。

## 文档结构整改结论

- `AGENTS.md`、`README.md`、`docs/README.md`、`docs/engineering-conventions.md` 已形成闭环。
- 当前 `docs/README.md` 已可作为工程文档入口。
- 后续新增一次性计划或审查，应优先落在 `docs/superpowers/plans/` 或 `docs/reports/`，不要再放根目录。

## 验证

- `sed -n` 完整阅读了 `AGENTS.md`、`docs/engineering-conventions.md`、`docs/README.md`。
- `rg --fixed-strings <basename> .` 检查了本轮移动的历史计划/报告引用，确认未命中代码、CI、测试或页面入口。
- `git ls-files` 口径扫描了入库大文件；本地 `.venv`、`node_modules`、`target`、`.mysql-local`、本地数据库文件只作为忽略目录风险，不纳入入库大文件清单。
- `rg "<Table\\b|Table\\s*from|\\.slice\\(" frontend/src` 扫描前端 raw Table 与 slice；raw Table 只命中 `DataTable` 封装，slice 遗留列入 P1。
- `rg "总收益|每日信号等权复利收益|真实组合|max5|max10|near_entry"` 检查关键报告口径。
- `npm pkg get scripts --prefix frontend` 确认前端已有 `api:check`、lint、build、test、analyze 分层命令。
- `git diff --check`：通过，无空白错误。
- `docs/README.md` 文件引用存在性脚本：通过；通配治理规则已排除为规则而非文件路径。
- `rg -n "^\\| *总收益 *\\|" docs/reports/strategy_24m_duckdb_report.md docs/reports/strategy-24m-backtest-2026-05-30.md docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.md`：无命中，退出码 1 表示未发现裸表头。
- `find docs/archive/plans -maxdepth 1 -type f | wc -l`：19；`find docs/archive/reports -maxdepth 1 -type f | wc -l`：19。

## 未完成项

- 未移动仍有活引用的根目录历史文档。
- 未移动仍被引用或体量较大的历史 JSON/ZIP/window 回测明细，只新增 ignore 与治理计划。
- 未拆分历史超长代码、样式、测试和脚本文件。
- 未修改前端 `slice(...)` 行为，避免改变页面展示语义。
- 未重写业务逻辑。
- 未做大规模文件搬迁或并行回测引擎改造。
