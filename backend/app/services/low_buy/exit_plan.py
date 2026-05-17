from __future__ import annotations

from app.models.schemas import LowBuyExitPlanOut
from app.services.low_buy.candidate_types import CandidateMetrics, StrategySetup
from app.services.low_buy.holding_policy import strategy_holding_policy, strategy_max_holding_days


def build_exit_plan(
    *,
    strategy: str,
    metrics: CandidateMetrics,
    setup: StrategySetup,
    stop_loss: float,
    take_profit: float,
) -> LowBuyExitPlanOut:
    if strategy == "divergence_consensus":
        return _right_side_breakout_plan(metrics, setup, stop_loss, take_profit)
    if strategy == "limit_up_breakout_retrace":
        return _limit_up_retrace_plan(metrics, stop_loss, take_profit)
    if strategy in {"n_pattern_long_wash", "n_pattern_short_wash"}:
        return _n_pattern_plan(strategy, metrics, stop_loss, take_profit)
    return _classic_low_buy_plan(strategy, metrics, stop_loss, take_profit)


def _right_side_breakout_plan(
    metrics: CandidateMetrics,
    setup: StrategySetup,
    stop_loss: float,
    take_profit: float,
) -> LowBuyExitPlanOut:
    trailing_stop = round(max(metrics.consolidation_high, metrics.ma5) * 0.99, 3)
    return LowBuyExitPlanOut(
        stop_loss=stop_loss,
        first_take_profit=round(setup.entry_zone_high * 1.03, 3),
        trailing_stop=max(stop_loss, trailing_stop),
        max_holding_days=strategy_max_holding_days("divergence_consensus"),
        time_stop_text=strategy_holding_policy("divergence_consensus").time_stop_text,
        invalid_condition="收盘跌回分歧高点或横盘下沿，右侧一致失败。",
        exit_rules=[
            "次日冲高 3%-5% 先止盈，不再幻想 5 日主升。",
            "跌回分歧高点下方，不再按低吸逻辑加仓。",
            "放量突破但长上影或冲高回落，按一致失败处理。",
        ],
    )


def _limit_up_retrace_plan(
    metrics: CandidateMetrics,
    stop_loss: float,
    take_profit: float,
) -> LowBuyExitPlanOut:
    trailing_stop = round(max(metrics.platform_high, metrics.ma5) * 0.985, 3)
    return LowBuyExitPlanOut(
        stop_loss=stop_loss,
        first_take_profit=round(max(metrics.platform_high, metrics.board_high) * 1.03, 3),
        trailing_stop=max(stop_loss, trailing_stop),
        max_holding_days=strategy_max_holding_days("limit_up_breakout_retrace"),
        time_stop_text=strategy_holding_policy("limit_up_breakout_retrace").time_stop_text,
        invalid_condition="跌回平台高点或涨停开盘价下方，突破回踩逻辑失效。",
        exit_rules=[
            "冲高 3%-5% 先分批止盈，不能把弹性收益拿成回撤。",
            "跌破平台支撑直接退出，不做补仓。",
            "冲高后跌破 VWAP 或放量阴线跌破承接区，按失败样本处理。",
        ],
    )


def _n_pattern_plan(
    strategy: str,
    metrics: CandidateMetrics,
    stop_loss: float,
    take_profit: float,
) -> LowBuyExitPlanOut:
    max_days = strategy_max_holding_days(strategy)
    trailing_stop = round(max(metrics.board_low, metrics.recent_low_guard) * 0.992, 3)
    if strategy == "n_pattern_short_wash":
        invalid_condition = "跌破锤头/红十字低点或启动日低点，短洗 N 字试错失败。"
        exit_rules = [
            "次日不能弱转强或站稳 VWAP，直接退出。",
            "冲高 2%-4% 先兑现，不把试错仓拿成被动持仓。",
            "跌破启动日低点，不补仓、不等待反抽。",
        ]
    else:
        invalid_condition = "跌破启动日低点或再度放量阴跌，长洗 N 字结构失败。"
        exit_rules = [
            "放量修复后 3-5 日内不能脱离买点区，主动降级。",
            "冲高 3%-5% 先处理一半风险，剩余仓位看低点是否继续抬高。",
            "跌破启动日低点或关键均线支撑，不再按 N 字结构持有。",
        ]
    return LowBuyExitPlanOut(
        stop_loss=stop_loss,
        first_take_profit=round(max(take_profit, metrics.latest_close * 1.03), 3),
        trailing_stop=max(stop_loss, trailing_stop),
        max_holding_days=max_days,
        time_stop_text=strategy_holding_policy(strategy).time_stop_text,
        invalid_condition=invalid_condition,
        exit_rules=exit_rules,
    )


