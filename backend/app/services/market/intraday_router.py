from __future__ import annotations

from app.services.market.shared import DataSourceError, KlineBar


class IntradaySourceRouter:
    def __init__(self, service) -> None:
        self.service = service

    def load_one_minute_bars(self, symbol: str) -> list[KlineBar]:
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
        if self.service.ak_available:
            for loader in (
                lambda target: self.service._fetch_sina_minute_bars(target, "1m"),
                self.service._fetch_sina_minute_bars_subprocess,
            ):
                try:
                    bars = loader(symbol)
                    if bars:
                        return bars
                except Exception:
                    continue
        raise DataSourceError(f"未获取到 {symbol} 的 1m 分钟K线。")
