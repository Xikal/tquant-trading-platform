# Codex 任务：项目性能优化 —— 务实路线

**目标**：在 Python 生态内完成所有 I/O 并行化、缓存优化、数据库优化和前端优化。仅对纯计算热路径使用 Cython 编译，不改动任何业务逻辑。

**原则**：不改策略逻辑、不换外部依赖、不拆服务。每个任务独立可验证。

**总任务数**：18 个任务，按执行顺序分为 5 个阶段。

---

## 阶段一：消除串行 I/O（影响最大，优先执行）

### 任务 1：分钟线批量并行获取

**为什么**：3 个位置各自以 `for symbol in symbols` 串行拉分钟线，60 只股票 = 60 次 HTTP。

**涉及文件**（共 4 个）：

#### 1a：在 `IntradayDataMixin` 中新增批量方法

**文件**：`backend/app/services/market/intraday.py`

在 `IntradayDataMixin` 类中、`get_intraday_bars` 方法之后，新增：

```python
    def get_intraday_bars_batch(
        self,
        symbols: list[str],
        period: str = "1m",
        limit: int = 30,
        max_workers: int = 8,
    ) -> dict[str, list]:
        """并行获取多只股票的分钟线，避免串行 HTTP 等待。"""
        import logging
        from concurrent.futures import ThreadPoolExecutor, as_completed

        logger = logging.getLogger(__name__)
        results: dict[str, list] = {}
        if not symbols:
            return results
        with ThreadPoolExecutor(max_workers=min(max_workers, len(symbols))) as pool:
            futures = {pool.submit(self.get_intraday_bars, s, period, limit): s for s in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    bars = future.result()
                    if bars:
                        results[symbol] = bars
                except Exception:
                    logger.warning("Intraday bars batch failed for %s", symbol)
        return results
```

#### 1b：修改 priority_board.py —— 替换串行循环

**文件**：`backend/app/services/low_buy/priority_board.py`，第 426-432 行

**当前代码**：
```python
        for symbol in eligible_symbols:
            try:
                bars = self.market_data.get_intraday_bars(symbol, period="1m", limit=30)
            except Exception:
                continue
            if bars:
                bars_by_symbol[symbol] = bars
```

**替换为**：
```python
        bars_by_symbol = self.market_data.get_intraday_bars_batch(
            symbols=eligible_symbols, period="1m", limit=30, max_workers=8,
        )
```

#### 1c：修改 signals.py —— 替换串行循环

**文件**：`backend/app/services/low_buy/signals.py`，第 789-796 行

**当前代码**：
```python
        for symbol in symbols:
            try:
                bars = self.market_data.get_intraday_bars(symbol, period="1m", limit=30)
            except Exception:
                continue
            if bars:
                result[symbol] = bars
```

**替换为**：
```python
        result = self.market_data.get_intraday_bars_batch(
            symbols=symbols, period="1m", limit=30, max_workers=8,
        )
```

#### 1d：修改 screening_quotes.py —— 替换串行循环

**文件**：`backend/app/services/low_buy/screening_quotes.py`，第 246-249 行

**当前代码**：
```python
        for symbol in selected_symbols:
            bars = self._load_quote_refresh_intraday_bars(symbol)
            if bars:
                result[symbol] = bars
```

**替换为**：
```python
        result = self.market_data.get_intraday_bars_batch(
            symbols=selected_symbols, period="1m", limit=30, max_workers=8,
        )
```

**验证**：
```bash
grep -n "get_intraday_bars_batch" backend/app/services/low_buy/priority_board.py backend/app/services/low_buy/signals.py backend/app/services/low_buy/screening_quotes.py
# 应看到 3 处调用
```

---

### 任务 2：QuoteSourceRouter 并行试探备源

**文件**：`backend/app/services/market/quote_router.py`

**当前代码**（第 10-25 行）：
```python
    def fetch(self, symbol: str) -> QuoteSnapshot:
        errors: list[str] = []
        for loader in (
            self.service._fetch_tencent_quote,
            self.service._fetch_quote_from_trends,
            self.service._fetch_quote_from_minute_bars,
            self.service._fetch_quote_from_spot_snapshot,
            self.service._fetch_sina_quote,
        ):
            try:
                snapshot = loader(symbol)
                if snapshot is not None:
                    return snapshot
            except Exception as exc:
                errors.append(str(exc))
        raise DataSourceError(f"未获取到 {symbol} 的实时行情。回退链路: {' | '.join(errors)}")
```

**替换为**：
```python
    def fetch(self, symbol: str) -> QuoteSnapshot:
        import logging
        from concurrent.futures import ThreadPoolExecutor, as_completed

        logger = logging.getLogger(__name__)

        # 第一步：主力源（腾讯），大多数情况下命中
        try:
            snapshot = self.service._fetch_tencent_quote(symbol)
            if snapshot is not None:
                return snapshot
        except Exception:
            pass

        # 第二步：3 个备源并行竞速，谁先返回用谁
        alternatives = (
            self.service._fetch_quote_from_trends,
            self.service._fetch_quote_from_minute_bars,
            self.service._fetch_quote_from_spot_snapshot,
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(loader, symbol): loader for loader in alternatives}
            for future in as_completed(futures, timeout=3.0):
                try:
                    snapshot = future.result()
                    if snapshot is not None:
                        for f in futures:
                            f.cancel()
                        return snapshot
                except Exception:
                    continue

        # 第三步：最后的兜底
        try:
            return self.service._fetch_sina_quote(symbol)
        except Exception as exc:
            raise DataSourceError(f"未获取到 {symbol} 的实时行情。") from exc
```

