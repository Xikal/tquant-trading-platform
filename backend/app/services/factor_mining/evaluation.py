from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.schema_defs.factor_mining import FactorEvaluationRequest, FactorEvalResultOut
from app.services.finance.rust_math import rust_rank_ic
from app.services.factor_mining.compute_engine import FactorComputeEngine
from app.services.factor_mining.data_store import FactorDataStore


@dataclass(frozen=True)
class FactorEvaluationPayload:
    result: FactorEvalResultOut
    elapsed_seconds: float
    factor_values: pd.DataFrame | None = None


class FactorEvaluationEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(self, formula_code: str, request: FactorEvaluationRequest) -> FactorEvaluationPayload:
        started = time.monotonic()
        bars = FactorDataStore(self.db).daily_bars(
            start_date=request.start_date,
            end_date=request.end_date,
            limit_symbols=request.limit_symbols,
            as_of_date=request.end_date or None,
        )
        if bars.empty:
            return FactorEvaluationPayload(
                FactorEvalResultOut(warnings=["日线快照为空，无法评估因子；请检查 as_of 时点数据是否已入库。"]),
                time.monotonic() - started,
            )
        factor_values = FactorComputeEngine().compute(formula_code, bars).values
        samples = _build_samples(bars, factor_values, holding_days=request.holding_days)
        if samples.empty:
            return FactorEvaluationPayload(
                FactorEvalResultOut(warnings=["因子样本为空，请检查公式输出或持有周期。"]),
                time.monotonic() - started,
            )
        result = _metrics(samples, bars=bars, factor_values=factor_values, min_cross_section=request.min_cross_section)
        return FactorEvaluationPayload(result, time.monotonic() - started, factor_values=factor_values)


def _build_samples(bars: pd.DataFrame, factor_values: pd.DataFrame, *, holding_days: int) -> pd.DataFrame:
    ordered = bars.sort_values(["symbol", "trade_date"]).copy()
    ordered["future_return"] = (
        ordered.groupby("symbol")["close_price"].shift(-holding_days) / ordered["close_price"] - 1.0
    )
    merged = ordered[["symbol", "trade_date", "future_return"]].merge(
        factor_values,
        on=["symbol", "trade_date"],
        how="inner",
    )
    merged["factor_value"] = pd.to_numeric(merged["factor_value"], errors="coerce")
    merged["future_return"] = pd.to_numeric(merged["future_return"], errors="coerce")
    return merged.dropna(subset=["factor_value", "future_return"])


