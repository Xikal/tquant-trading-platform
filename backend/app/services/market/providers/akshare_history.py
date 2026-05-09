from __future__ import annotations

from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.shared import ak


def fetch_daily_history(raw_call, *, provider_name: str, sina_symbol: str, start_date: str, end_date: str) -> ProviderResult:  # noqa: ANN001
    if ak is None:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=provider_name, message="akshare unavailable")
    normalized = None
    try:
        frame = raw_call(
            ak.stock_zh_a_daily,
            symbol=sina_symbol,
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
            frame = raw_call(
                ak.stock_zh_a_hist_tx,
                symbol=sina_symbol,
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
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=provider_name, message=str(exc)[:160])
    return ProviderResult(
        quality=MarketDataQuality.FRESH if normalized is not None and not normalized.empty else MarketDataQuality.UNAVAILABLE,
        source=provider_name,
        data=normalized,
    )
