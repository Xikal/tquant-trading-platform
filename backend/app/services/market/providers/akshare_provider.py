from __future__ import annotations

from app.models.schemas import KlineBar, QuoteSnapshot, SectorSnapshot
from app.services.market.providers.quality import MarketDataQuality, ProviderResult


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
            frame = self.service._load_board_breadth_frame()
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


def _bounded_strength(change_pct: float) -> float:
    return round(max(0.0, min(100.0, 50.0 + change_pct * 8.0)), 2)