def _metrics(
    samples: pd.DataFrame,
    *,
    bars: pd.DataFrame,
    factor_values: pd.DataFrame,
    min_cross_section: int,
) -> FactorEvalResultOut:
    daily_ic = _daily_rank_ic(samples, min_cross_section=min_cross_section)
    if daily_ic.empty:
        return FactorEvalResultOut(
            observation_count=int(len(samples)),
            symbol_count=int(samples["symbol"].nunique()),
            warnings=["可用横截面样本不足，无法计算 IC。"],
        )
    split_date = daily_ic.index[int(len(daily_ic) * 0.7)] if len(daily_ic) >= 3 else daily_ic.index[-1]
    is_ic = daily_ic[daily_ic.index <= split_date]
    oos_ic = daily_ic[daily_ic.index > split_date]
    ic_mean = float(is_ic.mean())
    ic_std = float(is_ic.std(ddof=1) if len(is_ic) > 1 else 0.0)
    icir = ic_mean / ic_std if ic_std > 1e-12 else 0.0
    t_stat = icir * math.sqrt(len(is_ic)) if ic_std > 1e-12 else 0.0
    oos_mean = float(oos_ic.mean()) if not oos_ic.empty else ic_mean
    top_return, spread, daily_spreads = _quintile_returns(samples)
    bootstrap_lower = _bootstrap_ci_lower(daily_ic.to_numpy())
    half_life = _half_life_days(daily_ic)
    consistent = abs(ic_mean - oos_mean) < 0.03
    max_corr, max_corr_key = _factor_orthogonality_check(bars, factor_values)
    wf_ics = _walk_forward_ic(daily_ic)
    wf_mean = float(np.mean(wf_ics)) if wf_ics else 0.0
    wf_positive_rate = float(sum(1 for value in wf_ics if value > 0) / len(wf_ics) * 100) if wf_ics else 0.0
    wf_no_negative = bool(wf_ics) and all(value > 0 for value in wf_ics)
    candidate = _candidate_gate(ic_mean, t_stat, icir, half_life, top_return, consistent, bootstrap_lower, max_corr)
    production = _production_gate(
        ic_mean,
        t_stat,
        icir,
        half_life,
        top_return,
        consistent,
        bootstrap_lower,
        max_corr,
        wf_mean,
        wf_no_negative,
        len(wf_ics),
    )
    return FactorEvalResultOut(
        ic_mean=round(ic_mean, 6),
        ic_std=round(ic_std, 6),
        icir=round(icir, 6),
        ic_t_stat=round(t_stat, 6),
        half_life_days=half_life,
        top_quintile_return=round(top_return, 6),
        spread_return=round(spread, 6),
        information_ratio=round(_information_ratio(daily_spreads), 6),
        oos_ic_mean=round(oos_mean, 6),
        is_oos_consistent=consistent,
        walk_forward_oos_ic_mean=round(wf_mean, 6),
        walk_forward_window_count=len(wf_ics),
        walk_forward_positive_window_rate_pct=round(wf_positive_rate, 2),
        walk_forward_no_negative_windows=wf_no_negative,
        bootstrap_ci_lower=round(bootstrap_lower, 6),
        max_existing_factor_corr=round(max_corr, 6),
        max_existing_factor_key=max_corr_key,
        passed_candidate_gate=candidate,
        passed_production_gate=production,
        sample_days=int(len(daily_ic)),
        observation_count=int(len(samples)),
        symbol_count=int(samples["symbol"].nunique()),
        warnings=_warnings(candidate, production, len(oos_ic), max_corr, max_corr_key, len(wf_ics), wf_mean, wf_no_negative),
    )


def _daily_rank_ic(samples: pd.DataFrame, *, min_cross_section: int) -> pd.Series:
    values: dict[str, float] = {}
    for trade_date, group in samples.groupby("trade_date"):
        if len(group) < min_cross_section:
            continue
        corr = rust_rank_ic(group["factor_value"].tolist(), group["future_return"].tolist())
        if corr is None:
            corr = _safe_rank_corr(group["factor_value"], group["future_return"])
        if pd.notna(corr):
            values[str(trade_date)] = float(corr)
    return pd.Series(values).sort_index()


def _safe_rank_corr(factors: pd.Series, returns: pd.Series) -> float | None:
    factor_ranks = pd.to_numeric(factors, errors="coerce").rank()
    return_ranks = pd.to_numeric(returns, errors="coerce").rank()
    valid = factor_ranks.notna() & return_ranks.notna()
    if int(valid.sum()) < 3:
        return None
    return _safe_pearson(factor_ranks[valid].to_numpy(dtype=float), return_ranks[valid].to_numpy(dtype=float))


