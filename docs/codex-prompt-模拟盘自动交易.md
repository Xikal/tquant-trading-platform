# Codex 任务：模拟盘自动交易系统

**目标**：实现交易时段内稳定运行的自动交易循环 —— 从 priority_board 信号自动生成委托单并执行，具备断线恢复、错误熔断、状态持久化能力。

**原则**：复用现有 PaperOrderService / PaperMatchingEngine / PaperRiskControlService / TaskManager，不修改现有策略逻辑。默认关闭，默认 dry-run。

**总任务数**：7 个任务，按顺序执行。

---

## 当前状态速查

| 组件 | 状态 | 说明 |
|------|------|------|
| PaperOrderService | ✓ 已实现 | 下单 → 风控 → 撮合 → 结算，链路完整 |
| PaperMatchingEngine | ✓ 已实现 | 市价/限价撮合，含滑点、停牌保护 |
| PaperRiskControlService | ✓ 已实现 | 单笔上限 30%、个股上限 40%、日累计上限 60%、日限 20 笔 |
| PaperTradingExecutor | ✓ 已实现 | 接收 `planned_orders` 并批量执行 |
| PaperAccountService | ✓ 已实现 | 账户管理、资金检查、市值更新 |
| TaskManager | ✓ 已实现 | daemon 线程注册与生命周期管理 |
| priority_board 接口 | ✓ 已实现 | 含市场状态、方向倾向、个股评分 |
| **信号 → 订单生成** | ❌ 缺失 | priority_board 信号到 planned_orders 的翻译层 |
| **自动交易循环** | ❌ 缺失 | 定时轮询、准入过滤、仓位计算、自动下单 |
| **断线恢复** | ❌ 缺失 | 进程重启后的状态恢复逻辑 |
| **错误熔断** | ❌ 缺失 | 连续失败的自动暂停机制 |

---

## 目标架构

```
交易日 9:30-15:00，每 120 秒一个循环

┌─────────────────────────────────────────────────────────┐
│  PaperAutoTrader (daemon thread via TaskManager)        │
│                                                         │
│  _run_one_cycle():                                      │
│    │                                                    │
│    ├─ 1. 行情时间校验（跳过非交易时段）                  │
│    │                                                    │
│    ├─ 2. 获取 priority_board 信号                       │
│    │    按 priority_score 降序，上限 20 条               │
│    │                                                    │
│    ├─ 3. AdmissionFilter 准入过滤                        │
│    │    ├─ 调度分阈值                                   │
│    │    ├─ 持仓查重 + T+1 锁定                          │
│    │    ├─ 市场方向兼容                                 │
│    │    ├─ 停牌保护                                     │
│    │    └─ 当日撤单免重复                                │
│    │                                                    │
│    ├─ 4. PositionSizer 仓位计算                         │
│    │    ├─ 单笔 = min(总资产×10%, 可用资金×30%)         │
│    │    ├─ 取 100 股整数倍                              │
│    │    └─ 按调度分降序分配，最多 5 笔                  │
│    │                                                    │
│    └─ 5. PaperTradingExecutor.execute_plan()            │
│         ├─ 资金检查 (OrderService._precheck)             │
│         ├─ 风控检查 (OrderService._risk_check)           │
│         ├─ 撮合成交 (PaperMatchingEngine.match)          │
│         └─ 持仓结算 (OrderService._apply_trade)          │
│                                                         │
│  可靠性保障:                                             │
│    ├─ SQLite WAL 模式（读写并发）                        │
│    ├─ 每循环独立 DB session（避免锁竞争）                │
│    ├─ 熔断器：连续 3 次失败 → 暂停 5 分钟               │
│    ├─ 心跳上报（监控可查询）                             │
│    ├─ 所有决策记录为 PaperOrder（source="auto"）         │
│    └─ 进程重启后通过 DB 查询当日已执行订单恢复状态       │
└─────────────────────────────────────────────────────────┘
```

---

## 可靠性设计（重点）

### 断线场景与恢复策略

| 场景 | 表现 | 恢复方式 |
|------|------|---------|
| akshare HTTP 超时 | 单次 priority_board 刷新失败 | 跳过本轮，下轮重试。连续 3 次失败触发熔断 |
| 数据库锁超时 | SQLite BUSY | 重试 3 次（间隔 1s/2s/4s），仍失败则跳过本轮 |
| FastAPI 进程崩溃 | daemon 线程终止 | Docker restart policy: `unless-stopped`。进程重启后自动启动 |
| 云服务器重启 | 全部服务中断 | Docker auto-start + 进程重启后 auto-trader 自动上线 |
| 循环中卡死 | 某步 hang 住 | 每循环设 60s 硬超时。超时后记录日志并跳过 |
| 网络分区 | 无法连接 akshare | 熔断器自动暂停，网络恢复后手动或自动重试 |

### 状态持久化

所有自动交易决策以 `PaperOrder` 记录存入数据库，标记 `source = "auto"`。进程重启后，通过查询当日 `source = "auto"` 的订单即可恢复状态：