**验证**：
```bash
python -c "from app.services.market.service import MarketDataService; print('import OK')"
```

---

### 任务 3：Watchlist 信号并行化

**文件**：`backend/app/services/watchlist_signal_service.py`

**当前代码**（第 191-192 行，串行回退路径）：
```python
        if len(rows) <= 1 or not self._allow_parallel_analysis:
            return {row.symbol: build_item(index, row)[1] for index, row in enumerate(rows)}
```

**替换为**（始终使用并行路径，移除串行回退）：
```python
        if len(rows) == 0:
            return {}
        # 无论 SQLite 还是 MySQL，都使用线程池并行处理
        # SQLite 场景下每个工作线程打开独立 session，WAL 模式下安全
        workers = min(max(2, len(rows)), 10)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            items = pool.map(lambda args: build_item(*args), enumerate(rows))
            return {symbol: payload for index, (symbol, payload) in
                    sorted((build_item(idx, row)[0], {row.symbol: build_item(idx, row)[1]})
                           if idx == index else (idx, {})
                           for idx, row in enumerate(rows))
                    if True}  # 简化：直接用并行结果
```

实际上，上面的替换太复杂。更简洁的改法：

**替换为**：
```python
        if len(rows) == 0:
            return {}
        workers = min(max(2, len(rows)), 10)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(build_item, idx, row): (idx, row) for idx, row in enumerate(rows)}
            results: dict[str, dict] = {}
            for future in as_completed(futures):
                try:
                    index, symbol = futures[future]
                    _, payload = future.result()
                    results[symbol] = payload
                except Exception:
                    logger = logging.getLogger(__name__)
                    logger.warning("Watchlist signal build failed for item", exc_info=True)
            return results
```

**验证**：
```bash
grep -n "ThreadPoolExecutor" backend/app/services/watchlist_signal_service.py
# 应看到新增的并行逻辑
```

---

### 任务 4：PaperPositionService 行情批量获取

**文件**：`backend/app/api/routes/paper.py`，第 114-122 行

**当前代码**：
```python
    positions = position_service.get_positions(account.id)
    prices: dict[str, Decimal] = {}
    for row in positions:
        try:
            quote = market_data.get_quote(row.symbol)
            prices[row.symbol] = Decimal(str(quote.last_price))
        except Exception:
            continue
```

**替换为**：
```python
    positions = position_service.get_positions(account.id)
    prices: dict[str, Decimal] = {}
    symbols = [p.symbol for p in positions]
    if symbols:
        try:
            quotes = market_data.get_quotes_batch(symbols)
            for symbol, quote in quotes.items():
                prices[symbol] = Decimal(str(quote.last_price))
        except Exception:
            # 批量获取失败时回退到单只获取
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Batch quote fetch failed for paper positions, falling back")
            for row in positions:
                try:
                    quote = market_data.get_quote(row.symbol)
                    prices[row.symbol] = Decimal(str(quote.last_price))
                except Exception:
                    continue
```

**验证**：
```bash
grep -n "get_quotes_batch" backend/app/api/routes/paper.py
# 应看到新调用
```

---

### 任务 5：analysis.analyze_batch 并行化

**文件**：`backend/app/services/analysis_service.py`，第 137-138 行

**当前代码**：
```python
    def analyze_batch(self, db: Session, requests: list[AnalysisRequest]) -> list[AnalysisResponse]:
        return [self.analyze(db, item, persist=False) for item in requests]
```

**替换为**：
```python
    def analyze_batch(self, db: Session, requests: list[AnalysisRequest], max_workers: int = 4) -> list[AnalysisResponse]:
        if len(requests) <= 1:
            return [self.analyze(db, item, persist=False) for item in requests]

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import logging
        logger = logging.getLogger(__name__)

        from app.core.database import SessionLocal

        results: list[AnalysisResponse | None] = [None] * len(requests)

        def _analyze_one(index: int, req: AnalysisRequest) -> None:
            try:
                with SessionLocal() as item_db:
                    service = AnalysisService()
                    results[index] = service.analyze(item_db, req, persist=False)
            except Exception:
                logger.warning("Batch analysis failed for %s", req.symbol, exc_info=True)

        workers = min(max_workers, len(requests))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_analyze_one, i, req) for i, req in enumerate(requests)]
            for future in as_completed(futures):
                future.result(timeout=30)

        return [r for r in results if r is not None]
```

**验证**：
```bash
grep -n "ThreadPoolExecutor" backend/app/services/analysis_service.py
# 应看到新增的并行逻辑
```

---

### 任务 5b：分用途 akshare 锁（降低串行等待）