def _classic_low_buy_plan(
    strategy: str,
    metrics: CandidateMetrics,
    stop_loss: float,
    take_profit: float,
) -> LowBuyExitPlanOut:
    if strategy in {"late_session_strong_support", "core_midcap_vwap_ma5_retrace"}:
        return _next_day_repair_plan(strategy, metrics, stop_loss, take_profit)
    if strategy == "sector_mainline_first_divergence_low_buy":
        return _mainline_first_divergence_plan(metrics, stop_loss, take_profit)
    if strategy == "mainline_limitup_shrink_retrace_reclaim":
        return _mainline_limitup_shrink_retrace_plan(metrics, stop_loss, take_profit)
    max_days = strategy_max_holding_days(strategy)
    trailing_stop = round(max(metrics.ma5, metrics.ma10 * 0.995) * 0.99, 3)
    exit_rules = _classic_exit_rules(strategy)
    return LowBuyExitPlanOut(
        stop_loss=stop_loss,
        first_take_profit=take_profit,
        trailing_stop=max(stop_loss, trailing_stop),
        max_holding_days=max_days,
        time_stop_text=strategy_holding_policy(strategy).time_stop_text,
        invalid_condition="跌破止损位或放量跌破关键均线，低吸逻辑失效。",
        exit_rules=exit_rules,
    )


def _classic_exit_rules(strategy: str) -> list[str]:
    if strategy == "first_board":
        return [
            "T+2 仍不能脱离买点区或弱于板块，先减仓降级。",
            "冲高 3%-5% 先分批止盈，强势票才验证到第 5 天。",
            "跌破首板低点、首板开盘价或移动防守线，直接退出。",
        ]
    if strategy == "volume_shrink":
        return [
            "1-3 个交易日内不能缩量后转强，主动降级退出。",
            "冲高 3%-5% 先分批止盈，不能让盈利票回到亏损。",
            "回调重新放量下跌或跌破移动防守线，直接退出。",
        ]
    return [
        "亏损触及止损位直接退出。",
        "到达首次止盈位先降低风险敞口。",
        "盈利后跌破移动防守线，不再等待反抽。",
    ]


def _next_day_repair_plan(
    strategy: str,
    metrics: CandidateMetrics,
    stop_loss: float,
    take_profit: float,
) -> LowBuyExitPlanOut:
    anchor_text = "收盘承接" if strategy == "late_session_strong_support" else "中军支撑"
    trailing_stop = round(max(metrics.ma5, metrics.ma10 * 0.995) * 0.992, 3)
    return LowBuyExitPlanOut(
        stop_loss=stop_loss,
        first_take_profit=round(max(take_profit, metrics.latest_close * 1.025), 3),
        trailing_stop=max(stop_loss, trailing_stop),
        max_holding_days=strategy_max_holding_days(strategy),
        time_stop_text=strategy_holding_policy(strategy).time_stop_text,
        invalid_condition="跌破 5 日线或分时承接位、放量转弱，短线修复逻辑失效。",
        exit_rules=_next_day_repair_rules(strategy, anchor_text),
    )


def _next_day_repair_rules(strategy: str, anchor_text: str) -> list[str]:
    if strategy == "core_midcap_vwap_ma5_retrace":
        return [
            "T+2 不强于板块先减仓，守住 VWAP/5 日线才验证到第 5 天。",
            "冲高 2%-4% 先处理一半风险，不追高加仓。",
            "跌回 VWAP、5 日线或明显弱于板块，直接退出。",
        ]
    return [
        "次日冲高 1.5%-3% 先分批兑现，不做趋势持有。",
        f"10:30 前不能延续{anchor_text}或明显弱于板块，主动降级。",
        "T+2 最晚退出，不把事件交易拿成中线持仓。",
    ]


def _mainline_first_divergence_plan(
    metrics: CandidateMetrics,
    stop_loss: float,
    take_profit: float,
) -> LowBuyExitPlanOut:
    trailing_stop = round(max(metrics.board_low, metrics.ma5 * 0.985), 3)
    return LowBuyExitPlanOut(
        stop_loss=stop_loss,
        first_take_profit=round(max(take_profit, metrics.latest_close * 1.03), 3),
        trailing_stop=max(stop_loss, trailing_stop),
        max_holding_days=strategy_max_holding_days("sector_mainline_first_divergence_low_buy"),
        time_stop_text=strategy_holding_policy("sector_mainline_first_divergence_low_buy").time_stop_text,
        invalid_condition="跌破首板低点、5 日线或板块核心票集体转弱，首分歧低吸逻辑失效。",
        exit_rules=[
            "次日弱转强或冲高 3%-5% 先处理一半风险。",
            "板块没有回流、个股不强于板块，不继续加仓。",
            "T+2 仍不能脱离买点区，直接降级退出。",
        ],
    )


def _mainline_limitup_shrink_retrace_plan(
    metrics: CandidateMetrics,
    stop_loss: float,
    take_profit: float,
) -> LowBuyExitPlanOut:
    trailing_stop = round(max(metrics.ma5 * 0.99, metrics.recent_low_guard), 3)
    return LowBuyExitPlanOut(
        stop_loss=stop_loss,
        first_take_profit=round(max(take_profit, metrics.latest_close * 1.035), 3),
        trailing_stop=max(stop_loss, trailing_stop),
        max_holding_days=strategy_max_holding_days("mainline_limitup_shrink_retrace_reclaim"),
        time_stop_text=strategy_holding_policy("mainline_limitup_shrink_retrace_reclaim").time_stop_text,
        invalid_condition="跌回 5 日线、均线合一区或启动低点，主线涨停回调逻辑失效。",
        exit_rules=[
            "二次站稳后 2-5 日内验证修复，不能转强就主动降级。",
            "冲高 3%-5% 先处理一半风险，不把低吸票拿成追高票。",
            "跌回 5 日线或放量跌破支撑带，直接退出，不补仓硬扛。",
        ],
    )
