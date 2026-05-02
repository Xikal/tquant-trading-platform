from __future__ import annotations

from app.services.low_buy import LowBuyScreenerService
from app.services.app_mobile.bootstrap import AppMobileBootstrapMixin
from app.services.app_mobile.home import AppMobileHomeMixin
from app.services.app_mobile.low_buy import AppMobileLowBuyMixin
from app.services.app_mobile.watchlist import AppMobileWatchlistMixin
from app.services.watchlist_signal_service import WatchlistSignalService


class AppMobileService(
    AppMobileBootstrapMixin,
    AppMobileHomeMixin,
    AppMobileWatchlistMixin,
    AppMobileLowBuyMixin,
):
    def __init__(self) -> None:
        self.watchlist_signal_service = WatchlistSignalService()
        self.low_buy_screener = LowBuyScreenerService()
