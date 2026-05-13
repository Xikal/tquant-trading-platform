from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable

from app.services.backtest.engine import BacktestConfig, BacktestEngine
from app.services.backtest.optimizer import (
    BacktestOptimizer,
    OptimizationCandidate,
    enumerate_param_sets,
)


ProgressCallback = Callable[[float, str], None]
DEFAULT_OOS_TOP_K = 10


@dataclass(frozen=True)
class ValidationWindow:
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_sharpe: float
    test_sharpe: float
    train_return_pct: float
    test_return_pct: float
    max_drawdown_pct: float
    best_params: dict[str, Any]
    is_rank: int
    oos_rank: int
    passed: bool
    overfit_signal: bool
    oos_failed: bool = False
    failure_reason: str = ""
    train_market_state_segments: list[dict[str, Any]] | None = None
    market_state_segments: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationReport:
    window_count: int
    avg_oos_sharpe: float
    oos_pass_rate: float
    pbo_risk: str
    downgrade_review: bool
    stability_conclusion: str
    windows: list[ValidationWindow]
    by_market_state: dict[str, Any] | None = None
    best_params_by_market_state: dict[str, dict[str, Any]] | None = None
    state_window_details: dict[str, list[dict[str, Any]]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_count": self.window_count,
            "avg_oos_sharpe": self.avg_oos_sharpe,
            "oos_pass_rate": self.oos_pass_rate,
            "pbo_risk": self.pbo_risk,
            "downgrade_review": self.downgrade_review,
            "downgrade_review_required": self.downgrade_review,
            "stability_conclusion": self.stability_conclusion,
            "by_market_state": self.by_market_state or {},
            "best_params_by_market_state": self.best_params_by_market_state or {},
            "state_window_details": self.state_window_details or {},
            "windows": [item.to_dict() for item in self.windows],
        }


