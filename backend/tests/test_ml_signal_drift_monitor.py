from __future__ import annotations

import math

import numpy as np

from app.services.ml_signal.drift_monitor import _kl_divergence, _psi


def test_kl_divergence_smooths_empty_baseline_buckets() -> None:
    recent = np.asarray([9.0, 9.2, 9.4, 9.6, 9.8])
    baseline = np.asarray([1.0, 1.2, 1.4, 1.6, 1.8])

    value = _kl_divergence(recent, baseline)

    assert math.isfinite(value)


def test_psi_smooths_empty_baseline_buckets() -> None:
    recent = np.asarray([9.0, 9.2, 9.4, 9.6, 9.8])
    baseline = np.asarray([1.0, 1.2, 1.4, 1.6, 1.8])

    value = _psi(recent, baseline)

    assert math.isfinite(value)
