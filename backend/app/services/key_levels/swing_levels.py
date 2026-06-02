from __future__ import annotations

from app.models.schema_defs.key_levels import KeyLevelCandidate
from app.repositories.low_buy.daily_history import DailyBarRow
from app.services.key_levels.score import clamp_score, zone_for_price


def build_swing_candidates(rows: list[DailyBarRow], latest_price: float) -> list[KeyLevelCandidate]:
    if len(rows) < 20 or latest_price <= 0:
        return []
    window = rows[-60:] if len(rows) >= 60 else rows
    support_row = min(window[:-1] or window, key=lambda item: float(item.low_price or 0))
    resistance_row = max(window[:-1] or window, key=lambda item: float(item.high_price or 0))
    candidates: list[KeyLevelCandidate] = []
    support_price = float(support_row.low_price or 0)
    if support_price > 0 and support_price <= latest_price:
        candidates.append(
            _candidate(
                price=support_price,
                direction="support",
                level_type="platform_low",
                score=58,
                evidence=["近 60 个交易日平台低点", "结构支撑位"],
                last_touched_date=str(support_row.trade_date),
                source_window_days=len(window),
            )
        )
    resistance_price = float(resistance_row.high_price or 0)
    if resistance_price > 0 and resistance_price >= latest_price:
        candidates.append(
            _candidate(
                price=resistance_price,
                direction="resistance",
                level_type="platform_high",
                score=58,
                evidence=["近 60 个交易日平台高点", "结构压力位"],
                last_touched_date=str(resistance_row.trade_date),
                source_window_days=len(window),
            )
        )
    candidates.extend(_gap_candidates(window, latest_price))
    candidates.extend(_limit_up_anchor_candidates(window, latest_price))
    return candidates


def _gap_candidates(rows: list[DailyBarRow], latest_price: float) -> list[KeyLevelCandidate]:
    candidates: list[KeyLevelCandidate] = []
    for previous, current in zip(rows, rows[1:]):
        previous_high = float(previous.high_price or 0)
        previous_low = float(previous.low_price or 0)
        current_high = float(current.high_price or 0)
        current_low = float(current.low_price or 0)
        if previous_high > 0 and current_low > previous_high:
            price = previous_high
            if price <= latest_price:
                candidates.append(
                    _candidate(
                        price=price,
                        direction="support",
                        level_type="gap",
                        score=50,
                        evidence=["向上缺口上沿", "结构支撑位"],
                        last_touched_date=str(current.trade_date),
                        source_window_days=len(rows),
                    )
                )
        if previous_low > 0 and current_high < previous_low:
            price = previous_low
            if price >= latest_price:
                candidates.append(
                    _candidate(
                        price=price,
                        direction="resistance",
                        level_type="gap",
                        score=50,
                        evidence=["向下缺口下沿", "结构压力位"],
                        last_touched_date=str(current.trade_date),
                        source_window_days=len(rows),
                    )
                )
    return candidates[-4:]


def _limit_up_anchor_candidates(rows: list[DailyBarRow], latest_price: float) -> list[KeyLevelCandidate]:
    candidates: list[KeyLevelCandidate] = []
    for row in rows:
        close_price = float(row.close_price or 0)
        open_price = float(row.open_price or 0)
        limit_up_price = float(row.limit_up_price or 0)
        pct_chg = float(row.pct_chg or 0)
        if close_price <= 0:
            continue
        is_limit_up = (limit_up_price > 0 and close_price >= limit_up_price * 0.998) or pct_chg >= 9.5
        if not is_limit_up:
            continue
        for price, label in ((open_price, "涨停日开盘价"), (close_price, "涨停日收盘价")):
            if price <= 0:
                continue
            candidates.append(
                _candidate(
                    price=price,
                    direction="support" if price <= latest_price else "resistance",
                    level_type="limit_up_anchor",
                    score=52,
                    evidence=[label, "事件锚点"],
                    last_touched_date=str(row.trade_date),
                    source_window_days=len(rows),
                )
            )
    return candidates[-4:]


def _candidate(
    *,
    price: float,
    direction: str,
    level_type: str,
    score: float,
    evidence: list[str],
    last_touched_date: str,
    source_window_days: int,
) -> KeyLevelCandidate:
    zone_low, zone_high = zone_for_price(price)
    return KeyLevelCandidate(
        price=round(price, 4),
        zone_low=zone_low,
        zone_high=zone_high,
        direction=direction,  # type: ignore[arg-type]
        level_type=level_type,  # type: ignore[arg-type]
        strength_score=clamp_score(score),
        evidence=evidence,
        invalid_condition=(
            f"放量跌破 {zone_low:.2f} 且未收回，支撑降级"
            if direction == "support"
            else f"放量突破 {zone_high:.2f} 后需观察能否站稳"
        ),
        last_touched_date=last_touched_date,
        touch_count=1,
        source_window_days=source_window_days,
        invalidate_below=zone_low if direction == "support" else None,
        invalidate_volume_x=1.5,
    )
