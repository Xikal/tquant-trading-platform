from __future__ import annotations

from typing import Any

from app.services.low_buy.candidate_rule_params import float_param, int_param, prefilter_params


def n_pattern_retracement_matches(strategy: str, anchor: Any, post_rows: list[Any]) -> bool:
    if strategy == "n_pattern_long_wash":
        return _long_wash_matches(anchor, post_rows, prefilter_params(strategy))
    if strategy == "n_pattern_short_wash":
        return _short_wash_matches(anchor, post_rows, prefilter_params(strategy))
    return True


def n_pattern_latest_bar_matches(strategy: str, latest_bar: Any) -> bool:
    if strategy not in {"n_pattern_long_wash", "n_pattern_short_wash"}:
        return True
    params = prefilter_params(strategy)
    close_position = _close_position(latest_bar)
    return (
        latest_bar.amount >= float_param(params, "min_amount", 80_000_000.0)
        and float_param(params, "latest_bar_min_change_pct", -4.0)
        <= latest_bar.pct_chg
        <= float_param(params, "latest_bar_max_change_pct", 6.8)
        and close_position >= float_param(params, "latest_bar_min_close_position_ratio", 0.42)
    )


def n_pattern_anchor_matches(strategy: str, anchor: Any, prior_rows: list[Any]) -> bool:
    if strategy not in {"n_pattern_long_wash", "n_pattern_short_wash"}:
        return False
    if anchor.close_price <= 0 or anchor.open_price <= 0:
        return False
    avg_volume = sum(row.volume for row in prior_rows) / max(len(prior_rows), 1) if prior_rows else 0.0
    volume_ratio = anchor.volume / max(avg_volume, 1.0)
    close_position = _close_position(anchor)
    params = prefilter_params(strategy)
    big_yang = anchor.pct_chg >= float_param(params, "anchor_min_pct_chg", 7.0) or anchor.close_price >= (
        anchor.open_price * float_param(params, "anchor_min_close_open_ratio", 1.055)
    )
    return (
        big_yang
        and volume_ratio >= float_param(params, "anchor_min_volume_ratio", 1.2)
        and close_position >= float_param(params, "anchor_min_close_position_ratio", 0.72)
    )


def _long_wash_matches(anchor: Any, post_rows: list[Any], params: dict[str, Any]) -> bool:
    min_days = int_param(params, "min_retracement_days", 7)
    max_days = int_param(params, "max_retracement_days", 15)
    if not min_days <= len(post_rows) <= max_days:
        return False
    latest = post_rows[-1]
    wash_rows = post_rows[:-1] or post_rows
    if min(row.low_price for row in post_rows) < anchor.low_price * float_param(
        params, "min_board_low_hold_ratio", 0.995
    ):
        return False
    wash_avg_volume = sum(row.volume for row in wash_rows) / max(len(wash_rows), 1)
    if wash_avg_volume > anchor.volume * float_param(params, "max_post_volume_ratio", 0.82):
        return False
    volume_repair = (
        latest.volume >= wash_avg_volume * float_param(params, "min_repair_volume_ratio", 1.08)
        and latest.volume <= anchor.volume * float_param(params, "max_latest_volume_ratio", 1.35)
    )
    price_repair = latest.pct_chg >= float_param(params, "min_price_repair_pct", 1.0) or _small_yang_climb(
        post_rows[-3:], params
    )
    return (
        volume_repair
        and price_repair
        and _close_position(latest) >= float_param(params, "min_close_position_ratio", 0.50)
    )


def _short_wash_matches(anchor: Any, post_rows: list[Any], params: dict[str, Any]) -> bool:
    min_days = int_param(params, "min_retracement_days", 2)
    max_days = int_param(params, "max_retracement_days", 5)
    if not min_days <= len(post_rows) <= max_days:
        return False
    latest = post_rows[-1]
    first_divergence = post_rows[0]
    if min(row.low_price for row in post_rows) < anchor.low_price * float_param(
        params, "min_board_low_hold_ratio", 0.995
    ):
        return False
    if first_divergence.volume < anchor.volume * float_param(params, "min_divergence_volume_ratio", 0.55) and (
        first_divergence.amount < float_param(params, "min_divergence_amount", 120_000_000.0)
    ):
        return False
    return (
        _doji_or_hammer(latest, params)
        and latest.close_price >= latest.open_price * float_param(params, "min_latest_close_open_ratio", 0.995)
        and _close_position(latest) >= float_param(params, "min_close_position_ratio", 0.45)
    )


def _small_yang_climb(rows: list[Any], params: dict[str, Any]) -> bool:
    if len(rows) < 2:
        return False
    min_close_open = 1.0 + float_param(params, "small_yang_min_pct", 0.3) / 100.0
    positives = sum(1 for row in rows if row.close_price >= row.open_price * min_close_open)
    closes = [row.close_price for row in rows]
    lows = [row.low_price for row in rows]
    close_climb = all(
        left <= right * (1.0 + float_param(params, "small_yang_close_tolerance", 0.003))
        for left, right in zip(closes, closes[1:])
    )
    low_climb = all(
        left <= right * (1.0 + float_param(params, "small_yang_low_tolerance", 0.006))
        for left, right in zip(lows, lows[1:])
    )
    return positives >= 2 and close_climb and low_climb


def _doji_or_hammer(bar: Any, params: dict[str, Any]) -> bool:
    daily_range = max(bar.high_price - bar.low_price, 0.01)
    body = abs(bar.close_price - bar.open_price) / daily_range
    lower_shadow = min(bar.open_price, bar.close_price) - bar.low_price
    return body <= float_param(params, "max_doji_body_ratio", 0.28) or lower_shadow / daily_range >= float_param(
        params, "min_hammer_lower_shadow_ratio", 0.42
    )


def _close_position(bar: Any) -> float:
    daily_range = max(float(bar.high_price or 0.0) - float(bar.low_price or 0.0), 0.01)
    return (float(bar.close_price or 0.0) - float(bar.low_price or 0.0)) / daily_range
