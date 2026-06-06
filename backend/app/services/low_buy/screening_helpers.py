from __future__ import annotations

from app.services.low_buy.factor_types import FactorContext
from collections.abc import Callable

from app.services.low_buy.shared import (
    LOW_BUY_RESULT_VERSION,
    LOW_BUY_THRESHOLDS,
    LowBuyCandidateOut,
    LowBuyScreenerResponse,
    datetime,
    json,
)


def build_pending_full_response(
    *,
    strategy: str,
    playbook: dict,
    latest_trade_date: str,
    requested_scan_limit: int,
    performance,
    full_scan_in_progress: bool,
) -> LowBuyScreenerResponse:
    as_of_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return LowBuyScreenerResponse(
        strategy_key=strategy,
        strategy_title=playbook["title"],
        strategy_subtitle=playbook["subtitle"],
        strategy_logic=playbook["logic"],
        requested_mode="full",
        response_mode="full",
        as_of_date=as_of_date,
        latest_trade_date=latest_trade_date,
        pool_size=0,
        scanned_count=0,
        matched_count=0,
        snapshot_warning="后台全量深筛仍在补齐，当前不展示今日推荐。",
        stale=False,
        stale_reason="",
        requested_scan_limit=requested_scan_limit,
        active_scan_limit=0,
        full_scan_ready=False,
        full_scan_in_progress=full_scan_in_progress,
        full_scan_updated_at=None,
        market_state_category="low_volume_wait",
        market_state_category_text="缩量无主线",
        data_quality="limited",
        data_quality_text="后台全量深筛仍在补齐",
        data_quality_tags=["全量快照待生成"],
        retracement_distribution={},
        filters={
            "scan_mode": "全量物化",
            "market_state_category": "low_volume_wait",
            "market_state_category_text": "缩量无主线",
            "data_quality": "limited",
            "data_quality_text": "后台全量深筛仍在补齐",
            "data_quality_tags_json": json.dumps(["全量快照待生成"], ensure_ascii=False),
            "_result_version": LOW_BUY_RESULT_VERSION,
        },
        strategy_notes=list(playbook["notes"]),
        performance=performance,
        confirmed_candidates=[],
        history_sections=[],
        candidates=[],
    )


def build_factor_sector_counts(scan_targets) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in scan_targets:
        sector = item.industry or "未分类"
        counts[sector] = counts.get(sector, 0) + 1
    return counts


def prefilter_scan_targets(scan_targets):
    """Drop obvious non-tradable tails before quote/history fan-out.

    The full strategy rules still run on the remaining candidates.  If the
    cheap filter would leave too few candidates, fall back to the original
    pool to avoid changing strategy semantics for sparse pools.
    """
    if len(scan_targets) <= 80:
        return scan_targets
    min_amount = float(LOW_BUY_THRESHOLDS.MIN_DAILY_AMOUNT_AUXILIARY)
    filtered = [
        item
        for item in scan_targets
        if getattr(item, "symbol", "") and float(getattr(item, "amount", 0.0) or 0.0) >= min_amount
    ]
    minimum_keep = max(30, int(len(scan_targets) * 0.25))
    return filtered if len(filtered) >= minimum_keep else scan_targets


def build_factor_context(
    *,
    item,
    sector_counts: dict[str, int],
    latest_trade_date: str,
    latest_completed_trade_date: str = "",
    allow_realtime_external_factors: bool = False,
    sector_flow_ranks: dict[str, float] | None = None,
) -> FactorContext:
    return FactorContext(
        sector_pass_counts=sector_counts,
        sector_flow_ranks=sector_flow_ranks or {},
        current_sector=item.industry or "未分类",
        current_symbol=getattr(item, "symbol", ""),
        retracement_days=getattr(item, "retracement_days", estimate_retracement_days(item, latest_trade_date)),
        confirmed_trade_date=latest_trade_date,
        current_date=latest_trade_date,
        total_strategies=1,
        allow_realtime_external_factors=allow_realtime_external_factors,
    )


