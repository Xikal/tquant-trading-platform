from __future__ import annotations

from app.models.schemas import KlineBar, MarketEventOut, QuoteSnapshot, SectorSnapshot
from app.services.market.providers.akshare_events import (
    fetch_news_events,
    fetch_notice_events,
)
from app.services.market.providers.akshare_history import fetch_daily_history as fetch_akshare_daily_history
from app.services.market.providers.akshare_instruments import (
    fetch_etf_instrument_rows as fetch_akshare_etf_instrument_rows,
    fetch_industry_constituent_map as fetch_akshare_industry_constituent_map,
    fetch_stock_industry as fetch_akshare_stock_industry,
    fetch_stock_instrument_rows as fetch_akshare_stock_instrument_rows,
)
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.regime_scoring import normalize_board_frame
from app.services.market.shared import ak
from app.services.market.providers.akshare_utils import (
    bounded_strength,
    parse_sina_minute_records,
    parse_spot_snapshot_records,
)


class AkshareMarketProvider:
    name = "akshare"

    def __init__(self, service) -> None:
        self.service = service
        self._industry_board_frame_cache = None
        self._spot_snapshot_cache: dict[str, dict[str, QuoteSnapshot]] = {}

    def _raw_call(self, func, *args, purpose: str = "default", **kwargs):  # noqa: ANN001
        raw_client = getattr(self.service, "akshare_raw", None)
        if raw_client is not None:
            return raw_client.call(func, *args, purpose=purpose, **kwargs)
        legacy_call = getattr(self.service, "_call_akshare", None)
        if legacy_call is not None:
            return legacy_call(func, *args, purpose=purpose, **kwargs)
        raise RuntimeError("akshare raw client unavailable")

    def fetch_quote(self, symbol: str) -> ProviderResult[QuoteSnapshot]:
        try:
            instrument_type = (
                "etf"
                if __import__("app.services.market.shared", fromlist=["MarketRuleService"]).MarketRuleService.looks_like_etf(symbol)
                else "stock"
            )
            snapshot = self._load_spot_snapshot_map(instrument_type).get(symbol)
            if snapshot is None:
                raise RuntimeError(f"{instrument_type} spot snapshot missing {symbol}")
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data=snapshot)

    def fetch_intraday_bars(self, symbol: str) -> ProviderResult[list[KlineBar]]:
        try:
            bars = self._fetch_sina_minute_bars(symbol, "1m")
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if bars else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=bars or None,
        )

    def _load_spot_snapshot_map(self, instrument_type: str) -> dict[str, QuoteSnapshot]:
        if ak is None:
            raise RuntimeError("akshare unavailable")
        cached = self._spot_snapshot_cache.get(instrument_type)
        if cached is not None:
            return cached
        frame = self._raw_call(
            ak.fund_etf_spot_em if instrument_type == "etf" else ak.stock_zh_a_spot,
            purpose="spot_snapshot",
        )
        if frame is None or getattr(frame, "empty", False):
            raise RuntimeError(f"{instrument_type} spot snapshot empty")
        result = parse_spot_snapshot_records(
            frame.to_dict("records"),
            instrument_type=instrument_type,
            source=self.name,
            normalize_timestamp=self.service._normalize_quote_timestamp,
        )
        self._spot_snapshot_cache[instrument_type] = result
        return result

    def _fetch_sina_minute_bars(self, symbol: str, period: str) -> list[KlineBar]:
        if ak is None:
            raise RuntimeError("akshare unavailable")
        frame = self._raw_call(
            ak.stock_zh_a_minute,
            symbol=self.service._to_sina_symbol(symbol),
            period=period.replace("m", ""),
            adjust="",
            purpose="minute_bars",
        )
        if frame is None or getattr(frame, "empty", False):
            raise RuntimeError(f"{symbol} minute bars empty")
        bars = parse_sina_minute_records(frame.tail(1970).to_dict("records"))
        if not bars:
            raise RuntimeError(f"{symbol} minute bars parse empty")
        return bars

    def fetch_sector_heatmap(self) -> ProviderResult[list[SectorSnapshot]]:
        try:
            frame_result = self.fetch_board_breadth_frame()
            frame = frame_result.data
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        if frame is None or frame.empty:
            return ProviderResult(
                quality=MarketDataQuality.UNAVAILABLE,
                source=self.name,
                message="industry board breadth unavailable",
            )
        median_change = float(frame["change_pct"].median()) if "change_pct" in frame else 0.0
        market_strength = bounded_strength(median_change)
        heatmap = [
            SectorSnapshot(
                sector_name=str(row.get("industry") or ""),
                sector_strength=bounded_strength(float(row.get("change_pct") or 0.0)),
                market_strength=market_strength,
                alignment_score=round(
                    (bounded_strength(float(row.get("change_pct") or 0.0)) + market_strength) / 2,
                    2,
                ),
                notes="板块热力来自 AkShare 行业板块快照。",
            )
            for row in frame.head(30).to_dict("records")
            if str(row.get("industry") or "").strip()
        ]
        return ProviderResult(
            quality=MarketDataQuality.FRESH if heatmap else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=heatmap or None,
        )

    def fetch_board_breadth_frame(self) -> ProviderResult:
        try:
            frame = self._industry_board_frame()
            normalized = normalize_board_frame(frame)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        if normalized is None or normalized.empty:
            return ProviderResult(
                quality=MarketDataQuality.UNAVAILABLE,
                source=self.name,
                message="industry board breadth unavailable",
            )
        return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data=normalized)

    def _industry_board_frame(self):
        if ak is None:
            raise RuntimeError("akshare unavailable")
        if self._industry_board_frame_cache is None:
            self._industry_board_frame_cache = self._raw_call(
                ak.stock_board_industry_name_em,
                purpose="industry",
            )
        return self._industry_board_frame_cache

    def fetch_trade_dates(self) -> ProviderResult[list[str]]:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        try:
            frame = self._raw_call(ak.tool_trade_date_hist_sina, purpose="trade_dates")
            values = [
                item.isoformat() if hasattr(item, "isoformat") else str(item)
                for item in frame["trade_date"].tolist()
            ]
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if values else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=values or None,
        )

    def fetch_market_emotion_pools(
        self,
        effective_trade_date: str,
        previous_trade_date: str | None = None,
    ) -> ProviderResult[dict[str, object]]:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        compact_date = effective_trade_date.replace("-", "")
        try:
            data = {
                "current": self._raw_call(
                    ak.stock_zt_pool_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "broken": self._raw_call(
                    ak.stock_zt_pool_zbgc_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "previous_board": self._raw_call(
                    ak.stock_zt_pool_previous_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "previous": None,
            }
            if previous_trade_date:
                data["previous"] = self._raw_call(
                    ak.stock_zt_pool_em,
                    date=previous_trade_date.replace("-", ""),
                    purpose="limit_pool",
                )
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data=data)

    def fetch_limit_up_pool(self, trade_date: str) -> ProviderResult:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        try:
            frame = self._raw_call(
                ak.stock_zt_pool_em,
                date=trade_date.replace("-", ""),
                purpose="limit_pool",
            )
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if frame is not None else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=frame,
        )

    def fetch_limit_down_pool(self, trade_date: str) -> ProviderResult:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        try:
            frame = self._raw_call(
                ak.stock_zt_pool_dtgc_em,
                date=trade_date.replace("-", ""),
                purpose="market_breadth",
            )
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if frame is not None else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=frame,
        )

    def fetch_daily_history(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        return fetch_akshare_daily_history(
            self._raw_call,
            provider_name=self.name,
            sina_symbol=self.service._to_sina_symbol(symbol),
            start_date=start_date,
            end_date=end_date,
        )

    def fetch_sector_fund_flow_rank(self) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_sector_fund_flow_rank,
                indicator="今日",
                sector_type="行业资金流",
                purpose="industry",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_individual_fund_flow(self, symbol: str, market: str) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_individual_fund_flow,
                stock=symbol,
                market=market,
                purpose="quote",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_northbound_fund_flow_summary(self) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_hsgt_fund_flow_summary_em,
                purpose="market_breadth",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_limit_up_snapshot(self) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(ak.stock_zt_pool_em, purpose="limit_pool")
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_lhb_stock_statistic(self) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_lhb_stock_statistic_em,
                symbol="近一月",
                purpose="market_breadth",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_stock_notice_report(self, symbol: str) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_notice_report,
                symbol=symbol,
                purpose="news",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_market_events(self, symbol: str) -> ProviderResult[list[MarketEventOut]]:
        if ak is None:
            return self._ak_unavailable()
        try:
            events = fetch_notice_events(self._raw_call, symbol) + fetch_news_events(self._raw_call, symbol)
        except Exception as exc:
            return self._unavailable(str(exc))
        deduped: list[MarketEventOut] = []
        seen: set[tuple[str, str]] = set()
        for event in events:
            key = (event.title, event.source)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)
        return ProviderResult(
            quality=MarketDataQuality.FRESH if deduped else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=deduped[:8] or None,
        )

    def fetch_stock_instrument_rows(self) -> ProviderResult[list[dict[str, object]]]:
        return fetch_akshare_stock_instrument_rows(self._raw_call, self.name)

    def fetch_etf_instrument_rows(self) -> ProviderResult[list[dict[str, object]]]:
        return fetch_akshare_etf_instrument_rows(self._raw_call, self.name)

    def fetch_industry_constituent_map(self) -> ProviderResult[dict[str, str]]:
        return fetch_akshare_industry_constituent_map(self._raw_call, self.name)

    def fetch_stock_industry(self, symbol: str) -> ProviderResult[str]:
        return fetch_akshare_stock_industry(self._raw_call, self.name, symbol)

    def _ak_unavailable(self) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")

    def _unavailable(self, message: str) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=message[:160])

    def _frame_result(self, frame) -> ProviderResult:
        usable = frame is not None and not getattr(frame, "empty", False)
        return ProviderResult(
            quality=MarketDataQuality.FRESH if usable else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=frame if usable else None,
        )
