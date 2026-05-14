"""EastMoney Datacenter API client for sector capital flow data."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_SHARED_CLIENT_LOCK = threading.Lock()
_SHARED_CLIENT: EastMoneyDatacenterClient | None = None
_SHARED_CLIENT_KEY: tuple[float, bool] | None = None

_DATACENTER_URL = "https://data.eastmoney.com/dataapi/bkzj/getbkzj"

# code parameter controls sector type (raw, requests will encode)
_SECTOR_TYPE_MAP = {
    "industry": "m:90+s:4",   # 行业板块 (128)
    "concept": "m:90+t:3",    # 概念板块 (486)
    "region": "m:90+t:2",     # 地域板块
}

# key parameter controls sort field / time period
_PERIOD_KEY_MAP = {
    "today": "f62",    # 今日主力净流入
    "5day": "f267",    # 5日主力净流入
    "10day": "f164",   # 10日主力净流入
}


@dataclass(frozen=True)
class SectorFundFlowItem:
    """Single sector fund flow record."""
    board_code: str      # e.g. "BK1037"
    board_type: int      # 90 = sector
    sector_name: str     # e.g. "消费电子"
    net_flow: float      # 主力净流入 (元), signed


@dataclass(frozen=True)
class SectorFundFlowResult:
    """Result of a sector fund flow query."""
    total: int
    items: list[SectorFundFlowItem]
    period: str          # "today" / "5day" / "10day"
    sector_type: str     # "industry" / "concept" / "region"
    fetched_at: float    # monotonic timestamp


class EastMoneyDatacenterClient:
    """Stateless client for EastMoney datacenter API.

    Proxy bypass is intentionally controlled by configuration.  Production
    environments often route outbound traffic through a managed proxy.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "TQuant-MarketDataService/1.0",
            "Referer": "https://data.eastmoney.com/bkzj/hy.html",
        })
        if bool(get_settings().eastmoney_bypass_proxy):
            self._session.proxies = {"http": None, "https": None}
            self._session.trust_env = False

    def close(self) -> None:
        self._session.close()

    def fetch_sector_fund_flow(
        self,
        period: str = "today",
        sector_type: str = "industry",
        limit: int = 50,
    ) -> SectorFundFlowResult:
        """Fetch sector fund flow ranking.

        Args:
            period: "today", "5day", or "10day"
            sector_type: "industry", "concept", or "region"
            limit: max items to return (API returns all, we truncate)

        Returns:
            SectorFundFlowResult with sorted items (highest net flow first)

        Raises:
            ValueError: invalid period or sector_type
            requests.RequestException: network error
        """
        key = _PERIOD_KEY_MAP.get(period)
        if key is None:
            raise ValueError(f"Invalid period: {period}. Use: {list(_PERIOD_KEY_MAP)}")

        code = _SECTOR_TYPE_MAP.get(sector_type)
        if code is None:
            raise ValueError(f"Invalid sector_type: {sector_type}. Use: {list(_SECTOR_TYPE_MAP)}")

        params = {"key": key, "code": code}
        resp = self._session.get(_DATACENTER_URL, params=params, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rc") != 0 or "data" not in data:
            raise ValueError(f"Unexpected API response: rc={data.get('rc')}")

        raw_items = data["data"].get("diff", [])
        items: list[SectorFundFlowItem] = []
        for entry in raw_items[:limit]:
            try:
                items.append(SectorFundFlowItem(
                    board_code=str(entry.get("f12", "")),
                    board_type=int(entry.get("f13", 0)),
                    sector_name=str(entry.get("f14", "")),
                    net_flow=float(entry.get(key, 0)),
                ))
            except (TypeError, ValueError):
                continue

        return SectorFundFlowResult(
            total=data["data"].get("total", len(items)),
            items=items,
            period=period,
            sector_type=sector_type,
            fetched_at=time.monotonic(),
        )

    def fetch_all_periods(
        self,
        sector_type: str = "industry",
        limit: int = 30,
    ) -> dict[str, SectorFundFlowResult]:
        """Fetch today/5day/10day fund flow in one batch.

        Returns dict keyed by period name.
        """
        results: dict[str, SectorFundFlowResult] = {}
        for period in ("today", "5day", "10day"):
            try:
                results[period] = self.fetch_sector_fund_flow(
                    period=period,
                    sector_type=sector_type,
                    limit=limit,
                )
            except Exception as exc:
                logger.warning("Failed to fetch %s %s fund flow: %s", sector_type, period, exc)
        return results


def get_shared_eastmoney_datacenter_client(timeout: float = 10.0) -> EastMoneyDatacenterClient:
    """Return a process-wide EastMoney datacenter client.

    The client owns a requests.Session and should be reused by provider
    instances so HTTP connection pools are not recreated on every request.
    """
    global _SHARED_CLIENT, _SHARED_CLIENT_KEY
    key = (float(timeout), bool(get_settings().eastmoney_bypass_proxy))
    with _SHARED_CLIENT_LOCK:
        if _SHARED_CLIENT is None or _SHARED_CLIENT_KEY != key:
            _SHARED_CLIENT = EastMoneyDatacenterClient(timeout=timeout)
            _SHARED_CLIENT_KEY = key
        return _SHARED_CLIENT


def reset_shared_eastmoney_datacenter_client() -> None:
    """Reset the shared client, primarily for tests/config reloads."""
    global _SHARED_CLIENT, _SHARED_CLIENT_KEY
    with _SHARED_CLIENT_LOCK:
        if _SHARED_CLIENT is not None:
            _SHARED_CLIENT.close()
        _SHARED_CLIENT = None
        _SHARED_CLIENT_KEY = None
