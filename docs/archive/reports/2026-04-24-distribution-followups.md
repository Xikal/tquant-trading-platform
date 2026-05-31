# 2026-04-24 派发风险识别后续优化项

本轮已完成：

- 市场环境引擎接入 `distribution_pressure`
- 低吸候选 / 信号 / 优先级榜接入派发风险
- 做T链路接入正T阻断、反T放宽
- Web / App 共用同一套后端语义

当前剩余项不阻塞本地策略灰度，但不建议忽略。

## P2

1. `emotion.py` 和 `regime.py` 仍各自保留一套派发压力语义
   - 当前对外输出已经统一到 `regime.py` 的复合派发压力
   - 但 `emotion.py` 里的 `distribution_pressure` 仍存在，后续维护时容易误读
   - 建议：
     - 把 `emotion.py` 的字段改名为 `emotion_distribution_pressure`
     - `regime.py` 保留 `distribution_pressure`

2. 优先级榜盘中只刷新价格，不重算派发风险
   - 当前优先级榜实时价是新的
   - 但 `false_breakout / stall_after_volume / intraday_reversal` 仍来自最近一次候选物化
   - 建议：
     - 增加轻量盘中派发刷新接口
     - 只对榜单当前股票重算分时派发风险

3. 低吸 `false_breakout` 仍是绝对硬阻断
   - 当前策略上是保守的
   - 适合灰度观察，不建议立刻放开
   - 建议：
     - 后续结合样本复盘，验证是否对 `classic_retrace / ma_support / breakout_support` 误杀偏多

## P3

1. `distribution_signals.py` 仍是单日/短分时识别
   - 还没有加入“连续 2-3 次冲高失败”的时间序列确认
   - 建议后续增加多次失败确认，降低误报

2. `weight_stock` 识别仍基于行业关键字
   - 对券商、白酒、中字头大票、核心宽基成分股覆盖还不完整
   - 建议后续加入：
     - 白名单ETF
     - 大市值股票池
     - 指数成分权重代理

3. 测试覆盖还可以继续补
   - 当前已覆盖：
     - 市场状态 P2
     - 正T / 反T 的派发接入
   - 建议后续补：
     - 低吸候选降分
     - 优先级榜排序变化
     - 分时派发刷新

## 验证结论

- 本地 `backend compileall` 通过
- 本地 `frontend build` 通过
- `test_market_regime_strategy_p2.py` 通过
- `test_low_buy*.py` 通过
- `test_app_mobile*.py` 通过
- `qa_smoke.sh` 当前仍可能因完整全量链路超时，不作为本轮派发风险接入的直接失败依据
