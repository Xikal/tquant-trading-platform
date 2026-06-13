from __future__ import annotations

from datetime import datetime

from app.models.schema_defs.late_session_board import (
    LateSessionBoardResponse,
    LateSessionBoardStatus,
    LateSessionItemState,
    LateSessionSnapshotSlot,
    LateSessionBoardItemOut,
)
from app.services.low_buy.late_session_cache import (
    late_session_cache_key,
    late_session_ttl_seconds,
    load_distributed_late_session_board_snapshot,
    load_late_session_board_snapshot,
    store_late_session_board_snapshot,
    store_distributed_late_session_board_snapshot,
    user_filter_hash,
)


def test_late_session_cache_key_includes_trade_date_slot_epoch_variant_and_user_filter() -> None:
    assert late_session_cache_key(
        trade_date="2026-06-13",
        slot="final_1457",
        strategy_variant="baseline",
        source_epoch="epoch-42",
        user_filter_hash="u:abc",
    ) == "late_session_board:2026-06-13:final_1457:baseline:epoch-42:u:abc"


def test_final_snapshot_ttl_is_longer_than_preview() -> None:
    assert late_session_ttl_seconds("preview_1450") == 10 * 60
    assert late_session_ttl_seconds("snapshot_1455") == 6 * 60 * 60
    assert late_session_ttl_seconds("final_1457") == 7 * 24 * 60 * 60
    assert late_session_ttl_seconds("final_1457") > late_session_ttl_seconds("preview_1450")


def test_user_filter_hash_changes_derived_cache_without_changing_global_key() -> None:
    global_key = late_session_cache_key(
        trade_date="2026-06-13",
        slot="latest",
        strategy_variant="baseline",
        source_epoch="epoch-42",
    )
    user_key = late_session_cache_key(
        trade_date="2026-06-13",
        slot="latest",
        strategy_variant="baseline",
        source_epoch="epoch-42",
        user_filter_hash=user_filter_hash(["银行", "地产"]),
    )

    assert global_key.endswith(":global")
    assert user_key != global_key
    assert user_filter_hash(["地产", "银行"]) == user_filter_hash(["银行", "地产"])


def test_final_snapshot_payload_is_not_overwritten_by_live_overlay_after_close() -> None:
    payload = LateSessionBoardResponse(
        trade_date="2026-06-13",
        snapshot_slot=LateSessionSnapshotSlot.FINAL_1457,
        generated_at=datetime(2026, 6, 13, 14, 57),
        status=LateSessionBoardStatus.OK,
        items=[
            LateSessionBoardItemOut(
                symbol="000001",
                latest_price=10.1,
                late_session_state=LateSessionItemState.LATE_CONFIRMED,
                snapshot_slot=LateSessionSnapshotSlot.FINAL_1457,
            )
        ],
    )
    cache: dict[str, tuple[float, str]] = {}

    store_late_session_board_snapshot(cache, "key", payload, ttl_seconds=3600)
    loaded = load_late_session_board_snapshot(cache, "key")
    assert loaded is not None
    loaded.items[0].latest_price = 12.5

    reloaded = load_late_session_board_snapshot(cache, "key")
    assert reloaded is not None
    assert reloaded.items[0].latest_price == 10.1


def test_distributed_late_session_snapshot_round_trip(monkeypatch) -> None:
    stored: dict[str, object] = {}
    monkeypatch.setattr(
        "app.services.low_buy.late_session_cache.set_json_cache",
        lambda key, value, ttl_seconds: stored.setdefault(key, value) is not None,
    )
    monkeypatch.setattr(
        "app.services.low_buy.late_session_cache.get_json_cache",
        lambda key: stored.get(key),
    )
    payload = LateSessionBoardResponse(
        trade_date="2026-06-13",
        snapshot_slot=LateSessionSnapshotSlot.PREVIEW_1450,
        generated_at=datetime(2026, 6, 13, 14, 50),
        status=LateSessionBoardStatus.PARTIAL_DATA,
        items=[
            LateSessionBoardItemOut(
                symbol="000001",
                latest_price=10.1,
                late_session_state=LateSessionItemState.LATE_WATCH,
                snapshot_slot=LateSessionSnapshotSlot.PREVIEW_1450,
            )
        ],
    )

    assert store_distributed_late_session_board_snapshot("key", payload, ttl_seconds=600) is True
    loaded = load_distributed_late_session_board_snapshot("key")

    assert loaded is not None
    assert loaded.trade_date == "2026-06-13"
    assert loaded.items[0].late_session_state == LateSessionItemState.LATE_WATCH
