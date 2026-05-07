from __future__ import annotations

from dataclasses import dataclass, replace

from app.services.low_buy.candidate_types import CandidateMetrics, StrategySetup
from app.services.low_buy.factor_types import FactorContext
from app.services.low_buy.shared import BoardCandidate, LOW_BUY_THRESHOLDS


@dataclass(frozen=True)
class SignalFamilyProfile:
    stage_scores: dict[str, float]
    score_bonus: float
    stage_text: str
    trigger_condition: str
    invalid_condition: str
    next_watch_price: float | None
    leader_rank: str


def build_signal_family_profile(
    *,
    strategy: str,
    item: BoardCandidate,
    metrics: CandidateMetrics,
    hot_industries: list[str],
    setup: StrategySetup | None = None,
) -> SignalFamilyProfile:
    stage_scores = {
        "startup_quality": _startup_quality(item, metrics, hot_industries),
        "pullback_health": _pullback_health(metrics),
        "confirmation_quality": _confirmation_quality(metrics),
        "failure_risk": _failure_risk(metrics),
    }
    weighted = (
        stage_scores["startup_quality"] * 0.24
        + stage_scores["pullback_health"] * 0.30
        + stage_scores["confirmation_quality"] * 0.26
        + stage_scores["failure_risk"] * 0.20
    )
    leader_rank = _leader_rank(item, metrics, hot_industries)
    leader_bonus = {"leader": 1.1, "strong_follow": 0.3, "laggard": -1.1}.get(leader_rank, 0.0)
    score_bonus = round(_clamp((weighted - 72.0) * 0.18 + leader_bonus, -4.0, 5.0), 2)
    profile = SignalFamilyProfile(
        stage_scores={key: round(value, 1) for key, value in stage_scores.items()},
        score_bonus=score_bonus,
        stage_text=_stage_text(strategy, stage_scores, leader_rank),
        trigger_condition="价格进入买点区，且日内止跌/承接确认。",
        invalid_condition="跌破止损位、放量下杀或重新出现假突破派发，低吸逻辑失效。",
        next_watch_price=None,
        leader_rank=leader_rank,
    )
    if setup is None:
        return profile
    return profile_with_setup(profile, setup, strategy=strategy)


def evaluate_deep_pullback_factor(metrics: CandidateMetrics) -> float:
    score = 0.0
    if -8.0 <= metrics.drawdown_from_board_pct <= -3.0:
        score += 2.0
    if -7.0 <= metrics.drawdown_from_board_pct <= -5.0:
        score += 1.5
    if metrics.latest_volume_ratio < 0.8:
        score += 1.0
    if 0 <= min(metrics.support_distance_ma20_pct, abs(metrics.close_to_ma20)) <= 2.0:
        score += 0.5
    return round(_clamp(score, 0.0, 5.0), 2)


def evaluate_trend_rebound_factor(metrics: CandidateMetrics) -> float:
    score = 0.0
    if metrics.board_gain_ok:
        score += 1.5
    if -15.0 <= metrics.drawdown_from_board_pct <= -8.0:
        score += 1.5
    if abs(metrics.close_to_ma20) <= 2.0:
        score += 1.0
    if metrics.latest_volume_ratio > 1.2:
        score += 1.0
    return round(_clamp(score, 0.0, 5.0), 2)


def evaluate_shrink_quality_factor(metrics: CandidateMetrics) -> float:
    score = 0.0
    if metrics.shrink_staircase:
        score += 2.5
    elif metrics.shrink_quality_score >= 5.0:
        score += 1.5
    elif metrics.shrink_basic_ok:
        score += 0.8
    if metrics.post_volume_ratio <= 0.55:
        score += 2.0
    elif metrics.post_volume_ratio <= 0.72:
        score += 1.5
    elif metrics.post_volume_ratio <= 0.88:
        score += 0.8
    if metrics.abnormal_volume_days >= 3:
        score -= 2.0
    elif metrics.abnormal_volume_days >= 1:
        score -= 1.0
    if metrics.shrink_volatility <= 0.15:
        score += 3.0
    elif metrics.shrink_volatility <= 0.30:
        score += 1.5
    return round(_clamp(score, 0.0, 5.0), 2)


def evaluate_volatility_regime_factor(metrics: CandidateMetrics) -> float:
    score = 0.0
    if metrics.retracement_atr_trend <= -0.15:
        score += 3.0
    elif metrics.retracement_atr_trend <= -0.05:
        score += 1.5
    elif metrics.retracement_atr_trend >= 0.15:
        score -= 1.5
    atr_pct = metrics.retracement_atr / max(metrics.latest_close, 0.01) * 100
    if 1.5 <= atr_pct <= 4.0:
        score += 1.5
    elif atr_pct > 7.0:
        score -= 1.0
    return round(_clamp(score, 0.0, 5.0), 2)


