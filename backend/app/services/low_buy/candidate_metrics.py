from __future__ import annotations

from app.services.distribution_signals import build_daily_distribution_snapshot
from app.services.low_buy.candidate_metrics_divergence import build_divergence_consensus_metrics
from app.services.low_buy.candidate_types import CandidateMetrics
from app.services.low_buy.atr_metrics import ATR_SOURCE, ATR_WINDOW, compute_daily_atr
from app.services.low_buy.multi_timeframe import evaluate_multi_timeframe_resonance
from app.services.low_buy.shared import BoardCandidate, DEFAULT_PRODUCTION_LOW_BUY_STRATEGY, LOW_BUY_THRESHOLDS, pd


def build_candidate_metrics(
    item: BoardCandidate,
    latest_trade_date: str,
    history: pd.DataFrame | None,
) -> CandidateMetrics | None:
    if history is None or history.empty or len(history) < 60:
        return None
    indices = _resolve_candidate_indices(history=history, board_date=item.board_date)
    if indices is None:
        return None
    board_index, latest_index = indices
    slices = _build_candidate_slices(history=history, board_index=board_index, latest_index=latest_index)
    if slices is None:
        return None
    board_row, latest, post_board, prior = slices
    averages = _resolve_candidate_averages(latest=latest)
    if averages is None:
        return None
    ma5, ma10, ma20, ma60 = averages
    volume_metrics = _build_volume_metrics(board_row=board_row, latest=latest, post_board=post_board, prior=prior)
    support_metrics = _build_support_metrics(
        history=history,
        latest_index=latest_index,
        board_index=board_index,
        latest_close=float(latest["close"]),
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        prior=prior,
        post_board=post_board,
    )
    gap_metrics = _compute_gap_risk(post_board=post_board, latest_close=float(latest["close"]))
    volatility_metrics = _compute_retracement_volatility(post_board=post_board)
    price_structure_metrics = _compute_price_structure(post_board=post_board, ma10=ma10, ma20=ma20)
    platform_metrics = _build_platform_metrics(
        history=history,
        board_index=board_index,
        latest_close=float(latest["close"]),
    )
    divergence_metrics = build_divergence_consensus_metrics(
        history=history,
        board_index=board_index,
        latest_index=latest_index,
        board_row=board_row,
        latest=latest,
    )
    candle_metrics, distribution_snapshot = build_daily_distribution_snapshot(
        open_price=float(latest["open"]),
        high_price=float(latest["high"]),
        low_price=float(latest["low"]),
        close_price=float(latest["close"]),
        latest_change_pct=float(latest["pct_chg"]),
        breakout_level=support_metrics["breakout_level"],
        reference_high=support_metrics["recent_swing_high"],
        volume_burst_ratio=volume_metrics["volume_burst_ratio"],
        latest_volume_ratio=volume_metrics["latest_volume_ratio"],
        post_volume_ratio=volume_metrics["post_volume_ratio"],
    )
    trend_fatigue_score = _trend_fatigue_score(history=history, latest_index=latest_index)
    resonance = evaluate_multi_timeframe_resonance(history, float(latest["close"]))
    base_trend_ok = float(latest["close"]) >= ma20 and float(latest["close"]) >= ma60 and ma10 >= ma20 * 0.99 and ma20 >= ma60 * 0.99
    base_strong_trend = ma5 >= ma10 >= ma20 >= ma60 * 0.995 and float(latest["close"]) >= ma20
    return CandidateMetrics(
        latest_trade_date=latest_trade_date,
        retracement_days=latest_index - board_index,
        latest_open=float(latest["open"]),
        latest_close=float(latest["close"]),
        latest_high=float(latest["high"]),
        latest_low=float(latest["low"]),
        latest_change_pct=float(latest["pct_chg"]),
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        board_open=float(board_row["open"]),
        board_close=float(board_row["close"]),
        board_low=float(board_row["low"]),
        board_high=float(board_row["high"]),
        board_mid_price=(float(board_row["open"]) + float(board_row["close"])) / 2,
        board_gain_ok=float(board_row["pct_chg"]) >= 9.5 or float(board_row["close"]) >= float(board_row["open"]) * 1.08,
        volume_burst_ratio=volume_metrics["volume_burst_ratio"],
        latest_volume_ratio=volume_metrics["latest_volume_ratio"],
        post_volume_ratio=volume_metrics["post_volume_ratio"],
        shrink_staircase=volume_metrics["shrink_staircase"],
        shrink_quality_score=volume_metrics["shrink_quality_score"],
        shrink_volatility=volume_metrics["shrink_volatility"],
        abnormal_volume_days=int(volume_metrics["abnormal_volume_days"]),
        close_to_ma5=support_metrics["close_to_ma5"],
        close_to_ma10=support_metrics["close_to_ma10"],
        close_to_ma20=support_metrics["close_to_ma20"],
        support_distance_pct=support_metrics["support_distance_pct"],
        support_distance_ma20_pct=support_metrics["close_to_ma20"],
        breakout_level=support_metrics["breakout_level"],
        breakout_distance_pct=support_metrics["breakout_distance_pct"],
        platform_high=platform_metrics["platform_high"],
        platform_low=platform_metrics["platform_low"],
        platform_window_days=int(platform_metrics["platform_window_days"]),
        platform_range_pct=platform_metrics["platform_range_pct"],
        platform_breakout_pct=platform_metrics["platform_breakout_pct"],
        platform_support_distance_pct=platform_metrics["platform_support_distance_pct"],
        divergence_high=divergence_metrics["divergence_high"],
        divergence_volume_ratio=divergence_metrics["divergence_volume_ratio"],
        divergence_day_stall=bool(divergence_metrics["divergence_day_stall"]),
        consolidation_days=int(divergence_metrics["consolidation_days"]),
        consolidation_low=divergence_metrics["consolidation_low"],
        consolidation_high=divergence_metrics["consolidation_high"],
        consolidation_volume_ratio=divergence_metrics["consolidation_volume_ratio"],
        consensus_breakout=bool(divergence_metrics["consensus_breakout"]),
        consensus_volume_ratio=divergence_metrics["consensus_volume_ratio"],
        consensus_close_strength=divergence_metrics["consensus_close_strength"],
        recent_low_guard=support_metrics["recent_low_guard"],
        recent_swing_high=support_metrics["recent_swing_high"],
        drawdown_from_board_pct=(float(latest["close"]) - float(board_row["close"])) / max(float(board_row["close"]), 0.01) * 100,
        drawdown_per_day=abs((float(latest["close"]) - float(board_row["close"])) / max(float(board_row["close"]), 0.01) * 100)
        / max(latest_index - board_index, 1),
        latest_body_pct=candle_metrics.body_pct,
        upper_shadow_ratio=distribution_snapshot.upper_shadow_ratio,
        lower_shadow_ratio=candle_metrics.lower_shadow_ratio,
        close_position_ratio=distribution_snapshot.close_position_ratio,
        doji_like=candle_metrics.doji_like,
        long_lower_shadow=candle_metrics.long_lower_shadow,
        long_upper_shadow=distribution_snapshot.long_upper_shadow,
        weak_close=distribution_snapshot.weak_close,
        false_breakout_flag=distribution_snapshot.false_breakout_flag,
        stall_after_volume_flag=distribution_snapshot.stall_after_volume_flag,
        intraday_reversal_flag=distribution_snapshot.intraday_reversal_flag,
        distribution_risk_score=distribution_snapshot.distribution_risk_score,
        trend_fatigue_score=trend_fatigue_score,
        momentum_exhaustion=_has_momentum_exhaustion(post_board=post_board, latest_close=float(latest["close"]), recent_low_guard=support_metrics["recent_low_guard"]),
        trend_ok=base_trend_ok,
        # strong_trend 是“趋势仍健康”的前置条件，不再只看均线多头；
        # 近 3 日若出现放量滞涨、涨幅递减或放量阴线，会通过 trend_fatigue_score 降级，
        # 避免趋势末端仍被误判为强趋势。
        strong_trend=base_strong_trend and trend_fatigue_score < LOW_BUY_THRESHOLDS.TREND_FATIGUE_STRONG_TREND_BLOCK,
        support_ok=support_metrics["support_distance_pct"] <= 2.8,
        shrink_ok=volume_metrics["latest_volume_ratio"] <= 0.72 and volume_metrics["post_volume_ratio"] <= 0.82,
        shrink_basic_ok=volume_metrics["latest_volume_ratio"] <= 0.92 and volume_metrics["post_volume_ratio"] <= 1.08,
        board_low_held=float(latest["close"]) >= float(board_row["low"]),
        board_open_held=float(latest["close"]) >= float(board_row["open"]) * 0.99,
        support_watch_ok=support_metrics["support_distance_pct"] <= 8.8,
        latest_change_ok=-8.0 <= float(latest["pct_chg"]) <= 5.5,
        unfilled_gap_count=int(gap_metrics["unfilled_gap_count"]),
        max_gap_size_pct=gap_metrics["max_gap_size_pct"],
        latest_gap_distance_pct=gap_metrics["latest_gap_distance_pct"],
        retracement_atr=volatility_metrics["retracement_atr"],
        retracement_atr_trend=volatility_metrics["retracement_atr_trend"],
        atr14=compute_daily_atr(history, ATR_WINDOW),
        atr_window=ATR_WINDOW,
        atr_source=ATR_SOURCE,
        consecutive_lower_lows=int(price_structure_metrics["consecutive_lower_lows"]),
        support_touch_count=int(price_structure_metrics["support_touch_count"]),
        retracement_smoothness=price_structure_metrics["retracement_smoothness"],
        multi_timeframe_resonance_score=resonance.score,
        multi_timeframe_resonance_text=resonance.text,
    )


