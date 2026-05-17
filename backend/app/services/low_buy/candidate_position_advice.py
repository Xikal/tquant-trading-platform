from __future__ import annotations

from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.position_sizing import compute_kelly_position
from app.services.low_buy.positioning import total_position_multiplier
from app.services.low_buy.shared import LOW_BUY_THRESHOLDS
from app.services.low_buy.strategy_policy import is_core_production


def position_advice_for_signal(
    candidate: LowBuyCandidateOut,
    state: str,
    performance=None,
) -> tuple[float, str]:
    strategy = candidate.strategy_key
    if state == "buy_now":
        position, text = _mapped_advice(strategy, _BUY_NOW_ADVICE, (20.0, "先小仓试错，确认后再加。"))
        position, text = _kelly_adjusted_base_position(position, text, performance)
        return _market_adjusted_position(candidate, position, text)
    if state == "soft_buy_now":
        position, text = _mapped_advice(strategy, _SOFT_BUY_ADVICE, (15.0, "软确认买点只建议轻仓试错。"))
        position, text = _kelly_adjusted_base_position(position, text, performance)
        return _market_adjusted_position(candidate, position, text)
    if state == "observe_confirmed":
        return _market_adjusted_position(candidate, 8.0, "观察确认已成立，但策略仍不自动交易；最多预留 8% 观察仓。")
    if state == "near_entry":
        return _market_adjusted_position(candidate, 15.0, "已经接近买点，先列计划，最多预留 15% 试仓。")
    if state == "watch":
        return 0.0, "还没到可执行区，暂时不下单。"
    return 0.0, "今天不做这只票。"


_BUY_NOW_ADVICE: dict[str, tuple[float, str]] = {
    "classic_retrace": (30.0, "先试仓 30%，承接继续增强再加到 50%。"),
    "ma_support": (30.0, "均线承接明确，先试仓 30%，确认后再加。"),
    "first_board": (25.0, "首板回踩波动更快，先试仓 25%。"),
    "volume_shrink": (25.0, "缩量承接型机会，先试仓 25%。"),
    "late_session_strong_support": (12.0, "收盘承接只做次日兑现，先试仓 12%。"),
    "core_midcap_vwap_ma5_retrace": (15.0, "主线中军回踩支撑，先试仓 15%，不做重仓追涨。"),
    "sector_mainline_first_divergence_low_buy": (12.0, "主线首分歧只做核心前排，先试仓 12%。"),
    "mainline_limitup_shrink_retrace_reclaim": (12.0, "主线涨停缩量回调只做二次确认，先试仓 12%。"),
    "breakout_support": (20.0, "突破回踩更看确认，先试仓 20%。"),
    "limit_up_breakout_retrace": (18.0, "突破回踩型机会更强调确认，先试仓 18%。"),
    "divergence_consensus": (16.0, "分歧转一致属于右侧确认，先试仓 16%，跌回突破位不留恋。"),
    "n_pattern_long_wash": (12.0, "长洗 N 字已纳入核心生产策略，只做冲高止盈，先试仓 12%。"),
    "n_pattern_short_wash": (8.0, "短洗 N 字已纳入核心生产策略，只做 T+1/T+2 冲高止盈，先试仓 8%。"),
    "deep_pullback": (15.0, "深水低吸风险高，只建议 15% 试仓。"),
    "trend_rebound": (25.0, "趋势龙回头，先试仓 25%，不要一次打满。"),
}

_SOFT_BUY_ADVICE: dict[str, tuple[float, str]] = {
    "classic_retrace": (20.0, "软确认已成立，先试仓 20%，强确认再补。"),
    "ma_support": (20.0, "均线承接基本成立，先试仓 20%。"),
    "first_board": (18.0, "首板回踩先轻仓，确认后再加。"),
    "volume_shrink": (18.0, "量能回落但还没到最强确认，先试仓 18%。"),
    "late_session_strong_support": (8.0, "收盘承接软确认，只允许轻仓观察次日冲高。"),
    "core_midcap_vwap_ma5_retrace": (10.0, "中军回踩软确认，先小仓看修复。"),
    "sector_mainline_first_divergence_low_buy": (8.0, "主线首分歧软确认，只能轻仓等待回流。"),
    "mainline_limitup_shrink_retrace_reclaim": (8.0, "主线涨停回调软确认，只能小仓等站稳 5 日线。"),
    "breakout_support": (15.0, "突破回踩先轻仓，等进一步承接。"),
    "limit_up_breakout_retrace": (12.0, "涨停突破回踩先小仓试错，确认二次转强再加。"),
    "divergence_consensus": (10.0, "突破确认还不够硬，只允许 10% 轻仓观察。"),
    "n_pattern_long_wash": (8.0, "长洗 N 字软确认只做 8% 轻仓，盈利来源以冲高兑现为主。"),
    "n_pattern_short_wash": (5.0, "短洗 N 字软确认只做 5% 轻仓，次日不冲高就快速退出。"),
    "deep_pullback": (10.0, "深水回撤只允许更轻的软确认试仓。"),
    "trend_rebound": (18.0, "龙回头软确认，先轻仓参与。"),
}


