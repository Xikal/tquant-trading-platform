from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import math
from typing import Any

from app.services.low_buy.shared import PERFORMANCE_FORWARD_DAYS
from app.services.low_buy.strategy_families import resolve_strategy_family_label

try:
    from .low_buy_market_backtest_signal_stats import (
        CONFIRMED_STATES,
        EVALUATED_STATES,
        NEAR_ENTRY_STATE,
        OBSERVE_CONFIRMED_STATE,
        conclusion_source,
        pct,
        profit_factor,
        signal_group_stats,
    )
except ImportError:
    from low_buy_market_backtest_signal_stats import (
        CONFIRMED_STATES,
        EVALUATED_STATES,
        NEAR_ENTRY_STATE,
        OBSERVE_CONFIRMED_STATE,
        conclusion_source,
        pct,
        profit_factor,
        signal_group_stats,
    )


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
    spike_return_1d: float = 0.0
    spike_return_2d: float = 0.0
    spike_return_3d: float = 0.0
    spike_return_4d: float = 0.0
    spike_return_5d: float = 0.0
    t1_high_return_pct: float = 0.0
    t1_close_return_pct: float = 0.0
    t1_spike_fade_pct: float = 0.0
    t2_high_return_pct: float = 0.0
    t2_close_return_pct: float = 0.0
    t1_hit_3_pct: bool = False
    t1_hit_5_pct: bool = False
    t1_fade_to_entry: bool = False
    entry_trade_date: str = ""
    exit_trade_date: str = ""
    market_state: str = ""
    market_state_text: str = ""
    market_state_category: str = ""
    market_state_strength: float = 0.0


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
    observe_confirmed_count: int = 0
    near_entry_count: int = 0
    watch_count: int = 0
    avoid_count: int = 0
    evaluated_count: int = 0
    pending_count: int = 0
    outcomes: list[TradeOutcome] = field(default_factory=list)
    signal_state_counts: dict[str, int] = field(default_factory=dict)
    skipped_by_state_count: int = 0
    skipped_by_state_counts: dict[str, int] = field(default_factory=dict)
    pending_reason_counts: dict[str, int] = field(default_factory=dict)
    market_guard_count: int = 0
    market_guard_counts: dict[str, int] = field(default_factory=dict)

    def record_signal_state(self, state: str) -> None:
        key = str(state or "unknown")
        self.signal_state_counts[key] = self.signal_state_counts.get(key, 0) + 1

    def record_skipped_state(self, state: str) -> None:
        key = str(state or "unknown")
        self.skipped_by_state_count += 1
        self.skipped_by_state_counts[key] = self.skipped_by_state_counts.get(key, 0) + 1

    def record_pending_reason(self, reason: str) -> None:
        key = str(reason or "unknown")
        self.pending_reason_counts[key] = self.pending_reason_counts.get(key, 0) + 1

    def record_market_guard(self, reason: str) -> None:
        key = str(reason or "unknown")
        self.market_guard_count += 1
        self.market_guard_counts[key] = self.market_guard_counts.get(key, 0) + 1

    def as_dict(self, target_profit_pct: float, selected_states: set[str] | None = None) -> dict[str, Any]:
        confirmed_result = signal_group_stats(
            outcomes=self.outcomes,
            states=CONFIRMED_STATES,
            target_profit_pct=target_profit_pct,
        )
        near_entry_result = signal_group_stats(
            outcomes=self.outcomes,
            states={NEAR_ENTRY_STATE},
            target_profit_pct=target_profit_pct,
        )
        observe_confirmed_result = signal_group_stats(
            outcomes=self.outcomes,
            states={OBSERVE_CONFIRMED_STATE},
            target_profit_pct=target_profit_pct,
        )
        backtest_metrics = backtest_performance_metrics(self.outcomes)
        conclusion_result = conclusion_source(confirmed_result, observe_confirmed_result, near_entry_result)
        selected = selected_states or EVALUATED_STATES
        total_result = signal_group_stats(
            outcomes=self.outcomes,
            states=selected,
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
            "observe_confirmed_count": self.observe_confirmed_count,
            "near_entry_count": self.near_entry_count,
            "watch_count": self.watch_count,
            "avoid_count": self.avoid_count,
            "evaluated_count": self.evaluated_count,
            "pending_count": self.pending_count,
            "selected_signal_states": sorted(selected),
            "signal_state_counts": _sorted_counts(self.signal_state_counts),
            "evaluation_diagnostics": {
                "selected_signal_states": sorted(selected),
                "skipped_by_state_count": self.skipped_by_state_count,
                "skipped_by_state_counts": _sorted_counts(self.skipped_by_state_counts),
                "pending_reason_counts": _sorted_counts(self.pending_reason_counts),
                "market_guard_count": self.market_guard_count,
                "market_guard_counts": _sorted_counts(self.market_guard_counts),
                "not_filled_reason_counts": _reason_counts(
                    self.outcomes,
                    status="not_filled",
                    field="execution_exit_reason",
                ),
                "filled_exit_reason_counts": _reason_counts(
                    self.outcomes,
                    status="filled",
                    field="execution_exit_reason",
                ),
            },
            "confirmed_result": confirmed_result,
            "observe_confirmed_result": observe_confirmed_result,
            "near_entry_result": near_entry_result,
            "total_evaluated_result": total_result,
            "backtest_metrics": backtest_metrics,
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
                evaluated_count=conclusion_result["evaluated_count"],
                hit_rate=conclusion_result["net_win_rate"],
                avg_return_5d=conclusion_result["avg_net_return_pct"],
                avg_max_drawdown_5d=conclusion_result["avg_max_drawdown_5d"],
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
    requested_start: str = "",
    requested_end: str = "",
    selected_states: set[str] | None = None,
    execution_model_label: str = "candidate_exit_plan",
    market_guard_label: str = "none",
    prefilter_override_label: str = "none",
) -> dict[str, Any]:
    selected = selected_states or EVALUATED_STATES
    strategy_rows = [item.as_dict(target_profit_pct=target_profit_pct, selected_states=selected) for item in stats]
    family_rows = _build_family_rows(stats=stats, target_profit_pct=target_profit_pct, selected_states=selected)
    all_outcomes = [outcome for item in stats for outcome in item.outcomes]
    snapshot_dates = sorted({trade_date for item in stats for trade_date in item.snapshot_dates})
    materialized_snapshot_count = sum(item.snapshot_count for item in stats)
    expected_snapshot_count = len(evaluation_dates) * len(stats)
    summary = _summary_stats(
        outcomes=all_outcomes,
        target_profit_pct=target_profit_pct,
        selected_states=selected,
        scanned_count=sum(item.scanned_count for item in stats),
        matched_count=sum(item.matched_count for item in stats),
        confirmed_count=sum(item.confirmed_count for item in stats),
        observe_confirmed_count=sum(item.observe_confirmed_count for item in stats),
        near_entry_count=sum(item.near_entry_count for item in stats),
        pending_count=sum(item.pending_count for item in stats),
    )
    summary["backtest_metrics"] = backtest_performance_metrics(all_outcomes)
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
            "requested_start": requested_start,
            "requested_end": requested_end,
            "selected_signal_states": sorted(selected),
            "execution_model": execution_model_label,
            "market_guard": market_guard_label,
            "prefilter_overrides": prefilter_override_label,
            "signal_state_counts": _merge_count_dicts(item.signal_state_counts for item in stats),
            "skipped_by_state_count": sum(item.skipped_by_state_count for item in stats),
            "skipped_by_state_counts": _merge_count_dicts(item.skipped_by_state_counts for item in stats),
            "pending_reason_counts": _merge_count_dicts(item.pending_reason_counts for item in stats),
            "market_guard_count": sum(item.market_guard_count for item in stats),
            "market_guard_counts": _merge_count_dicts(item.market_guard_counts for item in stats),
            "not_filled_reason_counts": _reason_counts(
                all_outcomes,
                status="not_filled",
                field="execution_exit_reason",
            ),
            "filled_exit_reason_counts": _reason_counts(
                all_outcomes,
                status="filled",
                field="execution_exit_reason",
            ),
            "data_coverage": data_coverage_summary(
                requested_months=months,
                evaluation_dates=evaluation_dates,
                requested_start=requested_start,
                requested_end=requested_end,
            ),
            "materialization_mode": materialization_mode,
            "completed_snapshot_count": materialized_snapshot_count,
            "completed_snapshot_coverage_pct": pct(materialized_snapshot_count, expected_snapshot_count),
            "materialized_snapshot_count": materialized_snapshot_count,
            "failed_snapshot_count": sum(item.failed_snapshot_count for item in stats),
            "expected_snapshot_count": expected_snapshot_count,
            "materialized_snapshot_coverage_pct": pct(materialized_snapshot_count, expected_snapshot_count),
        }
    )
    return {
        "title": f"低吸策略近 {months} 个月 A 股全市场回测",
        "methodology": [
            "股票池使用 A 股全市场清单计数，策略实际候选由全市场近期涨停/强势结构筛出。",
            "确定买入统计 buy_now / soft_buy_now；观察确认单独统计 observe_confirmed；接近买点单独统计 near_entry，均输出 1/2/3/4/5 日结果。",
            "真实执行指标按信号后 2 日触达买点、止损/止盈/移动防守退出，并扣除 16bps 成本计算。",
            f"冲高命中按买入后 {PERFORMANCE_FORWARD_DAYS} 个交易日内最高价达到 {target_profit_pct:.1f}% 计算，仅作为辅助观察。",
            "1/2/3/4/5 日收益按触发日参考入场价到后续收盘价计算，用于持股周期观察，并按平均收益给出最佳持股天数。",
            "接近买点样本按买点区参考价估算结果，用于观察信号质量，不等同已经触发买入。",
            f"快照模式：{_materialization_mode_text(materialization_mode)}。",
            f"执行模型：{execution_model_label}。",
            f"市场保护研究模型：{market_guard_label}。",
            f"预筛参数研究覆盖：{prefilter_override_label}。",
        ],
        "summary": summary,
        "families": family_rows,
        "strategies": strategy_rows,
        "top_examples": _top_examples(all_outcomes),
    }