def passes_common_prefilter(
    item: BoardCandidate,
    metrics: CandidateMetrics,
    strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
) -> bool:
    if strategy == "divergence_consensus":
        return all(
            [
                item.board_count == 1,
                metrics.board_gain_ok,
                metrics.volume_burst_ratio >= 1.4,
                metrics.platform_window_days >= 20,
                metrics.latest_change_pct <= 9.9,
            ]
        )
    if strategy in {
        "late_session_strong_support",
        "core_midcap_vwap_ma5_retrace",
        "sector_mainline_first_divergence_low_buy",
        "mainline_limitup_shrink_retrace_reclaim",
    }:
        return all(
            [
                metrics.volume_burst_ratio >= 0.85,
                metrics.support_watch_ok,
                metrics.latest_change_ok,
                item.board_count <= 2,
            ]
        )
    if strategy in {"n_pattern_long_wash", "n_pattern_short_wash"}:
        return all(
            [
                metrics.volume_burst_ratio >= 0.85,
                metrics.support_watch_ok,
                metrics.latest_change_ok,
                item.board_count <= 2,
                metrics.latest_close >= metrics.board_low * 0.995,
            ]
        )
    return all(
        [
            metrics.board_gain_ok,
            metrics.volume_burst_ratio >= 0.85,
            metrics.support_watch_ok,
            metrics.latest_change_ok,
            item.board_count <= 4,
        ]
    )