def build_screen_filters(
    *,
    board_window_days: int,
    scan_limit: int,
    retracement_days_max: int,
    pool_profile_text: str,
    strategy: str,
    market_regime,
    market_state_fields: dict,
    quality_fields: dict,
    hot_industries: list[str],
    hot_industry_source: str,
    hot_industry_source_text: str,
    limit_down_count,
    latest_trade_date: str,
    latest_completed_trade_date: str,
) -> dict:
    return {
        "board_window_days": board_window_days,
        "scan_limit": scan_limit,
        "scan_mode": "全量深筛，优先读取物化结果与候选池快照",
        "retracement_days_max": retracement_days_max,
        "pool_profile": pool_profile_text,
        "support_zone": "分歧高点突破区" if strategy == "divergence_consensus" else "5日/10日均线附近",
        "volume_rule": "底部涨停放量 + 横盘缩量 + 倍量突破" if strategy == "divergence_consensus" else "启动放量 + 回调缩量",
        "market_regime": market_regime.label,
        "market_state": market_regime.state,
        "market_state_category": market_state_fields["market_state_category"],
        "market_state_category_text": market_state_fields["market_state_category_text"],
        "market_regime_text": market_regime.description,
        "data_quality": quality_fields["data_quality"],
        "data_quality_text": quality_fields["data_quality_text"],
        "data_quality_tags_json": json.dumps(quality_fields["data_quality_tags"], ensure_ascii=False),
        "market_state_strength": market_regime.state_strength,
        "regime_confidence": market_regime.regime_confidence,
        "state_persistence_days": market_regime.state_persistence_days,
        "transition_risk": market_regime.transition_risk,
        "breadth_ready": market_regime.breadth_ready,
        "emotion_ready": market_regime.emotion_ready,
        "market_bonus": market_regime.ranking_bonus,
        "hot_industries": " / ".join(hot_industries) if hot_industries else "热点过滤不可用",
        "hot_industries_json": json.dumps(hot_industries, ensure_ascii=False),
        "hot_industry_source": hot_industry_source,
        "hot_industry_source_text": hot_industry_source_text,
        "limit_down_count": limit_down_count if limit_down_count is not None else "未获取",
        "limit_up_count": market_regime.limit_up_count,
        "board_height": market_regime.board_height,
        "promotion_ratio": market_regime.promotion_ratio,
        "broken_board_ratio": market_regime.broken_board_ratio,
        "high_flyer_retreat_ratio": market_regime.high_flyer_retreat_ratio,
        "stock_up_ratio": market_regime.stock_up_ratio,
        "stock_median_change": market_regime.stock_median_change,
        "style_divergence": market_regime.style_divergence,
        "hot_turnover": market_regime.hot_turnover,
        "hot_overlap_ratio": market_regime.hot_overlap_ratio,
        "previous_board_height": market_regime.previous_board_height,
        "promotion_break_gap": market_regime.promotion_break_gap,
        "promotion_break_pressure": market_regime.promotion_break_pressure,
        "high_flyer_gap_speed": market_regime.high_flyer_gap_speed,
        "emotion_temperature": market_regime.emotion_temperature,
        "emotion_temperature_text": market_regime.emotion_temperature_text,
        "emotion_temperature_score": market_regime.emotion_temperature_score,
        "distribution_pressure": market_regime.distribution_pressure,
        "mainline_lifecycle_state": market_regime.mainline_lifecycle_state,
        "mainline_lifecycle_text": market_regime.mainline_lifecycle_text,
        "structure_mode": "盘中临时结构样本" if latest_trade_date > latest_completed_trade_date else "完整日线样本",
        "_result_version": LOW_BUY_RESULT_VERSION,
    }