def evaluate_gap_risk_factor(metrics: CandidateMetrics) -> float:
    score = 5.0
    if metrics.unfilled_gap_count >= 3:
        score -= 3.0
    elif metrics.unfilled_gap_count >= 1:
        score -= metrics.unfilled_gap_count * 1.0
    if metrics.max_gap_size_pct >= 3.0:
        score -= 2.0
    elif metrics.max_gap_size_pct >= 1.5:
        score -= 1.0
    if metrics.latest_gap_distance_pct <= 2.0:
        score -= 1.5
    if metrics.latest_gap_distance_pct >= 5.0 and metrics.unfilled_gap_count > 0:
        score += 1.0
    return round(_clamp(score, 0.0, 5.0), 2)


def evaluate_time_efficiency_factor(metrics: CandidateMetrics) -> float:
    if metrics.retracement_days <= 0:
        return 0.0
    speed = metrics.drawdown_per_day or abs(metrics.drawdown_from_board_pct) / max(metrics.retracement_days, 1)
    score = 0.0
    if speed <= 0.8:
        score += 3.0
    elif speed <= 1.5:
        score += 2.0
    elif speed <= 2.5:
        score += 1.0
    elif speed >= 5.0:
        score -= 1.5
    return round(_clamp(score, 0.0, 5.0), 2)


def evaluate_signal_freshness_factor(context: FactorContext | None) -> float:
    if context is None or not context.confirmed_trade_date or not context.current_date:
        return 0.0
    try:
        from datetime import datetime

        confirmed = datetime.strptime(context.confirmed_trade_date[:10], "%Y-%m-%d")
        current = datetime.strptime(context.current_date[:10], "%Y-%m-%d")
        days_old = (current - confirmed).days
    except (ValueError, IndexError):
        return 0.0
    if days_old <= 0:
        return 3.0
    if days_old == 1:
        return 2.0
    if days_old == 2:
        return 1.0
    if days_old == 3:
        return 0.5
    return 0.0


def evaluate_sector_density_factor(context: FactorContext | None) -> float:
    if context is None or not context.current_sector:
        return 0.0
    count = int(context.sector_pass_counts.get(context.current_sector, 0) or 0)
    if count >= 6:
        return 3.0
    if count >= 4:
        return 2.0
    if count >= 2:
        return 1.0
    return 0.0


def evaluate_sector_flow_factor(context: FactorContext | None) -> float:
    if context is None or not context.current_sector or not context.sector_flow_ranks:
        return 0.0
    if context.current_sector in context.sector_flow_ranks:
        return context.sector_flow_ranks[context.current_sector]
    for name, score in context.sector_flow_ranks.items():
        if context.current_sector in name or name in context.current_sector:
            return round(score * 0.8, 2)
    return 0.0


def evaluate_absorption_quality_factor(intraday_bars: list[dict] | None = None) -> float:
    """盘中承接质量因子；无分时输入时返回 0，不影响盘后筛选。"""

    if not intraday_bars or len(intraday_bars) < 30:
        return 0.0
    midpoint = len(intraday_bars) // 2
    morning = intraday_bars[:midpoint]
    afternoon = intraday_bars[midpoint:]
    score = 0.0
    last_30 = intraday_bars[-6:]
    if len(last_30) >= 3:
        tail_trend = float(last_30[-1]["close"]) > float(last_30[0]["open"])
        tail_volume_up = sum(float(bar.get("volume", 0.0)) for bar in last_30[-3:]) > sum(
            float(bar.get("volume", 0.0)) for bar in last_30[:3]
        )
        if tail_trend and tail_volume_up:
            score += 2.0
        elif tail_trend:
            score += 1.0
        elif tail_volume_up:
            score -= 1.5
    morning_low = min(float(bar["low"]) for bar in morning)
    afternoon_low = min(float(bar["low"]) for bar in afternoon)
    if afternoon_low > morning_low * 1.002:
        score += 1.5
    day_high = max(float(bar["high"]) for bar in intraday_bars)
    day_low = min(float(bar["low"]) for bar in intraday_bars)
    close_position = (float(intraday_bars[-1]["close"]) - day_low) / max(day_high - day_low, 0.01)
    if close_position >= 0.6:
        score += 1.5
    elif close_position <= 0.3:
        score -= 1.0
    return round(_clamp(score, 0.0, 5.0), 2)


def evaluate_price_structure_factor(metrics: CandidateMetrics) -> float:
    score = 0.0
    if metrics.consecutive_lower_lows == 0:
        score += 3.0
    elif metrics.consecutive_lower_lows <= 2:
        score += 1.5
    elif metrics.consecutive_lower_lows >= 5:
        score -= 2.0
    if metrics.support_touch_count >= 3:
        score += 2.0
    elif metrics.support_touch_count >= 1:
        score += 1.0
    if metrics.retracement_smoothness >= 0.7:
        score += 2.0
    elif metrics.retracement_smoothness <= 0.3:
        score -= 1.0
    return round(_clamp(score, 0.0, 5.0), 2)


