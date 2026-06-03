from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
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


def run_backtest_24m_precompute_spike(*, count: int = 240) -> dict[str, Any]:
    inputs = fixture_outcome_inputs(count)
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

    return {
        "input_count": len(inputs),
        "baseline_ms": round(baseline_ms, 3),
        "precompute_ms": round(precompute_ms, 3),
        "wall_clock_reduction_pct": round(((baseline_ms - precompute_ms) / baseline_ms * 100.0) if baseline_ms > 0 else 0.0, 2),
        "max5_equal": _portfolio_golden(baseline_max5) == _portfolio_golden(precompute_max5),
        "max10_equal": _portfolio_golden(baseline_max10) == _portfolio_golden(precompute_max10),
        "baseline": {"max5": _portfolio_golden(baseline_max5), "max10": _portfolio_golden(baseline_max10)},
        "precompute": {"max5": _portfolio_golden(precompute_max5), "max10": _portfolio_golden(precompute_max10)},
        "final_executor": "portfolio_backtest_metrics",
        "productionized": False,
        "notes": [
            "only TradeOutcome input preparation is batched",
            "portfolio_backtest_metrics remains the final audited executor",
        ],
    }


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Fixture-only 24M backtest precompute acceleration spike.")
    parser.add_argument("--count", type=int, default=240)
    args = parser.parse_args()
    result = run_backtest_24m_precompute_spike(count=args.count)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

