from __future__ import annotations

from pathlib import Path
import threading

import requests

from app.core.config import get_settings
from app.services.market.emotion import MarketEmotionMixin
from app.services.market.intraday_router import IntradaySourceRouter
from app.services.market.instruments import MarketInstrumentMixin
from app.services.market.intraday import MarketIntradayMixin
from app.services.market.regime import MarketRegimeMixin
from app.services.market.quote_router import QuoteSourceRouter
from app.services.market.quotes import MarketQuoteMixin
from app.services.market.sectors import MarketSectorMixin
from app.services.market.providers.akshare_provider import AkshareMarketProvider
from app.services.market.providers.akshare_raw import AkshareRawClient
from app.services.market.providers.eastmoney_provider import EastmoneyMarketProvider
from app.services.market.providers.openbb_provider import OpenBBMarketProvider
from app.services.market.providers.router import MarketProviderRouter


class MarketDataService(
    MarketEmotionMixin,
    MarketRegimeMixin,
    MarketSectorMixin,
    MarketIntradayMixin,
    MarketQuoteMixin,
    MarketInstrumentMixin,
):
    quote_endpoint = "https://push2.eastmoney.com/api/qt/stock/get"
    kline_endpoint = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    stock_list_endpoint = "https://82.push2.eastmoney.com/api/qt/clist/get"
    etf_list_endpoint = "https://88.push2.eastmoney.com/api/qt/clist/get"
    seed_database_path = Path(__file__).resolve().parents[3] / "data" / "t_quant.db"
    _industry_board_frame_cache = None
    _sector_board_cache = {}
    _quote_cache = {}
    _intraday_cache = {}
    _spot_snapshot_cache = {}
    _market_breadth_cache = {}
    _market_regime_cache = {}
    _market_regime_jobs = set()
    _market_emotion_cache = {}
    _limit_down_cache = {}
    _trade_dates_cache = {}
    _market_breadth_jobs = set()
    _cache_lock = threading.Lock()
    _quote_cache_ttl = 10.0
    _intraday_cache_ttl = 20.0
    _spot_snapshot_cache_ttl = 12.0
    _market_breadth_cache_ttl = 45.0
    _market_regime_cache_ttl = 45.0
    _market_emotion_cache_ttl = 120.0
    _limit_down_cache_ttl = 60.0
    _trade_dates_cache_ttl = 600.0

    def __init__(self) -> None:
        self.settings = get_settings()
        self.session = requests.Session()
        self.session.trust_env = False
        self.ak_available = __import__("app.services.market.shared", fromlist=["ak"]).ak is not None
        self.akshare_raw = AkshareRawClient()
        self.quote_router = QuoteSourceRouter(self)
        self.intraday_router = IntradaySourceRouter(self)
        self.provider_router = MarketProviderRouter(
            [
                EastmoneyMarketProvider(self),
                AkshareMarketProvider(self),
                OpenBBMarketProvider(self),
            ]
        )
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
                )
            }
        )
