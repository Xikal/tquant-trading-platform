from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Any

from app.services.low_buy.shared import PERFORMANCE_FORWARD_DAYS
from app.services.low_buy.strategy_families import resolve_strategy_family_label


CONFIRMED_STATES = {"buy_now", "soft_buy_now"}
NEAR_ENTRY_STATE = "near_entry"
EVALUATED_STATES = CONFIRMED_STATES | {NEAR_ENTRY_STATE}
SIGNAL_GROUPS = {
    "confirmed": ("确定买入", CONFIRMED_STATES),
    "near_entry": ("接近买点", {NEAR_ENTRY_STATE}),
}


@dataclass
class TradeOutcome:
    symbol: str
    name: str
    signal_date: str
    strategy_key: str
    buy_signal_state: str
    entry_price: float
    execution_status: str
    net_return_pct: float
    execution_exit_reason: str
    return_1d: float
    return_2d: float
    return_3d: float
    return_4d: float
    return_5d: float
    max_gain_5d: float
    max_drawdown_5d: float
    t1_high_return_pct: float = 0.0
    t1_close_return_pct: float = 0.0
    t1_spike_fade_pct: float = 0.0
    t2_high_return_pct: float = 0.0
    t2_close_return_pct: float = 0.0
    t1_hit_3_pct: bool = False
    t1_hit_5_pct: bool = False
    t1_fade_to_entry: bool = False


@dataclass
class StrategyBacktestStats:
    strategy_key: str
    strategy_title: str
    strategy_family: str
    strategy_family_text: str
    snapshot_count: int = 0
    snapshot_dates: set[str] = field(default_factory=set)
    failed_snapshot_count: int = 0
    scanned_count: int = 0
    matched_count: int = 0
    confirmed_count: int = 0
    near_entry_count: int = 0
    watch_count: int = 0
    avoid_count: int = 0
    evaluated_count: int = 0
    pending_count: int = 0
    outcomes: list[TradeOutcome] = field(default_factory=list)

    def as_dict(self, target_profit_pct: float) -> dict[str, Any]:
        confirmed_result = _signal_group_stats(
            outcomes=self.outcomes,
            states=CONFIRMED_STATES,
            target_profit_pct=target_profit_pct,
        )
        near_entry_result = _signal_group_stats(
            outcomes=self.outcomes,
            states={NEAR_ENTRY_STATE},
            target_profit_pct=target_profit_pct,
        )
        total_result = _signal_group_stats(
            outcomes=self.outcomes,
            states=EVALUATED_STATES,
            target_profit_pct=target_profit_pct,
        )
        return {
            "strategy_key": self.strategy_key,
            "strategy_title": self.strategy_title,
            "strategy_family": self.strategy_family,
            "strategy_family_text": self.strategy_family_text,
            "snapshot_count": self.snapshot_count,
            "snapshot_start": min(self.snapshot_dates) if self.snapshot_dates else "",
            "snapshot_end": max(self.snapshot_dates) if self.snapshot_dates else "",
            "failed_snapshot_count": self.failed_snapshot_count,
            "scanned_count": self.scanned_count,
            "matched_count": self.matched_count,
            "confirmed_count": self.confirmed_count,
            "near_entry_count": self.near_entry_count,
            "watch_count": self.watch_count,
            "avoid_count": self.avoid_count,
            "evaluated_count": self.evaluated_count,
            "pending_count": self.pending_count,
            "confirmed_result": confirmed_result,
            "near_entry_result": near_entry_result,
            "total_evaluated_result": total_result,
            "hit_count": confirmed_result["hit_count"],
            "hit_rate": confirmed_result["hit_rate"],
            "win_rate_1d": confirmed_result["win_rate_1d"],
            "win_rate_2d": confirmed_result["win_rate_2d"],
            "win_rate_3d": confirmed_result["win_rate_3d"],
            "win_rate_4d": confirmed_result["win_rate_4d"],
            "win_rate_5d": confirmed_result["win_rate_5d"],
            "avg_return_1d": confirmed_result["avg_return_1d"],
            "avg_return_2d": confirmed_result["avg_return_2d"],
            "avg_return_3d": confirmed_result["avg_return_3d"],
            "avg_return_4d": confirmed_result["avg_return_4d"],
            "avg_return_5d": confirmed_result["avg_return_5d"],
            "median_return_5d": confirmed_result["median_return_5d"],
            "avg_max_gain_5d": confirmed_result["avg_max_gain_5d"],
            "avg_max_drawdown_5d": confirmed_result["avg_max_drawdown_5d"],
            "profit_factor_5d": confirmed_result["profit_factor_5d"],
            "sample_quality": _sample_quality(self.evaluated_count),
            "conclusion": _strategy_conclusion(
                evaluated_count=confirmed_result["evaluated_count"],
                hit_rate=confirmed_result["net_win_rate"],
                avg_return_5d=confirmed_result["avg_net_return_pct"],
                avg_max_drawdown_5d=confirmed_result["avg_max_drawdown_5d"],
            ),
        }


