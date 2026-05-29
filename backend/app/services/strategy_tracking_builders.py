from __future__ import annotations

from app.models.entities import LowBuyTradeLifecycleSnapshot
from app.models.schema_defs.strategy_tracking import (
    StrategyTrackingItemOut,
    StrategyTrackingMarkerOut,
    StrategyTrackingTimelinePointOut,
)
from app.repositories.low_buy import DailyBarRow
from app.services.finance.performance_math import sequence_max_drawdown_pct
from app.services.low_buy.strategy_policy import get_strategy_tier
from app.services.strategy_tracking_constants import (
    MISSING_SIGNAL_GRACE_DAYS,
    MAX_TRACKING_DAYS,
    PROFIT_TARGET_PCT,
    SIGNAL_LABELS,
    STATUS_LABELS,
)
from app.services.strategy_tracking_enhancements import (
    analyze_attribution,
    analyze_holding,
    audit_context,
    market_context,
)
from app.services.strategy_tracking_helpers import (
    attr_float,
    conclusion,
    data_quality_text,
    distance_to_entry,
    failure_reason,
    hit_entry,
    item_id,
    load_payload,
    missing_signal_days,
    number,
    pct,
    posterior_stats,
    resolve_data_quality,
    review_text,
    round_or_none,
    text,
)