def _resolve_candidate_indices(history: pd.DataFrame, board_date: str) -> tuple[int, int] | None:
    board_rows = history.index[history["date"] == board_date].tolist()
    if not board_rows:
        return None
    board_index = board_rows[-1]
    latest_index = len(history) - 1
    retracement_days = latest_index - board_index
    if retracement_days < 1 or retracement_days > 15:
        return None
    return board_index, latest_index


def _build_candidate_slices(
    history: pd.DataFrame,
    board_index: int,
    latest_index: int,
) -> tuple[pd.Series, pd.Series, pd.DataFrame, pd.DataFrame] | None:
    board_row = history.iloc[board_index]
    latest = history.iloc[latest_index]
    post_board = history.iloc[board_index + 1 : latest_index + 1]
    prior = history.iloc[max(0, board_index - 5) : board_index]
    if post_board.empty or prior.empty:
        return None
    return board_row, latest, post_board, prior


def _resolve_candidate_averages(latest: pd.Series) -> tuple[float, float, float, float] | None:
    ma5 = float(latest["ma5"])
    ma10 = float(latest["ma10"])
    ma20 = float(latest["ma20"])
    ma60 = float(latest["ma60"]) if pd.notna(latest.get("ma60")) else ma20
    if min(ma5, ma10, ma20, ma60) <= 0:
        return None
    return ma5, ma10, ma20, ma60


