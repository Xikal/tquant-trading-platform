from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.backtest.validator import ValidationReport, ValidationWindow


def enrich_regime_aware_report(report: ValidationReport) -> ValidationReport:
    from app.services.backtest.validator import ValidationReport as RuntimeValidationReport

    by_market_state, best_params_by_market_state, state_window_details = build_regime_aware_payload(report.windows)
    return RuntimeValidationReport(
        window_count=report.window_count,
        avg_oos_sharpe=report.avg_oos_sharpe,
        oos_pass_rate=report.oos_pass_rate,
        pbo_risk=report.pbo_risk,
        downgrade_review=report.downgrade_review,
        stability_conclusion=report.stability_conclusion,
        windows=report.windows,
        by_market_state=by_market_state,
        best_params_by_market_state=best_params_by_market_state,
        state_window_details=state_window_details,
    )


def build_regime_aware_payload(
    windows: list[ValidationWindow],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    buckets: dict[str, dict[str, Any]] = {}
    details: dict[str, list[dict[str, Any]]] = {}
    for window in windows:
        state = _dominant_state(window.market_state_segments)
        train_state = _dominant_state(window.train_market_state_segments)
        bucket = buckets.setdefault(state, _empty_bucket())
        bucket["window_count"] += 1
        bucket["passed_windows"] += 1 if window.passed else 0
        bucket["failed_windows"] += 0 if window.passed else 1
        bucket["avg_oos_sharpe"] += float(window.test_sharpe or 0.0)
        bucket["avg_oos_return_pct"] += float(window.test_return_pct or 0.0)
        bucket["avg_max_drawdown_pct"] += float(window.max_drawdown_pct or 0.0)
        bucket["signal_count"] += _segment_signal_count(window.market_state_segments)
        _record_params(bucket, window.best_params, float(window.test_sharpe or 0.0))
        details.setdefault(state, []).append(
            {
                "train_start": window.train_start,
                "train_end": window.train_end,
                "test_start": window.test_start,
                "test_end": window.test_end,
                "train_market_state": train_state,
                "test_market_state": state,
                "passed": window.passed,
                "oos_failed": window.oos_failed,
                "failure_reason": window.failure_reason,
                "test_sharpe": window.test_sharpe,
                "test_return_pct": window.test_return_pct,
                "max_drawdown_pct": window.max_drawdown_pct,
                "best_params": dict(window.best_params or {}),
            }
        )
    best_params_by_state: dict[str, dict[str, Any]] = {}
    for state, bucket in buckets.items():
        count = max(int(bucket["window_count"]), 1)
        bucket["avg_oos_sharpe"] = round(float(bucket["avg_oos_sharpe"]) / count, 4)
        bucket["avg_oos_return_pct"] = round(float(bucket["avg_oos_return_pct"]) / count, 4)
        bucket["avg_max_drawdown_pct"] = round(float(bucket["avg_max_drawdown_pct"]) / count, 4)
        bucket["pass_rate"] = round(float(bucket["passed_windows"]) / count, 4)
        best_params = _best_params(bucket.pop("_param_counts", {}))
        bucket["best_params"] = best_params
        best_params_by_state[state] = best_params
    return buckets, best_params_by_state, details


def _dominant_state(segments: list[dict[str, Any]] | None) -> str:
    if not segments:
        return "未标注"
    best = max(
        segments,
        key=lambda item: int(item.get("signal_count") or item.get("trade_count") or 0),
    )
    return str(best.get("name") or best.get("label") or best.get("market_state") or "未标注")


def _segment_signal_count(segments: list[dict[str, Any]] | None) -> int:
    if not segments:
        return 0
    return sum(int(item.get("signal_count") or item.get("trade_count") or 0) for item in segments)


def _record_params(bucket: dict[str, Any], params: dict[str, Any], test_sharpe: float) -> None:
    key = tuple(sorted((str(name), str(value)) for name, value in (params or {}).items()))
    counts = bucket.setdefault("_param_counts", {})
    row = counts.setdefault(key, {"count": 0, "params": dict(params or {}), "sharpe_sum": 0.0})
    row["count"] += 1
    row["sharpe_sum"] += test_sharpe


def _best_params(counts: dict[Any, dict[str, Any]]) -> dict[str, Any]:
    if not counts:
        return {}
    best = max(
        counts.values(),
        key=lambda item: (int(item.get("count") or 0), float(item.get("sharpe_sum") or 0.0)),
    )
    return dict(best.get("params") or {})


def _empty_bucket() -> dict[str, Any]:
    return {
        "window_count": 0,
        "signal_count": 0,
        "passed_windows": 0,
        "failed_windows": 0,
        "avg_oos_sharpe": 0.0,
        "avg_oos_return_pct": 0.0,
        "avg_max_drawdown_pct": 0.0,
        "_param_counts": {},
    }