def _safe_pearson(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    valid = np.isfinite(left) & np.isfinite(right)
    if int(valid.sum()) < 3:
        return None
    left = left[valid]
    right = right[valid]
    if float(np.std(left)) <= 1e-12 or float(np.std(right)) <= 1e-12:
        return None
    left_centered = left - float(np.mean(left))
    right_centered = right - float(np.mean(right))
    denominator = float(np.sqrt(np.sum(left_centered * left_centered) * np.sum(right_centered * right_centered)))
    if denominator <= 1e-12:
        return None
    return float(np.sum(left_centered * right_centered) / denominator)


def _walk_forward_ic(
    daily_ic: pd.Series,
    *,
    train_months: int = 6,
    oos_months: int = 1,
    min_train_days: int | None = None,
    min_oos_days: int = 5,
) -> list[float]:
    """Rolling OOS IC validation to avoid a lucky single 70/30 split."""

    if daily_ic.empty:
        return []
    series = daily_ic.copy()
    series.index = pd.to_datetime(series.index)
    series = series.sort_index()
    if series.empty:
        return []
    train_days = min_train_days or 20 * max(train_months, 1)
    first_date = pd.Timestamp(series.index.min())
    last_date = pd.Timestamp(series.index.max())
    first_oos = first_date + pd.DateOffset(months=max(train_months, 1))
    starts = pd.date_range(first_oos, last_date, freq=f"{max(oos_months, 1)}MS")
    oos_ics: list[float] = []
    for start in starts:
        train_start = start - pd.DateOffset(months=max(train_months, 1))
        train_end = start - pd.DateOffset(days=1)
        oos_end = start + pd.DateOffset(months=max(oos_months, 1)) - pd.DateOffset(days=1)
        train_data = series[(series.index >= train_start) & (series.index <= train_end)]
        oos_data = series[(series.index >= start) & (series.index <= oos_end)]
        if len(train_data) >= train_days and len(oos_data) >= min_oos_days:
            oos_ics.append(float(oos_data.mean()))
    return oos_ics


def _quintile_returns(samples: pd.DataFrame) -> tuple[float, float, list[float]]:
    top_returns: list[float] = []
    spread_returns: list[float] = []
    for _, group in samples.groupby("trade_date"):
        if len(group) < 10 or group["factor_value"].nunique() < 5:
            continue
        ranked = group.sort_values("factor_value")
        bucket_size = max(len(ranked) // 5, 1)
        bottom = ranked.head(bucket_size)["future_return"].mean()
        top = ranked.tail(bucket_size)["future_return"].mean()
        top_returns.append(float(top))
        spread_returns.append(float(top - bottom))
    return _mean(top_returns), _mean(spread_returns), spread_returns


def _information_ratio(spread_returns: list[float]) -> float:
    clean = [value for value in spread_returns if math.isfinite(value)]
    if len(clean) < 2:
        return 0.0
    avg = float(np.mean(clean))
    tracking_error = float(np.std(clean, ddof=1))
    if tracking_error <= 1e-12:
        return 0.0
    return avg / tracking_error * math.sqrt(252)


def _bootstrap_ci_lower(values: np.ndarray) -> float:
    clean = values[np.isfinite(values)]
    if len(clean) < 5:
        return 0.0
    rng = np.random.default_rng(42)
    means = [float(np.mean(rng.choice(clean, size=len(clean), replace=True))) for _ in range(400)]
    return float(np.percentile(means, 2.5))


def _half_life_days(daily_ic: pd.Series) -> int:
    base = abs(float(daily_ic.mean()))
    if base <= 1e-12 or len(daily_ic) < 4:
        return 0
    for lag in range(1, min(10, len(daily_ic) - 1) + 1):
        corr = _safe_autocorr(daily_ic, lag)
        if corr is not None and abs(corr) <= 0.5:
            return lag
    return min(10, len(daily_ic))


def _safe_autocorr(series: pd.Series, lag: int) -> float | None:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    lag = max(int(lag), 1)
    if len(values) <= lag:
        return None
    return _safe_pearson(values[:-lag], values[lag:])


def _candidate_gate(ic: float, t: float, icir: float, half_life: int, top: float, consistent: bool, ci: float, corr: float) -> bool:
    return ic > 0.02 and t > 1.5 and icir > 0.3 and half_life >= 2 and top > 0.003 and consistent and ci > 0 and corr < 0.8


def _production_gate(
    ic: float,
    t: float,
    icir: float,
    half_life: int,
    top: float,
    consistent: bool,
    ci: float,
    corr: float,
    wf_mean: float,
    wf_no_negative: bool,
    wf_count: int,
) -> bool:
    return (
        ic > 0.03
        and t > 2.0
        and icir > 0.4
        and half_life >= 3
        and top > 0.005
        and consistent
        and ci > 0.01
        and corr < 0.6
        and wf_count > 0
        and wf_mean > 0.025
        and wf_no_negative
    )


def _warnings(
    candidate: bool,
    production: bool,
    oos_count: int,
    corr: float,
    corr_key: str,
    wf_count: int,
    wf_mean: float,
    wf_no_negative: bool,
) -> list[str]:
    warnings: list[str] = []
    if not candidate:
        warnings.append("未通过候选因子门槛，建议继续研究或改进公式。")
    if candidate and not production:
        warnings.append("已达到研究候选标准，但未达到生产门槛。")
    if oos_count < 5:
        warnings.append("样本外交易日偏少，生产晋级需补充 Walk-forward 验证。")
    if wf_count <= 0:
        warnings.append("滚动 Walk-forward 窗口不足，生产晋级暂不放行。")
    elif wf_mean <= 0.025 or not wf_no_negative:
        warnings.append("滚动 Walk-forward 稳定性不足，需确认多个样本外窗口持续为正。")
    if corr >= 0.6:
        warnings.append(f"与现有因子 {corr_key or 'unknown'} 相关性较高 r={corr:.2f}，生产晋级需降低同质化。")
    return warnings


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _factor_orthogonality_check(bars: pd.DataFrame, factor_values: pd.DataFrame) -> tuple[float, str]:
    existing = _existing_factor_frame(bars)
    if existing.empty or factor_values.empty:
        return 0.0, ""
    merged = factor_values.merge(existing, on=["symbol", "trade_date"], how="inner")
    if merged.empty:
        return 0.0, ""
    max_corr = 0.0
    max_key = ""
    for key in [column for column in existing.columns if column not in {"symbol", "trade_date"}]:
        daily: list[float] = []
        for _, group in merged.groupby("trade_date"):
            if len(group) < 20 or group["factor_value"].nunique() < 5 or group[key].nunique() < 5:
                continue
            corr = _safe_rank_corr(group["factor_value"], group[key])
            if pd.notna(corr):
                daily.append(abs(float(corr)))
        avg_corr = _mean(daily)
        if avg_corr > max_corr:
            max_corr = avg_corr
            max_key = key
    return max_corr, max_key


def _existing_factor_frame(bars: pd.DataFrame) -> pd.DataFrame:
    ordered = bars.sort_values(["symbol", "trade_date"]).copy()
    grouped = ordered.groupby("symbol", sort=False)
    close = pd.to_numeric(ordered["close_price"], errors="coerce")
    high = pd.to_numeric(ordered["high_price"], errors="coerce")
    low = pd.to_numeric(ordered["low_price"], errors="coerce")
    volume = pd.to_numeric(ordered["volume"], errors="coerce")
    ma20 = grouped["close_price"].transform(lambda item: pd.to_numeric(item, errors="coerce").rolling(20, min_periods=5).mean())
    vol_ma5 = grouped["volume"].transform(lambda item: pd.to_numeric(item, errors="coerce").rolling(5, min_periods=3).mean())
    recent_high = grouped["high_price"].transform(lambda item: pd.to_numeric(item, errors="coerce").rolling(20, min_periods=5).max())
    frame = ordered[["symbol", "trade_date"]].copy()
    frame["deep_pullback_factor"] = (recent_high - close) / recent_high.replace(0, np.nan)
    frame["shrink_quality_factor"] = 1.0 - (volume / vol_ma5.replace(0, np.nan))
    frame["trend_rebound_factor"] = (close - ma20) / ma20.replace(0, np.nan)
    frame["price_structure_factor"] = (close - low) / (high - low).replace(0, np.nan)
    return frame.replace([np.inf, -np.inf], np.nan)
