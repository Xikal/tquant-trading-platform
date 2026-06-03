from __future__ import annotations

from app.core.config import get_settings
from app.services.read_models import indicator_cache
from app.services.read_models.indicator_cache import get_or_compute_indicator, indicator_cache_metrics_snapshot, reset_indicator_cache


def test_indicator_cache_hits_version_miss_and_ttl_miss(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "derived_indicator_cache_enabled", True)
    monkeypatch.setattr(settings, "derived_indicator_cache_ttl_seconds", 1)
    reset_indicator_cache()
    clock = {"now": 100.0}
    calls = {"count": 0}
    monkeypatch.setattr(indicator_cache.time, "monotonic", lambda: clock["now"])

    def loader() -> float:
        calls["count"] += 1
        return float(calls["count"])

    first = get_or_compute_indicator(indicator="atr", symbol="000001", trade_date="2026-06-03", params_hash="a", loader=loader)
    second = get_or_compute_indicator(indicator="atr", symbol="000001", trade_date="2026-06-03", params_hash="a", loader=loader)
    version_miss = get_or_compute_indicator(
        indicator="atr",
        symbol="000001",
        trade_date="2026-06-03",
        params_hash="a",
        indicator_version="v2",
        loader=loader,
    )
    clock["now"] += 2.0
    ttl_miss = get_or_compute_indicator(indicator="atr", symbol="000001", trade_date="2026-06-03", params_hash="a", loader=loader)

    snapshot = indicator_cache_metrics_snapshot()
    assert first == second == 1.0
    assert version_miss == 2.0
    assert ttl_miss == 3.0
    assert snapshot["hits"]["atr"] == 1
    assert snapshot["misses"]["atr"] == 3


def test_indicator_cache_flag_off_uses_original_compute(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "derived_indicator_cache_enabled", False)
    reset_indicator_cache()
    calls = {"count": 0}

    def loader() -> float:
        calls["count"] += 1
        return float(calls["count"])

    first = get_or_compute_indicator(indicator="rolling_mean", symbol="000001", trade_date="2026-06-03", params_hash="a", loader=loader)
    second = get_or_compute_indicator(indicator="rolling_mean", symbol="000001", trade_date="2026-06-03", params_hash="a", loader=loader)

    assert first == 1.0
    assert second == 2.0
    assert calls["count"] == 2

