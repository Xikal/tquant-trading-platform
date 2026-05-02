from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KellyPosition:
    full_kelly: float
    half_kelly: float
    quarter_kelly: float
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    expected_value: float


def compute_kelly_position(
    *,
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    max_position_pct: float = 0.25,
    min_position_pct: float = 0.05,
) -> KellyPosition:
    """Compute conservative Kelly sizing from realized win/loss stats."""

    if avg_loss_pct >= 0 or avg_win_pct <= 0 or win_rate <= 0:
        return KellyPosition(0.0, 0.0, 0.0, win_rate, avg_win_pct, avg_loss_pct, 0.0)

    b = avg_win_pct / abs(avg_loss_pct)
    q = 1.0 - win_rate
    full_kelly = (b * win_rate - q) / max(b, 0.0001)
    full_kelly = max(0.0, min(full_kelly, max_position_pct))
    half_kelly = full_kelly / 2.0
    quarter_kelly = full_kelly / 4.0

    if 0 < half_kelly < min_position_pct:
        half_kelly = min_position_pct
        quarter_kelly = min_position_pct / 2.0

    expected_value = win_rate * avg_win_pct - q * abs(avg_loss_pct)
    return KellyPosition(
        full_kelly=round(full_kelly, 4),
        half_kelly=round(half_kelly, 4),
        quarter_kelly=round(quarter_kelly, 4),
        win_rate=round(win_rate, 4),
        avg_win_pct=round(avg_win_pct, 4),
        avg_loss_pct=round(avg_loss_pct, 4),
        expected_value=round(expected_value, 4),
    )