- **已买入某标的** → ORDER 表中已有 filled 记录 → 不会重复买入
- **今日已下单 N 笔** → 计入每日上限
- **某标的已撤单** → 当天不再对该标的下单

**不依赖内存状态**——所有关键判断依据数据库。

### 熔断器

```
连续失败计数器（内存，进程级）
    成功 → 重置计数器
    失败 → 计数器 +1
    计数器 >= 3 → 暂停 300 秒，记录 WARNING 日志
    暂停结束后 → 计数器重置，恢复循环
```

### 交易日历

循环内判断：

```python
def _is_trading_time() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False  # 周末
    t = now.time()
    # 上午 9:30-11:30，下午 13:00-14:58（最后 2 分钟不下单）
    return (time(9,30) <= t <= time(11,30)) or (time(13,0) <= t <= time(14,58))
```

不引入交易日历库（A 股节假日判断依赖 akshare 即可），周末判断足够。如遇节假日误判，自动交易会因 akshare 返回空数据而自然跳过（不会报错）。

---

## 任务 1：准入过滤器 AdmissionFilter

**新建文件**：`backend/app/services/paper/admission.py`

准入过滤器是一个纯函数模块，不依赖数据库连接，方便单独测试。

### 核心数据结构

```python
from dataclasses import dataclass, field

@dataclass
class AdmissionResult:
    passed: bool
    symbol: str
    priority_score: float
    reason: str          # "通过" 或拒绝原因
    signal: dict         # 原始信号数据（透传给后续环节）

@dataclass
class AdmissionReport:
    passed: list[AdmissionResult]
    filtered: list[AdmissionResult]
    summary: str  # 如 "通过 3 条，过滤 15 条"
```

### 过滤规则（按优先级，命中即停止）

```python
class AdmissionFilter:
    def __init__(self, *, min_score: int = 75):
        self.min_score = min_score

    def evaluate(
        self,
        *,
        signals: list[dict],           # priority_board items，dict 形式
        existing_positions: list[dict], # 当前持仓 [{"symbol","hold_days","position_pct"}]
        today_orders: list[dict],       # 今日委托 [{"symbol","status"}]
        market_direction: str,          # "positive_t" / "negative_t" / "neutral"
    ) -> AdmissionReport:
        ...
```

**规则清单（按顺序判定）**：

```
① priority_score < min_score (75)
   → 拒绝: "调度分{score}<阈值75"

② 标的停牌 (signal.is_suspended 或 signal.risk_tier == "block")
   → 拒绝: "标的停牌"

③ 已持有且仓位 >= 40%
   → 拒绝: "已持有{position_pct}%，不再加仓"

④ 已持有且持有天数 < 1（T+1 锁定，含当日买入）
   → 拒绝: "当日已买入，T+1 锁定"

⑤ 今日该标的曾撤单
   → 拒绝: "今日已撤单，不重复下单"

⑥ 市场方向 = "negative_t"（退潮/高风险）
   → 拒绝: "市场退潮，暂停所有买入"

⑦ 市场方向 = "neutral" AND priority_score < 85
   → 拒绝: "观望日+信号偏弱({score}<85)"

⑧ buy_signal_state 为 "watch" 或非 "buy_now"/"soft_buy_now"
   → 拒绝: "信号未到买入级别"

⑨ 通过 → AdmissionResult(passed=True)
```

**市场方向来源**：priority_board 响应的 `directional_bias` 字段（由 `market_state_rules.compute_directional_bias()` 计算，已在现有代码中）。

### 边界情况

- **空信号列表**：返回空的 passed 和 filtered，summary = "无优先级信号"
- **priority_score 为 None**：视为 0，被规则①拒绝
- **positions/today_orders 为空列表**：视为无持仓/无当日订单，不影响过滤
- **market_direction 为 None 或未知**：视为 "neutral"

### 验证

```bash
cd backend && .venv/bin/python -c "
from app.services.paper.admission import AdmissionFilter
f = AdmissionFilter(min_score=75)
# 空信号
r = f.evaluate(signals=[], existing_positions=[], today_orders=[], market_direction='positive_t')
assert len(r.passed) == 0
# 低于阈值
r = f.evaluate(
    signals=[{'symbol':'000001','name':'测试','priority_score':60,'risk_tier':'note','buy_signal_state':'buy_now'}],
    existing_positions=[], today_orders=[], market_direction='positive_t'
)
assert len(r.passed) == 0
print('AdmissionFilter OK')
"
```

---

## 任务 2：仓位计算器 PositionSizer

**新建文件**：`backend/app/services/paper/sizing.py`

### 核心逻辑

```python
from dataclasses import dataclass

@dataclass
class SizedOrder:
    symbol: str
    name: str
    side: str            # 始终 "buy"
    order_type: str      # 始终 "market"
    quantity: int        # 100 股整数倍
    price: float         # 限价（市价单填 current_price 即可）
    current_price: float
    strategy_key: str
    reason: str
    signal_snapshot: dict
    source: str          # "auto"

class PositionSizer:
    def __init__(self, *, max_position_pct: float = 0.10, max_cash_pct: float = 0.30):
        self.max_position_pct = max_position_pct
        self.max_cash_pct = max_cash_pct

    def calculate(
        self,
        *,
        candidates: list,          # AdmissionResult.passed 列表
        total_assets: float,
        available_cash: float,
        max_orders: int = 5,
    ) -> list[SizedOrder]:
        ...
```

