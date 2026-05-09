from __future__ import annotations

from app.services.low_buy.shared import BoardCandidate, LowBuyCandidateOut


def build_retracement_buckets(
    ranked_pool: list[BoardCandidate],
    completed_trade_dates: list[str],
    latest_trade_date: str,
    max_days: int = 7,
) -> dict[int, list[BoardCandidate]]:
    trade_date_index = {trade_date: index for index, trade_date in enumerate(completed_trade_dates)}
    latest_index = trade_date_index.get(latest_trade_date)
    buckets = {days: [] for days in range(1, max_days + 1)}
    if latest_index is None:
        return buckets
    for item in ranked_pool:
        board_index = trade_date_index.get(item.board_date)
        if board_index is None:
            continue
        retracement_days = latest_index - board_index
        if 1 <= retracement_days <= max_days:
            buckets[retracement_days].append(item)
    return buckets


def build_balanced_scan_pool(
    retracement_buckets: dict[int, list[BoardCandidate]],
    scan_limit: int,
) -> list[BoardCandidate]:
    max_days = max(retracement_buckets) if retracement_buckets else 7
    day_priority = [2, 3, 4, 1, 5, 6, 7, *range(8, max_days + 1)]
    available_days = [day for day in day_priority if retracement_buckets.get(day)]
    if not available_days:
        return []

    selected: list[BoardCandidate] = []
    cursor_by_day = {day: 0 for day in available_days}
    base_quota = max(1, scan_limit // len(available_days))
    for day in available_days:
        batch = retracement_buckets[day][:base_quota]
        selected.extend(batch)
        cursor_by_day[day] = len(batch)

    while len(selected) < scan_limit:
        progressed = False
        for day in day_priority:
            if day not in cursor_by_day:
                continue
            cursor = cursor_by_day[day]
            bucket = retracement_buckets[day]
            if cursor >= len(bucket):
                continue
            selected.append(bucket[cursor])
            cursor_by_day[day] = cursor + 1
            progressed = True
            if len(selected) >= scan_limit:
                break
        if not progressed:
            break
    return selected[:scan_limit]


def rank_pool_candidates(
    candidates: dict[str, BoardCandidate],
    latest_trade_date: str,
) -> list[BoardCandidate]:
    return sorted(
        [item for item in candidates.values() if item.board_date < latest_trade_date],
        key=lambda item: (item.board_date, item.board_count == 1, item.amount),
        reverse=True,
    )


def dedupe_board_candidates(items: list[BoardCandidate]) -> list[BoardCandidate]:
    seen: set[str] = set()
    result: list[BoardCandidate] = []
    for item in items:
        if item.symbol in seen:
            continue
        seen.add(item.symbol)
        result.append(item)
    return result


def merge_board_candidates(*groups: list[BoardCandidate]) -> list[BoardCandidate]:
    merged: list[BoardCandidate] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item.symbol in seen:
                continue
            seen.add(item.symbol)
            merged.append(item)
    return merged


def dedupe_candidates(items: list[LowBuyCandidateOut]) -> list[LowBuyCandidateOut]:
    deduped: dict[str, LowBuyCandidateOut] = {}
    for item in items:
        current = deduped.get(item.symbol)
        if current is None or item.score > current.score:
            deduped[item.symbol] = item
    return list(deduped.values())