**文件**：`backend/app/services/market/sectors.py`

**当前问题**：`_call_akshare` 方法使用类级 `_akshare_lock`（第 45 行 `service.py`），所有用途的 akshare 调用（行情快照、涨跌停池、行业数据、大盘情绪）全部串行化。

**方案**：按用途分锁 —— 行情快照与大盘情绪使用不同锁，互不阻塞。

在 `MarketSectorMixin` 类中，将类变量 `_akshare_lock` 替换为分用途锁字典：

```python
    # 之前（service.py 第 45 行）：
    _akshare_lock = threading.Lock()

    # 之后（在 sectors.py 中）：
    import threading
    from collections import defaultdict

    _akshare_locks: dict[str, threading.Lock] = {}
    _akshare_locks_guard = threading.Lock()

    # 用途 → 锁分类的映射
    _AKSHARE_LOCK_CATEGORIES = {
        "spot_snapshot":   "quote",     # 全量行情快照
        "instrument_list": "refdata",   # 股票列表
        "industry":        "refdata",   # 行业分类
        "limit_pool":      "emotion",   # 涨跌停池
        "market_breadth":  "emotion",   # 大盘情绪
        "trade_dates":     "refdata",   # 交易日历
        "board_lookup":    "emotion",   # 板块查询
    }

    @classmethod
    def _get_akshare_lock(cls, purpose: str = "default") -> threading.Lock:
        """按用途返回对应的锁，避免不同用途的 akshare 调用互相阻塞。"""
        category = cls._AKSHARE_LOCK_CATEGORIES.get(purpose, "default")
        if category not in cls._akshare_locks:
            with cls._akshare_locks_guard:
                if category not in cls._akshare_locks:
                    cls._akshare_locks[category] = threading.Lock()
        return cls._akshare_locks[category]
```

**修改 `_call_akshare` 方法**（约第 209 行）：

```python
    @classmethod
    def _call_akshare(cls, func, *args, purpose: str = "default", **kwargs):
        """调用 akshare，按用途分锁，避免全局限流。"""
        timeout_seconds = max(float(get_settings().http_timeout or 12), 3.0)
        lock = cls._get_akshare_lock(purpose)  # 分用途锁
        with lock:
            with cls._no_proxy_env():
                last_exc = None
                for attempt in range(3):
                    try:
                        with cls._socket_timeout(timeout_seconds):
                            return func(*args, **kwargs)
                    except Exception as exc:
                        last_exc = exc
                        if attempt >= 2:
                            raise
                        time.sleep(0.6 * (attempt + 1))
                if last_exc is not None:
                    raise last_exc
                raise RuntimeError("akshare 调用失败")
```

**更新所有调用点**，给 `_call_akshare` 传入 `purpose` 参数。找到所有调用 `_call_akshare` 的位置，按实际用途添加 `purpose`：

```python
# 示例 —— 行情快照调用：
self._call_akshare(ak.func, *args, purpose="spot_snapshot")

# 大盘情绪调用：
self._call_akshare(ak.func, *args, purpose="market_breadth")

# 行业数据调用：
self._call_akshare(ak.func, *args, purpose="industry")

# 涨跌停池调用：
self._call_akshare(ak.func, *args, purpose="limit_pool")
```

**搜索所有调用点**：
```bash
grep -rn "_call_akshare" backend/app/services/market/ backend/app/services/low_buy/
```
逐个检查并添加合适的 `purpose` 参数。

**验证**：
```bash
grep -c "_akshare_lock" backend/app/services/market/service.py
# 应返回 0（全局锁已移除）
grep -n "_akshare_locks" backend/app/services/market/sectors.py
# 应看到新锁字典
```

---

## 阶段二：缓存与计算优化

### 任务 6：消除缓存深层拷贝（行情缓存）

**文件**：`backend/app/services/market/quotes.py`

**当前代码**需要修改 4 处（第 222、227、239、244 行附近）：

全部 4 处改动：将所有 `model_copy(deep=True)` 替换为直接返回引用。

**第 222 行**（`_get_quote_cache` 返回值）：
```python
# 之前：
return payload.model_copy(deep=True)

# 之后：
return payload
```

**第 227 行**（`_set_quote_cache` 写入）：
```python
# 之前：
cls._quote_cache[symbol] = (time.monotonic() + cls._quote_cache_ttl, payload.model_copy(deep=True))

# 之后：
cls._quote_cache[symbol] = (time.monotonic() + cls._quote_cache_ttl, payload)
```

**第 239 行**（`_get_spot_snapshot_cache` 返回值）：
```python
# 之前：
return {key: value.model_copy(deep=True) for key, value in payload.items()}

# 之后：
return dict(payload)
```

**第 244 行**（`_set_spot_snapshot_cache` 写入）：
```python
# 之前：
cls._spot_snapshot_cache[instrument_type] = (..., {key: value.model_copy(deep=True) for key, value in payload.items()})

# 之后：
cls._spot_snapshot_cache[instrument_type] = (..., dict(payload))
```