### 计算规则

```
对每个候选人（按 priority_score 降序）：

1. 单笔最大金额 = min(总资产 × 10%, 剩余可用资金 × 30%)
2. 买入数量 = floor(单笔最大金额 / 当前价 / 100) × 100
3. 如果 买入数量 < 100:
     跳过（资金不足以买 100 股）
4. 实际占用 = 买入数量 × 当前价
5. 如果 实际占用 > 剩余可用资金:
     重新计算买入数量 = floor(剩余可用资金 / 当前价 / 100) × 100
     如果仍然 < 100: 跳过
6. 剩余可用资金 -= 实际占用
7. 如果已生成订单数 >= max_orders: 停止
```

### 边界情况

- **total_assets 为 0 或负数**：返回空列表
- **available_cash 为 0**：返回空列表
- **当前价为 0 或负数**：跳过该 candidate
- **所有 candidate 都不够买 100 股**：返回空列表
- **当前价极高（如茅台 1700+）**：单笔可能买不到 100 股，自然跳过

### 生成的 planned_order dict 格式

与 PaperTradingExecutor.execute_plan() 要求的格式对齐：

```python
{
    "symbol": "510300",
    "name": "沪深300ETF",
    "side": "buy",
    "order_type": "market",
    "quantity": 2000,
    "price": 3.478,           # 限价单价格（市价单填 current_price）
    "current_price": 3.478,   # 撮合现价
    "quote_time": "2026-05-02T14:30:00",
    "is_suspended": False,
    "source": "auto",
    "strategy_key": "first_board",
    "reason": "自动调入: 首板回调+主线龙头，调度分82",
    "signal_snapshot": {...},
}
```

### 验证

```bash
cd backend && .venv/bin/python -c "
from app.services.paper.sizing import PositionSizer
s = PositionSizer()
# 空候选
result = s.calculate(candidates=[], total_assets=100000, available_cash=50000, max_orders=5)
assert len(result) == 0
# 正常计算
from collections import namedtuple
C = namedtuple('C', ['symbol','name','priority_score','signal'])
candidates = [
    C('510300','300ETF',82,{'symbol':'510300','name':'300ETF','latest_price':3.5,'strategy_key':'first_board','buy_signal_state':'buy_now','risk_tier':'note'}),
]
result = s.calculate(candidates=candidates, total_assets=100000, available_cash=50000, max_orders=5)
assert len(result) == 1
assert result[0].quantity >= 100
print('PositionSizer OK')
"
```

---

## 任务 3：自动交易调度器 PaperAutoTrader

**新建文件**：`backend/app/services/paper/scheduler.py`

这是核心模块，负责交易循环、熔断、心跳、状态管理。

### 数据结构

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class AutoTraderState:
    """自动交易器运行状态（可通过 API 查询）。"""
    running: bool = False
    dry_run: bool = True
    interval_seconds: int = 120
    max_orders_per_cycle: int = 5
    min_score: int = 75
    # 本轮统计
    last_cycle_at: str = ""
    last_cycle_duration_ms: float = 0.0
    last_cycle_passed: int = 0
    last_cycle_filtered: int = 0
    last_cycle_executed: int = 0
    last_cycle_skipped: int = 0
    last_cycle_summary: str = ""
    # 累计统计
    total_cycles: int = 0
    total_executed: int = 0
    total_errors: int = 0
    # 熔断
    circuit_open: bool = False
    circuit_reason: str = ""
    circuit_since: str = ""
    # 心跳
    heartbeat_at: str = ""
