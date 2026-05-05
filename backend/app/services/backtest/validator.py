from __future__ import annotations

from dataclasses import dataclass, replace

from app.services.backtest.engine import BacktestConfig, BacktestEngine


@dataclass(frozen=True)
class ValidationWindow:
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_return_pct: float
    test_return_pct: float
    passed: bool


@dataclass(frozen=True)
class ValidationReport:
    window_count: int
    pass_rate_pct: float
    windows: list[ValidationWindow]
    verdict: str


class BacktestValidator:
    """Phase 5 controlled skeleton for walk-forward validation."""

    def __init__(self, engine: BacktestEngine) -> None:
        self.engine = engine

    def walk_forward(
        self,
        base_config: BacktestConfig,
        *,
        windows: list[tuple[str, str, str, str]],
        min_test_return_pct: float = 0.0,
    ) -> ValidationReport:
        rows: list[ValidationWindow] = []
        for train_start, train_end, test_start, test_end in windows:
            train = self.engine.run(replace(base_config, start_date=train_start, end_date=train_end))
            test = self.engine.run(replace(base_config, start_date=test_start, end_date=test_end))
            train_return = float(train.metrics.get("total_return_pct") or 0.0)
            test_return = float(test.metrics.get("total_return_pct") or 0.0)
            rows.append(
                ValidationWindow(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_return_pct=train_return,
                    test_return_pct=test_return,
                    passed=test_return >= min_test_return_pct,
                )
            )
        pass_rate = sum(1 for item in rows if item.passed) / max(len(rows), 1) * 100
        return ValidationReport(
            window_count=len(rows),
            pass_rate_pct=round(pass_rate, 4),
            windows=rows,
            verdict="pass" if rows and pass_rate >= 60 else "review",
        )