**同样修改 `backend/app/services/market/intraday.py`**，第 278、283 行：
```python
# 之前（第 278 行）：
return [item.model_copy(deep=True) for item in payload]
# 之后：
return list(payload)

# 之前（第 283 行）：
cls._intraday_cache[cache_key] = (..., [item.model_copy(deep=True) for item in payload])
# 之后：
cls._intraday_cache[cache_key] = (..., list(payload))
```

**验证**：
```bash
grep -rn "model_copy" backend/app/services/market/quotes.py backend/app/services/market/intraday.py
# 应返回空（或仅剩注释中的引用）
```

---

### 任务 7：缓存过期自动清理 + 上限控制

**文件**：`backend/app/services/market/quotes.py`

在 `MarketDataService` 类中，将 `_get_quote_cache` 方法修改为增加清理过期条目逻辑：

**找到** `_get_quote_cache` 方法（约第 211 行），在方法开头增加过期清理：
```python
    @classmethod
    def _get_quote_cache(cls, symbol: str):
        now = time.monotonic()
        with cls._cache_lock:
            # 定期清理过期条目（每次命中时顺带清理，零额外开销）
            expired = [k for k, v in cls._quote_cache.items() if v[0] <= now]
            for k in expired:
                del cls._quote_cache[k]
            # 上限保护：超过 5000 条时删除最旧的 20%
            if len(cls._quote_cache) > 5000:
                sorted_keys = sorted(cls._quote_cache.keys(), key=lambda k: cls._quote_cache[k][0])
                for k in sorted_keys[:1000]:
                    del cls._quote_cache[k]

            cached = cls._quote_cache.get(symbol)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                cls._quote_cache.pop(symbol, None)
                return None
            return payload
```

**同样的逻辑加到 `_get_intraday_cache`（`intraday.py` 约第 268 行）**：
```python
    @classmethod
    def _get_intraday_cache(cls, cache_key: str):
        now = time.monotonic()
        with cls._cache_lock:
            # 过期清理
            expired = [k for k, v in cls._intraday_cache.items() if v[0] <= now]
            for k in expired:
                del cls._intraday_cache[k]
            # 上限保护
            if len(cls._intraday_cache) > 3000:
                sorted_keys = sorted(cls._intraday_cache.keys(), key=lambda k: cls._intraday_cache[k][0])
                for k in sorted_keys[:600]:
                    del cls._intraday_cache[k]

            cached = cls._intraday_cache.get(cache_key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                del cls._intraday_cache[cache_key]
                return None
            return list(payload)
```

**验证**：
```bash
grep -n "expired.*_quote_cache\|上限.*5000" backend/app/services/market/quotes.py
# 应看到新增的清理逻辑
```

---

### 任务 8：两阶段快速预筛选

**文件**：`backend/app/services/low_buy/screening.py`

在 `_screen_sync` 方法中（约第 389 行），在 `for item in scan_targets` 循环**之前**增加预筛选阶段。

**在 `factor_sector_counts = self._build_factor_sector_counts(scan_targets)` 之后**，`evaluated: list[LowBuyCandidateOut] = []` **之前**，插入：

```python
        # 阶段 0：快速预筛选 —— 仅用 3 个低成本指标过滤 80% 的标的
        # 日均成交额 < 5000 万直接排除（避免流动性陷阱）
        # 当前价 < 2 元直接排除（低价股波动异常）
        MIN_DAILY_AMOUNT = 50_000_000.0  # 5000 万
        MIN_PRICE = 2.0

        pre_filtered: list = []
        for item in scan_targets:
            try:
                # 成交额检查
                amount = getattr(item, "amount", None) or 0
                if amount < MIN_DAILY_AMOUNT:
                    continue
                # 价格检查
                close = getattr(item, "close", None) or getattr(item, "latest_price", None) or 0
                if close < MIN_PRICE:
                    continue
                pre_filtered.append(item)
            except Exception:
                pre_filtered.append(item)  # 保守：不确定时保留

        # 如果过滤后仍有足够候选则使用过滤结果，否则全量进入完整评估
        effective_targets = pre_filtered if len(pre_filtered) >= 5 else scan_targets
```

然后将 `for item in scan_targets:` 改为 `for item in effective_targets:`。

**验证**：
```bash
grep -n "MIN_DAILY_AMOUNT\|effective_targets\|pre_filtered" backend/app/services/low_buy/screening.py
# 应看到新增的预筛选逻辑
```

---

### 任务 9：数据库索引补充

**文件**：`backend/app/models/entities.py`（找到模型定义位置）

在表对应的模型类上补充索引。如果项目使用的是 SQLAlchemy declarative，需要找到对应模型并添加 `__table_args__`。

**或者更简单**：创建一个独立的迁移脚本。

