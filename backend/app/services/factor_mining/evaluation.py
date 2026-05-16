from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.schema_defs.factor_mining import FactorEvaluationRequest, FactorEvalResultOut
from app.services.factor_mining.compute_engine import FactorComputeEngine
from app.services.factor_mining.data_store import FactorDataStore


@dataclass(frozen=True)
class FactorEvaluationPayload:
    result: FactorEvalResultOut
    elapsed_seconds: float


class FactorEvaluationEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(self, formula_code: str, request: FactorEvaluationRequest) -> FactorEvaluationPayload:
        started = time.monotonic()
        bars = FactorDataStore(self.db).daily_bars(
            start_date=request.start_date,
            end_date=request.end_date,
            limit_symbols=request.limit_symbols,
        )
        if bars.empty:
            return FactorEvaluationPayload(
                FactorEvalResultOut(warnings=["日线快照为空，无法评估因子。"]),
                time.monotonic() - started,
            )
        factor_values = FactorComputeEngine().compute(formula_code, bars).values
        samples = _build_samples(bars, factor_values, holding_days=request.holding_days)
        if samples.empty:
            return FactorEvaluationPayload(
                FactorEvalResultOut(warnings=["因子样本为空，请检查公式输出或持有周期。"]),
                time.monotonic() - started,
            )
        result = _metrics(samples, min_cross_section=request.min_cross_section)
        return FactorEvaluationPayload(result, time.monotonic() - started)


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


def _metrics(samples: pd.DataFrame, *, min_cross_section: int) -> FactorEvalResultOut:
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
    top_return, spread = _quintile_returns(samples)
    bootstrap_lower = _bootstrap_ci_lower(daily_ic.to_numpy())
    half_life = _half_life_days(daily_ic)
    consistent = abs(ic_mean - oos_mean) < 0.03
    candidate = _candidate_gate(ic_mean, t_stat, icir, half_life, top_return, consistent, bootstrap_lower)
    production = _production_gate(ic_mean, t_stat, icir, half_life, top_return, consistent, bootstrap_lower)
    return FactorEvalResultOut(
        ic_mean=round(ic_mean, 6),
        ic_std=round(ic_std, 6),
        icir=round(icir, 6),
        ic_t_stat=round(t_stat, 6),
        half_life_days=half_life,
        top_quintile_return=round(top_return, 6),
        spread_return=round(spread, 6),
        oos_ic_mean=round(oos_mean, 6),
        is_oos_consistent=consistent,
        bootstrap_ci_lower=round(bootstrap_lower, 6),
        passed_candidate_gate=candidate,
        passed_production_gate=production,
        sample_days=int(len(daily_ic)),
        observation_count=int(len(samples)),
        symbol_count=int(samples["symbol"].nunique()),
        warnings=_warnings(candidate, production, len(oos_ic)),
    )


def _daily_rank_ic(samples: pd.DataFrame, *, min_cross_section: int) -> pd.Series:
    values: dict[str, float] = {}
    for trade_date, group in samples.groupby("trade_date"):
        if len(group) < min_cross_section:
            continue
        corr = group["factor_value"].rank().corr(group["future_return"].rank())
        if pd.notna(corr):
            values[str(trade_date)] = float(corr)
    return pd.Series(values).sort_index()


def _quintile_returns(samples: pd.DataFrame) -> tuple[float, float]:
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
    return _mean(top_returns), _mean(spread_returns)


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
        corr = daily_ic.autocorr(lag=lag)
        if pd.notna(corr) and abs(corr) <= 0.5:
            return lag
    return min(10, len(daily_ic))


def _candidate_gate(ic: float, t: float, icir: float, half_life: int, top: float, consistent: bool, ci: float) -> bool:
    return ic > 0.02 and t > 1.5 and icir > 0.3 and half_life >= 2 and top > 0.003 and consistent and ci > 0


def _production_gate(ic: float, t: float, icir: float, half_life: int, top: float, consistent: bool, ci: float) -> bool:
    return ic > 0.03 and t > 2.0 and icir > 0.4 and half_life >= 3 and top > 0.005 and consistent and ci > 0.01


def _warnings(candidate: bool, production: bool, oos_count: int) -> list[str]:
    warnings: list[str] = []
    if not candidate:
        warnings.append("未通过候选因子门槛，建议继续研究或改进公式。")
    if candidate and not production:
        warnings.append("已达到研究候选标准，但未达到生产门槛。")
    if oos_count < 5:
        warnings.append("样本外交易日偏少，生产晋级需补充 Walk-forward 验证。")
    return warnings


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0
