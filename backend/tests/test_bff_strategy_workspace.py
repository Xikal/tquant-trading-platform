from __future__ import annotations

import time
from types import SimpleNamespace

from app.models.schema_defs.backtest import BacktestRunListResponse, BacktestVerdictThresholdsResponse
from app.models.schema_defs.strategy_meta import StrategyMetaResponse, StrategyPresetResponse
from app.models.schema_defs.strategy_tracking import (
    StrategyTrackingItemOut,
    StrategyTrackingListResponse,
    StrategyTrackingPerformanceOut,
    StrategyTrackingSummaryOut,
)
from app.services.bff import strategy_workspace


def test_strategy_workspace_embeds_tracking_read_model(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeStrategyTrackingService:
        def __init__(self, db) -> None:
            self.db = db

        def list_items(self, **kwargs) -> StrategyTrackingListResponse:
            calls.append(kwargs)
            return StrategyTrackingListResponse(
                items=[
                    StrategyTrackingItemOut(
                        id="tracking-000001",
                        symbol="000001",
                        strategy_key="n_pattern",
                        strategy_name="N形洗盘低吸",
                    )
                ],
                total=1,
                limit=kwargs["limit"],
                offset=kwargs["offset"],
                sort=kwargs["sort"],
                summary=StrategyTrackingSummaryOut(tracking_count=1, active_count=1),
                performance=[
                    StrategyTrackingPerformanceOut(
                        strategy_key="n_pattern",
                        strategy_name="N形洗盘低吸",
                        recommendation_count=1,
                    )
                ],
                notes=["tracking read model"],
            )

    class FakeStrategyMetadataService:
        def __init__(self, db) -> None:
            self.db = db

        def list_strategy_meta(self, **_kwargs) -> StrategyMetaResponse:
            return StrategyMetaResponse(strategies=[])

        def list_presets(self) -> StrategyPresetResponse:
            return StrategyPresetResponse(presets=[])

    class FakeBacktestJobService:
        def __init__(self, db) -> None:
            self.db = db

        def list_runs(self, **_kwargs) -> BacktestRunListResponse:
            return BacktestRunListResponse(items=[], total=0, limit=8, offset=0)

    monkeypatch.setattr(strategy_workspace, "StrategyTrackingService", FakeStrategyTrackingService)
    monkeypatch.setattr(strategy_workspace, "StrategyMetadataService", FakeStrategyMetadataService)
    monkeypatch.setattr(strategy_workspace, "BacktestJobService", FakeBacktestJobService)
    monkeypatch.setattr(strategy_workspace, "_verdict_thresholds", lambda: BacktestVerdictThresholdsResponse())
    monkeypatch.setattr(strategy_workspace, "apply_strategy_tracking_live_overlay", lambda payload: payload)

    response = strategy_workspace.build_strategy_workspace(
        object(),
        current_user=SimpleNamespace(id=7),
        run_limit=8,
    )

    assert calls == [
        {
            "range_days": strategy_workspace.STRATEGY_TRACKING_BFF_RANGE_DAYS,
            "board_filter": "include_all",
            "limit": strategy_workspace.STRATEGY_TRACKING_BFF_LIMIT,
            "offset": 0,
            "sort": "max_gain_desc",
        }
    ]
    assert response.items[0].symbol == "000001"
    assert response.summary is not None
    assert response.summary.tracking_count == 1
    assert response.performance[0].strategy_key == "n_pattern"
    assert response.tracking_notes == ["tracking read model"]
    assert response.partial_errors == []


def test_strategy_workspace_degrades_slow_tracking_source(monkeypatch) -> None:
    class SlowStrategyTrackingService:
        def __init__(self, db) -> None:
            self.db = db

        def list_items(self, **_kwargs) -> StrategyTrackingListResponse:
            time.sleep(0.05)
            return StrategyTrackingListResponse()

    class FakeStrategyMetadataService:
        def __init__(self, db) -> None:
            self.db = db

        def list_strategy_meta(self, **_kwargs) -> StrategyMetaResponse:
            return StrategyMetaResponse(strategies=[])

        def list_presets(self) -> StrategyPresetResponse:
            return StrategyPresetResponse(presets=[])

    class FakeBacktestJobService:
        def __init__(self, db) -> None:
            self.db = db

        def list_runs(self, **_kwargs) -> BacktestRunListResponse:
            return BacktestRunListResponse(items=[], total=0, limit=8, offset=0)

    monkeypatch.setattr(strategy_workspace, "StrategyTrackingService", SlowStrategyTrackingService)
    monkeypatch.setattr(strategy_workspace, "StrategyMetadataService", FakeStrategyMetadataService)
    monkeypatch.setattr(strategy_workspace, "BacktestJobService", FakeBacktestJobService)
    monkeypatch.setattr(strategy_workspace, "_verdict_thresholds", lambda: BacktestVerdictThresholdsResponse())
    monkeypatch.setattr(strategy_workspace, "STRATEGY_WORKSPACE_SOURCE_TIMEOUT_MS", {"strategy_tracking_items": 10})

    started = time.perf_counter()
    response = strategy_workspace.build_strategy_workspace(
        object(),
        current_user=SimpleNamespace(id=7),
        run_limit=8,
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.04
    assert response.strategy_meta is not None
    assert response.recent_runs is not None
    assert response.items == []
    assert response.total == 0
    assert len(response.partial_errors) == 1
    assert response.partial_errors[0].source == "strategy_tracking_items"
    assert response.partial_errors[0].reason == "timeout"
