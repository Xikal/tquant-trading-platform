from __future__ import annotations

from pydantic import BaseModel

from app.services.bff import workspace_cache
from app.services.bff.workspace_cache import load_cached_workspace
from app.services.performance.read_model_metrics import record_response_payload, read_model_metrics_snapshot, reset_read_model_metrics


class _WorkspacePayload(BaseModel):
    generated_at: str
    value: int


def test_bff_workspace_cache_records_read_model_metrics(monkeypatch) -> None:
    reset_read_model_metrics()
    store: dict[str, dict] = {}
    calls = {"loader": 0}

    monkeypatch.setattr(workspace_cache, "get_json_cache", lambda key: store.get(key))
    monkeypatch.setattr(workspace_cache, "set_json_cache", lambda key, payload, ttl: store.setdefault(key, payload))

    def loader() -> _WorkspacePayload:
        calls["loader"] += 1
        return _WorkspacePayload(generated_at="2026-06-03 10:00:00", value=7)

    first = load_cached_workspace(
        workspace="monitor",
        model=_WorkspacePayload,
        user_id=1,
        params={"limit": 3},
        loader=loader,
    )
    second = load_cached_workspace(
        workspace="monitor",
        model=_WorkspacePayload,
        user_id=1,
        params={"limit": 3},
        loader=loader,
    )

    snapshot = read_model_metrics_snapshot()
    assert first.value == second.value == 7
    assert calls["loader"] == 1
    assert snapshot["read_model_cache_misses"]["bff_monitor"] == 1
    assert snapshot["read_model_cache_writes"]["bff_monitor"] == 1
    assert snapshot["read_model_cache_hits"]["bff_monitor"] == 1


def test_response_payload_metrics_record_hot_route_shape() -> None:
    reset_read_model_metrics()

    record_response_payload("priority_board", {"items": [{"symbol": "000001"}, {"symbol": "000002"}]})

    snapshot = read_model_metrics_snapshot()
    assert snapshot["response_item_count"]["priority_board"] == 2
    assert snapshot["response_bytes"]["priority_board"] > 0
    assert snapshot["response_serialization_ms"]["priority_board"] >= 0
