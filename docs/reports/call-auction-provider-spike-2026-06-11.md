# 集合竞价 Provider Spike 报告

- 生成时间：`2026-06-11T09:21:15+08:00`
- 数据源：`akshare.stock_zh_a_hist_pre_min_em`
- 状态：`provider_failed`
- 结论：`provider_failed`
- 说明：provider 未能稳定返回 9:25 结果或失败率过高。

## 窗口

- 交易日：`2026-06-11`
- 检查时间：`2026-06-11T09:21:15+08:00`
- 是否交易日：`True`
- 是否在 spike 窗口：`True`
- 窗口：`09:19:30` - `09:25:30`

## 样本与字段

- 样本数：`10`
- 调用数：`10`
- 可用数：`0`
- 失败率：`1.0`
- 有 9:20-9:25 过程行的标的数：`0`
- 有 9:25 结果行的标的数：`0`
- 字段并集：`无`

## 后续决策

- G2 允许：`False`
- G4 允许：`False`

## 明细

| symbol | type | quality | rows | process | result | latency_ms | message |
|---|---|---:|---:|---:|---:|---:|---|
| 600000 | stock | provider_failed | 0 | 0 | 0 | 1588 | Expecting value: line 1 column 1 (char 0) |
| 000001 | stock | provider_failed | 0 | 0 | 0 | 3641 | Expecting value: line 1 column 1 (char 0) |
| 510300 | etf | provider_failed | 0 | 0 | 0 | 1225 | Expecting value: line 1 column 1 (char 0) |
| 600519 | stock | provider_failed | 0 | 0 | 0 | 2123 | Expecting value: line 1 column 1 (char 0) |
| 000333 | stock | provider_failed | 0 | 0 | 0 | 8955 | Expecting value: line 1 column 1 (char 0) |
| 159915 | etf | provider_failed | 0 | 0 | 0 | 1453 | Expecting value: line 1 column 1 (char 0) |
| 300750 | stock | provider_failed | 0 | 0 | 0 | 1278 | Expecting value: line 1 column 1 (char 0) |
| 688981 | stock | provider_failed | 0 | 0 | 0 | 2289 | Expecting value: line 1 column 1 (char 0) |
| 512100 | etf | provider_failed | 0 | 0 | 0 | 2950 | Expecting value: line 1 column 1 (char 0) |
| 515000 | etf | provider_failed | 0 | 0 | 0 | 2090 | Expecting value: line 1 column 1 (char 0) |
