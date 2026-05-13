from __future__ import annotations

import math


def binomial_accuracy_p_value(correct_count: int, sample_count: int, *, baseline: float = 0.5) -> float:
    if sample_count <= 0:
        return 1.0
    successes = max(0, min(int(correct_count), int(sample_count)))
    try:
        from scipy.stats import binomtest

        return float(binomtest(successes, sample_count, baseline, alternative="greater").pvalue)
    except Exception:
        return _binomial_tail(successes, sample_count, baseline)


def _binomial_tail(successes: int, sample_count: int, baseline: float) -> float:
    probability = 0.0
    p = max(0.0, min(float(baseline), 1.0))
    for k in range(successes, sample_count + 1):
        probability += math.comb(sample_count, k) * (p**k) * ((1 - p) ** (sample_count - k))
    return round(min(max(probability, 0.0), 1.0), 8)
