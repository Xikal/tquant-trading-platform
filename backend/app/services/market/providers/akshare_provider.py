from __future__ import annotations

from app.models.schemas import KlineBar, QuoteSnapshot, SectorSnapshot
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.regime_scoring import normalize_board_frame
from app.services.market.shared import ak


class AkshareMarketProvider:
    name = "akshare"

    def __init__(self, service) -> None:
        self.service = service

    def fetch_quote(self, symbol: str) -> ProviderResult[QuoteSnapshot]:
        try:
            quote = self.service._fetch_quote_from_spot_snapshot(symbol)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data=quote)

    def fetch_intraday_bars(self, symbol: str) -> ProviderResult[list[KlineBar]]:
        try:
            bars = self.service._fetch_sina_minute_bars(symbol, "1m")
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if bars else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=bars or None,
        )

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
        market_strength = _bounded_strength(median_change)
        heatmap = [
            SectorSnapshot(
                sector_name=str(row.get("industry") or ""),
                sector_strength=_bounded_strength(float(row.get("change_pct") or 0.0)),
                market_strength=market_strength,
                alignment_score=round(
                    (_bounded_strength(float(row.get("change_pct") or 0.0)) + market_strength) / 2,
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
            if hasattr(self.service, "_get_industry_board_frame"):
                frame = self.service._get_industry_board_frame()
            else:
                frame = self.service._load_board_breadth_frame()
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

    def fetch_trade_dates(self) -> ProviderResult[list[str]]:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        try:
            frame = self.service._call_akshare(ak.tool_trade_date_hist_sina, purpose="trade_dates")
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
                "current": self.service._call_akshare(
                    ak.stock_zt_pool_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "broken": self.service._call_akshare(
                    ak.stock_zt_pool_zbgc_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "previous_board": self.service._call_akshare(
                    ak.stock_zt_pool_previous_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "previous": None,
            }
            if previous_trade_date:
                data["previous"] = self.service._call_akshare(
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
            frame = self.service._call_akshare(
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
            frame = self.service._call_akshare(
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
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        normalized = None
        try:
            frame = self.service._call_akshare(
                ak.stock_zh_a_daily,
                symbol=self.service._to_sina_symbol(symbol),
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
                purpose="daily_history",
            )
            if frame is not None and not frame.empty:
                normalized = frame.rename(
                    columns={
                        "date": "date",
                        "open": "open",
                        "close": "close",
                        "high": "high",
                        "low": "low",
                        "volume": "volume",
                        "amount": "amount",
                    }
                ).copy()
                normalized["pct_chg"] = normalized["close"].pct_change().fillna(0.0) * 100
        except Exception:
            normalized = None
        if normalized is None:
            try:
                frame = self.service._call_akshare(
                    ak.stock_zh_a_hist_tx,
                    symbol=self.service._to_sina_symbol(symbol),
                    start_date=start_date,
                    end_date=end_date,
                    purpose="daily_history",
                )
                if frame is not None and not frame.empty:
                    normalized = frame.rename(
                        columns={
                            "date": "date",
                            "open": "open",
                            "close": "close",
                            "high": "high",
                            "low": "low",
                            "amount": "volume",
                        }
                    ).copy()
                    normalized["amount"] = 0.0
                    normalized["pct_chg"] = normalized["close"].pct_change().fillna(0.0) * 100
            except Exception as exc:
                return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if normalized is not None and not normalized.empty else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=normalized,
        )


def _bounded_strength(change_pct: float) -> float:
    return round(max(0.0, min(100.0, 50.0 + change_pct * 8.0)), 2)
