from __future__ import annotations

from app.services.low_buy.screening import LowBuyScreeningMixin
from app.services.low_buy.service import LowBuyScreenerService


def test_low_buy_runtime_cache_methods_use_runtime_state():
    runtime = LowBuyScreenerService()._runtime

    assert runtime._get_screen_cache("missing-screen-cache") is None
    assert runtime._get_daily_history_cache("missing-daily-history-cache") is None
    runtime._set_spot_quote_cache({"600000": {"last_price": 10.0}})

    assert runtime._get_spot_quote_cache() == {"600000": {"last_price": 10.0}}


def test_low_buy_runtime_uses_composition_adapter_seam():
    runtime = LowBuyScreenerService()._runtime

    assert not isinstance(runtime, LowBuyScreeningMixin)
    assert runtime._adapters
    assert not any(isinstance(adapter, LowBuyScreeningMixin) for adapter in runtime._adapters)
    assert callable(runtime.screen)
    assert callable(runtime.priority_board)
