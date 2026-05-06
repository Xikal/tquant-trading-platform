from __future__ import annotations

from app.services.shared.feature_flags import list_feature_flags


def test_market_provider_router_flag_exists(monkeypatch) -> None:
    class _DB:
        def execute(self, *_args, **_kwargs):
            class _Result:
                def scalars(self):
                    return self

                def all(self):
                    return []

            return _Result()

    from app.services.shared import feature_flags

    feature_flags.clear_feature_flag_cache()
    flags = list_feature_flags(_DB())  # type: ignore[arg-type]
    feature_flags.clear_feature_flag_cache()
    assert "market_provider_router_enabled" in {item.key for item in flags}
    assert next(item for item in flags if item.key == "market_provider_router_enabled").enabled is True