```

### 主循环

```python
class PaperAutoTrader:
    """模拟盘自动交易调度器。

    通过 TaskManager 注册为 daemon 线程运行。
    每个循环：获取信号 → 准入过滤 → 仓位计算 → 执行委托。
    """

    def __init__(self, config: dict) -> None:
        self.state = AutoTraderState(
            dry_run=config.get("dry_run", True),
            interval_seconds=config.get("interval_seconds", 120),
            max_orders_per_cycle=config.get("max_orders_per_cycle", 5),
            min_score=config.get("min_score", 75),
        )
        self._consecutive_errors = 0
        self._circuit_until: datetime | None = None
        self._stop_event = threading.Event()

    def run_loop(self) -> None:
        """主循环入口（由 TaskManager 线程调用）。"""
        while not self._stop_event.is_set():
            try:
                self.state.heartbeat_at = datetime.now().isoformat()
                if not self._is_trading_time():
                    time.sleep(60)
                    continue
                if self._circuit_open():
                    time.sleep(30)
                    continue
                self._run_one_cycle()
                self._consecutive_errors = 0
            except Exception:
                logger.exception("自动交易循环异常")
                self._consecutive_errors += 1
                if self._consecutive_errors >= 3:
                    self._open_circuit("连续 3 次循环异常")
            # 分段 sleep，可中断
            for _ in range(self.state.interval_seconds):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _run_one_cycle(self) -> None:
        """执行一个完整交易循环。"""
        t0 = time.monotonic()
        db = SessionLocal()
        try:
            # 1. 获取 priority_board
            board = self._fetch_priority_board()
            if not board or not board.get("items"):
                self._record_cycle(0, 0, "无优先级信号")
                return
            signals = board["items"]
            market_direction = board.get("directional_bias", "neutral")

            # 2. 获取账户（取第一个 active 账户）
            account = self._get_active_account(db)
            if not account:
                self._record_cycle(0, 0, "无活跃模拟账户")
                return

            # 3. 获取持仓和当日委托（供准入过滤使用）
            positions = self._get_positions_summary(db, account.id)
            today_orders = self._get_today_auto_orders(db, account.id)

            # 4. 准入过滤
            from app.services.paper.admission import AdmissionFilter
            adm = AdmissionFilter(min_score=self.state.min_score)
            report = adm.evaluate(
                signals=signals,
                existing_positions=positions,
                today_orders=today_orders,
                market_direction=market_direction,
            )

            if not report.passed:
                self._record_cycle(0, len(report.filtered), report.summary)
                return

            # 5. 仓位计算
            from app.services.paper.sizing import PositionSizer
            sizer = PositionSizer()
            sized = sizer.calculate(
                candidates=report.passed,
                total_assets=account["total_assets"],
                available_cash=account["cash_available"],
                max_orders=self.state.max_orders_per_cycle,
            )

            if not sized:
                self._record_cycle(len(report.passed), len(report.filtered), "资金不足或候选不够")
                return

            # 6. 执行
            planned = [self._to_plan_dict(o) for o in sized]
            from app.services.paper.executor import PaperTradingExecutor
            from app.services.paper.order import PaperOrderService
            from app.services.paper.matching import PaperMatchingEngine

            order_service = PaperOrderService(db, PaperMatchingEngine())
            executor = PaperTradingExecutor(order_service)
            result = executor.execute_plan(
                account_id=account["id"],
                planned_orders=planned,
                max_orders=self.state.max_orders_per_cycle,
                dry_run=self.state.dry_run,
            )

            self._record_cycle(
                len(report.passed), len(report.filtered),
                result.get("summary", ""),
                executed=len(result.get("executed", [])),
                skipped=len(result.get("skipped", [])),
            )

        finally:
            elapsed = (time.monotonic() - t0) * 1000
            self.state.last_cycle_duration_ms = round(elapsed, 1)
            db.close()

    def _is_trading_time(self) -> bool:
        """判断当前是否在交易时段内（含 2 分钟收盘保护）。"""
        from datetime import time as dt_time
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        t = now.time()
        return (dt_time(9,30) <= t <= dt_time(11,30)) or (dt_time(13,0) <= t <= dt_time(14,58))

    def _circuit_open(self) -> bool:
        """检查熔断器是否开启。"""
        if self._circuit_until and datetime.now() < self._circuit_until:
            return True
        if self._circuit_until:
            logger.info("熔断器自动恢复")
            self._circuit_until = None
            self._consecutive_errors = 0
            self.state.circuit_open = False
        return False

    def _open_circuit(self, reason: str) -> None:
        """开启熔断器。"""
        self._circuit_until = datetime.now() + timedelta(seconds=300)
        self.state.circuit_open = True
        self.state.circuit_reason = reason
        self.state.circuit_since = datetime.now().isoformat()
        logger.warning("熔断器开启: %s，暂停至 %s", reason, self._circuit_until)

    def _record_cycle(self, passed, filtered, summary, executed=0, skipped=0):
        """记录本轮结果到状态。"""
        self.state.last_cycle_at = datetime.now().isoformat()
        self.state.last_cycle_passed = passed
        self.state.last_cycle_filtered = filtered
        self.state.last_cycle_executed = executed
        self.state.last_cycle_skipped = skipped
        self.state.last_cycle_summary = summary
        self.state.total_cycles += 1
        self.state.total_executed += executed
        if passed == 0 and executed == 0:
            pass  # 正常的空周期
        elif executed > 0:
            logger.info("自动交易循环: %s (通过%d, 执行%d)", summary, passed, executed)
        else:
            logger.info("自动交易循环: %s (通过%d, 过滤%d, 跳过)", summary, passed, filtered)
```

### 数据获取详情

**`_fetch_priority_board()`**：调用 `LowBuyScreenerService` 的 priority_board 方法，获取前 20 条候选。需要处理以下异常：

- akshare 超时：返回 None，本轮跳过
- 缓存命中（15ms）：正常返回
- 缓存过期需要刷新：等待（最多 15s），超时则返回 None

**`_get_active_account(db)`**：查询 PaperAccount 表，取 `status == "active"` 的第一个账户，返回 dict（id, total_assets, cash_available, status）。无活跃账户返回 None。

**`_get_positions_summary(db, account_id)`**：查询 PaperPosition，返回 `[{"symbol":..., "hold_days":..., "position_pct":...}]`。hold_days 通过 `(now - opened_at).days` 计算，position_pct = market_value / account.total_assets * 100。

**`_get_today_auto_orders(db, account_id)`**：查询今日订单（PaperOrder.created_at >= 今天 00:00），返回 `[{"symbol":..., "status":...}]`。

### 启动与停止

```python
# 模块级单例
_auto_trader: PaperAutoTrader | None = None

