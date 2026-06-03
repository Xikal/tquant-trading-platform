from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScanCandidate:
    symbol: str
    score: float
    buy_signal_state: str
    payload_hash: str


def run_parallel_scan_spike(
    *,
    symbols: list[str],
    trade_date: str,
    strategy_key: str = "first_board",
    max_workers: int = 8,
    simulate_io_seconds: float = 0.001,
) -> dict[str, Any]:
    serial_started = time.perf_counter()
    serial = [_evaluate_symbol(symbol, trade_date, strategy_key, simulate_io_seconds) for symbol in symbols]
    serial_ms = (time.perf_counter() - serial_started) * 1000.0

    parallel_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(int(max_workers or 1), 1)) as pool:
        parallel = list(pool.map(lambda symbol: _evaluate_symbol(symbol, trade_date, strategy_key, simulate_io_seconds), symbols))
    parallel_ms = (time.perf_counter() - parallel_started) * 1000.0

    serial_payload = _canonical_payload(serial)
    parallel_payload = _canonical_payload(parallel)
    wall_clock_reduction_pct = ((serial_ms - parallel_ms) / serial_ms * 100.0) if serial_ms > 0 else 0.0
    return {
        "strategy_key": strategy_key,
        "trade_date": trade_date,
        "symbol_count": len(symbols),
        "serial_ms": round(serial_ms, 3),
        "parallel_ms": round(parallel_ms, 3),
        "wall_clock_reduction_pct": round(wall_clock_reduction_pct, 2),
        "serial": _summary(serial),
        "parallel": _summary(parallel),
        "golden_equal": serial_payload == parallel_payload,
        "ordering_equal": [item["symbol"] for item in serial_payload] == [item["symbol"] for item in parallel_payload],
        "payload_hash": _payload_hash(serial_payload),
        "db_query_delta": 0,
        "productionized": False,
        "notes": [
            "fixture-only spike; no production table writes",
            "parallel map preserves one output per input symbol before canonical ordering",
        ],
    }


def fixture_symbols(count: int = 200) -> list[str]:
    bounded = max(1, min(int(count or 200), 300))
    return [f"{600000 + index:06d}" for index in range(bounded)]


def _evaluate_symbol(symbol: str, trade_date: str, strategy_key: str, simulate_io_seconds: float) -> ScanCandidate:
    if simulate_io_seconds > 0:
        time.sleep(simulate_io_seconds)
    seed = int(hashlib.sha256(f"{strategy_key}|{trade_date}|{symbol}".encode("utf-8")).hexdigest()[:8], 16)
    score = round(50.0 + (seed % 5000) / 100.0, 4)
    state = "buy_now" if score >= 92 else "near_entry" if score >= 82 else "watch"
    payload_hash = _payload_hash({"symbol": symbol, "score": score, "buy_signal_state": state})
    return ScanCandidate(symbol=symbol, score=score, buy_signal_state=state, payload_hash=payload_hash)


def _summary(items: list[ScanCandidate]) -> dict[str, Any]:
    ordered = _canonical_payload(items)
    return {
        "candidate_count": len(ordered),
        "buy_signal_state_counts": {
            state: sum(1 for item in ordered if item["buy_signal_state"] == state)
            for state in ("buy_now", "near_entry", "watch")
        },
        "top_symbols": [item["symbol"] for item in ordered[:10]],
        "top_scores": [item["score"] for item in ordered[:10]],
    }


def _canonical_payload(items: list[ScanCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "symbol": item.symbol,
            "score": item.score,
            "buy_signal_state": item.buy_signal_state,
            "payload_hash": item.payload_hash,
        }
        for item in sorted(items, key=lambda item: (-item.score, item.symbol))
    ]


def _payload_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fixture-only full-market scan parallelization spike.")
    parser.add_argument("--symbols", type=int, default=200)
    parser.add_argument("--trade-date", default="2026-06-03")
    parser.add_argument("--strategy-key", default="first_board")
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--simulate-io-seconds", type=float, default=0.001)
    args = parser.parse_args()
    result = run_parallel_scan_spike(
        symbols=fixture_symbols(args.symbols),
        trade_date=args.trade_date,
        strategy_key=args.strategy_key,
        max_workers=args.max_workers,
        simulate_io_seconds=args.simulate_io_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