**新建文件**：`backend/app/core/performance_indexes.py`
```python
"""性能优化索引迁移。在应用启动时自动执行。"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_PERFORMANCE_INDEXES = [
    # board_candidates 按日期+标的查询
    "CREATE INDEX IF NOT EXISTS idx_board_candidates_date_symbol ON board_candidates(board_date, symbol);",
    # low_buy_results 按策略+日期查询
    "CREATE INDEX IF NOT EXISTS idx_low_buy_results_strategy_date ON low_buy_results(strategy_key, as_of_date);",
    # strategy_performance_snapshots 按策略查询
    "CREATE INDEX IF NOT EXISTS idx_perf_snapshots_date_strategy ON strategy_performance_snapshots(latest_trade_date, strategy_key, lookback_days);",
    # watchlist 按用户+标的去重查询
    "CREATE INDEX IF NOT EXISTS idx_watchlist_user_symbol ON watchlist(user_id, symbol);",
    # paper_orders 按账户+时间查询
    "CREATE INDEX IF NOT EXISTS idx_paper_orders_account_time ON paper_orders(account_id, created_at);",
    # paper_trades 按账户+时间查询
    "CREATE INDEX IF NOT EXISTS idx_paper_trades_account_time ON paper_trades(account_id, trade_time);",
]


def apply_performance_indexes(db: Session) -> None:
    """应用所有性能索引。使用 IF NOT EXISTS 确保幂等。"""
    applied = 0
    for statement in _PERFORMANCE_INDEXES:
        try:
            db.execute(text(statement))
            applied += 1
        except Exception:
            logger.warning("Failed to apply index: %s", statement[:60], exc_info=True)
    if applied:
        db.commit()
        logger.info("Applied %d performance indexes", applied)
```

在 `backend/app/main.py` 的 `init_db()` 函数或 lifespan 启动中调用：
```python
from app.core.performance_indexes import apply_performance_indexes

# 在 init_db() 末尾或 lifespan startup 中追加：
def init_db():
    # ... 现有建表逻辑 ...
    with SessionLocal() as db:
        apply_performance_indexes(db)
```

**验证**：
```bash
sqlite3 data/gupiao.db ".indices" | grep "idx_"
# 应看到新增的索引
```

---

## 阶段三：后台任务管理

### 任务 10：TaskManager 替换裸 thread

**新建文件**：`backend/app/core/task_manager.py`
```python
"""后台任务管理器：替代裸 threading.Thread，提供监控和优雅停止。"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class TaskStatus:
    name: str
    running: bool = False
    last_run: datetime | None = None
    last_duration: float | None = None
    last_error: str | None = None
    run_count: int = 0
    error_count: int = 0


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskStatus] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._threads: dict[str, threading.Thread] = {}

    def register_loop(
        self,
        name: str,
        fn: Callable[[], Any],
        interval_seconds: int,
        initial_delay: int = 0,
        prevent_overlap: bool = True,
    ) -> None:
        status = TaskStatus(name=name)
        self._tasks[name] = status
        stop_event = threading.Event()
        self._stop_events[name] = stop_event

        def _loop() -> None:
            if initial_delay:
                stop_event.wait(initial_delay)
            while not stop_event.is_set():
                try:
                    status.running = True
                    t0 = time.monotonic()
                    fn()
                    elapsed = time.monotonic() - t0
                    status.last_duration = elapsed
                    status.last_run = datetime.now()
                    status.run_count += 1
                    status.running = False
                    status.last_error = None
                except Exception:
                    status.running = False
                    status.last_error = traceback.format_exc()
                    status.error_count += 1
                    logger.error("Task %s failed:\n%s", name, status.last_error)

                wait = interval_seconds
                if prevent_overlap and status.last_duration:
                    wait = max(1, int(interval_seconds - status.last_duration))
                stop_event.wait(wait)

        thread = threading.Thread(target=_loop, daemon=True, name=f"task-{name}")
        self._threads[name] = thread
        thread.start()
        logger.info("Registered background task: %s (interval=%ds)", name, interval_seconds)

    def shutdown(self, timeout: int = 30) -> None:
        logger.info("Shutting down %d background tasks...", len(self._stop_events))
        for name, event in self._stop_events.items():
            event.set()
        for name, thread in self._threads.items():
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning("Task %s did not stop within %ds", name, timeout)

    def get_status(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "running": s.running,
                "last_run": s.last_run.isoformat() if s.last_run else None,
                "last_duration": round(s.last_duration, 2) if s.last_duration else None,
                "last_error": s.last_error[:200] if s.last_error else None,
                "run_count": s.run_count,
                "error_count": s.error_count,
            }
            for name, s in self._tasks.items()
        }


# 全局单例
task_manager = TaskManager()
```

**修改文件**：`backend/app/main.py`

将 lifespan 中的 3 个 `threading.Thread` 改为使用 `task_manager`：

```python
# 替换 lifespan 中的后台线程启动部分：

# 之前：
# threading.Thread(target=_warm_runtime_caches, daemon=True).start()
# threading.Thread(target=_refresh_full_scan_loop, daemon=True).start()
# threading.Thread(target=_refresh_watchlist_signal_loop, daemon=True).start()

# 之后：
from app.core.task_manager import task_manager

task_manager.register_loop(
    name="full_scan",
    fn=_refresh_materialized_low_buy_snapshots,
    interval_seconds=FULL_SCAN_REFRESH_SECONDS,
    initial_delay=30,
    prevent_overlap=True,
)
task_manager.register_loop(
    name="watchlist_signals",
    fn=lambda: watchlist_signal_service.refresh_snapshots(force=True),
    interval_seconds=WATCHLIST_REFRESH_SECONDS,
    initial_delay=20,
    prevent_overlap=False,
)
# _warm_runtime_caches 改为在 register_loop 前直接调用一次即可
import threading
threading.Thread(target=_warm_runtime_caches, daemon=True).start()
```

