from __future__ import annotations

from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyPriorityBoardItemOut,
    LowBuyPriorityFamilyPerformanceOut,
    LowBuyPriorityFamilySectionOut,
    LowBuyStrategyPerformanceOut,
)
from app.services.low_buy.priority_types import PriorityCandidate, StrategyHit
from app.services.low_buy.strategy_families import resolve_strategy_family, resolve_strategy_family_label


def recommendation_days_by_title(hits: list[StrategyHit]) -> dict[str, int]:
    result: dict[str, int] = {}
    for hit in hits:
        days = int(hit.candidate.recommendation_days or 0)
        if days <= 0:
            continue
        title = hit.strategy_title or hit.strategy_key
        result[title] = max(result.get(title, 0), days)
    return result


def priority_recommendation_duration_text(
    *,
    candidate: LowBuyCandidateOut,
    recommendation_days_by_title: dict[str, int],
) -> str:
    if not recommendation_days_by_title:
        return candidate.recommendation_duration_text
    title, max_recommendation_days = max(
        recommendation_days_by_title.items(),
        key=lambda pair: pair[1],
    )
    max_holding_days = max(int(candidate.exit_plan.max_holding_days or 0), 1)
    if max_recommendation_days >= max_holding_days:
        return f"{title}第 {max_recommendation_days} 天，已达到建议验证窗口 {max_holding_days} 天；未转强应降级或退出。"
    return f"{title}第 {max_recommendation_days} 天，建议验证窗口 {max_holding_days} 天；剩余 {max_holding_days - max_recommendation_days} 天。"


def strategy_performance_text(performance: LowBuyStrategyPerformanceOut | None) -> str:
    if performance is None:
        return "策略表现：暂无可用绩效样本，先按结构和风控判断。"
    filled = int(performance.filled_signals or 0)
    if filled < 5:
        return f"策略表现：近 {performance.lookback_days} 日真实成交样本 {filled} 个，样本不足。"
    return (
        f"策略表现：近 {performance.lookback_days} 日盈利率 {performance.hit_rate:.1f}%、"
        f"净胜优势 {performance.net_win_rate:+.1f}%、"
        f"均收 {performance.avg_net_return_pct:+.2f}%、未成交 {performance.not_filled_rate:.1f}%"
    )


def build_priority_family_sections(
    *,
    items: list[LowBuyPriorityBoardItemOut],
    family_performance: dict[str, LowBuyPriorityFamilyPerformanceOut],
    limit_per_family: int = 6,
) -> list[LowBuyPriorityFamilySectionOut]:
    grouped: dict[str, list[LowBuyPriorityBoardItemOut]] = {}
    for item in items:
        grouped.setdefault(item.strategy_family or "uncategorized", []).append(item)
    sections: list[LowBuyPriorityFamilySectionOut] = []
    for family_key, family_items in grouped.items():
        ordered = sorted(family_items, key=lambda item: item.priority_score, reverse=True)
        family_text = ordered[0].strategy_family_text if ordered else resolve_strategy_family_label(family_key)
        sections.append(
            LowBuyPriorityFamilySectionOut(
                family_key=family_key,
                family_text=family_text,
                total_candidates=len(ordered),
                immediate_count=sum(item.buy_signal_state in {"buy_now", "soft_buy_now"} for item in ordered),
                focus_count=sum(item.buy_signal_state == "near_entry" for item in ordered),
                track_count=sum(item.buy_signal_state == "watch" for item in ordered),
                avg_priority_score=round(sum(item.priority_score for item in ordered) / max(len(ordered), 1), 2),
                top_strategy_titles=_unique_strategy_titles_from_items(ordered),
                performance=family_performance.get(family_key),
                items=ordered[:limit_per_family],
            )
        )
    sections.sort(
        key=lambda section: (
            section.immediate_count,
            section.focus_count,
            section.avg_priority_score,
            section.total_candidates,
        ),
        reverse=True,
    )
    return sections


