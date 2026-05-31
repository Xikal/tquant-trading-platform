# Project Conventions Remediation

状态：已完成首轮整改
适用范围：工程结构、文档结构、命名、文件规模、生成产物、生产/研究边界
最后核验日期：2026-05-31

## 结论

已补齐缺失的工程规范文档，并把它纳入 AGENTS 与 docs 索引。随后将一批无活引用历史报告迁入 `docs/archive/reports/`，并将一批无活引用历史计划迁入 `docs/archive/plans/`；同时在 `docs/README.md` 中明确 archive 入口。其余发现项以清单形式保留，不做高风险搬迁或业务重写。

## 数据范围

- 仓库根目录顶层文件
- `docs/README.md`
- `docs/reports/`
- `.gitignore`
- 前端源码的结构性扫描

## 不可信或限制条件

- 仅覆盖当前工作区可见文件和可搜索到的文本引用。
- 未对业务代码、运行时效果或部署环境做变更验证。
- 结构扫描中的 `slice(...)` 结果仅作为代码形态记录，不代表一定是缺陷。

## 已整改文件

- `/Users/j/Documents/gupiao/AGENTS.md`
- `/Users/j/Documents/gupiao/docs/engineering-conventions.md`
- `/Users/j/Documents/gupiao/docs/README.md`
- `/Users/j/Documents/gupiao/.gitignore`

## P0

1. `docs/engineering-conventions.md` 在工作区缺失，但 `AGENTS.md` 已要求遵循它。已恢复到工作区。
2. `AGENTS.md` 未显式链接默认工程规范。已补。
3. `docs/README.md` 未把工程规范列入当前文档入口。已补。

## P1

1. 根目录仍保留多份历史计划/评估/交付类文档，如 `IMPLEMENTATION_PLAN.md`、`OPTIMIZATION_PLAN.md`、`FINAL_DELIVERY.md`、`APP_API_SPEC.md`、`ARCHITECTURE.md`、`PROJECT_PLAN.md`、`PRODUCT_STAGE_ACCEPTANCE.md`、`全方位评估报告-2026-05-01.md`、`策略体系重组方案.md`、`系统级全方位提升方案-2026-05-30.md`。这些文件属于历史材料，未在本轮移动，以免破坏现有引用链。
2. `docs/reports/` 仍包含大量机器可读产物和大文件，例如 `front-row-weighted-production-scoring-backtest-2026-05-29.json`、`strategy-24m-backtest-2026-05-30.json`、`strategy-24m-optimization-report-2026-05-28.json`、`front-row-weighted-production-scoring-review-package-2026-05-30.zip`、`main-force-model-dataset-smoke.jsonl`。其中多个文件在计划、脚本或审查报告中存在引用，暂不移动。
3. 前端存在大量 `slice(...)` 截断用法，主要用于展示层的窗口裁剪或列表限长；本轮未改动业务 UI 逻辑，只做结构扫描记录。
4. 根目录仍有少量隐式配置文件（`.vercelignore`、`Dockerfile.prebuilt`、`pytest.ini`）没有文本引用，但属于工具/构建默认入口，未纳入本轮文档归档范围。

## P2

1. 仍有历史文档散落在根目录，建议后续分批归档到 `docs/archive/` 或更清晰的历史索引。
2. `docs/reports/` 中的机器可读产物建议继续向 `backend/data/analytics/reports/` 和外部 artifacts 收敛。
3. `main-force-model-dataset-smoke.jsonl` 已通过 `.gitignore` 增加后缀屏蔽，防止新 `.jsonl` 继续误入报告目录。

## 超大文件清单

| 文件 | 规模观察 | 处理建议 |
|---|---:|---|
| `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` | 约 13 MB / 369k 行 | 必须拆分候选说明和机器数据，保留引用但不再膨胀 |
| `docs/reports/strategy-24m-backtest-2026-05-30.json` | 约 1.4 MB / 38k 行 | 只小修，继续作为机器产物 |
| `docs/reports/strategy-24m-optimization-report-2026-05-28.json` | 约 1.3 MB / 36k 行 | 只小修，后续优先归档到数据目录 |
| `docs/contracts/openapi.json` | 约 38k 行 | 允许豁免，但需保持与生成源同步 |
| `frontend/src/generated/api-types.ts` | 约 26k 行 | 允许豁免，避免人工编辑 |

## 生成产物清理建议

- 保留：当前仍被计划、脚本或报告引用的 JSON/ZIP 证据文件。
- 已移动：无活引用的历史报告批次已迁入 `docs/archive/reports/`，无活引用的历史计划批次已迁入 `docs/archive/plans/`。
- 仅加 ignore：`docs/reports/*.jsonl`，避免新生成物继续进入报告目录。
- 后续可迁移：未被引用、纯机器产出的新 JSON/Parquet/ZIP，优先放 `backend/data/analytics/reports/` 或 `artifacts/`。

## 生产/研究边界检查结论

- 本轮未改业务路径，因此未改变生产/研究门控。
- 结构扫描没有显示新增生产入口或后台 loop。
- 研究型、回测型和报告型产物仍集中在报告与数据目录，边界总体清楚，但历史堆积仍需后续清理。

## 是否可作为生产依据

- 否。本文只记录工程结构整改结果与后续清理建议，不作为生产策略或收益判断依据。

## 文档结构整改结论

- `AGENTS.md`、`docs/README.md`、`docs/engineering-conventions.md` 已形成闭环。
- 当前 `docs/README.md` 已可作为工程文档入口。
- 后续新增一次性计划或审查，应优先落在 `docs/superpowers/plans/` 或 `docs/reports/`，不要再放根目录。

## 验证

- 运行了根目录、`docs/reports/` 和前端结构扫描。
- 运行了引用检查，确认 `front-row-weighted-production-scoring-review-package-2026-05-30.zip` 与 `front-row-weighted-production-scoring-backtest-2026-05-29.json` 等仍被引用，未做删除或搬迁。
- 运行了 archive 归档检查，确认迁移后的历史报告在 `docs/archive/reports/` 中可见，历史计划在 `docs/archive/plans/` 中可见。

## 未完成项

- 未移动仍有活引用的根目录历史文档。
- 未重写业务逻辑。
- 未做大规模文件搬迁或并行回测引擎改造。
