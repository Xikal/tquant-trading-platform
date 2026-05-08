from __future__ import annotations

import threading

from app.core.config import get_settings
from app.core.timezone import utc_now_naive
from app.services.market.shared import (
    Instrument,
    MarketEventCache,
    MarketEventOut,
    MicrostructureSnapshot,
    SectorSnapshot,
    contextmanager,
    datetime,
    delete,
    os,
    select,
    time,
)


class MarketSectorMixin:
    _AKSHARE_LOCK_CATEGORIES = {
        "default",
        "spot_snapshot",
        "minute_bars",
        "limit_pool",
        "trade_dates",
        "market_breadth",
        "industry",
        "daily_history",
        "news",
        "notice",
        "emotion",
    }
    _akshare_locks: dict[str, threading.Lock] = {
        category: threading.Lock() for category in _AKSHARE_LOCK_CATEGORIES
    }
    _akshare_locks_guard = threading.Lock()

    @staticmethod
    @contextmanager
    def _socket_timeout(timeout_seconds: float):
        # Do not mutate the process-wide socket default timeout from request
        # paths. Provider-level clients must own explicit timeout behavior.
        _ = timeout_seconds
        yield

    def get_sector_snapshot(self, instrument: Instrument, bars, use_board_lookup: bool = True) -> SectorSnapshot:
        market_strength = self._compute_market_strength(bars)
        sector_strength = market_strength
        notes = "当前为市场基准联动分析。"
        sector_name = instrument.sector_name or f"{instrument.market} 市场基准"
        if instrument.instrument_type == "etf":
            sector_strength += 4
            sector_name = instrument.sector_name or "ETF / 指数代理"
            notes = "ETF 使用主题代理联动评分。"
            alignment = max(0.0, min(100.0, (sector_strength + market_strength) / 2))
            return SectorSnapshot(sector_name=sector_name, sector_strength=round(max(0.0, min(100.0, sector_strength)), 2), market_strength=round(max(0.0, min(100.0, market_strength)), 2), alignment_score=round(alignment, 2), notes=notes)
        board_row = self._lookup_sector_board(sector_name) if use_board_lookup else None
        if board_row is not None:
            sector_strength = self._compute_board_strength(board_row)
            sector_name = self._board_sector_name(board_row, fallback=sector_name)
            notes = f"行业联动来自行业板块数据：{sector_name}。"
        elif instrument.market == "SZ" and instrument.symbol.startswith("30"):
            sector_strength += 2
            sector_name = instrument.sector_name or "创业板代理"
            notes = "缺少行业映射时，以创业成长风格作为代理。"
        elif instrument.market == "SH" and instrument.symbol.startswith("68"):
            sector_strength += 2
            sector_name = instrument.sector_name or "科创板代理"
            notes = "缺少行业映射时，以科创风格作为代理。"
        elif not use_board_lookup:
            notes = "回测模式下使用轻量板块代理评分。"
        alignment = max(0.0, min(100.0, (sector_strength + market_strength) / 2))
        return SectorSnapshot(sector_name=sector_name, sector_strength=round(max(0.0, min(100.0, sector_strength)), 2), market_strength=round(max(0.0, min(100.0, market_strength)), 2), alignment_score=round(alignment, 2), notes=notes)

    def get_sector_heatmap(self, limit: int = 30) -> list[SectorSnapshot]:
        result = self.provider_router.fetch_sector_heatmap()
        if result.usable and result.data:
            return list(result.data)[:limit]
        return []

    def _board_breadth_frame_from_provider(self):
        result = self.provider_router.fetch_board_breadth_frame()
        if not result.usable or result.data is None or result.data.empty:
            return None
        return result.data

    def get_market_events(self, db, symbol: str, quote) -> list[MarketEventOut]:
        events = self._load_or_refresh_cached_events(db, symbol)
        if abs(quote.change_pct) >= 7:
            events.append(MarketEventOut(title="价格波动异常", risk_level="high", description="日内涨跌幅较大，做T需收紧仓位和止损。", source="system", event_time=quote.timestamp))
        if (quote.volume_ratio or 0) >= 2.5:
            events.append(MarketEventOut(title="量能放大", risk_level="medium", description="量比显著放大，需警惕情绪驱动型冲高回落。", source="system", event_time=quote.timestamp))
        return events

    def get_microstructure(self, quote, bars, enabled: bool = True) -> MicrostructureSnapshot:
        if not enabled:
            return MicrostructureSnapshot(available=False, notes="已在系统配置中关闭盘口增强模块。")
        if not bars:
            return MicrostructureSnapshot(available=False, notes="暂无足够的分时数据。")
        price_range = max(quote.high_price - quote.low_price, 0.01)
        buy_pressure = max(0.0, min(100.0, ((quote.last_price - quote.low_price) / price_range) * 100))
        return MicrostructureSnapshot(available=True, buy_pressure=round(buy_pressure, 2), sell_pressure=round(100 - buy_pressure, 2), large_order_flow=round(((quote.volume_ratio or 1.0) - 1) * 15, 2), notes="免费数据源下使用价格位置和量能近似盘口压力。")

    def _load_or_refresh_cached_events(self, db, symbol: str) -> list[MarketEventOut]:
        threshold = utc_now_naive() - __import__("datetime").timedelta(hours=3)
        rows = db.execute(select(MarketEventCache).where(MarketEventCache.symbol == symbol).order_by(MarketEventCache.id.desc())).scalars().all()
        if rows and rows[0].created_at >= threshold:
            return [MarketEventOut(title=row.title, risk_level=row.risk_level, description=row.description, source=row.source, event_time=row.event_time) for row in rows]
        fetched = self._fetch_market_events(symbol)
        if fetched:
            db.execute(delete(MarketEventCache).where(MarketEventCache.symbol == symbol))
            for event in fetched:
                db.add(MarketEventCache(symbol=symbol, title=event.title, risk_level=event.risk_level, description=event.description, source=event.source, event_time=event.event_time))
            db.commit()
            return fetched
        return []

    def _fetch_market_events(self, symbol: str) -> list[MarketEventOut]:
        result = self.provider_router.fetch_market_events(symbol)
        if result.usable and result.data:
            return list(result.data)[:8]
        return []

    def _lookup_sector_board(self, sector_name: str):
        if not sector_name:
            return None
        if sector_name in self._sector_board_cache:
            return self._sector_board_cache[sector_name]
        try:
            df = self._board_breadth_frame_from_provider()
        except Exception:
            return None
        if df is None or df.empty:
            return None
        name_column = "industry" if "industry" in df else "板块名称"
        exact = df[df[name_column] == sector_name]
        if not exact.empty:
            result = exact.iloc[0].to_dict()
            self._sector_board_cache[sector_name] = result
            return result
        for alias in self._sector_aliases(sector_name):
            matched = df[df[name_column].astype(str).str.contains(alias, na=False)]
            if not matched.empty:
                result = matched.iloc[0].to_dict()
                self._sector_board_cache[sector_name] = result
                return result
        self._sector_board_cache[sector_name] = None
        return None

    @staticmethod
    def _sector_aliases(sector_name: str) -> list[str]:
        alias_map = {"半导体/芯片": ["半导体", "电子元件"], "国防军工": ["航天航空", "船舶制造"], "医药": ["医药商业", "化学制药", "医疗器械"], "新能源": ["光伏设备", "电池", "能源金属"], "消费": ["酿酒行业", "食品饮料", "商业百货"], "券商/证券": ["证券"], "银行": ["银行"], "宽基": ["上证指数", "深证成指"], "成长风格": ["创业板综"], "科创成长": ["科创板做市"]}
        return alias_map.get(sector_name, [sector_name])

    @staticmethod
    def _compute_board_strength(row: dict[str, object]) -> float:
        if "change_pct" in row:
            change_pct = float(row.get("change_pct") or 0)
            return round(max(0.0, min(100.0, 50.0 + change_pct * 8.0)), 2)
        rise_count = float(row.get("上涨家数") or 0)
        fall_count = float(row.get("下跌家数") or 0)
        total = max(rise_count + fall_count, 1.0)
        breadth = (rise_count - fall_count) / total * 18
        change_pct = float(row.get("涨跌幅") or 0)
        leader = float(row.get("领涨股票-涨跌幅") or 0)
        turnover = float(row.get("换手率") or 0)
        score = 50 + change_pct * 5 + breadth + leader * 0.8 + turnover * 1.2
        return round(max(0.0, min(100.0, score)), 2)

    @staticmethod
    def _board_sector_name(row: dict[str, object], fallback: str = "") -> str:
        for key in ("板块名称", "industry", "sector_name", "name", "名称", "行业"):
            value = row.get(key)
            if value not in (None, "", "-", "--"):
                return str(value)
        return fallback or "未分类行业"

    @staticmethod
    @contextmanager
    def _no_proxy_env():
        proxy_keys = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]
        backup = {key: os.environ.get(key) for key in proxy_keys}
        try:
            for key in proxy_keys:
                os.environ.pop(key, None)
            yield
        finally:
            for key, value in backup.items():
                if value is not None:
                    os.environ[key] = value

    @classmethod
    def _get_akshare_lock(cls, purpose: str) -> threading.Lock:
        key = purpose if purpose in cls._AKSHARE_LOCK_CATEGORIES else "default"
        lock = cls._akshare_locks.get(key)
        if lock is not None:
            return lock
        with cls._akshare_locks_guard:
            return cls._akshare_locks.setdefault(key, threading.Lock())

    @classmethod
    def _call_akshare(cls, func, *args, purpose: str = "default", **kwargs):
        timeout_seconds = max(float(get_settings().akshare_timeout_seconds or 12), 3.0)
        with cls._get_akshare_lock(purpose):
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

    @staticmethod
    def _compute_market_strength(bars) -> float:
        if len(bars) < 20:
            return 50.0
        closes = [bar.close for bar in bars]
        ma20 = sum(closes[-20:]) / 20
        slope = (closes[-1] - closes[-10]) / max(closes[-10], 0.01) * 100
        relative = (closes[-1] - ma20) / max(ma20, 0.01) * 100
        return round(max(0.0, min(100.0, 50 + slope * 2.2 + relative * 3)), 2)
