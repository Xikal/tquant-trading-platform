from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_runtime_caches_between_tests():
    """Keep class/process caches from leaking across test cases."""

    _clear_known_runtime_caches()
    yield
    _clear_known_runtime_caches()


def _clear_known_runtime_caches() -> None:
    try:
        from app.services.low_buy.service import clear_all_low_buy_runtime_caches

        clear_all_low_buy_runtime_caches()
    except Exception:
        pass
    try:
        from app.services.quant.runtime_parameters import clear_quant_parameter_cache

        clear_quant_parameter_cache()
    except Exception:
        pass
    try:
        from app.services.low_buy.factor_functions import clear_factor_weight_cache

        clear_factor_weight_cache()
    except Exception:
        pass
    try:
        from app.services.low_buy.strategy_tier_resolver import clear_strategy_tier_cache

        clear_strategy_tier_cache()
    except Exception:
        pass
    try:
        from app.services.strategy_tracking import clear_strategy_tracking_read_cache

        clear_strategy_tracking_read_cache()
    except Exception:
        pass