def build_report(
    *,
    universe_count: int,
    latest_completed: str,
    evaluation_dates: list[str],
    target_profit_pct: float,
    scan_limit: int,
    months: int,
    materialization_mode: str,
    stats: list[StrategyBacktestStats],
) -> dict[str, Any]:
    strategy_rows = [item.as_dict(target_profit_pct=target_profit_pct) for item in stats]
    family_rows = _build_family_rows(stats=stats, target_profit_pct=target_profit_pct)
    all_outcomes = [outcome for item in stats for outcome in item.outcomes]
    snapshot_dates = sorted({trade_date for item in stats for trade_date in item.snapshot_dates})
    materialized_snapshot_count = sum(item.snapshot_count for item in stats)
    expected_snapshot_count = len(evaluation_dates) * len(stats)
    summary = _summary_stats(
        outcomes=all_outcomes,
        target_profit_pct=target_profit_pct,
        scanned_count=sum(item.scanned_count for item in stats),
        matched_count=sum(item.matched_count for item in stats),
        confirmed_count=sum(item.confirmed_count for item in stats),
        near_entry_count=sum(item.near_entry_count for item in stats),
        pending_count=sum(item.pending_count for item in stats),
    )
    summary.update(
        {
            "universe_count": universe_count,
            "evaluation_start": evaluation_dates[0] if evaluation_dates else "",
            "evaluation_end": evaluation_dates[-1] if evaluation_dates else "",
            "evaluation_trade_days": len(evaluation_dates),
            "snapshot_start": snapshot_dates[0] if snapshot_dates else "",
            "snapshot_end": snapshot_dates[-1] if snapshot_dates else "",
            "snapshot_trade_days": len(snapshot_dates),
            "latest_completed_trade_date": latest_completed,
            "scan_limit_per_day": scan_limit,
            "backtest_window_months": months,
            "materialization_mode": materialization_mode,
            "completed_snapshot_count": materialized_snapshot_count,
            "completed_snapshot_coverage_pct": _pct(materialized_snapshot_count, expected_snapshot_count),
            "materialized_snapshot_count": materialized_snapshot_count,
            "failed_snapshot_count": sum(item.failed_snapshot_count for item in stats),
            "expected_snapshot_count": expected_snapshot_count,
            "materialized_snapshot_coverage_pct": _pct(materialized_snapshot_count, expected_snapshot_count),
        }
    )
    return {
        "title": f"低吸策略近 {months} 个月 A 股全市场回测",
        "methodology": [
            "股票池使用 A 股全市场清单计数，策略实际候选由全市场近期涨停/强势结构筛出。",
            "确定买入统计 buy_now / soft_buy_now；接近买点单独统计 near_entry，两类都输出 1/2/3/5 日结果。",
            "真实执行指标按信号后 2 日触达买点、止损/止盈/移动防守退出，并扣除 16bps 成本计算。",
            f"冲高命中按买入后 {PERFORMANCE_FORWARD_DAYS} 个交易日内最高价达到 {target_profit_pct:.1f}% 计算，仅作为辅助观察。",
            "1/2/3/5 日收益按触发日参考入场价到后续收盘价计算，用于持股周期观察。",
            "接近买点样本按买点区参考价估算结果，用于观察信号质量，不等同已经触发买入。",
            f"快照模式：{_materialization_mode_text(materialization_mode)}。",
        ],
        "summary": summary,
        "families": family_rows,
        "strategies": strategy_rows,
        "top_examples": _top_examples(all_outcomes),
    }


