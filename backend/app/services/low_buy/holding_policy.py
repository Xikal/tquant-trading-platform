from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyHoldingPolicy:
    max_holding_days: int
    brief: str
    time_stop_text: str
    card_hint: str


_DEFAULT_POLICY = StrategyHoldingPolicy(
    max_holding_days=3,
    brief="1-3日验证",
    time_stop_text="3 个交易日内没有脱离买点区或继续转强，先退出等待新结构。",
    card_hint="持有建议：1-3日验证，冲高先降风险，跌破止损退出。",
)

_POLICIES: dict[str, StrategyHoldingPolicy] = {
    "classic_retrace": StrategyHoldingPolicy(
        max_holding_days=3,
        brief="观察策略，不做生产持有",
        time_stop_text="该策略已降级，若仅作研究观察，3 个交易日内不转强就取消计划。",
        card_hint="持有建议：观察层，不作为生产买入依据。",
    ),
    "ma_support": StrategyHoldingPolicy(
        max_holding_days=3,
        brief="辅助因子，不单独持有",
        time_stop_text="均线支撑只作为辅助因子，3 个交易日内不转强就取消计划。",
        card_hint="持有建议：只作支撑确认，不能单独作为买入理由。",
    ),
    "first_board": StrategyHoldingPolicy(
        max_holding_days=5,
        brief="2-5日验证",
        time_stop_text="T+2 仍不能转强先降级；强势票可验证到第 5 天，跌破首板关键价退出。",
        card_hint="持有建议：2-5日验证，T+2弱先减，强势才看第5天。",
    ),
    "volume_shrink": StrategyHoldingPolicy(
        max_holding_days=3,
        brief="1-3日验证",
        time_stop_text="1-3 个交易日内没有缩量后转强，先退出等待下一次承接。",
        card_hint="持有建议：1-3日，T+2不转强就降级。",
    ),
    "late_session_strong_support": StrategyHoldingPolicy(
        max_holding_days=2,
        brief="T+1冲高兑现",
        time_stop_text="次日不能延续收盘承接并冲高，T+2 前必须降级退出。",
        card_hint="持有建议：T+1冲高兑现，不做趋势持有。",
    ),
    "core_midcap_vwap_ma5_retrace": StrategyHoldingPolicy(
        max_holding_days=5,
        brief="2-5日修复",
        time_stop_text="T+2 不强于板块先降级；守住 VWAP/5 日线才可验证到第 5 天。",
        card_hint="持有建议：2-5日修复，只要跌回VWAP/5日线就退出。",
    ),
    "sector_mainline_first_divergence_low_buy": StrategyHoldingPolicy(
        max_holding_days=2,
        brief="T+1/T+2验证",
        time_stop_text="主线首分歧只验证 T+1/T+2 回流，不能继续强于板块就退出。",
        card_hint="持有建议：T+1/T+2验证，板块不回流就放弃。",
    ),
    "breakout_support": StrategyHoldingPolicy(
        max_holding_days=3,
        brief="支撑因子观察",
        time_stop_text="突破支撑已降级为辅助因子，3 个交易日内不确认就取消计划。",
        card_hint="持有建议：只作为支撑位参考，不单独执行。",
    ),
    "limit_up_breakout_retrace": StrategyHoldingPolicy(
        max_holding_days=2,
        brief="T+1事件验证",
        time_stop_text="T+1 看冲高兑现或弱转强，T+2 仍不转强就取消计划。",
        card_hint="持有建议：T+1/T+2事件验证，不做5日持有。",
    ),
    "divergence_consensus": StrategyHoldingPolicy(
        max_holding_days=2,
        brief="T+1弱转强验证",
        time_stop_text="T+1 必须弱转强确认，T+2 不能继续强于板块就退出。",
        card_hint="持有建议：T+1弱转强确认，失败立即退出。",
    ),
    "deep_pullback": StrategyHoldingPolicy(
        max_holding_days=3,
        brief="研究层3日观察",
        time_stop_text="深回撤只保留研究观察，3 个交易日内不修复就放弃。",
        card_hint="持有建议：研究层，样本不足，不放大仓位。",
    ),
    "trend_rebound": StrategyHoldingPolicy(
        max_holding_days=3,
        brief="并入主线龙头逻辑",
        time_stop_text="趋势龙回头已降级，3 个交易日内不反包就取消计划。",
        card_hint="持有建议：不作为独立生产策略。",
    ),
}


def strategy_holding_policy(strategy_key: str) -> StrategyHoldingPolicy:
    return _POLICIES.get(strategy_key, _DEFAULT_POLICY)


def strategy_max_holding_days(strategy_key: str) -> int:
    return strategy_holding_policy(strategy_key).max_holding_days


def strategy_holding_card_hint(strategy_key: str) -> str:
    return strategy_holding_policy(strategy_key).card_hint


def strategy_holding_brief(strategy_key: str) -> str:
    return strategy_holding_policy(strategy_key).brief


def strategy_exit_plan_text(strategy_key: str, stop_loss: float) -> str:
    policy = strategy_holding_policy(strategy_key)
    stop_text = f"跌破 {stop_loss:.3f} 退出" if stop_loss > 0 else "跌破止损退出"
    return f"{policy.card_hint} {stop_text}。"
