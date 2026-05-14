from __future__ import annotations

from app.core.config import get_settings
from app.services.market.providers.eastmoney_fund_flow import (
    EastMoneyDatacenterClient,
    get_shared_eastmoney_datacenter_client,
    reset_shared_eastmoney_datacenter_client,
)
from app.services.market.providers.eastmoney_provider import EastmoneyMarketProvider


def test_eastmoney_datacenter_client_uses_service_user_agent() -> None:
    client = EastMoneyDatacenterClient()

    assert client._session.headers["User-Agent"] == "TQuant-MarketDataService/1.0"
    assert client._session.trust_env is True


def test_eastmoney_datacenter_client_can_bypass_proxy_when_configured(monkeypatch) -> None:
    get_settings.cache_clear()
    reset_shared_eastmoney_datacenter_client()
    monkeypatch.setenv("EASTMONEY_BYPASS_PROXY", "true")
    try:
        client = EastMoneyDatacenterClient()
    finally:
        get_settings.cache_clear()
        reset_shared_eastmoney_datacenter_client()

    assert client._session.trust_env is False
    assert client._session.proxies == {"http": None, "https": None}


def test_eastmoney_provider_reuses_shared_datacenter_client() -> None:
    reset_shared_eastmoney_datacenter_client()
    try:
        provider_a = EastmoneyMarketProvider(service=None)
        provider_b = EastmoneyMarketProvider(service=None)

        assert provider_a._dc_client is provider_b._dc_client
        assert provider_a._dc_client is get_shared_eastmoney_datacenter_client()
    finally:
        reset_shared_eastmoney_datacenter_client()