def build_tracking_item(
    *,
    group,
    bars: list[DailyBarRow],
    lifecycle: LowBuyTradeLifecycleSnapshot | None,
    latest_bar_date: str,
    first_signal_date: str,
) -> StrategyTrackingItemOut:
    strategy_name = text(group.payload, "strategy_title", "strategy_name") or group.latest_row.strategy_key
    entry_low = number(group.payload, "entry_zone_low", "entry_low") or attr_float(lifecycle, "entry_plan_low")
    entry_high = number(group.payload, "entry_zone_high", "entry_high") or attr_float(lifecycle, "entry_plan_high")
    stop_loss = number(group.payload, "stop_loss") or attr_float(lifecycle, "stop_loss")
    target_price = number(group.payload, "take_profit", "target_price") or attr_float(lifecycle, "take_profit")
    first_payload, _ = load_payload(group.first_row)
    first_price = number(first_payload, "latest_price", "signal_price") or number(group.payload, "latest_price", "signal_price")
    posterior = [item for item in bars if item.trade_date > first_signal_date]
    stats = posterior_stats(
        posterior,
        reference_price=first_price,
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        target_price=target_price,
    )
    status = lifecycle_status(group=group, posterior=posterior, stats=stats, lifecycle=lifecycle)
    current_price = stats["current_price"]
    quality = resolve_data_quality(has_payload_error=bool(group.payload_error), bars=posterior, latest_bar_date=latest_bar_date)
    holding = analyze_holding(
        bars=bars,
        first_signal_date=first_signal_date,
        reference_price=first_price,
        stop_loss=stop_loss,
    )
    attribution = analyze_attribution(
        payload=group.payload,
        lifecycle_status=status,
        stats=stats,
        holding=holding,
        data_quality=quality,
    )
    context = market_context(group.payload)
    audit = audit_context(
        payload=group.payload,
        bars=bars,
        first_signal_date=first_signal_date,
        latest_trade_date=str(group.latest_row.latest_trade_date),
        audit_flags=attribution.audit_flags,
    )
    entry_distance = distance_to_entry(current_price, entry_low, entry_high)
    high_bar = max(posterior, key=lambda item: item.high_price) if posterior else None
    low_bar = min(posterior, key=lambda item: item.low_price) if posterior else None
    return StrategyTrackingItemOut(
        id=item_id(group.strategy_key, group.symbol, first_signal_date),
        symbol=group.symbol,
        name=group.latest_row.name,
        strategy_key=group.strategy_key,
        strategy_name=strategy_name,
        strategy_family=get_strategy_tier(group.strategy_key).value,
        signal_state=group.latest_row.buy_signal_state,
        signal_text=SIGNAL_LABELS.get(group.latest_row.buy_signal_state, group.latest_row.buy_signal_state),
        observe_only=group.latest_row.buy_signal_state == "observe_confirmed",
        lifecycle_status=status,
        lifecycle_status_text=STATUS_LABELS.get(status, status),
        first_signal_date=first_signal_date,
        latest_signal_date=str(group.latest_row.latest_trade_date),
        first_signal_price=round_or_none(first_price),
        entry_zone_low=round_or_none(entry_low),
        entry_zone_high=round_or_none(entry_high),
        stop_loss=round_or_none(stop_loss),
        target_price=round_or_none(target_price),
        current_price=round_or_none(current_price),
        latest_trade_date=posterior[-1].trade_date if posterior else "",
        recommendation_days=len(posterior),
        distance_to_entry_pct=round_or_none(entry_distance),
        current_return_pct=round_or_none(stats["current_return_pct"]),
        max_price_after_signal=round_or_none(stats["max_price"]),
        max_gain_pct=round_or_none(stats["max_gain_pct"]),
        max_drawdown_pct=round_or_none(stats["max_drawdown_pct"]),
        actual_low_price=round_or_none(low_bar.low_price if low_bar else None),
        actual_low_date=low_bar.trade_date if low_bar else None,
        actual_high_date=high_bar.trade_date if high_bar else None,
        spike_retrace_pct=round_or_none(holding.giveback_from_peak_pct),
        best_holding_days=holding.best_holding_days,
        best_exit_date=holding.best_exit_date,
        best_exit_return_pct=holding.best_exit_return_pct,
        best_exit_drawdown_pct=holding.best_exit_drawdown_pct,
        return_drawdown_ratio=holding.return_drawdown_ratio,
        giveback_from_peak_pct=holding.giveback_from_peak_pct,
        holding_bucket=holding.holding_bucket,
        exit_quality=holding.exit_quality,
        exit_reason=holding.exit_reason,
        hold_extension_state=holding.hold_extension_state,
        hold_extension_text=holding.hold_extension_text,
        hold_extension_score=holding.hold_extension_score,
        hold_extension_reasons=holding.hold_extension_reasons,
        hold_extension_risks=holding.hold_extension_risks,
        suggested_holding_plan=holding.suggested_holding_plan,
        entry_touched=bool(stats["entry_touched"]),
        stop_triggered=bool(stats["stop_triggered"]),
        stop_triggered_date=stats["stop_triggered_date"],
        target_touched=bool(stats["target_touched"]),
        target_touched_date=stats["target_touched_date"],
        invalidated_date=posterior[-1].trade_date if status == "invalidated" and posterior else None,
        conclusion=conclusion(status, stats, entry_distance),
        failure_reason=failure_reason(status, stats),
        failure_tags=attribution.failure_tags,
        failure_reason_text=attribution.failure_reason_text,
        market_state=context["market_state"],
        market_state_text=context["market_state_text"],
        sector_state=context["sector_state"],
        sector_state_text=context["sector_state_text"],
        signal_generated_at=audit["signal_generated_at"],
        data_cutoff_at=audit["data_cutoff_at"],
        lookback_start_date=audit["lookback_start_date"],
        lookback_end_date=audit["lookback_end_date"],
        posterior_start_date=audit["posterior_start_date"],
        posterior_end_date=audit["posterior_end_date"],
        market_data_source=audit["market_data_source"],
        market_data_updated_at=audit["market_data_updated_at"],
        future_leak_check=audit["future_leak_check"],
        audit_flags=audit["audit_flags"],
        abnormal_return=attribution.abnormal_return,
        needs_review=attribution.needs_review,
        review_priority=attribution.review_priority,
        review_text=review_text(group.payload, status, stats),
        data_quality=quality,
        data_quality_text=data_quality_text(quality),
    )


def lifecycle_status(
    *,
    group,
    posterior: list[DailyBarRow],
    stats: dict,
    lifecycle: LowBuyTradeLifecycleSnapshot | None,
) -> str:
    if lifecycle and lifecycle.status in {"stopped", "invalidated", "expired"}:
        return lifecycle.status
    if not posterior:
        return "data_unavailable"
    if stats["stop_triggered"]:
        return "stopped"
    if stats["target_touched"] or (stats["max_gain_pct"] is not None and stats["max_gain_pct"] >= PROFIT_TARGET_PCT):
        return "completed_profit"
    if len(posterior) >= MAX_TRACKING_DAYS:
        return "expired"
    latest_known_date = posterior[-1].trade_date if posterior else str(group.latest_row.latest_trade_date)
    if missing_signal_days(group.rows, latest_known_date) >= MISSING_SIGNAL_GRACE_DAYS:
        return "invalidated"
    return "active"


