"""Signal diagnostics for the 24-month strategy review."""

from __future__ import annotations

from typing import Any


def buy_signal_diagnosis(
    *,
    strategy_key: str,
    layer: str,
    strong_buy_paused: bool,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    counts = metrics.get("signal_state_counts") or {}
    confirmed = metrics.get("confirmed_only_metrics") or {}
    confirmed_trades = int(confirmed.get("trade_count") or confirmed.get("evaluated_count") or 0)
    near_entry = int(counts.get("near_entry") or 0)
    watch = int(counts.get("watch") or 0)
    avoid = int(counts.get("avoid") or 0)
    blockers: list[str] = []
    if strong_buy_paused:
        blockers.append("strategy_layer_pauses_strong_buy")
    if confirmed_trades == 0:
        blockers.append("no_buy_now_or_soft_buy_now_samples")
    if confirmed_trades == 0 and (near_entry or watch):
        blockers.append("signals_are_observation_or_near_entry_only")
    if avoid and avoid >= near_entry + watch:
        blockers.append("avoid_signals_dominate_observation_pool")
    return {
        "strategy_key": strategy_key,
        "layer": layer,
        "strong_buy_paused": strong_buy_paused,
        "confirmed_trade_count": confirmed_trades,
        "near_entry_count": near_entry,
        "watch_count": watch,
        "avoid_count": avoid,
        "blockers": blockers,
        "production_buy_signal_ready": not blockers,
        "explanation": _explanation(layer, strong_buy_paused, confirmed_trades, near_entry, watch),
    }


def _explanation(
    layer: str,
    strong_buy_paused: bool,
    confirmed_trades: int,
    near_entry: int,
    watch: int,
) -> str:
    if strong_buy_paused:
        return "策略处于研究/因子层，强买入口被策略层级暂停。"
    if confirmed_trades == 0 and (near_entry or watch):
        return "只有接近买点或观察信号，未形成 buy_now/soft_buy_now 的确定买入样本。"
    if confirmed_trades == 0:
        return "未形成可成交的确定买入样本。"
    if layer != "production":
        return "虽有确认样本，但策略不在生产层，仍需 Shadow 和生产门禁。"
    return "已有确认样本，但仍需结合数据门禁、walk-forward 和 Shadow 决定能否生产。"
