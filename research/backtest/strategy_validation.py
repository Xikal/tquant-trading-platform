from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from research.data_sync.tquant_to_qlib import qlib_status, read_offline_table


STANDARD_REPORT_FIELDS = ("ic", "ir", "sharpe", "max_drawdown", "win_rate", "sample_count")


@dataclass(frozen=True)
class StrategyValidationSummary:
    strategy_key: str
    sample_count: int
    win_rate_3d: float
    avg_return_3d: float
    max_drawdown_5d: float
    ic: float | None = None
    ir: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    status: str = "empty"

    def to_report(self) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "status": self.status,
            "sample_count": self.sample_count,
            "win_rate": self.win_rate,
            "win_rate_3d": self.win_rate_3d,
            "avg_return_3d": self.avg_return_3d,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_5d": self.max_drawdown_5d,
            "ic": self.ic,
            "ir": self.ir,
        }


def summarize_strategy_results(path: str | Path, strategy_key: str) -> StrategyValidationSummary:
    """Summarize an exported strategy result file without touching production config."""

    frame = read_offline_table(path)
    return summarize_strategy_frame(frame, strategy_key)


def summarize_strategy_frame(frame: pd.DataFrame, strategy_key: str) -> StrategyValidationSummary:
    """Calculate standard offline research metrics for one strategy."""

    subset = frame[frame["strategy_key"] == strategy_key] if "strategy_key" in frame else frame.iloc[0:0]
    if subset.empty:
        return StrategyValidationSummary(strategy_key, 0, 0.0, 0.0, 0.0, status="empty")

    returns = _numeric_series(subset, "return_3d")
    if returns.empty:
        returns = _numeric_series(subset, "return")
    win_rate = round(float((returns > 0).mean() * 100), 2) if not returns.empty else None
    max_drawdown = _max_drawdown(returns)
    ic = _information_coefficient(subset, returns)
    ir = _information_ratio(subset, ic)
    sharpe = _sharpe(returns)
    return StrategyValidationSummary(
        strategy_key=strategy_key,
        sample_count=int(len(subset)),
        win_rate_3d=win_rate or 0.0,
        avg_return_3d=round(float(returns.mean()), 6) if not returns.empty else 0.0,
        max_drawdown_5d=round(float(max_drawdown or 0.0), 6),
        ic=ic,
        ir=ir,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        status="ok",
    )


def build_strategy_validation_report(
    path: str | Path,
    strategy_keys: list[str] | None = None,
) -> dict[str, object]:
    """Build a standard report payload; missing or empty input is not fatal."""

    source = Path(path)
    frame = read_offline_table(source)
    keys = strategy_keys or _strategy_keys(frame)
    reports = [summarize_strategy_frame(frame, key).to_report() for key in keys]
    is_empty = frame.empty or all(item["sample_count"] == 0 for item in reports)
    return {
        "status": "empty" if is_empty else "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source),
        "qlib": qlib_status(),
        "reports": reports,
        "standard_fields": list(STANDARD_REPORT_FIELDS),
    }


def write_strategy_validation_report(
    path: str | Path,
    output_path: str | Path,
    strategy_keys: list[str] | None = None,
) -> Path:
    report = build_strategy_validation_report(path, strategy_keys=strategy_keys)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def _strategy_keys(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "strategy_key" not in frame:
        return ["all"]
    keys = sorted(str(item) for item in frame["strategy_key"].dropna().unique())
    return keys or ["all"]


def _numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _safe_round(value: float | None, digits: int = 6) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def _sharpe(returns: pd.Series) -> float | None:
    if returns.empty:
        return None
    std = float(returns.std(ddof=1))
    if not std:
        return None
    return _safe_round(float(returns.mean()) / std * math.sqrt(len(returns)))


def _max_drawdown(returns: pd.Series) -> float | None:
    if returns.empty:
        return None
    equity = (1 + returns.astype(float)).cumprod()
    drawdowns = equity / equity.cummax() - 1
    return _safe_round(abs(float(drawdowns.min())))


def _information_coefficient(frame: pd.DataFrame, returns: pd.Series) -> float | None:
    factor = _numeric_series(frame, "factor_score")
    target = _numeric_series(frame, "forward_return_1d")
    if target.empty:
        target = returns
    aligned = pd.concat([factor.rename("factor"), target.rename("target")], axis=1).dropna()
    if len(aligned) < 2:
        return None
    return _safe_round(float(aligned["factor"].corr(aligned["target"])))


def _information_ratio(frame: pd.DataFrame, ic: float | None) -> float | None:
    if ic is None:
        return None
    if "trade_date" not in frame or "factor_score" not in frame:
        return ic
    target_col = "forward_return_1d" if "forward_return_1d" in frame else "return_3d"
    if target_col not in frame:
        return ic

    daily_ic: list[float] = []
    for _, group in frame.groupby("trade_date"):
        factor = pd.to_numeric(group["factor_score"], errors="coerce")
        target = pd.to_numeric(group[target_col], errors="coerce")
        aligned = pd.concat([factor.rename("factor"), target.rename("target")], axis=1).dropna()
        if len(aligned) < 2:
            continue
        value = aligned["factor"].corr(aligned["target"])
        if pd.notna(value):
            daily_ic.append(float(value))
    if len(daily_ic) < 2:
        return ic
    series = pd.Series(daily_ic, dtype=float)
    std = float(series.std(ddof=1))
    if not std:
        return ic
    return _safe_round(float(series.mean()) / std)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an offline strategy validation report.")
    parser.add_argument("--input", required=True, help="CSV/Parquet file exported from offline research.")
    parser.add_argument("--output", default="research/reports/strategy_validation.json")
    parser.add_argument("--strategy-key", action="append", dest="strategy_keys")
    args = parser.parse_args()
    path = write_strategy_validation_report(args.input, args.output, strategy_keys=args.strategy_keys)
    print(f"report: {path}")


if __name__ == "__main__":
    main()
