# TQuant 离线研究环境

本目录用于离线因子研究、策略验证和标准化回测。它不参与线上 FastAPI 请求链路，研究结果需要人工复核后才能进入生产策略配置。

## 目录

- `data_sync/`: 从 TQuant 数据库导出 qlib/Parquet 友好的行情与策略样本。
- `factor_research/`: 因子探索和 IC/IR 统计入口。
- `backtest/`: 标准化策略验证、基准对比和报告生成。
- `reports/`: 离线输出报告目录，不提交大型结果文件。

## 快速开始

```bash
# 1. 可选：安装离线研究依赖。qlib 不安装也可以运行降级报告。
python3 -m pip install -r research/requirements.txt

# 2. 从本地 TQuant 数据库导出行情。无 pyarrow 时自动输出 CSV。
PYTHONPATH=. python3 research/data_sync/tquant_to_qlib.py \
  --database-url sqlite:///backend/data/t_quant.db \
  --output-dir research/reports/datasets \
  --check-qlib

# 3. 对离线策略样本生成标准验证报告。
PYTHONPATH=. python3 research/backtest/strategy_validation.py \
  --input research/reports/datasets/strategy_samples.csv \
  --strategy-key auxiliary_alpha \
  --output research/reports/strategy_validation.json

# 4. 生成 benchmark 摘要报告。
PYTHONPATH=. python3 research/backtest/benchmark.py \
  --input research/reports/datasets/strategy_samples.csv \
  --output research/reports/benchmark.json
```

## 标准报告字段

策略验证与 benchmark 报告都会输出以下字段，即使输入为空也返回空报告而不是抛异常：

- `sample_count`: 样本量。
- `win_rate`: 胜率百分比。
- `sharpe`: 基于离线收益序列的 Sharpe 占位/可计算值。
- `max_drawdown`: 基于离线收益序列的最大回撤幅度。
- `ic`: `factor_score` 与 `forward_return_1d` 或 `return_3d` 的信息系数。
- `ir`: 按日 IC 可计算时输出 IR，否则使用 IC 作为占位，缺少因子时为 `null`。

## qlib 降级

`qlib` 是可选研究增强依赖。脚本只在运行时检查可用性，不会在 import 阶段崩溃；未安装时会输出“已跳过 qlib 初始化”的说明，仍可基于 CSV/Parquet 完成离线报告。

## 边界

- 不直接修改生产策略阈值。
- 不阻塞线上接口。
- 不调用外部大模型。
- 默认只读取本地数据库或导出的离线文件。
- 不从 research 脚本发起线上行情请求。
