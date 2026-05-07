from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Any

import requests

from app.core.config import get_settings


@dataclass(frozen=True)
class OpenBBQuote:
    symbol: str
    last_price: float = 0.0
    previous_close: float = 0.0
    change_amount: float = 0.0
    change_pct: float = 0.0
    source: str = "openbb_adapter"
    available: bool = False
    message: str = ""


class OpenBBDataAdapter:
    """Optional overseas/macro data adapter.

    The A-share production path continues to use AkShare/Eastmoney. This
    adapter is intentionally isolated and best-effort so optional global data
    cannot slow or break core strategy endpoints.
    """

    def __init__(self, timeout: int | float | None = None) -> None:
        self.settings = get_settings()
        configured_timeout = timeout if timeout is not None else getattr(self.settings, "market_quote_timeout_seconds", 3)
        self.timeout = max(0.5, min(float(configured_timeout or 3), 3.0))

    def is_configured(self) -> bool:
        api_url = getattr(self.settings, "openbb_api_url", "") or ""
        api_key = getattr(self.settings, "openbb_api_key", "") or ""
        return bool(api_url.strip() or api_key.strip())

    def status(self) -> dict[str, Any]:
        """Return adapter status without probing optional networks."""

        return {
            "optional": True,
            "configured": self.is_configured(),
            "source": "openbb_adapter",
            "timeout_seconds": self.timeout,
            "capabilities": ["quote", "macro_status"],
            "core_a_share_impact": "none",
            "message": "OpenBB/海外宏观数据为可选增强源，失败不影响 A 股核心链路。",
        }

    def quote(self, symbol: str) -> OpenBBQuote:
        """Fetch a lightweight quote from a free Yahoo chart endpoint.

        This is a fallback-compatible adapter until a formal OpenBB deployment
        is configured. Errors return an empty quote instead of raising.
        """

        normalized = symbol.strip().upper()
        if not normalized:
            return OpenBBQuote(symbol="", message="empty symbol")
        try:
            payload = self._yahoo_chart(normalized)
            meta = payload["chart"]["result"][0]["meta"]
            previous_close = float(meta.get("chartPreviousClose") or 0.0)
            last_price = float(meta.get("regularMarketPrice") or 0.0)
            change_amount = last_price - previous_close if previous_close else 0.0
            change_pct = ((last_price - previous_close) / previous_close * 100) if previous_close else 0.0
            return OpenBBQuote(
                symbol=normalized,
                last_price=round(last_price, 4),
                previous_close=round(previous_close, 4),
                change_amount=round(change_amount, 4),
                change_pct=round(change_pct, 4),
                available=True,
                message="ok",
            )
        except Exception as exc:
            return OpenBBQuote(symbol=normalized, message=f"failed: {exc}")

    def macro_status(self, indicators: list[str] | None = None) -> dict[str, Any]:
        """Fetch optional macro indicators from a free FRED CSV endpoint.

        This method is best-effort and intentionally isolated from A-share
        production data paths. Each indicator degrades independently.
        """

        requested = indicators or ["CPIAUCSL", "DGS10", "GDP"]
        rows = [self._fred_latest(str(code).strip().upper()) for code in requested if str(code).strip()]
        available_count = sum(1 for item in rows if item["available"])
        return {
            "status": "ok" if rows and available_count == len(rows) else "degraded",
            "optional": True,
            "configured": self.is_configured(),
            "source": "fred_csv",
            "timeout_seconds": self.timeout,
            "indicators": rows,
            "message": "宏观数据为可选增强源；失败时返回空指标，不影响 A 股核心链路。",
        }

    def macro_placeholder(self) -> dict[str, Any]:
        return self.macro_status()

    def _yahoo_chart(self, symbol: str) -> dict[str, Any]:
        response = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": "1d", "interval": "1d"},
            timeout=self.timeout,
            headers={"User-Agent": "TQuant/1.0"},
        )
        response.raise_for_status()
        return response.json()

    def _fred_latest(self, indicator: str) -> dict[str, Any]:
        if not indicator:
            return self._empty_macro_indicator(indicator, "empty indicator")
        try:
            response = requests.get(
                "https://fred.stlouisfed.org/graph/fredgraph.csv",
                params={"id": indicator},
                timeout=self.timeout,
                headers={"User-Agent": "TQuant/1.0"},
            )
            response.raise_for_status()
            reader = csv.DictReader(StringIO(response.text))
            latest: dict[str, str] | None = None
            for row in reader:
                value = (row.get(indicator) or "").strip()
                if value and value != ".":
                    latest = row
            if latest is None:
                return self._empty_macro_indicator(indicator, "no data")
            return {
                "code": indicator,
                "available": True,
                "latest_date": latest.get("observation_date") or latest.get("DATE") or "",
                "latest_value": float(latest[indicator]),
                "message": "ok",
            }
        except Exception as exc:
            return self._empty_macro_indicator(indicator, f"failed: {exc}")

    @staticmethod
    def _empty_macro_indicator(indicator: str, message: str) -> dict[str, Any]:
        return {
            "code": indicator,
            "available": False,
            "latest_date": "",
            "latest_value": None,
            "message": message,
        }
