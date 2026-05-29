from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from app.models.schema_defs.strategy_tracking import StrategyTrackingHoldingAnalysisOut, StrategyTrackingItemOut
from app.services.strategy_tracking_helpers import avg, ratio, round_value, text


def board_type(symbol: str, payload: dict[str, Any] | None = None) -> tuple[str, str]:
    payload = payload or {}
    explicit = text(payload, "board_type", "market_board", "listing_board")
    if explicit:
        normalized = explicit.lower()
        if normalized in {"chinext", "gem", "创业板"}:
            return "chinext", "创业板"
        if normalized in {"star", "sci-tech", "科创板"}:
            return "star", "科创板"
        if normalized in {"bse", "北交所"}:
            return "bse", "北交所"
        if normalized in {"main", "main_board", "主板"}:
            return "main", "主板"
    if symbol.startswith(("300", "301")):
        return "chinext", "创业板"
    if symbol.startswith(("688", "689")):
        return "star", "科创板"
    if symbol.startswith(("8", "4")):
        return "bse", "北交所"
    return "main", "主板"


def sector_lists(payload: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    industry = _list_values(
        payload,
        "industry_sectors",
        "industries",
        "industry",
        "instrument_sector_name",
        "sector_name",
        "sw_industry",
        "citic_industry",
    )
    concepts = _list_values(
        payload,
        "concept_sectors",
        "concepts",
        "concept",
        "theme_sectors",
        "themes",
        "tags",
    )
    custom = _list_values(payload, "strategy_sectors", "mainline_sectors", "hot_industries")
    return _unique(industry), _unique(concepts), _unique(custom)


def display_sectors(payload: dict[str, Any], board_text: str) -> list[str]:
    industry, concepts, custom = sector_lists(payload)
    values = [*concepts, *industry, *custom, board_text]
    return _unique([item for item in values if item])[:6]


def sector_detail(
    *,
    board_value: str,
    board_text: str,
    industry_sectors: list[str],
    concept_sectors: list[str],
    display_sectors: list[str],
    sector_state: str,
    sector_state_text: str,
) -> dict[str, Any]:
    return {
        "board_type": board_value,
        "board_type_text": board_text,
        "industry_sectors": industry_sectors,
        "concept_sectors": concept_sectors,
        "display_sectors": display_sectors,
        "sector_state": sector_state,
        "sector_state_text": sector_state_text,
    }


def friendly_status(item: StrategyTrackingItemOut) -> tuple[str, str, str]:
    if item.data_quality in {"partial", "unavailable"}:
        return "data_missing", "数据不足", item.data_quality_text or "后续行情数据不足，暂时不能判断。"
    if item.needs_review or item.abnormal_return:
        return "review_needed", "需要复核", item.failure_reason_text or "数据或收益表现存在异常，需要人工核对。"
    if item.stop_triggered or item.lifecycle_status == "stopped":
        return "weakening", "已经走弱", "已经跌破风险线，优先复盘失败原因。"
    if item.target_touched or item.lifecycle_status == "completed_profit":
        return "take_profit_watch", "冲高后观察", "推荐后已经出现冲高，重点看是否回落。"
    if not item.entry_touched:
        return "wait_entry", "等计划买点", "还没到计划买入区，暂时只观察。"
    return "focus", "值得重点看", "已经到达计划买入区，且暂未触发风险线。"


def plain_language_summary(item: StrategyTrackingItemOut) -> str:
    gain = _pct_text(item.max_gain_pct)
    drawdown = _pct_text(item.max_drawdown_pct)
    current = _pct_text(item.current_return_pct)
    stop_text = "已经跌破风险线" if item.stop_triggered else "没有跌破风险线"
    if item.data_quality in {"partial", "unavailable"}:
        return f"数据不足：推荐后最高涨过 {gain}，最多跌过 {drawdown}，暂时不能完整判断。"
    if item.hold_extension_state in {"qualified", "watch"}:
        hold_text = item.hold_extension_text
    elif item.best_holding_days:
        hold_text = f"更像 {holding_bucket_text(item.holding_bucket)} 的复盘样本"
    else:
        hold_text = "持有建议不足"
    return f"推荐后最高涨过 {gain}，最多跌过 {drawdown}，现在涨跌 {current}，{stop_text}，{hold_text}。"


def holding_bucket_text(value: str) -> str:
    return {
        "short_1_3d": "短线 1-3 天",
        "swing_4_10d": "波段 4-10 天",
        "trend_11_30d": "趋势 11-30 天",
        "trend_11_20d": "趋势 11-20 天",
        "midlong_31_120d": "中长线观察",
        "midlong_20d_plus": "中长线观察",
        "unsuitable": "不适合延长",
        "unavailable": "样本不足",
    }.get(value, value or "样本不足")


def build_holding_analysis(items: list[StrategyTrackingItemOut]) -> list[StrategyTrackingHoldingAnalysisOut]:
    grouped: dict[str, list[StrategyTrackingItemOut]] = {}
    for item in items:
        grouped.setdefault(item.strategy_key, []).append(item)
    rows: list[StrategyTrackingHoldingAnalysisOut] = []
    for strategy_key, strategy_items in grouped.items():
        rows.append(_holding_row(strategy_key, strategy_items))
    return sorted(rows, key=lambda item: (item.sample_count, item.avg_best_exit_return_pct), reverse=True)


def _holding_row(strategy_key: str, items: list[StrategyTrackingItemOut]) -> StrategyTrackingHoldingAnalysisOut:
    valid_days = [item.best_holding_days for item in items if item.best_holding_days > 0]
    buckets = Counter(_normalized_bucket(item.holding_bucket) for item in items if item.best_holding_days > 0)
    dominant_bucket = buckets.most_common(1)[0][0] if buckets else "unavailable"
    returns = [item.best_exit_return_pct or 0.0 for item in items if item.best_exit_return_pct is not None]
    drawdowns = [item.best_exit_drawdown_pct or 0.0 for item in items if item.best_exit_drawdown_pct is not None]
    givebacks = [item.giveback_from_peak_pct or 0.0 for item in items if item.giveback_from_peak_pct is not None]
    return StrategyTrackingHoldingAnalysisOut(
        strategy_key=strategy_key,
        strategy_name=items[0].strategy_name,
        strategy_family=items[0].strategy_family,
        sample_count=len(items),
        avg_best_holding_days=round_value(sum(valid_days) / len(valid_days), 1) if valid_days else 0.0,
        median_best_holding_days=round_value(float(median(valid_days)), 1) if valid_days else 0.0,
        dominant_holding_bucket=dominant_bucket,
        dominant_holding_bucket_text=holding_bucket_text(dominant_bucket),
        short_hold_ratio=_bucket_ratio(buckets, "short_1_3d", len(items)),
        swing_hold_ratio=_bucket_ratio(buckets, "swing_4_10d", len(items)),
        trend_hold_ratio=_bucket_ratio(buckets, "trend_11_30d", len(items)),
        midlong_hold_ratio=_bucket_ratio(buckets, "midlong_31_120d", len(items)),
        avg_best_exit_return_pct=avg(returns),
        avg_best_exit_drawdown_pct=avg(drawdowns),
        avg_giveback_from_peak_pct=avg(givebacks),
        extension_qualified_ratio=ratio(sum(1 for item in items if item.hold_extension_state == "qualified"), len(items)),
        conclusion=_holding_conclusion(items[0].strategy_name, dominant_bucket, givebacks),
    )


def _holding_conclusion(strategy_name: str, bucket: str, givebacks: list[float]) -> str:
    name = strategy_name or "该策略"
    avg_giveback = avg(givebacks)
    if bucket == "short_1_3d":
        suffix = "后续利润回吐明显。" if avg_giveback >= 4 else "后续仍需观察是否回落。"
        return f"{name}更适合短线 1-3 天，多数样本在 3 天内出现较优收益，{suffix}"
    if bucket == "swing_4_10d":
        return f"{name}更适合波段 4-10 天，有利润垫且回撤可控时可继续观察。"
    if bucket == "trend_11_30d":
        return f"{name}更适合趋势观察，需持续跟踪支撑位和利润回吐。"
    if bucket == "midlong_31_120d":
        return f"{name}有中长线观察样本，但只能作为复盘结论，不能自动延长持有。"
    return f"{name}样本不足，暂时不能判断最适合持有多久。"


def _normalized_bucket(value: str) -> str:
    if value == "trend_11_20d":
        return "trend_11_30d"
    if value == "midlong_20d_plus":
        return "midlong_31_120d"
    return value or "unavailable"


def _bucket_ratio(counts: Counter[str], bucket: str, total: int) -> float:
    return ratio(int(counts.get(bucket, 0)), total)


def _list_values(payload: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = payload.get(key)
        if isinstance(raw, str):
            values.extend(_split_text(raw))
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    values.extend(_split_text(item))
                elif isinstance(item, dict):
                    values.extend(_split_text(str(item.get("name") or item.get("sector") or item.get("label") or "")))
    return values


def _split_text(value: str) -> list[str]:
    normalized = value.replace("，", ",").replace("/", ",").replace("、", ",").replace("|", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _pct_text(value: float | None) -> str:
    if value is None:
        return "--"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"
