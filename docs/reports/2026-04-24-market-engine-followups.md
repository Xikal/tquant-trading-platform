# 2026-04-24 市场环境引擎与交易策略后续优化项

本轮实现已经通过本地验证，并经策略复核确认为“无重大问题，可上线”。

以下事项不构成当前上线阻断，但仍建议后续继续优化。

## P2

### 1. 市场状态机继续增强时间序列输入

目标文件：
- `/Users/j/Documents/gupiao/backend/app/services/market/regime.py`

建议补充：
- 昨日/今日主线重合度
- 高标断层速度
- 更细的炸板晋级关系

目的：
- 提升 `fast_rotation`
- 提升 `high_flyer_retreat`
- 降低早期退潮误判和单日分化误判

### 2. 低吸链路进一步减少重复惩罚

目标文件：
- `/Users/j/Documents/gupiao/backend/app/services/low_buy/candidate.py`
- `/Users/j/Documents/gupiao/backend/app/services/low_buy/signals.py`
- `/Users/j/Documents/gupiao/backend/app/services/low_buy/priority_board.py`

当前状态：
- 候选层、信号层、排序层已经明显收敛
- 但在 `weight_support / fast_rotation` 下，仍有轻度重复惩罚

后续方向：
- 候选层负责降分
- 信号层负责阻断
- 排序层只做轻微修正

### 3. 做T继续细化 ETF / 权重股 / 题材股差异

目标文件：
- `/Users/j/Documents/gupiao/backend/app/services/quant_engine_execution.py`

当前状态：
- 已支持 ETF 与个股在不同市场状态下差异化
- 但仍主要通过参数修正实现

后续方向：
- 让 `positive_direction_gate`
- `negative_direction_gate`
- 不再只靠阈值放松
- 而是进一步拆成品种级逻辑分叉

## P3

### 1. 行业轮动 bonus 继续降权并细化

目标文件：
- `/Users/j/Documents/gupiao/backend/app/services/low_buy/priority_board.py`

当前状态：
- 已经从强加分降到轻量修正
- 但仍偏“热点 Top3 加分”

后续方向：
- 引入轮动持续性
- 引入热点衰减
- 避免单日板块异动被过度放大

### 2. 开盘初期宽度快照未就绪时的体验优化

目标文件：
- `/Users/j/Documents/gupiao/backend/app/services/market/regime.py`

当前状态：
- 未就绪时会安全回退到 `low_volume_wait`
- 逻辑安全，但盘初偏保守

后续方向：
- 给盘初显示更明确的“宽度未就绪”说明
- 或引入更平滑的盘初临时状态