def data_coverage_summary(
    *,
    requested_months: int,
    evaluation_dates: list[str],
    requested_start: str = "",
    requested_end: str = "",
) -> dict[str, Any]:
    if not evaluation_dates:
        return {
            "requested_months": requested_months,
            "requested_start": requested_start,
            "requested_end": requested_end,
            "actual_start": "",
            "actual_end": "",
            "actual_calendar_days": 0,
            "actual_months_estimate": 0.0,
            "coverage_pct": 0.0,
            "status": "empty",
            "warning": "没有可评估交易日，不能作为策略验收证据。",
        }
    start = date.fromisoformat(evaluation_dates[0])
    end = date.fromisoformat(evaluation_dates[-1])
    actual_days = max((end - start).days + 1, 1)
    requested_days = max(int(requested_months or 0) * 31, 1)
    coverage = round(min(actual_days / requested_days * 100.0, 100.0), 2)
    status = "complete" if coverage >= 90.0 else "partial"
    warning = "" if status == "complete" else "本地可评估数据不足请求窗口，报告只能作为部分区间基线，不能替代完整 24 个月验收。"
    return {
        "requested_months": requested_months,
        "requested_start": requested_start,
        "requested_end": requested_end,
        "actual_start": evaluation_dates[0],
        "actual_end": evaluation_dates[-1],
        "actual_calendar_days": actual_days,
        "actual_months_estimate": round(actual_days / 31.0, 2),
        "coverage_pct": coverage,
        "status": status,
        "warning": warning,
    }