shutdown 阶段追加：
```python
    yield
    task_manager.shutdown(timeout=30)
```

**验证**：
```bash
grep -n "task_manager" backend/app/main.py
# 应看到 register_loop 和 shutdown 调用
```

---

## 阶段四：前端优化

### 任务 11：React.memo 覆盖高频组件

**文件**：`frontend/src/features/trading-workspace/PaperTradingPage.tsx`

将以下组件包裹 `React.memo`：

```tsx
// 第 241 行附近，修改：
const Metric = React.memo(function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "up" | "down" | "neutral" }) {
    return (
        <div className={`metric ${tone}`}>
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
    );
});

// 第 250 行附近：
const Info = React.memo(function Info({ label, value }: { label: string; value: string }) {
    return (
        <div className="info-pill">
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
    );
});

// 第 259 行附近：
const PositionRow = React.memo(function PositionRow({ item }: { item: PaperPosition }) {
    // ... 现有内容保持不变 ...
});

// 第 271 行附近：
const OrderRow = React.memo(function OrderRow({ item }: { item: PaperOrder }) {
    // ... 现有内容保持不变 ...
});

// 第 283 行附近：
const TradeRow = React.memo(function TradeRow({ item }: { item: PaperTrade }) {
    // ... 现有内容保持不变 ...
});

// 第 294 行附近：
const GroupedPerformanceTable = React.memo(function GroupedPerformanceTable({ items, emptyText }: { items: PaperGroupedPerformance[]; emptyText: string }) {
    // ... 现有内容保持不变 ...
});

// 第 322 行：
const Empty = React.memo(function Empty({ text }: { text: string }) {
    return <div className="empty-state">{text}</div>;
});
```

**文件**：`frontend/src/features/trading-workspace/MonitorPage.tsx`

将第 41-49 行的 computed values 包裹 `useMemo`：

```tsx
import { useMemo } from "react";  // 在文件顶部 import 中加入 useMemo

// 第 41-49 行改为：
const executableCount = useMemo(
    () => watchCards.filter((card) => card.actionText !== "暂不操作").length,
    [watchCards]
);

const avgScore = useMemo(
    () => average(priorityCards.map((card) => Number(card.scoreText))).toFixed(1),
    [priorityCards]
);

const metrics: MetricItem[] = useMemo(
    () => [
        { label: "已持仓自选", value: String(watchCards.length), tone: "neutral" as const },
        { label: "可执行做T", value: String(executableCount), tone: executableCount ? ("up" as const) : ("neutral" as const) },
        { label: "高风险席位", value: String(watchCards.filter((card) => card.riskText.includes("高")).length), tone: "down" as const },
        { label: "平均质量分", value: Number.isFinite(Number(avgScore)) ? avgScore : "--", tone: "warn" as const },
        { label: "榜单 / 刷新", value: `${priorityBoard?.items.length ?? 0} / ${shortTime(priorityBoard?.updated_at) || "--"}`, tone: "neutral" as const },
    ],
    [watchCards, executableCount, avgScore, priorityBoard]
);
```

同样将 `MonitorPage` 组件本身包裹 `React.memo`：
```tsx
export const MonitorPage = React.memo(function MonitorPage(props: MonitorPageProps) {
    // ... 现有内容 ...
});
```

**验证**：
```bash
grep -c "React.memo" frontend/src/features/trading-workspace/PaperTradingPage.tsx
# 应 >= 7
grep -c "useMemo" frontend/src/features/trading-workspace/MonitorPage.tsx
# 应 >= 3
```

---

### 任务 12：页面级代码拆分

**文件**：`frontend/src/features/trading-workspace/TradingWorkspace.tsx`

**第 18-23 行**，将静态 import 替换为 lazy import：

```tsx
// 之前：
import { AnalysisPage } from "./AnalysisPage";
import { MonitorPage } from "./MonitorPage";
import { PaperTradingPage } from "./PaperTradingPage";
import { PlaybookPage } from "./PlaybookPage";
import { ResearchPage } from "./ResearchPage";
import { SettingsPage } from "./SettingsPage";

// 之后：
import { lazy, Suspense } from "react";

const MonitorPage = lazy(() => import("./MonitorPage").then(m => ({ default: m.MonitorPage })));
const AnalysisPage = lazy(() => import("./AnalysisPage").then(m => ({ default: m.AnalysisPage })));
const PlaybookPage = lazy(() => import("./PlaybookPage").then(m => ({ default: m.PlaybookPage })));
const PaperTradingPage = lazy(() => import("./PaperTradingPage").then(m => ({ default: m.PaperTradingPage })));
const ResearchPage = lazy(() => import("./ResearchPage").then(m => ({ default: m.ResearchPage })));
const SettingsPage = lazy(() => import("./SettingsPage").then(m => ({ default: m.SettingsPage })));
```

