# reports 目录索引与产物保留规则

`docs/reports/` 的端态是保存人读 Markdown 审查、验收和复盘摘要。大型机器产物默认进入 `backend/data/reports/`、`backend/data/analytics/reports/` 或外部 artifact/object storage。

## 当前规则

- 新增人读 Markdown 可以放在本目录。
- 新增大型机器产物不要直接放入本目录。
- 必须保留 JSON 证据时，需要有同名 Markdown 或本索引说明口径。
- 不要直接删除历史 JSON、JSONL、zip 或 walk-forward 明细；先做引用检查和审计价值判断。
- 本地缓存使用 `scripts/clean_local_artifacts.sh` 清理，不把缓存产物提交入库。

## 当前人读资料与审查记录

- `docs/reports/artifact-manifest-2026-06-02.md`
- `docs/reports/project-engineering-compliance-remediation-2026-06-02.md`
- `docs/reports/full-project-code-review-2026-06-02.md`
- `docs/reports/zhangmengzhu-16-articles-analysis-2026-06-02.md`
- `docs/reports/zhangmengzhu-16-articles-source-2026-06-02.md`

## 历史机器产物现状

截至 2026-06-02，本目录仍有历史机器产物。它们不代表新增规范，而是保留用于审计、回溯和报告引用。

代表性保留项：

| 路径 | 类型 | 保留原因 | 后续处理 |
|---|---|---|---|
| `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json` | 回测 JSON | 多份 front-row 审查和开发计划引用 | 迁移前保留，补 artifact manifest |
| `docs/reports/strategy-24m-backtest-2026-05-30.json` | 回测 JSON | 24 个月策略报告引用 | 后续迁入 `backend/data/reports/` |
| `docs/reports/strategy-24m-optimization-report-2026-05-28.json` | 优化报告 JSON | 闭环优化和策略验收引用 | 后续迁入 `backend/data/reports/` |
| `docs/reports/front-row-weighted-production-scoring-review-package-2026-05-30.zip` | 审查包 | 历史审查证据 | 后续迁入外部 artifact |
| `docs/reports/main-force-model-dataset-smoke.jsonl` | smoke JSONL | 主力模型验证证据 | 后续迁入 `backend/data/reports/` |

## 新产物落位

| 产物 | 默认位置 |
|---|---|
| 人读审查/验收摘要 | `docs/reports/*.md` |
| 回测/矩阵/大 JSON | `backend/data/reports/` |
| DuckDB/Parquet/analytics 结果 | `backend/data/analytics/reports/` |
| 大 zip、截图、录屏 | 外部 artifact/object storage |

## 迁移门禁

迁移或删除历史产物前必须执行：

```bash
rg --fixed-strings "<basename>" .
```

只有在确认无代码、脚本、测试、文档、部署或审计引用后，才允许删除；否则先改引用并保留迁移记录。
