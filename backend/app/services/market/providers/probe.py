from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.config import get_settings
from app.core.timezone import beijing_now_string
from app.models.schema_defs.phase4 import DataSourceProbeResponse, DataSourceQualityOut
from app.services.market.providers.base import ProviderResult, ProviderTimer


class DataSourceProbeService:
    """Health probe for market data providers without changing read paths."""

    def __init__(self, probes: dict[str, Callable[[], Any]] | None = None) -> None:
        self.settings = get_settings()
        self._probes = probes or {}

    def probe(self) -> DataSourceProbeResponse:
        provider_order = _provider_order(self.settings.market_data_provider_order)
        items = [self._probe_provider(provider) for provider in provider_order]
        ok_count = sum(1 for item in items if item.ok)
        return DataSourceProbeResponse(
            updated_at=beijing_now_string(),
            provider_order=provider_order,
            items=items,
            summary=f"可用数据源 {ok_count}/{len(items)}；失败时按顺序自动降级。",
        )

    def run_provider(self, provider_name: str, loader: Callable[[], Any]) -> ProviderResult[Any]:
        timer = ProviderTimer(provider_name)
        try:
            value = loader()
        except Exception as exc:
            return ProviderResult(
                value=None,
                quality=timer.quality(ok=False, quality="failed", warning=str(exc)[:180]),
                warnings=[str(exc)[:180]],
            )
        is_stale = bool(getattr(value, "is_stale", False))
        quality = "stale" if is_stale else "ok"
        return ProviderResult(
            value=value,
            quality=timer.quality(ok=True, quality=quality, is_stale=is_stale),
            warnings=[],
        )

    def _probe_provider(self, provider_name: str) -> DataSourceQualityOut:
        timer = ProviderTimer(provider_name)
        probe = self._probes.get(provider_name)
        if probe is None:
            # Provider is configured but not actively probed in this process.
            return DataSourceQualityOut(
                source=provider_name,
                ok=True,
                quality="degraded",
                latency_ms=timer.quality(ok=True).latency_ms,
                warning="未配置主动探测函数，仅确认 provider 已进入降级链。",
            )
        result = self.run_provider(provider_name, probe)
        return DataSourceQualityOut(
            source=result.quality.source,
            ok=result.quality.ok,
            quality=result.quality.quality,  # type: ignore[arg-type]
            latency_ms=result.quality.latency_ms,
            is_stale=result.quality.is_stale,
            warning=result.quality.warning,
        )


def _provider_order(raw: str) -> list[str]:
    values = [item.strip() for item in str(raw or "").split(",") if item.strip()]
    return values or ["tencent", "eastmoney", "akshare", "sina"]