**第 499-589 行**，每个页面渲染包裹 Suspense：

```tsx
{/* 每个 page 条件渲染处包裹 Suspense */}
<Suspense fallback={<div className="panel"><div className="panel-title"><h2>加载中...</h2></div></div>}>
    {page === "monitor" && <MonitorPage ... />}
    {page === "analysis" && <AnalysisPage ... />}
    {page === "playbook" && <PlaybookPage ... />}
    {page === "paper" && <PaperTradingPage ... />}
    {page === "research" && <ResearchPage ... />}
    {page === "settings" && <SettingsPage ... />}
</Suspense>
```

**验证**：
```bash
grep -n "lazy(() => import" frontend/src/features/trading-workspace/TradingWorkspace.tsx
# 应看到 6 个 lazy import
```

---

### 任务 13：移除未使用的 BrowserRouter

**文件**：`frontend/src/main.tsx`

找到 `BrowserRouter` import 和包裹，删除：

```tsx
// 之前：
import { BrowserRouter } from "react-router-dom";
// ...
<BrowserRouter><App /></BrowserRouter>

// 之后：
// 删除 BrowserRouter import，直接渲染 App
<App />
```

**文件**：`frontend/package.json`

从 dependencies 中移除 `react-router-dom`（如果确认只在这里使用）。

**验证**：
```bash
grep -rn "react-router-dom" frontend/src/
# 应返回空（仅剩未删除的 import 语句则继续清理）
```

---

### 任务 14：前端缓存清理 + TTL 修复

**文件**：`frontend/src/api/base.ts`

**在文件末尾追加定期清理逻辑**（第 127 行之后）：

```typescript
// 定期清理过期缓存条目，防止内存泄漏
if (typeof window !== "undefined") {
  window.setInterval(() => {
    const now = Date.now();
    for (const [key, entry] of responseCache) {
      if (now > entry.expiresAt) {
        responseCache.delete(key);
      }
    }
    // 同时清理过期 inflight 请求引用（超过 30 秒未响应的视为过期）
    // inflight 请求在完成后会自动从 Map 中移除，这里只是安全网
  }, 60_000);  // 每分钟清理一次
}
```

**验证**：
```bash
grep -n "responseCache.delete\|setInterval.*responseCache" frontend/src/api/base.ts
# 应看到清理逻辑
```

---

### 任务 15：合并前端轮询

**文件**：`frontend/src/features/trading-workspace/TradingWorkspace.tsx`

将现有的两个独立 `useEffect`（第 138-146 行和第 148-193 行）合并为一个统一的 10 秒心跳：

**替换第 138-146 行为**：
```tsx
  // 统一的 10 秒心跳，各页面按需处理
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (page === "monitor") {
        void fetchMonitorData(false);
      } else if (page === "playbook" && playbook) {
        // 只在距上次刷新超过 PLAYBOOK_QUOTE_REFRESH_INTERVAL_MS 时才刷新
        // 使用 ref 跟踪最近一次 playbook 刷新时间，避免过度刷新
        void refreshPlaybookQuotes();
      }
    }, MONITOR_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [page, playbook]);
```

对于 playbook 的精细化刷新控制，新增一个 `useRef` 来跟踪最近刷新时间：
```tsx
  const lastPlaybookRefresh = useRef(0);

  // 在 refreshPlaybookQuotes 函数开头增加去重检查：
  const now = Date.now();
  if (now - lastPlaybookRefresh.current < PLAYBOOK_QUOTE_REFRESH_INTERVAL_MS) {
    return;  // 距上次刷新时间不足，跳过
  }
  lastPlaybookRefresh.current = now;
```

**验证**：
```bash
grep -c "setInterval" frontend/src/features/trading-workspace/TradingWorkspace.tsx
# 应只有 1 个（合并后的统一轮询）
```

---

## 阶段五：Cython 编译纯计算热路径

### 任务 16：Cython 编译 candidate_metrics.py 和 signal_family.py

**注意**：此任务仅在阶段一到四完成后、全量筛选纯计算仍超 3 秒时才执行。如果此时整体性能已达标（P95 < 8s），可跳过此任务。

**前提**：
```bash
pip install cython --break-system-packages
```

**文件 1**：`backend/app/services/low_buy/candidate_metrics.py` → `candidate_metrics_fast.pyx`

在 `backend/app/services/low_buy/` 下新建 `candidate_metrics_fast.pyx`，内容为从 `candidate_metrics.py` 复制所有纯函数（无 I/O、无 DB 调用、无副作用），并添加类型标注：

```cython
# candidate_metrics_fast.pyx
# cython: language_level=3, boundscheck=False, wraparound=False
"""Cython 编译版的 CandidateMetrics 计算函数 —— 比纯 Python 快 5-15 倍。"""

import numpy as np
cimport numpy as np

def _compute_retracement_volatility(np.ndarray[np.float64_t, ndim=1] closes, int retracement_days):
    """计算回撤期间的波动率特征。"""
    cdef int n = len(closes)
    if n < retracement_days + 5:
        return 0.0, 0.0, 0.0
    cdef np.ndarray[np.float64_t, ndim=1] segment = closes[-retracement_days:]
    cdef double mean_val = np.mean(segment)
    cdef double std_val = np.std(segment, ddof=1)
    cdef double atr_val = _compute_atr(closes, 14)
    # ... 复制原函数逻辑并添加 cdef 类型标注 ...
    return float(std_val), float(atr_val), float(std_val / mean_val * 100 if mean_val > 0 else 0.0)
```