def build_family_performance(rows: list[PriorityCandidate]) -> dict[str, LowBuyPriorityFamilyPerformanceOut]:
    accumulators: dict[str, dict[str, float | int | str | set[str]]] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        for hit in row.hits:
            if hit.performance is None:
                continue
            family_key = hit.family_key or resolve_strategy_family(hit.strategy_key)
            strategy_key = hit.strategy_key
            if (family_key, strategy_key) in seen:
                continue
            seen.add((family_key, strategy_key))
            bucket = accumulators.setdefault(
                family_key,
                {
                    "family_text": resolve_strategy_family_label(strategy_key),
                    "strategies": set(),
                    "evaluated_signals": 0,
                    "filled_signals": 0,
                    "not_filled_signals": 0,
                    "hit_count": 0,
                    "net_win_rate_sum": 0.0,
                    "net_return_sum": 0.0,
                    "not_filled_count": 0.0,
                    "stop_loss_count": 0.0,
                },
            )
            _add_performance_to_bucket(bucket=bucket, hit=hit, strategy_key=strategy_key)
    return {
        family_key: _family_performance_from_bucket(family_key, bucket)
        for family_key, bucket in accumulators.items()
    }


def _unique_strategy_titles_from_items(items: list[LowBuyPriorityBoardItemOut]) -> list[str]:
    titles: list[str] = []
    for item in items:
        for title in item.strategy_titles or [item.strategy_title]:
            if title not in titles:
                titles.append(title)
    return titles[:4]


def _add_performance_to_bucket(
    *,
    bucket: dict[str, float | int | str | set[str]],
    hit: StrategyHit,
    strategy_key: str,
) -> None:
    performance = hit.performance
    if performance is None:
        return
    evaluated = int(performance.evaluated_signals or 0)
    filled = int(performance.filled_signals or 0)
    not_filled = int(performance.not_filled_signals or 0)
    hit_count = int(performance.hit_count or 0)
    bucket["strategies"].add(strategy_key)  # type: ignore[union-attr]
    bucket["evaluated_signals"] = int(bucket["evaluated_signals"]) + evaluated
    bucket["filled_signals"] = int(bucket["filled_signals"]) + filled
    bucket["not_filled_signals"] = int(bucket["not_filled_signals"]) + not_filled
    bucket["hit_count"] = int(bucket["hit_count"]) + hit_count
    bucket["net_win_rate_sum"] = float(bucket["net_win_rate_sum"]) + performance.net_win_rate * filled
    bucket["net_return_sum"] = float(bucket["net_return_sum"]) + performance.avg_net_return_pct * filled
    bucket["not_filled_count"] = float(bucket["not_filled_count"]) + not_filled
    bucket["stop_loss_count"] = float(bucket["stop_loss_count"]) + performance.stop_loss_rate / 100 * filled


def _family_performance_from_bucket(
    family_key: str,
    bucket: dict[str, float | int | str | set[str]],
) -> LowBuyPriorityFamilyPerformanceOut:
    evaluated = int(bucket["evaluated_signals"])
    filled = int(bucket["filled_signals"])
    hit_count = int(bucket["hit_count"])
    not_filled = int(bucket["not_filled_signals"])
    strategies = bucket["strategies"]
    strategy_count = len(strategies) if isinstance(strategies, set) else 0
    return LowBuyPriorityFamilyPerformanceOut(
        family_key=family_key,
        family_text=str(bucket["family_text"]),
        strategy_count=strategy_count,
        evaluated_signals=evaluated,
        filled_signals=filled,
        not_filled_signals=not_filled,
        hit_count=hit_count,
        net_win_rate=round(float(bucket["net_win_rate_sum"]) / max(filled, 1), 2),
        avg_net_return_pct=round(float(bucket["net_return_sum"]) / max(filled, 1), 2),
        not_filled_rate=round(not_filled / max(evaluated, 1) * 100, 2),
        stop_loss_rate=round(float(bucket["stop_loss_count"]) / max(filled, 1) * 100, 2),
        hit_rate=round(hit_count / max(filled, 1) * 100, 2),
    )