class BacktestValidator:
    """Walk-forward validation: optimize in train windows, verify in OOS windows."""

    def __init__(self, engine: BacktestEngine) -> None:
        self.engine = engine
        self.optimizer = BacktestOptimizer(engine)

    def generate_windows(
        self,
        *,
        start_date: str,
        end_date: str,
        window_count: int = 4,
        train_ratio: float = 0.75,
    ) -> list[tuple[str, str, str, str]]:
        trade_dates = self.engine.data_provider.fetch_trade_dates(start_date, end_date)
        dates = trade_dates or _calendar_dates(start_date, end_date)
        if len(dates) < 4:
            return []
        total = len(dates)
        window_span = max(int(total / max(window_count, 1)), 2)
        train_len = max(int(window_span * train_ratio), 1)
        test_len = max(window_span - train_len, 1)
        step = test_len
        windows: list[tuple[str, str, str, str]] = []
        start_index = 0
        while len(windows) < window_count:
            train_start_index = start_index
            train_end_index = train_start_index + train_len - 1
            test_start_index = train_end_index + 1
            test_end_index = test_start_index + test_len - 1
            if test_end_index >= total:
                break
            windows.append(
                (
                    dates[train_start_index],
                    dates[train_end_index],
                    dates[test_start_index],
                    dates[test_end_index],
                )
            )
            start_index += step
        return windows

    def walk_forward(
        self,
        base_config: BacktestConfig,
        *,
        param_grid: dict[str, list[Any]],
        start_date: str,
        end_date: str,
        window_count: int = 4,
        train_ratio: float = 0.75,
        max_combinations: int = 500,
        score_key: str = "sharpe",
        oos_top_k: int = DEFAULT_OOS_TOP_K,
        cancel_token: Any | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ValidationReport:
        windows = self.generate_windows(
            start_date=start_date,
            end_date=end_date,
            window_count=window_count,
            train_ratio=train_ratio,
        )
        return self.walk_forward_windows(
            base_config,
            param_grid=param_grid,
            windows=windows,
            max_combinations=max_combinations,
            score_key=score_key,
            oos_top_k=oos_top_k,
            cancel_token=cancel_token,
            progress_callback=progress_callback,
        )

    def regime_aware_walk_forward(
        self,
        base_config: BacktestConfig,
        *,
        param_grid: dict[str, list[Any]],
        start_date: str,
        end_date: str,
        window_count: int = 4,
        train_ratio: float = 0.75,
        max_combinations: int = 500,
        score_key: str = "sharpe",
        oos_top_k: int = DEFAULT_OOS_TOP_K,
        cancel_token: Any | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ValidationReport:
        report = self.walk_forward(
            base_config,
            param_grid=param_grid,
            start_date=start_date,
            end_date=end_date,
            window_count=window_count,
            train_ratio=train_ratio,
            max_combinations=max_combinations,
            score_key=score_key,
            oos_top_k=oos_top_k,
            cancel_token=cancel_token,
            progress_callback=progress_callback,
        )
        from app.services.backtest.regime_walkforward import enrich_regime_aware_report

        return enrich_regime_aware_report(report)

    def walk_forward_windows(
        self,
        base_config: BacktestConfig,
        *,
        param_grid: dict[str, list[Any]],
        windows: list[tuple[str, str, str, str]],
        max_combinations: int = 500,
        score_key: str = "sharpe",
        oos_top_k: int = DEFAULT_OOS_TOP_K,
        cancel_token: Any | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ValidationReport:
        param_sets, _, _ = enumerate_param_sets(param_grid, max_combinations=max_combinations)
        rows: list[ValidationWindow] = []
        total_windows = max(len(windows), 1)
        for window_index, (train_start, train_end, test_start, test_end) in enumerate(windows):
            if _cancel_requested(cancel_token):
                break
            window_progress_start = window_index / total_windows * 95
            window_progress_end = (window_index + 1) / total_windows * 95
            train_candidates = self.optimizer.evaluate_param_sets(
                base_config,
                param_sets=param_sets,
                start_date=train_start,
                end_date=train_end,
                score_key=score_key,
                period="is",
                cancel_token=cancel_token,
                progress_start=window_progress_start,
                progress_end=window_progress_start + (window_progress_end - window_progress_start) * 0.55,
                progress_callback=progress_callback,
            )
            if not train_candidates or _cancel_requested(cancel_token):
                break
            oos_candidates = train_candidates[: max(1, min(int(oos_top_k or DEFAULT_OOS_TOP_K), len(train_candidates)))]
            test_candidates = self.optimizer.evaluate_param_sets(
                base_config,
                param_sets=[item.params for item in oos_candidates],
                start_date=test_start,
                end_date=test_end,
                score_key=score_key,
                period="oos",
                cancel_token=cancel_token,
                progress_start=window_progress_start + (window_progress_end - window_progress_start) * 0.55,
                progress_end=window_progress_end,
                progress_callback=progress_callback,
            )
            by_params = {_params_key(item.params): item for item in test_candidates}
            best_train = train_candidates[0]
            best_test = by_params.get(_params_key(best_train.params))
            if best_test is None:
                rows.append(
                    _failed_validation_window(
                        best_train,
                        train_start,
                        train_end,
                        test_start,
                        test_end,
                        "样本外评估失败或没有有效成交结果。",
                    )
                )
                continue
            overfit_signal = best_test.rank > max(int(len(test_candidates) * 0.3), 1)
            rows.append(_validation_window(best_train, best_test, train_start, train_end, test_start, test_end, overfit_signal))
        if progress_callback is not None:
            progress_callback(98.0, "Walk-forward 汇总结论生成")
        return _report(rows)


def _validation_window(
    best_train: OptimizationCandidate,
    best_test: OptimizationCandidate,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    overfit_signal: bool,
) -> ValidationWindow:
    test_sharpe = _float(best_test.metrics.get("sharpe_ratio"), 0.0)
    return ValidationWindow(
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
        train_sharpe=_float(best_train.metrics.get("sharpe_ratio"), 0.0),
        test_sharpe=test_sharpe,
        train_return_pct=_float(best_train.metrics.get("total_return_pct"), 0.0),
        test_return_pct=_float(best_test.metrics.get("total_return_pct"), 0.0),
        max_drawdown_pct=_float(best_test.metrics.get("max_drawdown_pct"), 0.0),
        best_params=best_train.params,
        is_rank=best_train.rank,
        oos_rank=best_test.rank,
        passed=test_sharpe > 0,
        overfit_signal=overfit_signal,
        train_market_state_segments=list(best_train.metrics.get("market_state_attribution") or []),
        market_state_segments=list(best_test.metrics.get("market_state_attribution") or []),
    )


def _failed_validation_window(
    best_train: OptimizationCandidate,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    failure_reason: str,
) -> ValidationWindow:
    return ValidationWindow(
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
        train_sharpe=_float(best_train.metrics.get("sharpe_ratio"), 0.0),
        test_sharpe=-1.0,
        train_return_pct=_float(best_train.metrics.get("total_return_pct"), 0.0),
        test_return_pct=0.0,
        max_drawdown_pct=0.0,
        best_params=best_train.params,
        is_rank=best_train.rank,
        oos_rank=0,
        passed=False,
        overfit_signal=True,
        oos_failed=True,
        failure_reason=failure_reason,
        train_market_state_segments=list(best_train.metrics.get("market_state_attribution") or []),
        market_state_segments=[],
    )


def _report(windows: list[ValidationWindow]) -> ValidationReport:
    passed = sum(1 for item in windows if item.passed)
    total = len(windows)
    avg_oos_sharpe = round(sum(item.test_sharpe for item in windows) / max(total, 1), 4)
    pass_rate = round(passed / max(total, 1), 4)
    overfit_count = sum(1 for item in windows if item.overfit_signal)
    pbo_ratio = overfit_count / max(total, 1)
    pbo_risk = "high" if pbo_ratio >= 0.5 else "medium" if pbo_ratio >= 0.25 else "low"
    downgrade = any(item.test_sharpe < 0 for item in windows)
    if total == 0:
        conclusion = "未生成有效 Walk-forward 窗口，建议检查日期范围和行情数据。"
    elif pass_rate >= 0.75 and pbo_risk == "low":
        conclusion = f"该策略在 {passed}/{total} 个窗口样本外 Sharpe 为正，稳定性良好。"
    elif pass_rate >= 0.5:
        conclusion = f"该策略在 {passed}/{total} 个窗口样本外通过，建议人工复核降级和参数稳定性。"
    else:
        conclusion = f"该策略仅在 {passed}/{total} 个窗口样本外通过，建议暂缓实盘。"
    return ValidationReport(
        window_count=total,
        avg_oos_sharpe=avg_oos_sharpe,
        oos_pass_rate=pass_rate,
        pbo_risk=pbo_risk,
        downgrade_review=downgrade,
        stability_conclusion=conclusion,
        windows=windows,
        by_market_state=_market_state_summary(windows),
    )


def _market_state_summary(windows: list[ValidationWindow]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for window in windows:
        segments = window.market_state_segments or []
        if not segments:
            buckets.setdefault(
                "未标注",
                _empty_market_state_bucket(),
            )
            buckets["未标注"]["window_count"] += 1
            buckets["未标注"]["passed_windows"] += 1 if window.passed else 0
            buckets["未标注"]["avg_oos_sharpe"] += float(window.test_sharpe or 0.0)
            _record_market_state_params(buckets["未标注"], window)
            continue
        for segment in segments:
            state = str(segment.get("name") or segment.get("label") or segment.get("market_state") or "未标注")
            bucket = buckets.setdefault(
                state,
                _empty_market_state_bucket(),
            )
            bucket["window_count"] += 1
            bucket["signal_count"] += int(segment.get("signal_count") or segment.get("trade_count") or 0)
            bucket["passed_windows"] += 1 if window.passed else 0
            bucket["avg_oos_sharpe"] += float(window.test_sharpe or 0.0)
            _record_market_state_params(bucket, window)
    for bucket in buckets.values():
        count = max(int(bucket["window_count"]), 1)
        bucket["avg_oos_sharpe"] = round(float(bucket["avg_oos_sharpe"]) / count, 4)
        bucket["pass_rate"] = round(float(bucket["passed_windows"]) / count, 4)
        bucket["best_params"] = _best_params_from_counts(bucket.pop("_param_counts", {}))
    return buckets


def _empty_market_state_bucket() -> dict[str, Any]:
    return {
        "window_count": 0,
        "signal_count": 0,
        "passed_windows": 0,
        "avg_oos_sharpe": 0.0,
        "_param_counts": {},
    }


def _record_market_state_params(bucket: dict[str, Any], window: ValidationWindow) -> None:
    key = _params_key(window.best_params)
    counts = bucket.setdefault("_param_counts", {})
    row = counts.setdefault(key, {"count": 0, "params": window.best_params, "sharpe_sum": 0.0})
    row["count"] += 1
    row["sharpe_sum"] += float(window.test_sharpe or 0.0)


def _best_params_from_counts(counts: dict[str, Any]) -> dict[str, Any]:
    if not counts:
        return {}
    best = max(
        counts.values(),
        key=lambda item: (int(item.get("count") or 0), float(item.get("sharpe_sum") or 0.0)),
    )
    return dict(best.get("params") or {})


def _calendar_dates(start_date: str, end_date: str) -> list[str]:
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start is None or end is None or start > end:
        return []
    output: list[str] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            output.append(current.isoformat())
        current += timedelta(days=1)
    return output


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _params_key(params: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in params.items()))


def _cancel_requested(cancel_token: Any | None) -> bool:
    if cancel_token is None:
        return False
    checker = getattr(cancel_token, "is_cancelled", None)
    if callable(checker):
        return bool(checker())
    return bool(getattr(cancel_token, "cancelled", False))


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