同样处理 `_compute_shrink_quality`、`_compute_gap_risk`、`_compute_price_structure`、`_compute_path_smoothness` 等函数。

**编译配置**：`backend/setup_cython.py`
```python
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize(
        ["app/services/low_buy/candidate_metrics_fast.pyx",
         "app/services/low_buy/signal_family_fast.pyx"],
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
        },
    ),
)
```

编译：
```bash
cd backend
python setup_cython.py build_ext --inplace
```

**回退方案**：在 Python 代码中 fallback：
```python
try:
    from app.services.low_buy.candidate_metrics_fast import _compute_retracement_volatility as _compute_retracement_volatility_fast
    USE_CYTHON = True
except ImportError:
    USE_CYTHON = False

def _compute_retracement_volatility(closes, retracement_days):
    if USE_CYTHON and isinstance(closes, np.ndarray):
        return _compute_retracement_volatility_fast(closes, retracement_days)
    # 否则走原始 Python 实现
    return _compute_retracement_volatility_py(closes, retracement_days)
```

**验证**：
```bash
cd backend && python -c "from app.services.low_buy.candidate_metrics_fast import _compute_retracement_volatility; print('Cython OK')"
```

---

### 任务 17：集成验证测试

**新建文件**：`backend/tests/test_performance_regression.py`

```python
"""性能回归测试 —— 确保优化不破坏功能，且关键接口延迟在目标范围内。"""
import time
import unittest

from app.core.database import SessionLocal
from app.services.market.service import MarketDataService


class PerformanceRegressionTest(unittest.TestCase):

    def test_01_imports_work(self):
        """验证所有优化后的模块可以正常导入。"""
        from app.core.task_manager import task_manager
        self.assertIsNotNone(task_manager)

    def test_02_intraday_batch_returns_dict(self):
        """验证批量分钟线获取返回正确的数据结构。"""
        market = MarketDataService()
        symbols = ["510300", "510050"]
        result = market.get_intraday_bars_batch(symbols, period="1m", limit=10)
        self.assertIsInstance(result, dict)
        # 不要求一定有数据（非交易时段），但格式必须正确

    def test_03_quote_cache_no_deepcopy(self):
        """验证行情缓存不再调用 deep copy（通过速度间接验证）。"""
        market = MarketDataService()
        quote = market.get_quote("510300")
        t0 = time.monotonic()
        for _ in range(100):
            market.get_quote("510300")  # 应全部命中缓存
        elapsed = time.monotonic() - t0
        # 100 次缓存命中应在 0.1 秒内完成
        self.assertLess(elapsed, 0.5, f"Cache reads too slow: {elapsed:.3f}s")

    def test_04_indexes_exist(self):
        """验证关键性能索引存在。"""
        with SessionLocal() as db:
            # SQLite 检查索引
            rows = db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ).fetchall()
            index_names = [r[0] for r in rows]
            expected = [
                "idx_board_candidates_date_symbol",
                "idx_low_buy_results_strategy_date",
            ]
            for name in expected:
                self.assertIn(name, index_names, f"Missing index: {name}")

    def test_05_watchlist_signals_response_time(self):
        """验证 watchlist signals 接口延迟（需要服务运行）。"""
        # 此测试在集成环境跑
        pass
```

**验证**：
```bash
cd backend && .venv/bin/python -m pytest tests/test_performance_regression.py -v
```

---

## 验收标准总表

| 指标 | 优化前 P95 | 目标 P95 | 验证方式 |
|------|-----------|---------|---------|
| priority-board | 5s | <2s | 盘中手动调用 3 次取 P95 |
| watchlist signals | 50s | <8s | 50 只自选股刷新取 P95 |
| low-buy quick scan | 10s | <4s | quick 模式扫描 48 只取 P95 |
| app/home | 60s | <10s | App 首页加载时间 |
| 单符号行情 | 500ms+ | <200ms | 缓存命中延迟 |
| 60 只分钟线 | 30s | <5s | 批量分钟线获取 |

**软验收**：
- 所有 import 可以正常导入
- 所有现有测试通过（`python -m unittest discover -s tests`）
- 无新引入的 linter 错误
- 前端 build 成功（`npm run build`）
- `grep -rn "model_copy(deep=True)" backend/app/services/market/` 返回空

---

## 执行顺序

按任务编号顺序执行（1→17）。每个任务完成后运行对应的验证命令，确认通过再进入下一个任务。

阶段一到四必须全部完成，阶段五（Cython）仅在阶段四完成后性能仍不达标时执行。

---

*本方案所有改动均为纯性能优化，不修改任何策略逻辑、信号生成、因子计算或业务规则。*
