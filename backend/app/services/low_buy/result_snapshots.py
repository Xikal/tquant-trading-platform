from __future__ import annotations

from app.models.entities import LowBuyScanSnapshot
from app.services.low_buy.shared import LowBuyCandidateOut, LowBuyScreenerResponse
from app.services.low_buy.result_payloads import safe_json_list, safe_json_object


def build_materialized_response(
    *,
    summary: LowBuyScanSnapshot,
    summary_filters: dict,
    confirmed_candidates: list[LowBuyCandidateOut],
    watch_candidates: list[LowBuyCandidateOut],
    history_sections: list,
) -> LowBuyScreenerResponse:
    return LowBuyScreenerResponse(
        strategy_key=summary.strategy_key,
        strategy_title=summary.strategy_title,
        strategy_subtitle=summary.strategy_subtitle,
        strategy_logic=summary.strategy_logic,
        requested_mode="full",
        response_mode="full",
        as_of_date=summary.as_of_date,
        latest_trade_date=summary.latest_trade_date,
        pool_size=summary.pool_size,
        scanned_count=summary.scanned_count,
        matched_count=summary.matched_count,
        requested_scan_limit=summary.requested_scan_limit,
        active_scan_limit=summary.active_scan_limit,
        full_scan_ready=True,
        full_scan_in_progress=False,
        full_scan_updated_at=summary.as_of_date,
        market_state=str(summary_filters.get("market_state") or "low_volume_wait"),
        market_state_text=str(summary_filters.get("market_regime") or ""),
        market_state_category=str(summary_filters.get("market_state_category") or "low_volume_wait"),
        market_state_category_text=str(summary_filters.get("market_state_category_text") or "缩量无主线"),
        data_quality=str(summary_filters.get("data_quality") or "ok"),
        data_quality_text=str(summary_filters.get("data_quality_text") or "数据完整"),
        data_quality_tags=safe_json_list(summary_filters.get("data_quality_tags_json", "[]")),
        market_bonus=float(summary_filters.get("market_bonus") or 0.0),
        market_state_strength=float(summary_filters.get("market_state_strength") or 0.0),
        regime_confidence=float(summary_filters.get("regime_confidence") or 0.0),
        state_persistence_days=int(summary_filters.get("state_persistence_days") or 1),
        transition_risk=float(summary_filters.get("transition_risk") or 0.0),
        breadth_ready=bool(summary_filters.get("breadth_ready") or False),
        emotion_ready=bool(summary_filters.get("emotion_ready") or False),
        stock_up_ratio=float(summary_filters.get("stock_up_ratio") or 0.0),
        stock_median_change=float(summary_filters.get("stock_median_change") or 0.0),
        style_divergence=float(summary_filters.get("style_divergence") or 0.0),
        hot_turnover=float(summary_filters.get("hot_turnover") or 0.0),
        hot_overlap_ratio=float(summary_filters.get("hot_overlap_ratio") or 0.0),
        limit_down_count=_optional_int(summary_filters.get("limit_down_count")),
        limit_up_count=int(summary_filters.get("limit_up_count") or 0),
        board_height=int(summary_filters.get("board_height") or 0),
        previous_board_height=int(summary_filters.get("previous_board_height") or 0),
        promotion_ratio=float(summary_filters.get("promotion_ratio") or 0.0),
        broken_board_ratio=float(summary_filters.get("broken_board_ratio") or 0.0),
        promotion_break_gap=float(summary_filters.get("promotion_break_gap") or 0.0),
        promotion_break_pressure=float(summary_filters.get("promotion_break_pressure") or 0.0),
        high_flyer_retreat_ratio=float(summary_filters.get("high_flyer_retreat_ratio") or 0.0),
        high_flyer_gap_speed=float(summary_filters.get("high_flyer_gap_speed") or 0.0),
        distribution_pressure=float(summary_filters.get("distribution_pressure") or 0.0),
        emotion_temperature=str(summary_filters.get("emotion_temperature") or "unknown"),
        emotion_temperature_text=str(summary_filters.get("emotion_temperature_text") or "情绪温度数据不足"),
        emotion_temperature_score=float(summary_filters.get("emotion_temperature_score") or 0.0),
        hot_industries=_hot_industries(summary_filters),
        hot_industry_source=str(summary_filters.get("hot_industry_source") or ""),
        hot_industry_source_text=str(summary_filters.get("hot_industry_source_text") or ""),
        mainline_lifecycle_state=str(summary_filters.get("mainline_lifecycle_state") or ""),
        mainline_lifecycle_text=str(summary_filters.get("mainline_lifecycle_text") or ""),
        retracement_distribution=safe_json_object(summary.retracement_distribution_json),
        filters=summary_filters,
        strategy_notes=safe_json_list(summary.strategy_notes_json),
        confirmed_candidates=confirmed_candidates,
        history_sections=history_sections,
        candidates=watch_candidates,
    )


def _hot_industries(summary_filters: dict) -> list:
    return safe_json_list(summary_filters.get("hot_industries_json", "[]")) or [
        item.strip() for item in str(summary_filters.get("hot_industries") or "").split("/") if item.strip()
    ]


def _optional_int(value) -> int | None:
    return int(value) if str(value or "").isdigit() else None