def history_window_days(months: int, forward_days: int) -> int:
    return max(260, months * 31 + forward_days + 80)


def _build_family_rows(
    *,
    stats: list[StrategyBacktestStats],
    target_profit_pct: float,
    selected_states: set[str],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[StrategyBacktestStats]] = {}
    for item in stats:
        grouped.setdefault(item.strategy_family, []).append(item)
    rows: list[dict[str, Any]] = []
    for family_key, family_stats in grouped.items():
        outcomes = [outcome for item in family_stats for outcome in item.outcomes]
        confirmed_result = signal_group_stats(
            outcomes=outcomes,
            states=CONFIRMED_STATES,
            target_profit_pct=target_profit_pct,
        )
        near_entry_result = signal_group_stats(
            outcomes=outcomes,
            states={NEAR_ENTRY_STATE},
            target_profit_pct=target_profit_pct,
        )
        observe_confirmed_result = signal_group_stats(
            outcomes=outcomes,
            states={OBSERVE_CONFIRMED_STATE},
            target_profit_pct=target_profit_pct,
        )
        total_result = signal_group_stats(
            outcomes=outcomes,
            states=selected_states,
            target_profit_pct=target_profit_pct,
        )
        conclusion_result = conclusion_source(confirmed_result, observe_confirmed_result, near_entry_result)
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
                "observe_confirmed_count": sum(item.observe_confirmed_count for item in family_stats),
                "near_entry_count": sum(item.near_entry_count for item in family_stats),
                "evaluated_count": sum(item.evaluated_count for item in family_stats),
                "pending_count": sum(item.pending_count for item in family_stats),
                "confirmed_result": confirmed_result,
                "observe_confirmed_result": observe_confirmed_result,
                "near_entry_result": near_entry_result,
                "total_evaluated_result": total_result,
                "conclusion": _strategy_conclusion(
                    conclusion_result["evaluated_count"],
                    conclusion_result["net_win_rate"],
                    conclusion_result["avg_net_return_pct"],
                    conclusion_result["avg_max_drawdown_5d"],
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
    selected_states: set[str],
    scanned_count: int,
    matched_count: int,
    confirmed_count: int,
    observe_confirmed_count: int,
    near_entry_count: int,
    pending_count: int,
) -> dict[str, Any]:
    evaluated = len(outcomes)
    confirmed_result = signal_group_stats(
        outcomes=outcomes,
        states=CONFIRMED_STATES,
        target_profit_pct=target_profit_pct,
    )
    near_entry_result = signal_group_stats(
        outcomes=outcomes,
        states={NEAR_ENTRY_STATE},
        target_profit_pct=target_profit_pct,
    )
    observe_confirmed_result = signal_group_stats(
        outcomes=outcomes,
        states={OBSERVE_CONFIRMED_STATE},
        target_profit_pct=target_profit_pct,
    )
    total_result = signal_group_stats(
        outcomes=outcomes,
        states=selected_states,
        target_profit_pct=target_profit_pct,
    )
    conclusion_result = conclusion_source(confirmed_result, observe_confirmed_result, near_entry_result)
    return {
        "scanned_count": scanned_count,
        "matched_count": matched_count,
        "confirmed_count": confirmed_count,
        "observe_confirmed_count": observe_confirmed_count,
        "near_entry_count": near_entry_count,
        "evaluated_count": evaluated,
        "pending_count": pending_count,
        "confirmed_result": confirmed_result,
        "observe_confirmed_result": observe_confirmed_result,
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
            conclusion_result["evaluated_count"],
            conclusion_result["net_win_rate"],
            conclusion_result["avg_net_return_pct"],
            conclusion_result["avg_max_drawdown_5d"],
        ),
    }