def get_auto_trader() -> PaperAutoTrader | None:
    return _auto_trader

def start_auto_trader(config: dict) -> PaperAutoTrader:
    global _auto_trader
    if _auto_trader and _auto_trader.state.running:
        return _auto_trader
    _auto_trader = PaperAutoTrader(config)
    task_manager.register_loop(
        name="paper_auto_trading",
        target=_auto_trader.run_loop,
        interval_seconds=0,  # run_loop 内部自行管理间隔
        initial_delay_seconds=10,
    )
    _auto_trader.state.running = True
    return _auto_trader

def stop_auto_trader() -> None:
    global _auto_trader
    if _auto_trader:
        _auto_trader._stop_event.set()
        _auto_trader.state.running = False
```

### 边界情况处理

| 场景 | 行为 |
|------|------|
| 无 priority_board 数据 | 跳过本轮，不计入错误 |
| 无活跃账户 | 跳过本轮，info 日志记录 |
| 资金不足买 100 股 | 跳过所有候选人，视为正常 |
| 单个 order 创建失败 | Executor 捕获异常并记入 skipped，不影响其他 order |
| 数据库锁 | 重试 3 次，仍失败则跳过本轮（不触发熔断） |
| 熔断器开启中 | 跳过循环，30s 后重试 |
| 非交易时段 | 每 60s 检查一次是否进入交易时段 |
| 收盘前 2 分钟 | 停止下单，等下一交易日 |

### 验证

```bash
cd backend && .venv/bin/python -c "
from app.services.paper.scheduler import PaperAutoTrader
t = PaperAutoTrader({'dry_run': True, 'interval_seconds': 120, 'max_orders_per_cycle': 5, 'min_score': 75})
assert t.state.dry_run == True
assert t._is_trading_time() == False  # 非交易时段
# 模拟一次循环（需数据库和 priority_board 可用）
# t._run_one_cycle()
print('PaperAutoTrader OK')
"
```

---

## 任务 4：配置项增加

**修改文件**：`backend/app/core/config.py`

在 AppSettings 类中，agent 相关配置之后追加：

```python
    # 模拟盘自动交易
    paper_auto_trading_enabled: bool = False   # 默认关闭
    paper_auto_trading_interval: int = 120     # 循环间隔（秒）
    paper_auto_trading_max_orders: int = 5     # 每轮最多下单数
    paper_auto_trading_dry_run: bool = True    # 默认空跑
    paper_auto_trading_min_score: int = 75     # 最低准入分
```

**修改文件**：`backend/.env.example`（如果存在）

追加：
```bash
# 模拟盘自动交易（默认关闭，dry-run）
PAPER_AUTO_TRADING_ENABLED=false
PAPER_AUTO_TRADING_INTERVAL=120
PAPER_AUTO_TRADING_MAX_ORDERS=5
PAPER_AUTO_TRADING_DRY_RUN=true
PAPER_AUTO_TRADING_MIN_SCORE=75
```

**环境变量覆盖方式**：启动时设置环境变量或修改 `.env` 文件即可。云服务器上的 `data/runtime.env` 可覆盖。

### 验证

```bash
cd backend && .venv/bin/python -c "
from app.core.config import get_settings
s = get_settings()
assert s.paper_auto_trading_enabled == False
assert s.paper_auto_trading_dry_run == True
print('Config OK')
"
```

---

## 任务 5：FastAPI 生命周期集成

**修改文件**：`backend/app/main.py`

### 启动时

在 `lifespan()` 函数中，`init_db()` 之后，`_background_jobs_enabled()` 块之内，追加：

```python
from app.services.paper.scheduler import start_auto_trader, stop_auto_trader

# 在 lifespan 中：
if _background_jobs_enabled() and settings.paper_auto_trading_enabled:
    logger.info("启动模拟盘自动交易")
    start_auto_trader({
        "dry_run": settings.paper_auto_trading_dry_run,
        "interval_seconds": settings.paper_auto_trading_interval,
        "max_orders_per_cycle": settings.paper_auto_trading_max_orders,
        "min_score": settings.paper_auto_trading_min_score,
    })