def build_screen_response(
    *,
    strategy: str,
    playbook: dict,
    scan_mode: str,
    as_of_date: str,
    latest_trade_date: str,
    latest_completed_trade_date: str,
    ranked_pool: list,
    scan_targets: list,
    confirmed_candidates: list,
    candidates: list,
    history_sections: list,
    retracement_buckets: dict[int, list],
    board_window_days: int,
    scan_limit: int,
    retracement_days_max: int,
    pool_profile_text: str,
    market_regime,
    market_state_fields: dict,
    quality_fields: dict,
    hot_industries: list[str],
    hot_industry_source: str,
    hot_industry_source_text: str,
    limit_down_count,
    strategy_notes: list[str],
) -> LowBuyScreenerResponse:
    return LowBuyScreenerResponse(
        strategy_key=strategy,
        strategy_title=playbook["title"],
        strategy_subtitle=playbook["subtitle"],
        strategy_logic=playbook["logic"],
        requested_mode=scan_mode,
        response_mode=scan_mode,
        as_of_date=as_of_date,
        latest_trade_date=latest_trade_date,
        pool_size=len(ranked_pool),
        scanned_count=len(scan_targets),
        matched_count=len(confirmed_candidates) + len(candidates),
        requested_scan_limit=scan_limit,
        active_scan_limit=len(scan_targets),
        full_scan_ready=scan_mode == "full",
        full_scan_in_progress=False,
        full_scan_updated_at=as_of_date if scan_mode == "full" else None,
        market_state=market_regime.state,
        market_state_text=market_regime.label,
        market_state_category=market_state_fields["market_state_category"],
        market_state_category_text=market_state_fields["market_state_category_text"],
        **quality_fields,
        market_bonus=market_regime.ranking_bonus,
        market_state_strength=market_regime.state_strength,
        regime_confidence=market_regime.regime_confidence,
        state_persistence_days=market_regime.state_persistence_days,
        transition_risk=market_regime.transition_risk,
        breadth_ready=market_regime.breadth_ready,
        emotion_ready=market_regime.emotion_ready,
        stock_up_ratio=market_regime.stock_up_ratio,
        stock_median_change=market_regime.stock_median_change,
        style_divergence=market_regime.style_divergence,
        hot_turnover=market_regime.hot_turnover,
        hot_overlap_ratio=market_regime.hot_overlap_ratio,
        limit_down_count=market_regime.limit_down_count,
        limit_up_count=market_regime.limit_up_count,
        board_height=market_regime.board_height,
        previous_board_height=market_regime.previous_board_height,
        promotion_ratio=market_regime.promotion_ratio,
        broken_board_ratio=market_regime.broken_board_ratio,
        promotion_break_gap=market_regime.promotion_break_gap,
        promotion_break_pressure=market_regime.promotion_break_pressure,
        high_flyer_retreat_ratio=market_regime.high_flyer_retreat_ratio,
        high_flyer_gap_speed=market_regime.high_flyer_gap_speed,
        distribution_pressure=market_regime.distribution_pressure,
        emotion_temperature=market_regime.emotion_temperature,
        emotion_temperature_text=market_regime.emotion_temperature_text,
        emotion_temperature_score=market_regime.emotion_temperature_score,
        hot_industries=hot_industries,
        hot_industry_source=hot_industry_source,
        hot_industry_source_text=hot_industry_source_text,
        mainline_lifecycle_state=market_regime.mainline_lifecycle_state,
        mainline_lifecycle_text=market_regime.mainline_lifecycle_text,
        retracement_distribution={f"{days}天": len(items) for days, items in sorted(retracement_buckets.items()) if items},
        filters=build_screen_filters(
            board_window_days=board_window_days,
            scan_limit=scan_limit,
            retracement_days_max=retracement_days_max,
            pool_profile_text=pool_profile_text,
            strategy=strategy,
            market_regime=market_regime,
            market_state_fields=market_state_fields,
            quality_fields=quality_fields,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
            limit_down_count=limit_down_count,
            latest_trade_date=latest_trade_date,
            latest_completed_trade_date=latest_completed_trade_date,
        ),
        strategy_notes=strategy_notes,
        performance=None,
        confirmed_candidates=confirmed_candidates,
        history_sections=history_sections,
        candidates=candidates,
    )


def evaluate_scan_targets(
    *,
    scan_targets: list,
    histories: dict,
    strategy: str,
    latest_trade_date: str,
    latest_completed_trade_date: str = "",
    allow_realtime_external_factors: bool = False,
    hot_industries: list[str],
    market_regime,
    factor_sector_counts: dict[str, int],
    sector_flow_ranks: dict[str, float],
    evaluate_candidate: Callable[..., LowBuyCandidateOut | None],
) -> list[LowBuyCandidateOut]:
    evaluated: list[LowBuyCandidateOut] = []
    for item in scan_targets:
        candidate = evaluate_candidate(
            item=item,
            latest_trade_date=latest_trade_date,
            history=histories.get(item.symbol),
            strategy=strategy,
            hot_industries=hot_industries,
            market_regime=market_regime,
            factor_context=build_factor_context(
                item=item,
                sector_counts=factor_sector_counts,
                latest_trade_date=latest_trade_date,
                latest_completed_trade_date=latest_completed_trade_date,
                allow_realtime_external_factors=allow_realtime_external_factors,
                sector_flow_ranks=sector_flow_ranks,
            ),
        )
        if candidate is not None:
            evaluated.append(candidate)
    return evaluated


def split_signal_candidates(
    evaluated: list[LowBuyCandidateOut],
    *,
    confirmed_states: tuple[str, ...],
    limit: int,
) -> tuple[list[LowBuyCandidateOut], list[LowBuyCandidateOut]]:
    confirmed_candidates = [
        item for item in evaluated if item.buy_signal_state in confirmed_states
    ][:12]
    candidates = [
        item for item in evaluated if item.buy_signal_state not in confirmed_states
    ][:limit]
    return confirmed_candidates, candidates


def estimate_retracement_days(item, latest_trade_date: str) -> int:
    try:
        board_date = datetime.strptime(getattr(item, "board_date", "")[:10], "%Y-%m-%d")
        latest_date = datetime.strptime(latest_trade_date[:10], "%Y-%m-%d")
        return max((latest_date - board_date).days, 0)
    except (TypeError, ValueError):
        return 0