def history_window_days(months: int, forward_days: int) -> int:
    return max(260, months * 31 + forward_days + 80)


def _build_family_rows(
    *,
    stats: list[StrategyBacktestStats],
    target_profit_pct: float,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[StrategyBacktestStats]] = {}
    for item in stats:
        grouped.setdefault(item.strategy_family, []).append(item)
    rows: list[dict[str, Any]] = []
    for family_key, family_stats in grouped.items():
        outcomes = [outcome for item in family_stats for outcome in item.outcomes]
        confirmed_result = _signal_group_stats(
            outcomes=outcomes,
            states=CONFIRMED_STATES,
            target_profit_pct=target_profit_pct,
        )
        near_entry_result = _signal_group_stats(
            outcomes=outcomes,
            states={NEAR_ENTRY_STATE},
            target_profit_pct=target_profit_pct,
        )
        total_result = _signal_group_stats(
            outcomes=outcomes,
            states=EVALUATED_STATES,
            target_profit_pct=target_profit_pct,
        )
        family_text = family_stats[0].strategy_family_text if family_stats else resolve_strategy_family_label(family_key)
        rows.append(
            {
                "strategy_family": family_key,
                "strategy_family_text": family_text,
                "strategy_count": len(family_stats),
                "strategy_titles": [item.strategy_title for item in family_stats],
                "snapshot_count": sum(item.snapshot_count for item in family_stats),
                "failed_snapshot_count": sum(item.failed_snapshot_count for item in family_stats),
                "scanned_count": sum(item.scanned_count for item in family_stats),
                "matched_count": sum(item.matched_count for item in family_stats),
                "confirmed_count": sum(item.confirmed_count for item in family_stats),
                "near_entry_count": sum(item.near_entry_count for item in family_stats),
                "evaluated_count": sum(item.evaluated_count for item in family_stats),
                "pending_count": sum(item.pending_count for item in family_stats),
                "confirmed_result": confirmed_result,
                "near_entry_result": near_entry_result,
                "total_evaluated_result": total_result,
                "conclusion": _strategy_conclusion(
                    confirmed_result["evaluated_count"],
                    confirmed_result["net_win_rate"],
                    confirmed_result["avg_net_return_pct"],
                    confirmed_result["avg_max_drawdown_5d"],
                ),
            }
        )
    rows.sort(
        key=lambda item: (
            item["confirmed_result"]["filled_count"],
            item["confirmed_result"]["net_win_rate"],
            item["confirmed_result"]["avg_net_return_pct"],
        ),
        reverse=True,
    )
    return rows