def _build_volume_metrics(
    board_row: pd.Series,
    latest: pd.Series,
    post_board: pd.DataFrame,
    prior: pd.DataFrame,
) -> dict[str, float | bool]:
    shrink_tail = post_board["volume"].tail(min(3, len(post_board))).tolist()
    shrink_staircase = len(shrink_tail) >= 2 and all(float(left) >= float(right) for left, right in zip(shrink_tail, shrink_tail[1:]))
    post_volumes = [float(value) for value in post_board["volume"].tolist()]
    shrink_volatility = _compute_variation_coefficient(post_volumes)
    board_volume = float(board_row["volume"])
    return {
        "volume_burst_ratio": float(board_volume / max(prior["volume"].mean(), 1.0)),
        "latest_volume_ratio": float(latest["volume"] / max(board_volume, 1.0)),
        "post_volume_ratio": float(post_board["volume"].mean() / max(board_volume, 1.0)),
        "shrink_staircase": shrink_staircase,
        "shrink_quality_score": _compute_shrink_quality(post_volumes),
        "shrink_volatility": shrink_volatility,
        "abnormal_volume_days": sum(1 for volume in post_volumes if volume >= board_volume * 0.8),
    }


def _trend_fatigue_score(history: pd.DataFrame, latest_index: int) -> float:
    recent = history.iloc[max(0, latest_index - 2) : latest_index + 1]
    if len(recent) < 3:
        return 0.0
    score = 0.0
    pct_changes = [float(value) for value in recent["pct_chg"].tolist()]
    volumes = [float(value) for value in recent["volume"].tolist()]
    closes = [float(value) for value in recent["close"].tolist()]
    opens = [float(value) for value in recent["open"].tolist()]

    if pct_changes[0] > pct_changes[1] > pct_changes[2]:
        score += 2.0
    if volumes[0] < volumes[1] < volumes[2]:
        score += 2.0
    if closes[-1] < opens[-1] and volumes[-1] >= max(sum(volumes[:-1]) / 2, 1.0) * 1.2:
        score += 3.0
    if pct_changes[-1] < 0 and pct_changes[-2] < 0:
        score += 1.5
    latest_range = max(float(recent.iloc[-1]["high"]) - float(recent.iloc[-1]["low"]), 0.01)
    latest_upper_shadow = float(recent.iloc[-1]["high"]) - max(float(recent.iloc[-1]["open"]), float(recent.iloc[-1]["close"]))
    if latest_upper_shadow / latest_range >= 0.45:
        score += 1.5
    return round(min(score, 10.0), 2)


