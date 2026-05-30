from __future__ import annotations

from app.models.schema_defs.strategy_tracking import StrategyTrackingItemOut
from app.services.low_buy.strategy_lanes import project_items_to_lane


def filter_items(
    items: list[StrategyTrackingItemOut],
    *,
    lifecycle_status: str | None,
    data_quality: str | None,
    hit_entry: bool | None,
    stopped: bool | None,
    exclude_chinext: bool,
    exclude_star: bool,
    board_filter: str | None,
    user_status: str | None,
    strategy_variant: str | None = None,
) -> list[StrategyTrackingItemOut]:
    result = items
    if strategy_variant:
        result = project_items_to_lane(result, strategy_variant)
    if lifecycle_status:
        result = [item for item in result if item.lifecycle_status == lifecycle_status]
    if data_quality:
        result = [item for item in result if item.data_quality == data_quality]
    if hit_entry is not None:
        result = [item for item in result if item.entry_touched == hit_entry]
    if stopped is not None:
        result = [item for item in result if item.stop_triggered == stopped]
    if user_status:
        result = [item for item in result if item.user_friendly_status == user_status]
    if board_filter == "main_only":
        result = [item for item in result if item.board_type == "main"]
    if exclude_chinext:
        result = [item for item in result if item.board_type != "chinext"]
    if exclude_star:
        result = [item for item in result if item.board_type != "star"]
    return result


def sort_items(items: list[StrategyTrackingItemOut], *, sort: str) -> list[StrategyTrackingItemOut]:
    if sort == "best_holding_desc":
        return sorted(items, key=lambda item: item.best_exit_return_pct or -999.0, reverse=True)
    if sort == "needs_review_desc":
        return sorted(items, key=lambda item: (item.needs_review, item.abnormal_return, item.max_gain_pct or 0.0), reverse=True)
    if sort == "current_return_desc":
        return sorted(items, key=lambda item: item.current_return_pct or -999.0, reverse=True)
    if sort == "drawdown_asc":
        return sorted(items, key=lambda item: item.max_drawdown_pct or 0.0)
    if sort == "days_desc":
        return sorted(items, key=lambda item: item.recommendation_days, reverse=True)
    if sort == "risk_desc":
        return sorted(items, key=lambda item: (item.stop_triggered, -(item.max_drawdown_pct or 0.0)), reverse=True)
    if sort == "latest_desc":
        return sorted(items, key=lambda item: (item.latest_signal_date, item.max_gain_pct or -999.0), reverse=True)
    return sorted(items, key=lambda item: item.max_gain_pct or -999.0, reverse=True)
