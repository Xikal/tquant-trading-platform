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


def test_refresh_latest_materialization_falls_back_when_go_reference_is_async(monkeypatch):
    scanned: list[dict] = []
    published: list[list[str]] = []

    class _FakeScreener:
        def refresh_full_scan_cache(self, **kwargs):  # noqa: ANN001
            scanned.append(kwargs)
            return SimpleNamespace(latest_trade_date="2026-06-12")

    monkeypatch.setattr(
        "app.services.low_buy.go_scan_worker.run_go_scan_worker",
        lambda **_kwargs: {"ok": True, "accepted": True, "status": "accepted", "job_id": "42"},
    )
    monkeypatch.setattr("app.services.low_buy_screener.LowBuyScreenerService", lambda: _FakeScreener())
    monkeypatch.setattr(materialization, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(
        materialization,
        "publish_latest_trade_date_if_ready",
        lambda _db, strategies: published.append(list(strategies))
        or {
            "status": "success",
            "published_trade_date": "2026-06-12",
            "missing_strategies": [],
        },
    )
    monkeypatch.setattr(
        materialization,
        "warm_priority_board_read_models",
        lambda **_kwargs: {"ok": True, "warmed": [], "skipped": []},
    )

    result = materialization.refresh_latest_low_buy_materialization(
        strategies=["first_board"],
        prefer_go=True,
    )

    assert result["ok"] is True
    assert result["source"] == "python_fallback"
    assert result["fallback_reason"] == "go_scan_worker_accepted_async"
    assert scanned == [
        {
            "strategy": "first_board",
            "limit": materialization.DEFAULT_LIMIT,
            "scan_limit": materialization.DEFAULT_SCAN_LIMIT,
            "include_history": False,
            "compute_performance": True,
            "build_close_review": False,
        }
    ]
    assert published == [["first_board"]]


def test_refresh_latest_materialization_skips_non_production_strategies_without_full_failure(monkeypatch):
    scanned: list[list[str]] = []

    monkeypatch.setattr(
        "app.services.low_buy.go_scan_worker.run_go_scan_worker",
        lambda **kwargs: scanned.append(list(kwargs["strategies"])) or {"ok": True, "fallback_reason": ""},
    )
    monkeypatch.setattr(
        materialization,
        "_publish_latest_materialization_state",
        lambda strategies: {
            "status": "success",
            "expected_trade_date": "2026-06-05",
            "published_trade_date": "2026-06-05",
            "daily_bar_count": 5000,
            "min_daily_bar_count": 4500,
            "post_close_daily_bars_ready": True,
            "missing_strategies": [],
            "required_strategies": list(strategies),
        },
    )
    monkeypatch.setattr(
        materialization,
        "warm_priority_board_read_models",
        lambda **_kwargs: {"ok": True, "warmed": [], "skipped": []},
    )
    monkeypatch.setattr(
        materialization,
        "warm_main_force_shadow_observations",
        lambda **_kwargs: {"ok": True, "enabled": False},
    )

    result = materialization.refresh_latest_low_buy_materialization(
        strategies=["first_board", "classic_retrace", "deep_pullback"],
        prefer_go=True,
    )

    assert scanned == [["first_board"]]
    assert result["ok"] is True
    assert result["missing_required_strategies"] == []
    assert result["is_partial"] is True
    assert result["stale_reason"] == "skipped_non_production_strategies"
    assert {item["strategy"] for item in result["skipped_strategies"]} == {"classic_retrace", "deep_pullback"}


def test_refresh_latest_materialization_fails_when_required_strategy_missing(monkeypatch):
    monkeypatch.setattr(
        "app.services.low_buy.go_scan_worker.run_go_scan_worker",
        lambda **_kwargs: {"ok": True, "fallback_reason": ""},
    )
    monkeypatch.setattr(
        materialization,
        "_publish_latest_materialization_state",
        lambda _strategies: {
            "status": "pending",
            "expected_trade_date": "2026-06-05",
            "published_trade_date": "",
            "daily_bar_count": 5000,
            "min_daily_bar_count": 4500,
            "post_close_daily_bars_ready": True,
            "missing_strategies": ["first_board"],
        },
    )
    monkeypatch.setattr(
        materialization,
        "warm_priority_board_read_models",
        lambda **_kwargs: {"ok": True, "warmed": [], "skipped": []},
    )
    monkeypatch.setattr(
        materialization,
        "warm_main_force_shadow_observations",
        lambda **_kwargs: {"ok": True, "enabled": False},
    )

    result = materialization.refresh_latest_low_buy_materialization(
        strategies=["first_board", "classic_retrace"],
        prefer_go=True,
    )

    assert result["ok"] is False
    assert result["missing_required_strategies"] == ["first_board"]
    assert result["publish_status"]["status"] == "pending"
    assert result["publish_status"]["published_trade_date"] == ""
    assert result["stale_reason"] == "missing_required_strategies"


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
