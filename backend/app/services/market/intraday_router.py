from __future__ import annotations

from app.services.market.shared import DataSourceError, KlineBar


class IntradaySourceRouter:
    def __init__(self, service) -> None:
        self.service = service

    def load_one_minute_bars(self, symbol: str, *, allow_slow_fallback: bool = True) -> list[KlineBar]:
        for loader in (
            self.service._fetch_trend_bars,
            self.service._fetch_tencent_minute_bars,
        ):
            try:
                bars = loader(symbol)
                if bars:
                    return bars
            except Exception:
                continue
        if allow_slow_fallback:
            provider_router = getattr(self.service, "provider_router", None)
            if provider_router is not None:
                try:
                    result = provider_router.fetch_intraday_bars(symbol)
                    if result.usable and result.data:
                        return result.data
                except Exception:
                    pass
            legacy_sina_loader = getattr(self.service, "_fetch_sina_minute_bars", None)
            if legacy_sina_loader is not None:
                try:
                    bars = legacy_sina_loader(symbol, "1m")
                    if bars:
                        return bars
                except Exception:
                    pass
        raise DataSourceError(f"未获取到 {symbol} 的 1m 分钟K线。")
