from __future__ import annotations

import random

from app.services.finance.performance_math import annualized_sharpe_ratio


def compute_cvar(returns: list[float], confidence: float = 0.95) -> float:
    """Return the average of the worst tail returns."""

    if not returns:
        return 0.0
    sorted_returns = sorted(float(item) for item in returns)
    tail_count = max(1, int(len(sorted_returns) * (1.0 - confidence)))
    tail = sorted_returns[:tail_count]
    return round(sum(tail) / len(tail), 4)


def compute_pbo(
    *,
    real_sharpe: float,
    signal_series: list[bool],
    returns_series: list[float],
    n_permutations: int = 1000,
) -> dict:
    """Estimate whether realized signal returns beat randomized signal placement."""

    n = min(len(signal_series), len(returns_series))
    if n < 2 or n_permutations <= 0:
        return _empty_pbo(real_sharpe=real_sharpe, n_permutations=max(n_permutations, 0))

    rng = random.Random(42)
    pseudo_sharpes: list[float] = []
    signal_count = sum(1 for item in signal_series[:n] if item)
    base_returns = [float(item) for item in returns_series[:n]]

    for _ in range(n_permutations):
        active_indices = set(rng.sample(range(n), min(signal_count, n)))
        pseudo_returns = [base_returns[index] if index in active_indices else 0.0 for index in range(n)]
        pseudo_sharpes.append(_compute_sharpe_from_returns(pseudo_returns))

    better_count = sum(1 for value in pseudo_sharpes if value >= real_sharpe)
    pbo = 1.0 - better_count / n_permutations
    pseudo_sharpes.sort()
    pct95_index = min(len(pseudo_sharpes) - 1, int(n_permutations * 0.95))
    return {
        "pbo": round(pbo, 4),
        "real_sharpe": round(real_sharpe, 4),
        "pseudo_sharpe_mean": round(sum(pseudo_sharpes) / len(pseudo_sharpes), 4),
        "pseudo_sharpe_95pct": round(pseudo_sharpes[pct95_index], 4),
        "n_permutations": n_permutations,
        "verdict": _pbo_verdict(pbo),
    }


def _compute_sharpe_from_returns(returns: list[float], risk_free: float = 0.02) -> float:
    return annualized_sharpe_ratio(
        [float(item) / 100.0 for item in returns],
        risk_free_rate_annual_pct=float(risk_free) * 100,
    )


def _empty_pbo(*, real_sharpe: float, n_permutations: int) -> dict:
    return {
        "pbo": 0.0,
        "real_sharpe": round(real_sharpe, 4),
        "pseudo_sharpe_mean": 0.0,
        "pseudo_sharpe_95pct": 0.0,
        "n_permutations": n_permutations,
        "verdict": "insufficient_sample",
    }


def _pbo_verdict(pbo: float) -> str:
    if pbo < 0.5:
        return "likely_overfit"
    if pbo < 0.9:
        return "potentially_valid"
    return "strong_evidence"
