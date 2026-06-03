# Repository Cleanup Report 2026-05-27

## Conclusion

本轮清理只处理证据明确的临时产物、重复运行报告和失效引用，未删除生产路径、策略逻辑、迁移、部署脚本、测试基线和审计主报告。

## Removed

- 本地运行缓存：`.runtime/`
  - 内容包括临时 SQLite、smoke/preflight 日志、full-regression 临时 JSON/Markdown、warning-budget 临时 JSON、移动端截图/XML。
  - 判定依据：`.runtime/` 已在 `.gitignore` 中；持久结论已汇总到 `docs/archive/reports/full-regression-2026-05-27.md`、`docs/archive/reports/observability-warning-budget-2026-05-27.md` 和云端性能报告。

- Python 缓存：`__pycache__/`、`.pytest_cache/`
  - 判定依据：均为解释器/pytest 可再生成缓存，已被 `.gitignore` 覆盖。

- TypeScript 增量编译缓存：
  - `frontend/tsconfig.node.tsbuildinfo`
  - `frontend/tsconfig.app.tsbuildinfo`
  - 判定依据：`frontend/*.tsbuildinfo` 已被 `.gitignore` 覆盖；`.tsbuildinfo` 是 `tsc -b` 可再生成缓存，不应作为源码或发布产物跟踪。

- 本地 smoke 生成残留：`dist/responsive-smoke-report.json`
  - 判定依据：`dist/` 已被 `.gitignore` 覆盖；该文件是本地 UI smoke 输出，不被代码、CI、部署脚本或报告引用。

- 重复云端性能中间报告：
  - `docs/reports/gupiao-cloud-performance-2026-05-27-024452.json`
  - `docs/reports/gupiao-cloud-performance-2026-05-27-024931.json`
  - `docs/reports/gupiao-cloud-performance-2026-05-27-025144.json`
  - `docs/reports/gupiao-cloud-performance-2026-05-27-025303.json`
  - `docs/reports/gupiao-cloud-performance-2026-05-27-030533.json`
  - `docs/reports/gupiao-cloud-performance-2026-05-27-103535.json`
  - `docs/reports/gupiao-cloud-performance-2026-05-27-113055.json`
  - 判定依据：未被代码、脚本、CI 或持久报告引用；同日已有更完整的 `docs/reports/gupiao-cloud-performance-2026-05-27-120241.json` 和上线后最新 `docs/reports/gupiao-cloud-performance-2026-05-27-124403.json` 保留。

## Updated References

- `docs/README.md`
  - 新增文档索引，把当前运行文档、当前产品/策略参考、历史架构/重构记录、报告证据和清理规则分层。

- `docs/archive/plans/策略体系重组方案.md`
  - 增加历史状态说明，避免旧策略分层方案被误当作当前上线验收口径。

- `docs/archive/reports/full-regression-2026-05-27.md`
  - 移除对 `.runtime/full-regression/...` 临时明细报告的持久引用，改为说明临时报告已汇总到本文。

- `docs/archive/reports/observability-warning-budget-2026-05-27.md`
  - 移除对 `.runtime/full-regression/...` 临时明细报告的持久引用，改为说明临时报告已汇总到本文。

## Kept

- `docs/reports/gupiao-cloud-performance-2026-05-27-120241.json`
  - 被全量回归报告引用，是本轮全量回归云端性能验收依据。

- `docs/reports/gupiao-cloud-performance-2026-05-27-124403.json`
  - 最新上线后的云端性能验收依据，包含 observability 分级。

- `docs/reports/go-rust-performance-acceptance-2026-05-25.json`
  - 被历史审查报告和 Go/Rust 文档引用，作为早期验收基线保留。

- 根目录计划/交付/评估类文档：
  - `FINAL_DELIVERY.md`、`IMPLEMENTATION_PLAN.md`、`OPTIMIZATION_PLAN.md`、`PROJECT_PLAN.md`、`PRODUCT_STAGE_ACCEPTANCE.md`、`docs/archive/reports/全方位评估报告-2026-05-01.md`、`docs/archive/plans/策略体系重组方案.md`
  - 判定依据：仍被 `README.md`、脚本或历史方案引用，且保留了产品/策略演进背景；本轮通过 `docs/README.md` 分层和历史状态标记降低误用风险，不直接删除。

- `docs/reports/go-rust-performance-acceptance-2026-05-27.json`、`docs/reports/gupiao-go-rust-runtime-performance-2026-05-27.json`、`docs/reports/rust-bench-baseline.json`
  - 当前 Go/Rust 生产主路径、运行时性能和 Rust benchmark 门禁仍在引用或需要作为基线。

- `frontend/node_modules/`、`node_modules/`、`backend/.venv/`、`rust/tquant-rs/target/`、`frontend/dist/`、`frontend/android/app/build/`
  - 均为 ignored 依赖或构建缓存。可按需要本地删除，但会显著影响后续验证速度，本轮不作为仓库内容清理对象。

- `.mysql-local/`、`backend/data/`、`backend/.env`、`frontend/.env.native.local`、`.codex/`、`.continue/`
  - 均为本地运行状态、数据库、密钥配置或 Codex/Continue 工作区配置。虽然不进入版本控制，但可能包含用户本地状态或凭据，本轮不删除。

## Maintenance Rules

- `.runtime/` 只保存本地运行临时明细，不在文档中作为长期证据引用；需要持久化的结论应汇总到 `docs/reports/`。
- 同一天多次生成的 `gupiao-cloud-performance-*.json` 只保留被报告引用的验收证据和最新上线后报告。
- `__pycache__/`、`.pytest_cache/`、日志、临时 DB、移动端截图/XML 均应保持 ignored，不进入版本控制。
- 删除文档或报告前先用 `rg` 查引用关系；被代码、CI、部署脚本、测试或审计报告引用的文件不直接删除。
