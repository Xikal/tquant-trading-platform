from __future__ import annotations

from datetime import date, timedelta

from app.services.strategy_engine.parity_tracker import (
    PARITY_BOUNDARY_NOTE,
    StrategyEngineParityObservation,
    build_strategy_engine_parity_report,
    parity_observation_from_shadow_payload,
)
from app.services.strategy_engine.shadow import low_buy_strategy_engine_shadow_payload
from app.services.low_buy.production_scoring import score_low_buy_candidate_for_production
from test_low_buy_production_scoring import _front_row_candidate


def test_strategy_engine_parity_tracker_accumulates_30_trading_days_without_production_adoption() -> None:
    observations: list[StrategyEngineParityObservation] = []
    for index in range(30):
        observations.append(
            StrategyEngineParityObservation(
                trade_date=(date(2026, 1, 1) + timedelta(days=index)).isoformat(),
                strategy_key="first_board" if index < 20 else "volume_shrink",
                symbol=f"600{index:03d}",
                production_priority_score=80.0,
                strategy_engine_production_score=80.0 if index != 5 else 78.5,
                production_watch_score=72.0,
                strategy_engine_watch_score=72.0,
                parity_status="match" if index != 5 else "production_score_delta",
                decision="production_candidate",
                signal_state="soft_buy_now",
            )
        )
    observations.append(
        StrategyEngineParityObservation(
            trade_date="2026-01-30",
            strategy_key="first_board",
            symbol="600999",
            production_priority_score=0.0,
            strategy_engine_production_score=None,
            production_watch_score=10.0,
            strategy_engine_watch_score=0.0,
            parity_status="production_score_delta",
            decision="watch_only",
            signal_state="near_entry",
        )
    )

    report = build_strategy_engine_parity_report(observations)

    assert report["status"] == "ok"
    assert report["trading_day_count"] == 30
    assert report["sample_count"] == 31
    assert report["shadow_only"] is True
    assert report["replacement_enabled"] is False
    assert report["production_adoption_allowed"] is False
    assert report["boundary_note"] == PARITY_BOUNDARY_NOTE
    assert report["overall"]["missing_rate_pct"] > 0
    assert report["overall"]["production_score_delta"]["max_abs"] == 1.5
    assert report["overall"]["watch_zero_rate_pct"] > 0
    assert report["by_strategy"]["first_board"]["sample_count"] == 21
    assert report["by_strategy"]["volume_shrink"]["sample_count"] == 10


def test_strategy_engine_parity_tracker_blocks_when_history_is_short() -> None:
    report = build_strategy_engine_parity_report(
        [
            StrategyEngineParityObservation(
                trade_date="2026-01-01",
                strategy_key="first_board",
                production_priority_score=80.0,
                strategy_engine_production_score=80.0,
            )
        ]
    )

    assert report["status"] == "insufficient_history"
    assert report["trading_day_count"] == 1
    assert report["production_adoption_allowed"] is False


def test_shadow_payload_can_be_converted_to_parity_observation() -> None:
    candidate = _front_row_candidate("first_board")
    existing = score_low_buy_candidate_for_production(candidate)
    payload = low_buy_strategy_engine_shadow_payload(
        candidate,
        current_production_score=existing.production_score,
        current_watch_score=existing.watch_score,
    )

    observation = parity_observation_from_shadow_payload(
        payload,
        trade_date="2026-01-01",
        current_production_score=existing.production_score,
        current_watch_score=existing.watch_score,
    )

    assert observation.strategy_key == "first_board"
    assert observation.trade_date == "2026-01-01"
    assert observation.strategy_engine_production_score == existing.production_score
    assert observation.strategy_engine_watch_score == existing.watch_score
    assert observation.parity_status == "match"