```

### 关闭时

在 `lifespan()` 的 `finally` 块中，`task_manager.shutdown()` 之前：

```python
stop_auto_trader()
```

### 注意事项

- `paper_auto_trading_enabled` 默认 `False`，不影响现有部署
- 上线时先在 `runtime.env` 中设置 `PAPER_AUTO_TRADING_ENABLED=true` 和 `PAPER_AUTO_TRADING_DRY_RUN=true`，观察 dry-run 日志 1-2 天无误后再关闭 dry-run
- 如果 `_background_jobs_enabled()` 返回 False（如 SQLite 环境），自动交易也不会启动

### 验证

```bash
# 启动服务，观察日志
cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000 2>&1 | grep "自动交易"
# 默认不启（enabled=false）：不应看到自动交易相关日志
# 设置 PAPER_AUTO_TRADING_ENABLED=true 后重启：应看到 "启动模拟盘自动交易"
```

---

## 任务 6：控制 API 端点

**修改文件**：`backend/app/api/routes/paper.py`

在文件末尾追加 4 个自动交易控制端点：

### 6a：查询自动交易状态

```python
@router.get("/auto-trading/status")
def get_auto_trading_status(
    current_user: User = Depends(require_paper_trading),
) -> dict:
    """返回自动交易器的运行状态和最近统计。"""
    from app.services.paper.scheduler import get_auto_trader

    trader = get_auto_trader()
    if trader is None:
        return {"running": False, "reason": "未启动"}
    return {
        "running": trader.state.running,
        "dry_run": trader.state.dry_run,
        "interval_seconds": trader.state.interval_seconds,
        "max_orders_per_cycle": trader.state.max_orders_per_cycle,
        "min_score": trader.state.min_score,
        "last_cycle_at": trader.state.last_cycle_at,
        "last_cycle_duration_ms": trader.state.last_cycle_duration_ms,
        "last_cycle_passed": trader.state.last_cycle_passed,
        "last_cycle_filtered": trader.state.last_cycle_filtered,
        "last_cycle_executed": trader.state.last_cycle_executed,
        "last_cycle_skipped": trader.state.last_cycle_skipped,
        "last_cycle_summary": trader.state.last_cycle_summary,
        "total_cycles": trader.state.total_cycles,
        "total_executed": trader.state.total_executed,
        "total_errors": trader.state.total_errors,
        "circuit_open": trader.state.circuit_open,
        "circuit_reason": trader.state.circuit_reason,
        "circuit_since": trader.state.circuit_since,
        "heartbeat_at": trader.state.heartbeat_at,
    }
```

### 6b：启动自动交易

```python
@router.post("/auto-trading/start")
def start_auto_trading(
    dry_run: bool = Query(True, description="是否以空跑模式启动"),
    current_user: User = Depends(require_paper_trading),
    _admin=Depends(require_admin_auth),
) -> dict:
    """启动模拟盘自动交易（需管理员权限）。"""
    from app.services.paper.scheduler import get_auto_trader, start_auto_trader

    existing = get_auto_trader()
    if existing and existing.state.running:
        return {"started": False, "reason": "已在运行中"}

    settings = get_settings()
    trader = start_auto_trader({
        "dry_run": dry_run,
        "interval_seconds": settings.paper_auto_trading_interval,
        "max_orders_per_cycle": settings.paper_auto_trading_max_orders,
        "min_score": settings.paper_auto_trading_min_score,
    })
    return {"started": True, "dry_run": trader.state.dry_run}
```

### 6c：停止自动交易

```python
@router.post("/auto-trading/stop")
def stop_auto_trading(
    current_user: User = Depends(require_paper_trading),
    _admin=Depends(require_admin_auth),
) -> dict:
    """停止模拟盘自动交易（需管理员权限）。"""
    from app.services.paper.scheduler import stop_auto_trader, get_auto_trader

    trader = get_auto_trader()
    if trader is None or not trader.state.running:
        return {"stopped": False, "reason": "未在运行"}
    stop_auto_trader()
    return {"stopped": True}
