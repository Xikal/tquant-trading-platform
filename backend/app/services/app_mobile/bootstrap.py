from __future__ import annotations

from app.models.schemas import AppBootstrapResponse, AppBootstrapTab, AppFeatureFlags
from app.services.app_mobile.common import now_string


class AppMobileBootstrapMixin:
    _app_name = "A股短线做T助手"
    _app_version = "1.0.0"
    _min_supported_version = "1.0.0"
    _default_refresh_seconds = 20
    _market_disclaimer = "数据仅供研究与辅助决策，不构成投资建议。"

    def bootstrap(self) -> AppBootstrapResponse:
        return AppBootstrapResponse(
            app_name=self._app_name,
            app_version=self._app_version,
            min_supported_version=self._min_supported_version,
            tabs=[
                AppBootstrapTab(key="home", title="实时监控"),
                AppBootstrapTab(key="low_buy", title="选股宝典"),
            ],
            default_refresh_seconds=self._default_refresh_seconds,
            market_disclaimer=self._market_disclaimer,
            feature_flags=AppFeatureFlags(),
            updated_at=now_string(),
            is_stale=False,
            warnings=[],
        )
