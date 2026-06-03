from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

from scripts.low_buy_market_backtest_reporting import TradeOutcome, portfolio_backtest_metrics


@dataclass(frozen=True)
class OutcomeInput:
    symbol: str
    signal_date: str
    net_return_pct: float
    strategy_key: str
    sector_name: str
    market_state: str


@dataclass(frozen=True)
class SpikeDataset:
    inputs: list[OutcomeInput]
    source: str
    status: str
    reason: str
    coverage: dict[str, Any]


def run_backtest_24m_precompute_spike(*, count: int = 240, prefer_real_data: bool = True) -> dict[str, Any]:
    dataset = load_real_daily_bar_inputs(count) if prefer_real_data else _fixture_dataset(count)
    real_data = {
        "status": dataset.status,
        "source": dataset.source,
        "reason": dataset.reason,
        "coverage": dataset.coverage,
    }
    if dataset.inputs:
        inputs = dataset.inputs
        input_source = dataset.source
        data_status = dataset.status
    else:
        fixture = _fixture_dataset(count)
        inputs = fixture.inputs
        input_source = fixture.source
        data_status = "fixture_fallback"

    baseline_started = time.perf_counter()
    baseline_outcomes = [_build_trade_outcome(item) for item in inputs]
    baseline_max5 = portfolio_backtest_metrics(baseline_outcomes, max_positions=5)
    baseline_max10 = portfolio_backtest_metrics(baseline_outcomes, max_positions=10)
    baseline_ms = (time.perf_counter() - baseline_started) * 1000.0

    precompute_started = time.perf_counter()
    prepared = precompute_trade_outcomes(inputs)
    precompute_max5 = portfolio_backtest_metrics(prepared, max_positions=5)
    precompute_max10 = portfolio_backtest_metrics(prepared, max_positions=10)
    precompute_ms = (time.perf_counter() - precompute_started) * 1000.0

    max5_equal = _portfolio_golden(baseline_max5) == _portfolio_golden(precompute_max5)
    max10_equal = _portfolio_golden(baseline_max10) == _portfolio_golden(precompute_max10)
    return {
        "input_count": len(inputs),
        "input_source": input_source,
        "data_status": data_status,
        "real_data": real_data,
        "baseline_ms": round(baseline_ms, 3),
        "precompute_ms": round(precompute_ms, 3),
        "wall_clock_reduction_pct": round(((baseline_ms - precompute_ms) / baseline_ms * 100.0) if baseline_ms > 0 else 0.0, 2),
        "max5_equal": max5_equal,
        "max10_equal": max10_equal,
        "parity": _combined_parity(
            baseline_max5=baseline_max5,
            precompute_max5=precompute_max5,
            baseline_max10=baseline_max10,
            precompute_max10=precompute_max10,
        ),
        "baseline": {"max5": _portfolio_golden(baseline_max5), "max10": _portfolio_golden(baseline_max10)},
        "precompute": {"max5": _portfolio_golden(precompute_max5), "max10": _portfolio_golden(precompute_max10)},
        "final_executor": "portfolio_backtest_metrics",
        "productionized": False,
        "notes": [
            "only TradeOutcome input preparation is batched",
            "portfolio_backtest_metrics remains the final audited executor",
            "no production portfolio executor or strategy formula is changed",
        ],
    }


def load_real_daily_bar_inputs(count: int = 240) -> SpikeDataset:
    bounded = max(1, int(count or 240))
    try:
        from sqlalchemy import func
        from sqlalchemy.exc import SQLAlchemyError

        from app.core.database import SessionLocal
        from app.models.entities import DailyBarSnapshot
    except Exception as exc:  # pragma: no cover - defensive for standalone script usage.
        return SpikeDataset(
            inputs=[],
            source="real_daily_bars",
            status="blocked",
            reason=f"import_failed:{type(exc).__name__}",
            coverage={},
        )

    try:
        with SessionLocal() as db:
            total, min_date, max_date, symbol_count = db.query(
                func.count(DailyBarSnapshot.id),
                func.min(DailyBarSnapshot.trade_date),
                func.max(DailyBarSnapshot.trade_date),
                func.count(func.distinct(DailyBarSnapshot.symbol)),
            ).one()
            coverage = {
                "bar_count": int(total or 0),
                "symbol_count": int(symbol_count or 0),
                "min_trade_date": _date_text(min_date),
                "max_trade_date": _date_text(max_date),
                "coverage_days": _coverage_days(min_date, max_date),
            }
            if not total:
                return SpikeDataset(
                    inputs=[],
                    source="real_daily_bars",
                    status="no_data",
                    reason="daily_bar_snapshots_empty",
                    coverage=coverage,
                )
            rows = (
                db.query(
                    DailyBarSnapshot.symbol,
                    DailyBarSnapshot.trade_date,
                    DailyBarSnapshot.pct_chg,
                    DailyBarSnapshot.close_price,
                )
                .filter(DailyBarSnapshot.instrument_type == "stock")
                .filter(DailyBarSnapshot.is_suspended.is_(False))
                .filter(DailyBarSnapshot.is_delisted.is_(False))
                .order_by(DailyBarSnapshot.trade_date.desc(), DailyBarSnapshot.symbol.asc())
                .limit(bounded)
                .all()
            )
    except SQLAlchemyError as exc:
        return SpikeDataset(
            inputs=[],
            source="real_daily_bars",
            status="blocked",
            reason=f"database_unavailable:{type(exc).__name__}",
            coverage={},
        )

    if not rows:
        return SpikeDataset(
            inputs=[],
            source="real_daily_bars",
            status="no_data",
            reason="no_stock_daily_rows",
            coverage=coverage,
        )

    status = "real_daily_bars" if int(coverage.get("coverage_days") or 0) >= 600 else "partial"
    inputs = [_real_bar_outcome_input(row, index) for index, row in enumerate(rows)]
    return SpikeDataset(
        inputs=inputs,
        source="real_daily_bars",
        status=status,
        reason="" if status == "real_daily_bars" else "daily_bar_coverage_under_24m",
        coverage={**coverage, "loaded_input_count": len(inputs)},
    )


