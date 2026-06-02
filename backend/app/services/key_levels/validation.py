from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.key_levels.engine import AKeyLevelEngine
from app.services.key_levels.score import distance_pct


@dataclass(frozen=True)
class KeyLevelValidationSummary:
    symbol: str
    start_trade_date: str
    end_trade_date: str
    sample_count: int
    support_touch_count: int
    support_effective_1d_count: int
    support_effective_3d_count: int
    support_effective_5d_count: int
    support_failure_count: int
    resistance_breakout_count: int
    resistance_extension_3d_count: int
    data_quality: str

    def as_payload(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "start_trade_date": self.start_trade_date,
            "end_trade_date": self.end_trade_date,
            "sample_count": self.sample_count,
            "support_touch_count": self.support_touch_count,
            "support_effective_1d_count": self.support_effective_1d_count,
            "support_effective_3d_count": self.support_effective_3d_count,
            "support_effective_5d_count": self.support_effective_5d_count,
            "support_failure_count": self.support_failure_count,
            "resistance_breakout_count": self.resistance_breakout_count,
            "resistance_extension_3d_count": self.resistance_extension_3d_count,
            "data_quality": self.data_quality,
        }


class KeyLevelValidationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.engine = AKeyLevelEngine(db)

    def validate_symbol(
        self,
        symbol: str,
        *,
        lookback_days: int = 120,
        evaluation_days: int = 60,
        touch_pct: float = 0.3,
        rebound_pct: float = 1.0,
        failure_days: int = 3,
    ) -> KeyLevelValidationSummary:
        all_rows = self.engine.repository.fetch_rows(
            symbol,
            "1900-01-01",
            self.engine.repository.latest_trade_date_for_symbol(symbol) or "",
        )
        if len(all_rows) < lookback_days + 5:
            return KeyLevelValidationSummary(
                symbol=symbol,
                start_trade_date=str(all_rows[0].trade_date) if all_rows else "",
                end_trade_date=str(all_rows[-1].trade_date) if all_rows else "",
                sample_count=0,
                support_touch_count=0,
                support_effective_1d_count=0,
                support_effective_3d_count=0,
                support_effective_5d_count=0,
                support_failure_count=0,
                resistance_breakout_count=0,
                resistance_extension_3d_count=0,
                data_quality="insufficient",
            )
        start_index = max(lookback_days, len(all_rows) - max(1, evaluation_days) - 5)
        support_touch = 0
        support_effective_1d = 0
        support_effective_3d = 0
        support_effective_5d = 0
        support_failure = 0
        resistance_breakout = 0
        resistance_extension_3d = 0
        sample_count = 0
        for index in range(start_index, len(all_rows) - 5):
            row = all_rows[index]
            history_start = max(0, index - max(lookback_days * 2, 90) + 1)
            rows = all_rows[history_start : index + 1]
            result = self.engine._build_from_rows(  # noqa: SLF001
                symbol=symbol,
                name=symbol,
                scope="stock",
                rows=rows,
                include_intraday=False,
            )
            if result.data_quality not in {"ok", "research_only"}:
                continue
            sample_count += 1
            low_price = float(row.low_price or 0.0)
            close_price = float(row.close_price or 0.0)
            if _touched_support(low_price, result.support_zone_low, result.support_zone_high, touch_pct):
                support_touch += 1
                future = all_rows[index + 1 : index + 6]
                support_effective_1d += _rebounded(future[:1], result.support_zone_low, rebound_pct)
                support_effective_3d += _rebounded(future[:3], result.support_zone_low, rebound_pct)
                support_effective_5d += _rebounded(future[:5], result.support_zone_low, rebound_pct)
                support_failure += _failed_support(future[:failure_days], result.support_zone_low)
            if result.resistance_zone_high and close_price > result.resistance_zone_high:
                resistance_breakout += 1
                future = all_rows[index + 1 : index + 4]
                resistance_extension_3d += int(any(distance_pct(close_price, float(item.close_price or 0.0)) and float(item.close_price or 0.0) > close_price for item in future))
        return KeyLevelValidationSummary(
            symbol=symbol,
            start_trade_date=str(all_rows[start_index].trade_date),
            end_trade_date=str(all_rows[-6].trade_date),
            sample_count=sample_count,
            support_touch_count=support_touch,
            support_effective_1d_count=support_effective_1d,
            support_effective_3d_count=support_effective_3d,
            support_effective_5d_count=support_effective_5d,
            support_failure_count=support_failure,
            resistance_breakout_count=resistance_breakout,
            resistance_extension_3d_count=resistance_extension_3d,
            data_quality="ok" if sample_count else "research_only",
        )


def _rebounded(rows, support_zone_low: float, rebound_pct: float) -> int:  # noqa: ANN001
    return int(any(distance_pct(support_zone_low, float(row.high_price or 0.0)) and float(row.high_price or 0.0) >= support_zone_low * (1 + rebound_pct / 100.0) for row in rows))


def _failed_support(rows, support_zone_low: float) -> int:  # noqa: ANN001
    return int(bool(rows) and all(float(row.close_price or 0.0) < support_zone_low for row in rows))


def _touched_support(low_price: float, zone_low: float | None, zone_high: float | None, touch_pct: float) -> bool:
    if not zone_low or not zone_high or low_price <= 0:
        return False
    lower_bound = zone_low * (1 - max(float(touch_pct or 0), 0.0) / 100.0)
    return lower_bound <= low_price <= zone_high