def profile_with_setup(profile: SignalFamilyProfile, setup: StrategySetup, strategy: str | None = None) -> SignalFamilyProfile:
    if strategy == "divergence_consensus":
        trigger = f"放量阳线站上 {setup.entry_zone_low:.3f}-{setup.entry_zone_high:.3f}，且不能跌回分歧高点。"
    elif strategy == "late_session_strong_support":
        trigger = f"收盘站稳 {setup.entry_zone_low:.3f}-{setup.entry_zone_high:.3f}，次日只做冲高兑现。"
    elif strategy == "core_midcap_vwap_ma5_retrace":
        trigger = f"回踩 5/10 日线 {setup.entry_zone_low:.3f}-{setup.entry_zone_high:.3f} 后重新转强。"
    elif strategy == "sector_mainline_first_divergence_low_buy":
        trigger = f"主线首分歧回踩 {setup.entry_zone_low:.3f}-{setup.entry_zone_high:.3f}，次日弱转强确认。"
    elif strategy == "mainline_limitup_shrink_retrace_reclaim":
        trigger = f"主线涨停后缩量回踩 {setup.entry_zone_low:.3f}-{setup.entry_zone_high:.3f}，重新站回 5 日线。"
    else:
        trigger = f"价格进入 {setup.entry_zone_low:.3f}-{setup.entry_zone_high:.3f}，并出现止跌确认。"
    return replace(profile, trigger_condition=trigger, next_watch_price=round(setup.entry_zone_high, 3))


def _startup_quality(item: BoardCandidate, metrics: CandidateMetrics, hot_industries: list[str]) -> float:
    volume_score = _normalize(metrics.volume_burst_ratio, 1.15, 2.8) * 42
    board_score = (22 if item.board_count == 1 else 16 if item.board_count == 2 else 8)
    trend_score = 22 if metrics.strong_trend else 16 if metrics.trend_ok else 6
    hot_score = 14 if item.industry and item.industry in hot_industries else 6
    return _clamp(volume_score + board_score + trend_score + hot_score, 0, 100)


def _pullback_health(metrics: CandidateMetrics) -> float:
    retrace_score = _retracement_day_score(metrics.retracement_days)
    shrink_score = 100 if metrics.shrink_ok else 78 if metrics.shrink_basic_ok else 45
    drawdown_score = 92 if -8.0 <= metrics.drawdown_from_board_pct <= -2.5 else 70
    support_score = 92 if metrics.support_ok else 72 if metrics.support_watch_ok else 42
    return retrace_score * 0.28 + shrink_score * 0.30 + drawdown_score * 0.20 + support_score * 0.22


def _retracement_day_score(retracement_days: int) -> float:
    """平滑回踩天数曲线，避免把 3/4 天差异写成过拟合硬编码。"""
    optimal_start, optimal_end = LOW_BUY_THRESHOLDS.PULLBACK_HEALTH_OPTIMAL_DAYS
    if optimal_start <= retracement_days <= optimal_end:
        return LOW_BUY_THRESHOLDS.PULLBACK_HEALTH_MAX_SCORE
    if retracement_days < optimal_start:
        distance = optimal_start - retracement_days
    else:
        distance = retracement_days - optimal_end
    score = LOW_BUY_THRESHOLDS.PULLBACK_HEALTH_MAX_SCORE - distance * LOW_BUY_THRESHOLDS.PULLBACK_HEALTH_DAY_DECAY
    return _clamp(score, LOW_BUY_THRESHOLDS.PULLBACK_HEALTH_MIN_SCORE, LOW_BUY_THRESHOLDS.PULLBACK_HEALTH_MAX_SCORE)


def _confirmation_quality(metrics: CandidateMetrics) -> float:
    score = 42.0
    if metrics.momentum_exhaustion:
        score += 24
    if metrics.doji_like:
        score += 11
    if metrics.long_lower_shadow:
        score += 10
    if metrics.latest_change_pct >= -1.2:
        score += 8
    if metrics.close_position_ratio >= 0.42:
        score += 5
    return _clamp(score, 0, 100)


def _failure_risk(metrics: CandidateMetrics) -> float:
    score = 100 - _normalize(metrics.distribution_risk_score, 2.0, 8.5) * 58
    if metrics.false_breakout_flag:
        score -= 24
    if metrics.stall_after_volume_flag:
        score -= 15
    if metrics.intraday_reversal_flag:
        score -= 13
    return _clamp(score, 0, 100)


def _leader_rank(item: BoardCandidate, metrics: CandidateMetrics, hot_industries: list[str]) -> str:
    hot = bool(item.industry and item.industry in hot_industries)
    if hot and item.board_count <= 2 and metrics.volume_burst_ratio >= 1.8 and metrics.strong_trend:
        return "leader"
    if (hot or metrics.strong_trend) and metrics.volume_burst_ratio >= 1.45:
        return "strong_follow"
    return "laggard"


def _stage_text(strategy: str, scores: dict[str, float], leader_rank: str) -> str:
    weakest = min(scores, key=scores.get)
    label_map = {
        "startup_quality": "启动质量",
        "pullback_health": "回调健康度",
        "confirmation_quality": "止跌确认",
        "failure_risk": "失败风险",
    }
    rank_text = {"leader": "龙头/强主线", "strong_follow": "强跟随", "laggard": "后排跟随"}.get(
        leader_rank,
        "未归类",
    )
    return f"{rank_text} · {strategy} · 短板：{label_map.get(weakest, weakest)}"


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clamp((value - low) / (high - low), 0.0, 1.0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