def _build_support_metrics(
    history: pd.DataFrame,
    latest_index: int,
    board_index: int,
    latest_close: float,
    ma5: float,
    ma10: float,
    ma20: float,
    prior: pd.DataFrame,
    post_board: pd.DataFrame,
) -> dict[str, float]:
    close_to_ma5 = abs(latest_close - ma5) / max(ma5, 0.01) * 100
    close_to_ma10 = abs(latest_close - ma10) / max(ma10, 0.01) * 100
    close_to_ma20 = abs(latest_close - ma20) / max(ma20, 0.01) * 100
    breakout_level = float(prior["high"].max())
    return {
        "close_to_ma5": close_to_ma5,
        "close_to_ma10": close_to_ma10,
        "close_to_ma20": close_to_ma20,
        "support_distance_pct": min(close_to_ma5, close_to_ma10, close_to_ma20),
        "breakout_level": breakout_level,
        "breakout_distance_pct": abs(latest_close - breakout_level) / max(breakout_level, 0.01) * 100,
        "recent_low_guard": float(post_board["low"].tail(min(3, len(post_board))).min()),
        "recent_swing_high": float(history["high"].iloc[max(0, board_index - 5) : latest_index + 1].max()),
    }


def _build_platform_metrics(
    history: pd.DataFrame,
    board_index: int,
    latest_close: float,
) -> dict[str, float]:
    platform_window = history.iloc[max(0, board_index - 40) : board_index]
    if platform_window.empty:
        return {
            "platform_high": latest_close,
            "platform_low": latest_close,
            "platform_window_days": 0,
            "platform_range_pct": 0.0,
            "platform_breakout_pct": 0.0,
            "platform_support_distance_pct": 0.0,
        }
    platform_high = float(platform_window["high"].max())
    platform_low = float(platform_window["low"].min())
    platform_range_pct = (platform_high - platform_low) / max(platform_low, 0.01) * 100
    platform_breakout_pct = (float(history.iloc[board_index]["close"]) - platform_high) / max(platform_high, 0.01) * 100
    platform_support_distance_pct = abs(latest_close - platform_high) / max(platform_high, 0.01) * 100
    return {
        "platform_high": platform_high,
        "platform_low": platform_low,
        "platform_window_days": len(platform_window),
        "platform_range_pct": platform_range_pct,
        "platform_breakout_pct": platform_breakout_pct,
        "platform_support_distance_pct": platform_support_distance_pct,
    }


def _has_momentum_exhaustion(post_board: pd.DataFrame, latest_close: float, recent_low_guard: float) -> bool:
    return (
        float(post_board.iloc[-1]["pct_chg"]) > -1.8
        and float(post_board["pct_chg"].tail(min(3, len(post_board))).mean()) > -2.2
        and latest_close >= recent_low_guard
    )