def _summary_stats(
    *,
    outcomes: list[TradeOutcome],
    target_profit_pct: float,
    scanned_count: int,
    matched_count: int,
    confirmed_count: int,
    near_entry_count: int,
    pending_count: int,
) -> dict[str, Any]:
    evaluated = len(outcomes)
    confirmed_result = _signal_group_stats(
        outcomes=outcomes,
        states=CONFIRMED_STATES,
        target_profit_pct=target_profit_pct,
    )
    near_entry_result = _signal_group_stats(
        outcomes=outcomes,
        states={NEAR_ENTRY_STATE},
        target_profit_pct=target_profit_pct,
    )
    total_result = _signal_group_stats(
        outcomes=outcomes,
        states=EVALUATED_STATES,
        target_profit_pct=target_profit_pct,
    )
    return {
        "scanned_count": scanned_count,
        "matched_count": matched_count,
        "confirmed_count": confirmed_count,
        "near_entry_count": near_entry_count,
        "evaluated_count": evaluated,
        "pending_count": pending_count,
        "confirmed_result": confirmed_result,
        "near_entry_result": near_entry_result,
        "total_evaluated_result": total_result,
        "filled_count": confirmed_result["filled_count"],
        "not_filled_rate": confirmed_result["not_filled_rate"],
        "net_win_rate": confirmed_result["net_win_rate"],
        "avg_net_return_pct": confirmed_result["avg_net_return_pct"],
        "stop_loss_rate": confirmed_result["stop_loss_rate"],
        "hit_count": confirmed_result["hit_count"],
        "hit_rate": confirmed_result["hit_rate"],
        "t1_high_3_hit_rate": confirmed_result["t1_high_3_hit_rate"],
        "t1_high_5_hit_rate": confirmed_result["t1_high_5_hit_rate"],
        "t1_fade_to_entry_rate": confirmed_result["t1_fade_to_entry_rate"],
        "avg_t1_high_return_pct": confirmed_result["avg_t1_high_return_pct"],
        "avg_t1_close_return_pct": confirmed_result["avg_t1_close_return_pct"],
        "avg_t1_spike_fade_pct": confirmed_result["avg_t1_spike_fade_pct"],
        "avg_t2_high_return_pct": confirmed_result["avg_t2_high_return_pct"],
        "avg_t2_close_return_pct": confirmed_result["avg_t2_close_return_pct"],
        "win_rate_1d": confirmed_result["win_rate_1d"],
        "win_rate_2d": confirmed_result["win_rate_2d"],
        "win_rate_3d": confirmed_result["win_rate_3d"],
        "win_rate_4d": confirmed_result["win_rate_4d"],
        "win_rate_5d": confirmed_result["win_rate_5d"],
        "avg_return_1d": confirmed_result["avg_return_1d"],
        "avg_return_2d": confirmed_result["avg_return_2d"],
        "avg_return_3d": confirmed_result["avg_return_3d"],
        "avg_return_4d": confirmed_result["avg_return_4d"],
        "avg_return_5d": confirmed_result["avg_return_5d"],
        "median_return_5d": confirmed_result["median_return_5d"],
        "avg_max_gain_5d": confirmed_result["avg_max_gain_5d"],
        "avg_max_drawdown_5d": confirmed_result["avg_max_drawdown_5d"],
        "profit_factor_5d": confirmed_result["profit_factor_5d"],
        "sample_quality": _sample_quality(evaluated),
        "conclusion": _strategy_conclusion(
            confirmed_result["evaluated_count"],
            confirmed_result["net_win_rate"],
            confirmed_result["avg_net_return_pct"],
            confirmed_result["avg_max_drawdown_5d"],
        ),
    }


def _signal_group_stats(
    *,
    outcomes: list[TradeOutcome],
    states: set[str],
    target_profit_pct: float,
) -> dict[str, Any]:
    scoped = [item for item in outcomes if item.buy_signal_state in states]
    evaluated = len(scoped)
    returns_1d = [item.return_1d for item in scoped]
    returns_2d = [item.return_2d for item in scoped]
    returns_3d = [item.return_3d for item in scoped]
    returns_4d = [item.return_4d for item in scoped]
    returns_5d = [item.return_5d for item in scoped]
    gains_5d = [item.max_gain_5d for item in scoped]
    drawdowns_5d = [item.max_drawdown_5d for item in scoped]
    t1_high_returns = [item.t1_high_return_pct for item in scoped]
    t1_close_returns = [item.t1_close_return_pct for item in scoped]
    t1_spike_fades = [item.t1_spike_fade_pct for item in scoped]
    t2_high_returns = [item.t2_high_return_pct for item in scoped]
    t2_close_returns = [item.t2_close_return_pct for item in scoped]
    wins_5d = [value for value in returns_5d if value > 0]
    losses_5d = [abs(value) for value in returns_5d if value < 0]
    filled = [item for item in scoped if item.execution_status == "filled"]
    not_filled = [item for item in scoped if item.execution_status == "not_filled"]
    net_winners = [item for item in filled if item.net_return_pct > 0]
    net_wins = [item.net_return_pct for item in net_winners]
    net_losses = [abs(item.net_return_pct) for item in filled if item.net_return_pct < 0]
    stop_losses = [item for item in filled if "止损" in item.execution_exit_reason]
    hit_count = sum(1 for item in scoped if item.max_gain_5d >= target_profit_pct)
    return {
        "label": _signal_group_label(states),
        "states": sorted(states),
        "evaluated_count": evaluated,
        "filled_count": len(filled),
        "not_filled_count": len(not_filled),
        "not_filled_rate": _pct(len(not_filled), evaluated),
        "net_win_rate": _pct(len(net_winners), len(filled)),
        "avg_net_return_pct": _avg([item.net_return_pct for item in filled]),
        "stop_loss_rate": _pct(len(stop_losses), len(filled)),
        "execution_profit_factor": _profit_factor(net_wins, net_losses),
        "hit_count": hit_count,
        "hit_rate": _pct(hit_count, evaluated),
        "win_rate_1d": _pct(sum(1 for value in returns_1d if value > 0), evaluated),
        "win_rate_2d": _pct(sum(1 for value in returns_2d if value > 0), evaluated),
        "win_rate_3d": _pct(sum(1 for value in returns_3d if value > 0), evaluated),
        "win_rate_4d": _pct(sum(1 for value in returns_4d if value > 0), evaluated),
        "win_rate_5d": _pct(len(wins_5d), evaluated),
        "avg_return_1d": _avg(returns_1d),
        "avg_return_2d": _avg(returns_2d),
        "avg_return_3d": _avg(returns_3d),
        "avg_return_4d": _avg(returns_4d),
        "avg_return_5d": _avg(returns_5d),
        "median_return_5d": _median(returns_5d),
        "avg_max_gain_5d": _avg(gains_5d),
        "avg_max_drawdown_5d": _avg(drawdowns_5d),
        "t1_high_3_hit_rate": _pct(sum(1 for item in scoped if item.t1_hit_3_pct), evaluated),
        "t1_high_5_hit_rate": _pct(sum(1 for item in scoped if item.t1_hit_5_pct), evaluated),
        "t1_fade_to_entry_rate": _pct(sum(1 for item in scoped if item.t1_fade_to_entry), evaluated),
        "avg_t1_high_return_pct": _avg(t1_high_returns),
        "avg_t1_close_return_pct": _avg(t1_close_returns),
        "avg_t1_spike_fade_pct": _avg(t1_spike_fades),
        "avg_t2_high_return_pct": _avg(t2_high_returns),
        "avg_t2_close_return_pct": _avg(t2_close_returns),
        "profit_factor_5d": _profit_factor(wins_5d, losses_5d),
    }


