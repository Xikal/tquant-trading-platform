from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.core.timezone import utc_now_naive
from app.services.market.parameter_defaults import MARKET_SECTOR_PROXY_DEFAULTS
from app.services.market.shared import (
    Instrument,
    MarketEventCache,
    MarketEventOut,
    MicrostructureSnapshot,
    SectorSnapshot,
    delete,
    select,
)


class MarketSectorMixin:
    def get_sector_snapshot(self, instrument: Instrument, bars, use_board_lookup: bool = True) -> SectorSnapshot:
        params = _sector_proxy_params()
        market_strength = self._compute_market_strength(bars)
        sector_strength = market_strength
        notes = "当前为市场基准联动分析。"
        sector_name = instrument.sector_name or f"{instrument.market} 市场基准"
        if instrument.instrument_type == "etf":
            sector_strength += _float_param(params, "etf_strength_bonus")
            sector_name = instrument.sector_name or "ETF / 指数代理"
            notes = "ETF 使用主题代理联动评分。"
            alignment = _clamp_score((sector_strength + market_strength) / 2, params)
            return SectorSnapshot(sector_name=sector_name, sector_strength=round(_clamp_score(sector_strength, params), 2), market_strength=round(_clamp_score(market_strength, params), 2), alignment_score=round(alignment, 2), notes=notes)
        board_row = self._lookup_sector_board(sector_name) if use_board_lookup else None
        if board_row is not None:
            sector_strength = self._compute_board_strength(board_row)
            sector_name = self._board_sector_name(board_row, fallback=sector_name)
            notes = f"行业联动来自行业板块数据：{sector_name}。"
        elif instrument.market == "SZ" and instrument.symbol.startswith("30"):
            sector_strength += _float_param(params, "growth_board_bonus")
            sector_name = instrument.sector_name or "创业板代理"
            notes = "缺少行业映射时，以创业成长风格作为代理。"
        elif instrument.market == "SH" and instrument.symbol.startswith("68"):
            sector_strength += _float_param(params, "growth_board_bonus")
            sector_name = instrument.sector_name or "科创板代理"
            notes = "缺少行业映射时，以科创风格作为代理。"
        elif not use_board_lookup:
            notes = "回测模式下使用轻量板块代理评分。"
        alignment = _clamp_score((sector_strength + market_strength) / 2, params)
        return SectorSnapshot(sector_name=sector_name, sector_strength=round(_clamp_score(sector_strength, params), 2), market_strength=round(_clamp_score(market_strength, params), 2), alignment_score=round(alignment, 2), notes=notes)

    def get_sector_heatmap(self, limit: int = 30) -> list[SectorSnapshot]:
        result = self.provider_router.fetch_sector_heatmap()
        if result.usable and result.data:
            return list(result.data)[:limit]
        return []

    def sector_relative_strength_rank(self, db, limit: int = 8, per_sector_limit: int = 10):
        from app.services.market.sector_relative_strength import build_sector_relative_strength_rank

        regime = self.get_market_regime_fast()
        return build_sector_relative_strength_rank(
            db,
            hot_sectors=list(getattr(regime, "hot_industries", []) or []),
            sector_limit=limit,
            per_sector_limit=per_sector_limit,
        )

    def _board_breadth_frame_from_provider(self):
        result = self.provider_router.fetch_board_breadth_frame()
        if not result.usable or result.data is None or result.data.empty:
            return None
        return result.data

    def get_market_events(self, db, symbol: str, quote) -> list[MarketEventOut]:
        params = _sector_proxy_params()
        events = self._load_or_refresh_cached_events(db, symbol)
        if abs(quote.change_pct) >= _float_param(params, "event_change_high_threshold_pct"):
            events.append(MarketEventOut(title="价格波动异常", risk_level="high", description="日内涨跌幅较大，做T需收紧仓位和止损。", source="system", event_time=quote.timestamp))
        if (quote.volume_ratio or 0) >= _float_param(params, "event_volume_ratio_threshold"):
            events.append(MarketEventOut(title="量能放大", risk_level="medium", description="量比显著放大，需警惕情绪驱动型冲高回落。", source="system", event_time=quote.timestamp))
        return events

    def get_microstructure(self, quote, bars, enabled: bool = True) -> MicrostructureSnapshot:
        params = _sector_proxy_params()
        if not enabled:
            return MicrostructureSnapshot(available=False, notes="已在系统配置中关闭盘口增强模块。")
        if not bars:
            return MicrostructureSnapshot(available=False, notes="暂无足够的分时数据。")
        price_range = max(quote.high_price - quote.low_price, _float_param(params, "micro_min_price_range"))
        buy_pressure = _clamp_score(((quote.last_price - quote.low_price) / price_range) * 100, params)
        large_order_flow = ((quote.volume_ratio or _float_param(params, "micro_default_volume_ratio")) - 1) * _float_param(params, "micro_large_order_weight")
        return MicrostructureSnapshot(available=True, buy_pressure=round(buy_pressure, 2), sell_pressure=round(100 - buy_pressure, 2), large_order_flow=round(large_order_flow, 2), notes="免费数据源下使用价格位置和量能近似盘口压力。")

    def _load_or_refresh_cached_events(self, db, symbol: str) -> list[MarketEventOut]:
        params = _sector_proxy_params()
        threshold = utc_now_naive() - timedelta(hours=_float_param(params, "event_cache_hours"))
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
        params = _sector_proxy_params()
        if "change_pct" in row:
            change_pct = float(row.get("change_pct") or 0)
            return round(_clamp_score(_float_param(params, "board_change_base_score") + change_pct * _float_param(params, "board_change_weight"), params), 2)
        rise_count = float(row.get("上涨家数") or 0)
        fall_count = float(row.get("下跌家数") or 0)
        total = max(rise_count + fall_count, 1.0)
        breadth = (rise_count - fall_count) / total * _float_param(params, "board_breadth_weight")
        change_pct = float(row.get("涨跌幅") or 0)
        leader = float(row.get("领涨股票-涨跌幅") or 0)
        turnover = float(row.get("换手率") or 0)
        score = (
            _float_param(params, "board_change_base_score")
            + change_pct * _float_param(params, "board_change_pct_weight")
            + breadth
            + leader * _float_param(params, "board_leader_weight")
            + turnover * _float_param(params, "board_turnover_weight")
        )
        return round(_clamp_score(score, params), 2)

    @staticmethod
    def _board_sector_name(row: dict[str, object], fallback: str = "") -> str:
        for key in ("板块名称", "industry", "sector_name", "name", "名称", "行业"):
            value = row.get(key)
            if value not in (None, "", "-", "--"):
                return str(value)
        return fallback or "未分类行业"

    @staticmethod
    def _compute_market_strength(bars) -> float:
        params = _sector_proxy_params()
        min_bars = _int_param(params, "market_min_bars")
        ma_window = _int_param(params, "market_ma_window")
        slope_window = _int_param(params, "market_slope_window")
        required_bars = max(min_bars, ma_window, slope_window)
        if len(bars) < required_bars:
            return _float_param(params, "market_base_score")
        closes = [bar.close for bar in bars]
        ma_value = sum(closes[-ma_window:]) / ma_window
        denominator_floor = _float_param(params, "market_denominator_floor")
        slope = (closes[-1] - closes[-slope_window]) / max(closes[-slope_window], denominator_floor) * 100
        relative = (closes[-1] - ma_value) / max(ma_value, denominator_floor) * 100
        score = (
            _float_param(params, "market_base_score")
            + slope * _float_param(params, "market_slope_weight")
            + relative * _float_param(params, "market_relative_weight")
        )
        return round(_clamp_score(score, params), 2)


def _sector_proxy_params() -> dict[str, Any]:
    try:
        from app.services.quant.runtime_parameters import get_market_regime_scoring

        values = get_market_regime_scoring().get("sector_proxy", {})
    except Exception:
        values = {}
    if not isinstance(values, dict):
        values = {}
    return {**MARKET_SECTOR_PROXY_DEFAULTS, **values}


def _float_param(params: dict[str, Any], key: str) -> float:
    try:
        return float(params.get(key, MARKET_SECTOR_PROXY_DEFAULTS.get(key, 0.0)))
    except (TypeError, ValueError):
        return float(MARKET_SECTOR_PROXY_DEFAULTS.get(key, 0.0))


def _int_param(params: dict[str, Any], key: str) -> int:
    try:
        return int(params.get(key, MARKET_SECTOR_PROXY_DEFAULTS.get(key, 0)))
    except (TypeError, ValueError):
        return int(MARKET_SECTOR_PROXY_DEFAULTS.get(key, 0))


def _clamp_score(value: float, params: dict[str, Any]) -> float:
    return max(_float_param(params, "score_min"), min(_float_param(params, "score_max"), float(value or 0.0)))