def _merge_count_dicts(rows: Any) -> dict[str, int]:
    merged: dict[str, int] = {}
    for row in rows:
        for key, value in dict(row or {}).items():
            merged[str(key)] = merged.get(str(key), 0) + int(value or 0)
    return _sorted_counts(merged)


def _sorted_counts(values: dict[str, int]) -> dict[str, int]:
    return {
        key: int(count)
        for key, count in sorted(values.items(), key=lambda item: (-int(item[1] or 0), str(item[0])))
    }


def _reason_counts(
    outcomes: list[TradeOutcome],
    *,
    status: str,
    field: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in outcomes:
        if item.execution_status != status:
            continue
        reason = str(getattr(item, field, "") or "未标注原因")
        counts[reason] = counts.get(reason, 0) + 1
    return _sorted_counts(counts)


def backtest_performance_metrics(outcomes: list[TradeOutcome], states: set[str] | None = None) -> dict[str, Any]:
    scoped = [item for item in outcomes if states is None or item.buy_signal_state in states]
    filled = [item for item in scoped if item.execution_status == "filled"]
    returns = [float(item.net_return_pct or 0.0) for item in filled]
    equity_curve = _equity_curve(returns)
    drawdown = _drawdown_stats(equity_curve)
    holding_days = [_holding_days(item) for item in filled if _holding_days(item) > 0]
    wins = [value for value in returns if value > 0]
    losses = [abs(value) for value in returns if value < 0]
    total_return = round((equity_curve[-1] - 1.0) * 100, 4) if equity_curve else 0.0
    annualized = _annualized_return(total_return, filled)
    sharpe = _sharpe_ratio(returns)
    return {
        "trade_count": len(filled),
        "evaluated_count": len(scoped),
        "total_return_pct": total_return,
        "annualized_return_pct": annualized,
        "max_drawdown_pct": drawdown["max_drawdown_pct"],
        "drawdown_recovery_trades": drawdown["drawdown_recovery_trades"],
        "drawdown_recovery_status": drawdown["drawdown_recovery_status"],
        "sharpe_ratio": sharpe,
        "win_rate_pct": pct(len(wins), len(filled)),
        "profit_loss_ratio": round((sum(wins) / len(wins)) / (sum(losses) / len(losses)), 4) if wins and losses else 0.0,
        "profit_factor": profit_factor(wins, losses),
        "avg_holding_days": round(sum(holding_days) / len(holding_days), 2) if holding_days else 0.0,
        "median_holding_days": _median_float(holding_days),
    }


def _equity_curve(returns_pct: list[float]) -> list[float]:
    equity = 1.0
    curve: list[float] = []
    for value in returns_pct:
        equity *= max(0.0, 1.0 + value / 100.0)
        curve.append(equity)
    return curve


def _drawdown_stats(equity_curve: list[float]) -> dict[str, Any]:
    if not equity_curve:
        return {"max_drawdown_pct": 0.0, "drawdown_recovery_trades": 0, "drawdown_recovery_status": "无成交"}
    peak = 1.0
    peak_index = 0
    max_drawdown = 0.0
    trough_index = 0
    recovery_trades = 0
    recovered = True
    for index, equity in enumerate(equity_curve):
        if equity > peak:
            peak = equity
            peak_index = index
        drawdown = equity / max(peak, 0.000001) - 1.0
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            trough_index = index
            recovered = False
            recovery_trades = 0
        elif not recovered and equity >= peak:
            recovered = True
            recovery_trades = index - trough_index
    if max_drawdown == 0.0:
        status = "未发生回撤"
    elif recovered:
        status = f"最大回撤后 {recovery_trades} 笔交易恢复"
    else:
        status = "截至回测结束尚未恢复最大回撤"
        recovery_trades = len(equity_curve) - trough_index - 1
    return {
        "max_drawdown_pct": round(max_drawdown * 100, 4),
        "drawdown_recovery_trades": recovery_trades,
        "drawdown_recovery_status": status,
        "peak_trade_index": peak_index,
        "trough_trade_index": trough_index,
    }


def _annualized_return(total_return_pct: float, filled: list[TradeOutcome]) -> float:
    dates = sorted({item.signal_date for item in filled if item.signal_date})
    if len(dates) < 2:
        return 0.0
    try:
        start = date.fromisoformat(dates[0])
        end = date.fromisoformat(dates[-1])
    except ValueError:
        return 0.0
    days = max((end - start).days, 1)
    total_multiple = max(0.0, 1.0 + total_return_pct / 100.0)
    if total_multiple <= 0:
        return -100.0
    return round((total_multiple ** (365.0 / days) - 1.0) * 100.0, 4)


def _sharpe_ratio(returns_pct: list[float]) -> float:
    if len(returns_pct) < 2:
        return 0.0
    mean_value = sum(returns_pct) / len(returns_pct)
    variance = sum((value - mean_value) ** 2 for value in returns_pct) / (len(returns_pct) - 1)
    stddev = math.sqrt(variance)
    if stddev <= 0:
        return 0.0
    return round((mean_value / stddev) * math.sqrt(252), 4)


def _holding_days(item: TradeOutcome) -> int:
    if not item.entry_trade_date or not item.exit_trade_date:
        return 0
    try:
        return max((date.fromisoformat(item.exit_trade_date) - date.fromisoformat(item.entry_trade_date)).days, 0)
    except ValueError:
        return 0


def _median_float(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return round((ordered[mid - 1] + ordered[mid]) / 2.0, 2)


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


try:
    from .low_buy_market_backtest_markdown import render_markdown_report
except ImportError:
    from low_buy_market_backtest_markdown import render_markdown_report