def _compute_retracement_volatility(post_board: pd.DataFrame) -> dict[str, float]:
    if len(post_board) < 3:
        return {"retracement_atr": 0.0, "retracement_atr_trend": 0.0}
    ranges = [
        max(float(row["high"]) - float(row["low"]), 0.0)
        for _, row in post_board.iterrows()
    ]
    midpoint = max(len(ranges) // 2, 1)
    first_avg = sum(ranges[:midpoint]) / max(midpoint, 1)
    second_avg = sum(ranges[midpoint:]) / max(len(ranges) - midpoint, 1)
    trend = (second_avg - first_avg) / max(first_avg, 0.01)
    return {
        "retracement_atr": round(sum(ranges) / len(ranges), 3),
        "retracement_atr_trend": round(trend, 4),
    }


def _compute_gap_risk(post_board: pd.DataFrame, latest_close: float) -> dict[str, float | int]:
    unfilled_gap_count = 0
    max_gap_size_pct = 0.0
    latest_gap_distance_pct = 99.0
    rows = list(post_board.iterrows())
    for index in range(1, len(rows)):
        _, prev_row = rows[index - 1]
        _, current_row = rows[index]
        prev_low = float(prev_row["low"])
        current_open = float(current_row["open"])
        if current_open >= prev_low:
            continue
        subsequent_highs = [float(post_board.iloc[row_index]["high"]) for row_index in range(index, len(post_board))]
        if any(high >= prev_low for high in subsequent_highs):
            continue
        gap_size_pct = (prev_low - current_open) / max(prev_low, 0.01) * 100
        distance_pct = abs(latest_close - prev_low) / max(prev_low, 0.01) * 100
        unfilled_gap_count += 1
        max_gap_size_pct = max(max_gap_size_pct, gap_size_pct)
        latest_gap_distance_pct = min(latest_gap_distance_pct, distance_pct)
    return {
        "unfilled_gap_count": unfilled_gap_count,
        "max_gap_size_pct": round(max_gap_size_pct, 2),
        "latest_gap_distance_pct": round(latest_gap_distance_pct, 2) if unfilled_gap_count else 99.0,
    }


def _compute_price_structure(post_board: pd.DataFrame, ma10: float, ma20: float) -> dict[str, float | int]:
    lows = [float(value) for value in post_board["low"].tolist()]
    closes = [float(value) for value in post_board["close"].tolist()]
    consecutive_lower_lows = _count_consecutive_lower_lows(lows)
    support_touch_count = _count_support_touches(lows=lows, closes=closes, ma10=ma10, ma20=ma20)
    return {
        "consecutive_lower_lows": consecutive_lower_lows,
        "support_touch_count": support_touch_count,
        "retracement_smoothness": round(_compute_path_smoothness(closes), 3),
    }


def _count_consecutive_lower_lows(lows: list[float]) -> int:
    count = 0
    for index in range(1, len(lows)):
        if lows[index] < lows[index - 1] * 0.998:
            count += 1
            continue
        break
    return count


def _count_support_touches(lows: list[float], closes: list[float], ma10: float, ma20: float) -> int:
    touches = 0
    for low, close in zip(lows, closes):
        lower_shadow_pct = (close - low) / max(close, 0.01)
        close_to_ma10 = abs(close - ma10) / max(ma10, 0.01)
        close_to_ma20 = abs(close - ma20) / max(ma20, 0.01)
        if close_to_ma10 <= 0.02 and lower_shadow_pct >= 0.01:
            touches += 1
        elif close_to_ma20 <= 0.025 and lower_shadow_pct >= 0.015:
            touches += 1
    return touches


def _compute_path_smoothness(prices: list[float]) -> float:
    if len(prices) < 3:
        return 0.5
    residuals, total_variance = _linear_residuals(prices)
    if total_variance <= 0.0001:
        return 1.0
    return max(0.0, min(1.0, 1.0 - residuals / total_variance))


def _compute_shrink_quality(volumes: list[float]) -> float:
    if len(volumes) < 3:
        return 5.0
    residuals, total_variance = _linear_residuals(volumes)
    mean_volume = sum(volumes) / len(volumes)
    if mean_volume <= 0:
        return 0.0
    rmse = (residuals / len(volumes)) ** 0.5
    trend_bonus = 1.5 if volumes[-1] <= volumes[0] else 0.0
    score = 10.0 - rmse / max(mean_volume, 1.0) * 10.0 + trend_bonus
    return round(max(0.0, min(10.0, score)), 2)


def _linear_residuals(values: list[float]) -> tuple[float, float]:
    count = len(values)
    x_mean = (count - 1) / 2.0
    y_mean = sum(values) / count
    numerator = sum((index - x_mean) * (values[index] - y_mean) for index in range(count))
    denominator = sum((index - x_mean) ** 2 for index in range(count))
    if denominator == 0:
        return 0.0, 0.0
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    residuals = sum((values[index] - (slope * index + intercept)) ** 2 for index in range(count))
    total_variance = sum((value - y_mean) ** 2 for value in values)
    return residuals, total_variance


def _compute_variation_coefficient(values: list[float]) -> float:
    if not values:
        return 0.0
    mean_value = sum(values) / len(values)
    if mean_value <= 0:
        return 0.0
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return round((variance ** 0.5) / mean_value, 4)