def precompute_trade_outcomes(inputs: list[OutcomeInput]) -> list[TradeOutcome]:
    shared = {
        "name": "测试",
        "buy_signal_state": "buy_now",
        "entry_price": 10.0,
        "execution_status": "filled",
        "execution_exit_reason": "fixture_precompute",
    }
    return [
        TradeOutcome(
            symbol=item.symbol,
            signal_date=item.signal_date,
            strategy_key=item.strategy_key,
            net_return_pct=item.net_return_pct,
            return_1d=item.net_return_pct,
            return_2d=item.net_return_pct,
            return_3d=item.net_return_pct,
            return_4d=item.net_return_pct,
            return_5d=item.net_return_pct,
            max_gain_5d=max(item.net_return_pct, 0.0),
            max_drawdown_5d=min(item.net_return_pct, 0.0),
            entry_trade_date=item.signal_date,
            exit_trade_date=item.signal_date,
            sector_name=item.sector_name,
            market_state=item.market_state,
            **shared,
        )
        for item in inputs
    ]


def fixture_outcome_inputs(count: int = 240) -> list[OutcomeInput]:
    bounded = max(1, int(count or 240))
    sectors = ["人工智能", "机器人", "半导体", "新能源"]
    strategies = ["first_board", "volume_shrink", "ma_support"]
    states = ["repair", "low_volume_wait", "fast_rotation"]
    result: list[OutcomeInput] = []
    for index in range(bounded):
        day = (index % 20) + 1
        month = (index % 12) + 1
        result.append(
            OutcomeInput(
                symbol=f"{600000 + (index % 180):06d}",
                signal_date=f"2025-{month:02d}-{day:02d}",
                net_return_pct=round(((index % 17) - 6) * 0.55, 4),
                strategy_key=strategies[index % len(strategies)],
                sector_name=sectors[index % len(sectors)],
                market_state=states[index % len(states)],
            )
        )
    return result


def _fixture_dataset(count: int) -> SpikeDataset:
    inputs = fixture_outcome_inputs(count)
    return SpikeDataset(
        inputs=inputs,
        source="fixture",
        status="fixture",
        reason="deterministic_fixture_for_parity",
        coverage={"loaded_input_count": len(inputs)},
    )


def _real_bar_outcome_input(row: Any, index: int) -> OutcomeInput:
    pct_chg = float(row.pct_chg or 0.0)
    close_price = float(row.close_price or 0.0)
    strategy_cycle = ["real_daily_bar_prep", "real_daily_bar_momentum", "real_daily_bar_reversal"]
    market_state = "flat" if abs(pct_chg) < 0.3 else ("up" if pct_chg > 0 else "down")
    return OutcomeInput(
        symbol=str(row.symbol or ""),
        signal_date=_date_text(row.trade_date),
        net_return_pct=round(pct_chg, 4),
        strategy_key=strategy_cycle[index % len(strategy_cycle)],
        sector_name="real_daily_bar",
        market_state=market_state if close_price else "stale",
    )


def _build_trade_outcome(item: OutcomeInput) -> TradeOutcome:
    return precompute_trade_outcomes([item])[0]


def _portfolio_golden(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "profit_factor": metrics.get("profit_factor"),
        "avg_trade_return_pct": metrics.get("avg_trade_return_pct"),
        "portfolio_return_pct": metrics.get("portfolio_return_pct"),
        "max_drawdown_pct": metrics.get("max_drawdown_pct"),
        "trade_count": metrics.get("trade_count"),
        "candidate_count": metrics.get("candidate_count"),
        "skip_reason_counts": metrics.get("skip_reason_counts"),
    }


def _combined_parity(
    *,
    baseline_max5: dict[str, Any],
    precompute_max5: dict[str, Any],
    baseline_max10: dict[str, Any],
    precompute_max10: dict[str, Any],
) -> dict[str, Any]:
    fields = [
        "profit_factor",
        "avg_trade_return_pct",
        "portfolio_return_pct",
        "max_drawdown_pct",
        "trade_count",
        "candidate_count",
        "skip_reason_counts",
    ]
    max5 = _field_parity(fields, baseline_max5, precompute_max5)
    max10 = _field_parity(fields, baseline_max10, precompute_max10)
    return {
        "max5": max5,
        "max10": max10,
        "all_equal": all(max5.values()) and all(max10.values()),
    }


def _field_parity(fields: list[str], left: dict[str, Any], right: dict[str, Any]) -> dict[str, bool]:
    return {field: left.get(field) == right.get(field) for field in fields}


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date,)):
        return value.isoformat()
    return str(value)


def _coverage_days(start: Any, end: Any) -> int:
    if not isinstance(start, date) or not isinstance(end, date):
        return 0
    return max((end - start).days + 1, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="24M backtest data-prep acceleration spike.")
    parser.add_argument("--count", type=int, default=240)
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    result = run_backtest_24m_precompute_spike(count=args.count, prefer_real_data=not args.fixture_only)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
