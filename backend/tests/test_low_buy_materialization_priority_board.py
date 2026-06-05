from __future__ import annotations

from types import SimpleNamespace

from app.services import low_buy_materialization as materialization


class _FakeSession:
    def __init__(self) -> None:
        self.rollback_count = 0

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def rollback(self) -> None:
        self.rollback_count += 1

    def commit(self) -> None:
        pass


def test_warm_priority_board_read_models_materializes_all_display_lanes(monkeypatch):
    calls: list[tuple[int, str, str]] = []

    class _FakeScreener:
        def priority_board(self, *, db, limit, refresh_mode, strategy_variant):  # noqa: ANN001
            calls.append((limit, refresh_mode, strategy_variant))
            return SimpleNamespace(
                latest_trade_date="2026-06-05",
                items=[SimpleNamespace(symbol=f"{strategy_variant}-{limit}")],
                total_candidates=1,
                read_path="priority_board_sync_warmup",
            )

    monkeypatch.setattr(materialization, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("app.services.low_buy_screener.LowBuyScreenerService", lambda: _FakeScreener())

    result = materialization.warm_priority_board_read_models(limits=(12,))

    assert result["ok"] is True
    assert result["skipped"] == []
    assert calls == [
        (12, "sync", "baseline"),
        (12, "sync", "front_row_weighted"),
        (12, "sync", "front_row_only"),
    ]
    assert [item["strategy_variant"] for item in result["warmed"]] == [
        "baseline",
        "front_row_weighted",
        "front_row_only",
    ]


def test_refresh_latest_materialization_warms_priority_board_after_publish(monkeypatch):
    warmed: list[str] = []

    monkeypatch.setattr(
        "app.services.low_buy.go_scan_worker.run_go_scan_worker",
        lambda **_kwargs: {"ok": True, "fallback_reason": ""},
    )
    monkeypatch.setattr(
        materialization,
        "_publish_latest_materialization_state",
        lambda _strategies: {
            "status": "success",
            "published_trade_date": "2026-06-05",
            "missing_strategies": [],
        },
    )
    monkeypatch.setattr(
        materialization,
        "warm_priority_board_read_models",
        lambda **_kwargs: warmed.append("priority_board") or {"ok": True, "warmed": [], "skipped": []},
    )
    monkeypatch.setattr(
        materialization,
        "warm_main_force_shadow_observations",
        lambda **_kwargs: {"ok": True, "enabled": False},
    )

    result = materialization.refresh_latest_low_buy_materialization(
        strategies=["first_board"],
        prefer_go=True,
    )

    assert result["ok"] is True
    assert warmed == ["priority_board"]
    assert result["priority_board_read_models"]["ok"] is True


def test_refresh_latest_materialization_reports_incomplete_when_priority_board_warmup_fails(monkeypatch):
    monkeypatch.setattr(
        "app.services.low_buy.go_scan_worker.run_go_scan_worker",
        lambda **_kwargs: {"ok": True, "fallback_reason": ""},
    )
    monkeypatch.setattr(
        materialization,
        "_publish_latest_materialization_state",
        lambda _strategies: {
            "status": "success",
            "published_trade_date": "2026-06-05",
            "missing_strategies": [],
        },
    )
    monkeypatch.setattr(
        materialization,
        "warm_priority_board_read_models",
        lambda **_kwargs: {
            "ok": False,
            "warmed": [],
            "skipped": [{"strategy_variant": "front_row_only", "limit": "12", "reason": "cache write failed"}],
        },
    )
    monkeypatch.setattr(
        materialization,
        "warm_main_force_shadow_observations",
        lambda **_kwargs: {"ok": True, "enabled": False},
    )

    result = materialization.refresh_latest_low_buy_materialization(
        strategies=["first_board"],
        prefer_go=True,
    )

    assert result["ok"] is False
    assert result["priority_board_read_models"]["ok"] is False
    assert result["priority_board_read_models"]["skipped"][0]["strategy_variant"] == "front_row_only"


def test_python_fallback_materialization_also_warms_priority_board(monkeypatch):
    warmed: list[str] = []

    class _FakeScreener:
        def refresh_full_scan_cache(self, **_kwargs):  # noqa: ANN001
            return SimpleNamespace(latest_trade_date="2026-06-05")

    monkeypatch.setattr("app.services.low_buy_screener.LowBuyScreenerService", lambda: _FakeScreener())
    monkeypatch.setattr(materialization, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(
        materialization,
        "publish_latest_trade_date_if_ready",
        lambda _db, strategies: {
            "status": "success",
            "published_trade_date": "2026-06-05",
            "missing_strategies": [],
        },
    )
    monkeypatch.setattr(
        materialization,
        "warm_priority_board_read_models",
        lambda **_kwargs: warmed.append("priority_board") or {"ok": True, "warmed": [], "skipped": []},
    )

    result = materialization.refresh_latest_low_buy_materialization(
        strategies=["first_board"],
        prefer_go=False,
    )

    assert result["ok"] is True
    assert result["source"] == "python"
    assert warmed == ["priority_board"]
    assert result["priority_board_read_models"]["ok"] is True
