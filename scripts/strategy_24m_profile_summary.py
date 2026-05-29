"""Lightweight profiling for the strategy optimization report pipeline."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
REPORT_DATE = "2026-05-28"


def build_profile(report_date: str = REPORT_DATE, root: Path = ROOT, iterations: int = 3) -> dict[str, Any]:
    from generate_strategy_24m_optimization_report import _build_strategy_items, _read_sources, build_report
    from strategy_24m_scope_coverage import scope_coverage

    iterations = max(1, min(int(iterations or 1), 10))
    source_date = report_date
    sources = _read_sources(root, source_date)
    steps = [
        _profile_step("read_sources", lambda: _read_sources(root, source_date), iterations),
        _profile_step("build_strategy_items", lambda: _build_strategy_items(sources), iterations),
        _profile_step("build_scope_coverage", lambda: scope_coverage(sources), iterations),
        _profile_step("build_full_report", lambda: build_report(report_date=report_date, source_date=source_date, root=root), iterations),
    ]
    bottleneck = max(steps, key=lambda item: item["avg_ms"]) if steps else {}
    return {
        "title": "策略优化报告轻量 profiling 摘要",
        "report_date": report_date,
        "iterations": iterations,
        "profile_scope": "report_generation_and_existing_json_aggregation_only",
        "full_backtest_profiled": False,
        "data_refetch": False,
        "steps": steps,
        "bottleneck_step": bottleneck.get("step"),
        "bottleneck_avg_ms": bottleneck.get("avg_ms", 0.0),
        "go_rust_recommendation": _go_rust_recommendation(steps),
        "existing_rust_parity": {
            "status": "covered_by_tests",
            "test_file": "backend/tests/test_finance_performance_math.py",
            "covered_metrics": [
                "max_drawdown",
                "rolling_mean",
                "rolling_std",
                "volatility",
                "correlation",
                "beta",
                "bollinger_bands",
                "ATR Wilder",
                "RSI Wilder",
                "VWAP",
                "RankIC",
            ],
        },
    }


def write_profile(payload: dict[str, Any], root: Path = ROOT) -> Path:
    path = root / "docs" / "reports" / f"strategy-24m-profile-{payload['report_date']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _profile_step(name: str, fn: Callable[[], Any], iterations: int) -> dict[str, Any]:
    samples: list[float] = []
    output_shape: dict[str, Any] = {}
    for _ in range(iterations):
        start = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - start) * 1000.0)
        output_shape = _shape(result)
    return {
        "step": name,
        "iterations": iterations,
        "avg_ms": _round(statistics.mean(samples)),
        "min_ms": _round(min(samples)),
        "max_ms": _round(max(samples)),
        "output_shape": output_shape,
    }


def _shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"type": "dict", "key_count": len(value)}
    if isinstance(value, list):
        return {"type": "list", "item_count": len(value)}
    return {"type": type(value).__name__}


def _go_rust_recommendation(steps: list[dict[str, Any]]) -> dict[str, Any]:
    if not steps:
        return {
            "use_go_or_rust_now": False,
            "reason": "没有可用 profile 样本。",
        }
    bottleneck = max(steps, key=lambda item: item["avg_ms"])
    if float(bottleneck["avg_ms"]) < 1000.0:
        return {
            "use_go_or_rust_now": False,
            "reason": "本轮瓶颈在报告 JSON 聚合，平均耗时低于 1 秒，不值得迁移 Go/Rust。",
            "candidate_future_modules": [
                "全市场多参数候选网格回测 worker",
                "大规模分钟线 ETF T0 参数扫描",
            ],
        }
    return {
        "use_go_or_rust_now": False,
        "reason": "本轮只做轻量 profile；如要迁移，需先对完整候选网格回测单独 profile 并做 parity。",
        "candidate_future_modules": [
            "全市场多参数候选网格回测 worker",
            "大规模分钟线 ETF T0 参数扫描",
        ],
    }


def _round(value: float) -> float:
    return round(float(value), 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=REPORT_DATE)
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()
    path = write_profile(build_profile(report_date=args.date, iterations=args.iterations))
    print(json.dumps({"json": str(path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