```

### 6d：执行一次 dry-run 预览

```python
@router.post("/auto-trading/dry-run")
def dry_run_auto_trading(
    limit: int = Query(20, description="最多检查多少个优先级信号"),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> dict:
    """执行一次空跑预览，返回"将会买入"和"已过滤"的清单（不实际下单）。"""
    from app.services.low_buy.service import LowBuyScreenerService
    from app.services.paper.account import PaperAccountService
    from app.services.paper.admission import AdmissionFilter

    # 获取信号
    screener = LowBuyScreenerService()
    try:
        board = screener.priority_board(db=db, limit=limit)
    except Exception as e:
        return {"error": f"获取优先级信号失败: {e}"}

    if not board or not board.items:
        return {"error": "无优先级信号", "will_buy": [], "filtered": []}

    signals = [item.model_dump() for item in board.items]
    market_direction = board.directional_bias or "neutral"

    # 获取账户
    account_service = PaperAccountService(db)
    account = account_service.get_or_create_default(current_user.id)

    # 持仓和当日订单
    from app.models.entities import PaperPosition, PaperOrder
    from datetime import datetime, time as dt_time

    positions = []
    for p in db.execute(
        select(PaperPosition).where(PaperPosition.account_id == account.id)
    ).scalars().all():
        hold_days = (datetime.now() - p.opened_at).days if p.opened_at else 0
        pct = p.market_value / max(account.total_assets, 1) * 100
        positions.append({"symbol": p.symbol, "hold_days": hold_days, "position_pct": pct})

    today_start = datetime.combine(datetime.now().date(), dt_time.min)
    today_orders = []
    for o in db.execute(
        select(PaperOrder).where(
            PaperOrder.account_id == account.id,
            PaperOrder.created_at >= today_start,
        )
    ).scalars().all():
        today_orders.append({"symbol": o.symbol, "status": o.status})

    # 准入过滤
    adm = AdmissionFilter(min_score=settings.paper_auto_trading_min_score)
    report = adm.evaluate(
        signals=signals,
        existing_positions=positions,
        today_orders=today_orders,
        market_direction=market_direction,
    )

    return {
        "market_state": board.market_state,
        "directional_bias": market_direction,
        "will_buy": [
            {"symbol": r.symbol, "score": r.priority_score, "reason": r.reason}
            for r in report.passed
        ],
        "filtered": [
            {"symbol": r.symbol, "score": r.priority_score, "reason": r.reason}
            for r in report.filtered
        ],
        "summary": report.summary,
    }
```

### 权限设计

- `GET /auto-trading/status`：所有有模拟盘权限的用户可查看
- `POST /auto-trading/start` / `stop`：需要 admin token（安全考虑，避免普通用户误操作）
- `POST /auto-trading/dry-run`：所有有模拟盘权限的用户可执行

### 验证

```bash
# 查看状态
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/paper/auto-trading/status

# 执行 dry-run 预览
curl -X POST -H "Authorization: Bearer <token>" http://localhost:8000/api/paper/auto-trading/dry-run?limit=20

# 启动（需 admin）
curl -X POST -H "Authorization: Bearer <token>" -H "X-Admin-Token: <admin>" \
  "http://localhost:8000/api/paper/auto-trading/start?dry_run=true"
```

---

## 任务 7：集成测试

**新建文件**：`backend/tests/test_paper_auto_trading.py`

```python
"""模拟盘自动交易集成测试。"""
import unittest
from datetime import datetime, time as dt_time


class PaperAutoTradingTest(unittest.TestCase):

    def test_01_imports_work(self):
        """验证所有新模块可正常导入。"""
        from app.services.paper.admission import AdmissionFilter, AdmissionResult
        from app.services.paper.sizing import PositionSizer, SizedOrder
        from app.services.paper.scheduler import PaperAutoTrader, AutoTraderState
        self.assertTrue(callable(AdmissionFilter))
        self.assertTrue(callable(PositionSizer))

    def test_02_admission_filter_empty(self):
        """空信号列表返回空结果。"""
        from app.services.paper.admission import AdmissionFilter
        f = AdmissionFilter(min_score=75)
        r = f.evaluate(signals=[], existing_positions=[], today_orders=[], market_direction="positive_t")
        self.assertEqual(len(r.passed), 0)
        self.assertEqual(len(r.filtered), 0)

    def test_03_admission_score_too_low(self):
        """信号分数低于阈值被过滤。"""
        from app.services.paper.admission import AdmissionFilter
        f = AdmissionFilter(min_score=75)
        signal = {
            "symbol": "000001", "name": "测试",
            "priority_score": 60, "risk_tier": "note",
            "buy_signal_state": "buy_now",
        }
        r = f.evaluate(signals=[signal], existing_positions=[], today_orders=[], market_direction="positive_t")
        self.assertEqual(len(r.passed), 0)
        self.assertIn("调度分60<阈值75", r.filtered[0].reason)

    def test_04_admission_market_negative(self):
        """退潮市场拒绝所有买入。"""
        from app.services.paper.admission import AdmissionFilter
        f = AdmissionFilter(min_score=75)
        signal = {
            "symbol": "000001", "name": "测试",
            "priority_score": 82, "risk_tier": "note",
            "buy_signal_state": "buy_now",
        }
        r = f.evaluate(signals=[signal], existing_positions=[], today_orders=[], market_direction="negative_t")
        self.assertEqual(len(r.passed), 0)
        self.assertIn("退潮", r.filtered[0].reason)

    def test_05_position_sizer_empty(self):
        """零资产时返回空。"""
        from app.services.paper.sizing import PositionSizer
        s = PositionSizer()
        result = s.calculate(candidates=[], total_assets=0, available_cash=0, max_orders=5)
        self.assertEqual(len(result), 0)

    def test_06_position_sizer_normal(self):
        """正常资金应产生100股整数倍的订单。"""
        from app.services.paper.sizing import PositionSizer
        from collections import namedtuple
        s = PositionSizer()
        C = namedtuple("C", ["symbol", "name", "priority_score", "signal"])
        candidates = [
            C("510300", "300ETF", 85, {
                "symbol": "510300", "name": "300ETF",
                "latest_price": 3.478, "strategy_key": "first_board",
                "buy_signal_state": "buy_now", "risk_tier": "note",
            }),
        ]
        result = s.calculate(candidates=candidates, total_assets=100000, available_cash=50000, max_orders=5)
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(result[0].quantity, 100)
        self.assertEqual(result[0].quantity % 100, 0)
        self.assertEqual(result[0].source, "auto")

    def test_07_auto_trader_trading_time(self):
        """验证交易时段判断逻辑。"""
        from app.services.paper.scheduler import PaperAutoTrader
        t = PaperAutoTrader({})
        # 非交易时段（周六）
        self.assertFalse(t._is_trading_time())

    def test_08_auto_trader_state_init(self):
        """验证自动交易器初始状态。"""
        from app.services.paper.scheduler import PaperAutoTrader
        t = PaperAutoTrader({"dry_run": True, "interval_seconds": 120, "max_orders_per_cycle": 5, "min_score": 75})
        self.assertTrue(t.state.dry_run)
        self.assertFalse(t.state.running)
        self.assertEqual(t.state.interval_seconds, 120)
        self.assertEqual(t.state.max_orders_per_cycle, 5)
        self.assertEqual(t.state.min_score, 75)

    def test_09_config_defaults(self):
        """验证配置默认值。"""
        from app.core.config import get_settings
        s = get_settings()
        self.assertFalse(s.paper_auto_trading_enabled,
                         "默认应关闭自动交易")
        self.assertTrue(s.paper_auto_trading_dry_run,
                       "默认应空跑")

    def test_10_planned_order_format(self):
        """验证生成的 planned_order 与 Executor 期望格式兼容。"""
        from app.services.paper.sizing import PositionSizer
        from collections import namedtuple
        s = PositionSizer()
        C = namedtuple("C", ["symbol", "name", "priority_score", "signal"])
        candidates = [
            C("510300", "300ETF", 82, {
                "symbol": "510300", "name": "300ETF",
                "latest_price": 3.5, "strategy_key": "first_board",
                "buy_signal_state": "buy_now", "risk_tier": "note",
            }),
        ]
        result = s.calculate(candidates=candidates, total_assets=100000, available_cash=50000, max_orders=1)
        self.assertEqual(len(result), 1)
        order = result[0]
        # Executor 期望的字段
        required = ["symbol", "name", "side", "order_type", "quantity", "price", "source", "strategy_key"]
        for field_name in required:
            self.assertTrue(hasattr(order, field_name) or field_name in order.__dict__,
                           f"缺少字段: {field_name}")


if __name__ == "__main__":
    unittest.main()
```

### 验证

```bash
cd backend && .venv/bin/python -m pytest tests/test_paper_auto_trading.py -v
# 所有 10 个测试应通过
```

---

## 上线流程

```
步骤 1：部署代码，PAPER_AUTO_TRADING_ENABLED=false（默认）
        ↓
步骤 2：设置 PAPER_AUTO_TRADING_DRY_RUN=true
        PAPER_AUTO_TRADING_ENABLED=true
        重启服务
        ↓
步骤 3：观察 1-2 天 dry-run 日志
        检查 GET /api/paper/auto-trading/status 的 last_cycle_summary
        确认准入过滤逻辑合理
        ↓
步骤 4：生产环境开启（关闭 dry-run）
        PAPER_AUTO_TRADING_DRY_RUN=false
        重启服务
        ↓
步骤 5：持续监控
        - GET /api/paper/auto-trading/status
        - 检查 PaperOrder 中 source="auto" 的订单
        - 观察熔断器是否触发
```

---

## 验收标准

| 检查项 | 通过标准 |
|--------|---------|
| 准入过滤器 | 正确的信号通过，不正确的被拒绝，拒绝理由准确 |
| 仓位计算器 | 下单量是 100 股整数倍，不超过资金上限 |
| 自动交易循环 | 交易时段内每 120s 执行一次 |
| 非交易时段 | 不执行订单，休眠等待 |
| 断线恢复 | akshare 不可用时跳过本轮，不计为错误 |
| 数据库锁 | 重试 3 次后跳过，不触发熔断 |
| 熔断器 | 连续 3 次错误后暂停 300s，之后自动恢复 |
| 心跳 | GET /status 返回最近心跳时间 |
| dry-run 模式 | 显示"将会买入X/过滤Y"但不产生真实订单 |
| 真实执行 | dry_run=False 时产生 PaperOrder（source="auto"） |
| 控制 API | start/stop/status/dry-run 四个端点均可正常调用 |
| 进程重启 | 重启后自动恢复循环（如果 enabled=true） |
| 导入验证 | 所有新模块正常导入，不破坏现有功能 |

---

## 被排除的设计决策

| 方案 | 理由 |
|------|------|
| 引入 Celery/Redis 做任务队列 | 单机部署不需要。TaskManager daemon 线程足够 |
| 独立的自动交易微服务 | 当前单体架构够用，拆分不带来收益 |
| 机器学习动态仓位分配 | V1 用固定比例公式（10% × 30%）足够，后续可迭代 |
| WebSocket 实时推送交易结果 | 轮询 GET /status 在当前规模下足够 |
| 完整的 A 股节假日历库 | 周末判断足够，节假日 akshare 会返回空数据自然跳过 |
| 多账户并行交易 | 当前只有一个默认模拟账户，单账户循环即可 |
| 卖出自动执行 | 卖出逻辑更复杂（止盈/止损/T+1判断），V1 只做买入，卖出后续迭代 |

---

*本方案所有改动为新增功能，不修改任何现有策略逻辑、信号生成、因子计算或业务规则。默认关闭 + 默认 dry-run，对现有部署零影响。*