def build_timeline(
    *,
    bars: list[DailyBarRow],
    item: StrategyTrackingItemOut,
) -> list[StrategyTrackingTimelinePointOut]:
    posterior = [bar for bar in bars if bar.trade_date > item.first_signal_date][:120]
    reference_price = item.first_signal_price
    timeline: list[StrategyTrackingTimelinePointOut] = []
    running_high = reference_price or 0.0
    closes = [reference_price] if reference_price else []
    for bar in posterior:
        holding_day = len(timeline) + 1
        if reference_price:
            running_high = max(running_high, bar.high_price)
            closes.append(bar.close_price)
            current_return = pct(bar.close_price, reference_price)
            max_return = pct(running_high, reference_price)
            max_drawdown = sequence_max_drawdown_pct(closes)
        else:
            current_return = None
            max_return = None
            max_drawdown = None
        timeline.append(
            StrategyTrackingTimelinePointOut(
                trade_date=bar.trade_date,
                open=bar.open_price,
                high=bar.high_price,
                low=bar.low_price,
                close=bar.close_price,
                pct_chg=bar.pct_chg,
                current_return_pct=round_or_none(current_return),
                max_return_pct=round_or_none(max_return),
                max_drawdown_pct=round_or_none(max_drawdown),
                holding_day=holding_day,
                is_best_exit=bool(item.best_exit_date and bar.trade_date == item.best_exit_date),
                hold_extension_state=item.hold_extension_state if bar.trade_date == item.latest_trade_date else "unavailable",
                hit_entry_zone=hit_entry(bar, item.entry_zone_low, item.entry_zone_high),
                hit_stop_loss=bool(item.stop_loss and bar.low_price <= item.stop_loss),
                hit_target=bool(item.target_price and bar.high_price >= item.target_price),
                lifecycle_status=item.lifecycle_status,
                data_quality=bar.data_quality or "unknown",
            )
        )
    return timeline


def build_markers(
    *,
    item: StrategyTrackingItemOut,
    timeline: list[StrategyTrackingTimelinePointOut],
) -> list[StrategyTrackingMarkerOut]:
    markers = [
        StrategyTrackingMarkerOut(
            kind="first_signal",
            trade_date=item.first_signal_date,
            price=item.first_signal_price,
            label="首次推荐",
        )
    ]
    if item.stop_triggered_date:
        markers.append(
            StrategyTrackingMarkerOut(kind="stop", trade_date=item.stop_triggered_date, price=item.stop_loss, label="跌破止损")
        )
    if item.target_touched_date:
        markers.append(
            StrategyTrackingMarkerOut(kind="target", trade_date=item.target_touched_date, price=item.target_price, label="达到止盈观察")
        )
    if timeline:
        highest = max(timeline, key=lambda point: point.high)
        markers.append(
            StrategyTrackingMarkerOut(kind="highest", trade_date=highest.trade_date, price=highest.high, label="推荐后最高")
        )
        lowest = min(timeline, key=lambda point: point.low)
        markers.append(
            StrategyTrackingMarkerOut(kind="lowest", trade_date=lowest.trade_date, price=lowest.low, label="推荐后最低")
        )
    if item.best_exit_date:
        markers.append(
            StrategyTrackingMarkerOut(
                kind="best_exit",
                trade_date=item.best_exit_date,
                price=None,
                label=f"最优持有 {item.best_holding_days}天",
            )
        )
    if item.hold_extension_state in {"watch", "qualified"} and item.latest_trade_date:
        markers.append(
            StrategyTrackingMarkerOut(
                kind="hold_extension",
                trade_date=item.latest_trade_date,
                price=item.current_price,
                label=item.hold_extension_text,
            )
        )
    return markers