def _mapped_advice(
    strategy: str,
    mapping: dict[str, tuple[float, str]],
    fallback: tuple[float, str],
) -> tuple[float, str]:
    return mapping.get(strategy, fallback)


def _kelly_adjusted_base_position(base_position_pct: float, text: str, performance=None) -> tuple[float, str]:
    filled_signals = int(getattr(performance, "filled_signals", 0) or 0)
    if performance is None or filled_signals < LOW_BUY_THRESHOLDS.MIN_SAMPLE_SIZE_DISPLAY:
        return base_position_pct, text
    avg_win_pct = float(getattr(performance, "avg_win_pct", 0.0) or 0.0)
    avg_loss_pct = float(getattr(performance, "avg_loss_pct", 0.0) or 0.0)
    if avg_win_pct <= 0 or avg_loss_pct >= 0:
        return base_position_pct, text
    kelly = compute_kelly_position(
        win_rate=float(getattr(performance, "hit_rate", 0.0) or 0.0) / 100.0,
        avg_win_pct=avg_win_pct,
        avg_loss_pct=avg_loss_pct,
    )
    if kelly.half_kelly <= 0:
        return 0.0, f"{text} 策略历史盈亏比暂不支持放大仓位，先观察。"
    kelly_position_pct = round(kelly.half_kelly * 100, 2)
    adjusted = min(base_position_pct, kelly_position_pct)
    return adjusted, f"{text} 已按半凯利仓位上限 {kelly_position_pct:.1f}% 收敛。"


def _market_adjusted_position(
    candidate: LowBuyCandidateOut,
    base_position_pct: float,
    text: str,
) -> tuple[float, str]:
    market_multiplier = max(candidate.market_position_multiplier, 0.0)
    risk_multiplier = max(candidate.risk_position_multiplier, 0.0)
    industry_multiplier = max(candidate.industry_position_multiplier, 0.0)
    dynamic_multiplier = max(candidate.dynamic_position_multiplier, 0.0)
    multiplier = total_position_multiplier(candidate)
    adjusted = round(base_position_pct * multiplier, 2)
    notes: list[str] = []
    deep_pullback_factor = float(candidate.factor_scores.get("deep_pullback_factor", 0.0) or 0.0)
    if deep_pullback_factor > 0 and not is_core_production(candidate.strategy_key):
        adjusted = min(adjusted, LOW_BUY_THRESHOLDS.DEEP_PULLBACK_NON_CORE_POSITION_CAP)
        notes.append("深回撤因子只作为辅助判断，非核心策略仓位封顶 10%。")
    if market_multiplier < 0.99:
        notes.append(f"当前{candidate.market_state_text or '市场偏弱'}，仓位已自动下调。")
    if risk_multiplier <= 0.01:
        notes.append("当前风险层级已阻断，不建议开仓。")
    elif risk_multiplier < 0.95:
        notes.append("当前风险层级偏谨慎，仓位已自动收缩。")
    if industry_multiplier > 1.03:
        notes.append(f"{candidate.industry_tier_text}，仓位小幅上调。")
    elif industry_multiplier < 0.95:
        notes.append(f"{candidate.industry_tier_text}，仓位继续收紧。")
    if dynamic_multiplier <= 0.9:
        notes.append("动态权重偏弱，仓位已进一步收紧。")
    elif dynamic_multiplier >= 1.05:
        notes.append("动态权重偏强，可按计划执行。")
    if not notes:
        return adjusted, text
    return adjusted, f"{text} {' '.join(notes)}"
