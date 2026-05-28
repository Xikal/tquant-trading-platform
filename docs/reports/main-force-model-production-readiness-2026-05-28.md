# 主力模型生产验收报告

- 生成时间：2026-05-28
- 模型：`main_force_accumulation_washout_markup_v1`
- 验证窗口：2024-05-28 至 2026-05-28
- 切分策略：12m train / 3m valid / 3m test，purged gap 10 天，随机切分禁止
- 当前结论：样本外研究指标通过，但 Shadow 观察样本和结算样本为 0，生产晋级仍阻断。

## 样本外摘要

- 样本数：2390
- 可买动作样本：779
- 样本外胜率：74.198%
- Profit Factor：82.046
- 20 日平均收益：10.9145%
- fallback rate：0.0%
- 防未来函数：pass，`max_source_date <= as_of_date`，`label_start_date > as_of_date`
- OOS 研究门禁：通过

## Shadow 门禁

- Shadow 观察样本：0 / 300
- Shadow 已结算样本：0 / 120
- Shadow 晋级：否
- 阻断原因：`shadow_record_count_lt_300`、`settled_shadow_count_lt_120`

因此：

- 排序加权仍保持默认关闭。
- 模拟盘小仓建议仍保持默认关闭。
- 模型可以进入生产只读展示和 Shadow 记录。
- 不允许自动下单，不允许覆盖硬止损，不允许绕过仓位、现金、最大持仓数或日亏损暂停。

## 分组表现

- 阶段表现：washout 784 条，胜率 76.276%，20 日均收益 9.2284%；markup_confirm 458 条，胜率 73.799%，20 日均收益 11.371%。
- 策略表现：main_force_research 2390 条，胜率 76.36%，20 日均收益 9.5495%。
- 市场状态：当前脚本未接入历史市场状态快照，统一标记为 unknown，不能作为市场状态晋级证据。
- 参数稳定性：55/60/65/70 分阈值均为研究正向，但生产参数变更仍禁止。

## 复现命令

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/main_force_model_backtest.py \
  --database backend/data/t_quant.db \
  --start 2024-05-28 \
  --end 2026-05-28 \
  --train-months 12 \
  --valid-months 3 \
  --test-months 3 \
  --purged-gap-days 10 \
  --limit-symbols 80 \
  --sample-stride 12 \
  --output docs/reports/main-force-model-production-readiness-2026-05-28.json
```

完整生产验收应在补齐 Shadow 样本后扩大 `--limit-symbols` 并降低 `--sample-stride` 重跑。
