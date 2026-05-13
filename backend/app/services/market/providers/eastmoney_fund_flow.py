"""EastMoney Datacenter API client for sector capital flow data.

Uses data.eastmoney.com/dataapi/bkzj/getbkzj — a free, no-auth JSON API
that returns sector fund flow rankings.  Bypasses local proxy to avoid
ProxyError on push2.eastmoney.com.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

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

    All requests bypass system proxy (proxies=None) to avoid local proxy
    issues with push2.eastmoney.com.  The datacenter endpoint
    (data.eastmoney.com) works without proxy bypass too, but we set
    proxies=None for consistency.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://data.eastmoney.com/bkzj/hy.html",
        })
        # Bypass proxy for all requests
        self._session.proxies = {"http": None, "https": None}
        self._session.trust_env = False

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