def _signal_group_label(states: set[str]) -> str:
    for label, group_states in SIGNAL_GROUPS.values():
        if states == group_states:
            return label
    return "合计"


def _top_examples(outcomes: list[TradeOutcome], limit: int = 20) -> list[dict[str, Any]]:
    ordered = sorted(outcomes, key=lambda item: item.max_gain_5d, reverse=True)
    return [item.__dict__ for item in ordered[:limit]]


def _strategy_conclusion(
    evaluated_count: int,
    hit_rate: float,
    avg_return_5d: float,
    avg_max_drawdown_5d: float,
) -> str:
    if evaluated_count < 30:
        return "样本不足，只能作为观察结论。"
    if avg_return_5d > 0.8 and hit_rate >= 50 and avg_max_drawdown_5d > -5.5:
        return "阶段可行，适合继续保留并用仓位控制执行。"
    if avg_return_5d > 0 and hit_rate >= 42:
        return "有一定可行性，但需要继续用市场状态和行业强弱过滤。"
    return "阶段表现不足，生产交易应降权或只保留观察。"


def _sample_quality(evaluated_count: int) -> str:
    if evaluated_count >= 100:
        return "高"
    if evaluated_count >= 30:
        return "中"
    return "低"


def _materialization_mode_text(mode: str) -> str:
    labels = {
        "isolated": "隔离计算，不写入线上物化结果表",
        "production": "写入线上物化结果表，仅用于明确需要回灌缓存的任务",
        "read-only": "只读取已有物化结果，不补算缺失日期",
    }
    return labels.get(mode, mode)


def _avg(values: list[float]) -> float:
    return round(mean(values), 4) if values else 0.0


def _median(values: list[float]) -> float:
    return round(median(values), 4) if values else 0.0


def _pct(part: int, total: int) -> float:
    return round(part / total * 100, 2) if total else 0.0


def _profit_factor(wins: list[float], losses: list[float]) -> float:
    if not losses:
        return round(float(bool(wins)), 4)
    value = sum(wins) / sum(losses)
    return round(value if math.isfinite(value) else 0.0, 4)


try:
    from .low_buy_market_backtest_markdown import render_markdown_report
except ImportError:
    from low_buy_market_backtest_markdown import render_markdown_report
