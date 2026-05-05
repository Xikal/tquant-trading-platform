from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot, LowBuyResultSnapshot
from app.services.low_buy.holding_policy import strategy_max_holding_days


DATA_PROVIDER_VERSION = "daily_bar_snapshots:v1"


@dataclass(frozen=True)
class DailyBar:
    symbol: str
    trade_date: str
    open_price: float
    close_price: float
    high_price: float
    low_price: float
    volume: float
    amount: float
    pct_chg: float
    pre_close: float = 0.0
    instrument_type: str = "stock"
    market: str = "CN"

    @property
    def is_valid(self) -> bool:
        prices = [self.open_price, self.close_price, self.high_price, self.low_price]
        if any(value <= 0 for value in prices):
            return False
        return self.high_price >= max(self.open_price, self.close_price, self.low_price)

    @property
    def is_suspended(self) -> bool:
        return self.volume <= 0 or not self.is_valid

    @property
    def vwap(self) -> float:
        if self.amount > 0 and self.volume > 0:
            value = self.amount / self.volume
            if self.low_price * 0.5 <= value <= self.high_price * 1.5:
                return value
        return (self.high_price + self.low_price + self.close_price) / 3


@dataclass(frozen=True)
class BacktestSignal:
    signal_date: str
    symbol: str
    strategy_key: str
    score: float = 0.0
    name: str = ""
    signal_state: str = "watch"
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    max_holding_days: int = 5
    position_pct: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DataQualityReport:
    version: str
    start_date: str
    end_date: str
    symbol_count: int
    trade_date_count: int
    missing_symbol_count: int = 0
    missing_bar_count: int = 0
    invalid_bar_count: int = 0
    suspended_bar_count: int = 0
    adjustment_method: str = "forward"
    source_hash: str = ""
    quality_tag: str = "ok"
    warnings: list[str] = field(default_factory=list)


class DailyBarDataProvider:
    """Read-only data access for daily-bar backtests."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch_trade_dates(self, start_date: str, end_date: str) -> list[str]:
        rows = (
            self.db.execute(
                select(DailyBarSnapshot.trade_date)
                .distinct()
                .where(
                    DailyBarSnapshot.trade_date >= start_date,
                    DailyBarSnapshot.trade_date <= end_date,
                )
                .order_by(DailyBarSnapshot.trade_date.asc())
            )
            .scalars()
            .all()
        )
        return [str(row) for row in rows]

    def fetch_bars(
        self,
        symbols: Iterable[str],
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, list[DailyBar]]:
        unique_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        if not unique_symbols:
            return {}
        rows = (
            self.db.execute(
                select(DailyBarSnapshot)
                .where(
                    DailyBarSnapshot.symbol.in_(unique_symbols),
                    DailyBarSnapshot.trade_date >= start_date,
                    DailyBarSnapshot.trade_date <= end_date,
                )
                .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
            )
            .scalars()
            .all()
        )
        grouped: dict[str, list[DailyBar]] = {}
        previous_close_by_symbol: dict[str, float] = {}
        for row in rows:
            bar = _bar_from_row(row, previous_close=previous_close_by_symbol.get(row.symbol))
            grouped.setdefault(row.symbol, []).append(bar)
            if bar.close_price > 0:
                previous_close_by_symbol[row.symbol] = bar.close_price
        return grouped

    def load_low_buy_signals(
        self,
        *,
        strategies: Iterable[str],
        start_date: str,
        end_date: str,
        max_signals_per_day: int = 20,
    ) -> list[BacktestSignal]:
        strategy_keys = [item.strip() for item in strategies if item and item.strip()]
        if not strategy_keys:
            return []
        rows = (
            self.db.execute(
                select(LowBuyResultSnapshot)
                .where(
                    LowBuyResultSnapshot.strategy_key.in_(strategy_keys),
                    LowBuyResultSnapshot.latest_trade_date >= start_date,
                    LowBuyResultSnapshot.latest_trade_date <= end_date,
                )
                .order_by(
                    LowBuyResultSnapshot.latest_trade_date.asc(),
                    LowBuyResultSnapshot.score.desc(),
                    LowBuyResultSnapshot.symbol.asc(),
                )
            )
            .scalars()
            .all()
        )
        grouped: dict[str, list[BacktestSignal]] = {}
        for row in rows:
            signal = _signal_from_low_buy_row(row)
            if signal.signal_state in {"blocked", "avoid", "skip"}:
                continue
            grouped.setdefault(signal.signal_date, []).append(signal)
        output: list[BacktestSignal] = []
        for trade_date in sorted(grouped):
            ranked = sorted(
                (item for item in grouped[trade_date] if not _is_st_signal(item)),
                key=lambda item: (item.score, item.symbol),
                reverse=True,
            )
            output.extend(ranked[: max(max_signals_per_day, 1)])
        return output

    def quality_report(
        self,
        *,
        symbols: Iterable[str],
        trade_dates: list[str],
        histories: dict[str, list[DailyBar]],
        start_date: str,
        end_date: str,
    ) -> DataQualityReport:
        unique_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        missing_symbols = [symbol for symbol in unique_symbols if not histories.get(symbol)]
        expected_dates = set(trade_dates)
        missing_bar_count = 0
        invalid_bar_count = 0
        suspended_bar_count = 0
        warnings: list[str] = []
        for symbol in unique_symbols:
            bars = histories.get(symbol, [])
            dates = {bar.trade_date for bar in bars}
            missing_bar_count += max(len(expected_dates - dates), 0)
            invalid_bar_count += sum(1 for bar in bars if not bar.is_valid)
            suspended_bar_count += sum(1 for bar in bars if bar.is_suspended)
        if missing_symbols:
            warnings.append(f"{len(missing_symbols)} symbols have no daily bars.")
        if missing_bar_count:
            warnings.append(f"{missing_bar_count} daily bars are missing in the requested range.")
        if invalid_bar_count:
            warnings.append(f"{invalid_bar_count} bars have invalid OHLC values.")
        quality_tag = "warning" if warnings else "ok"
        return DataQualityReport(
            version=DATA_PROVIDER_VERSION,
            start_date=start_date,
            end_date=end_date,
            symbol_count=len(unique_symbols),
            trade_date_count=len(trade_dates),
            missing_symbol_count=len(missing_symbols),
            missing_bar_count=missing_bar_count,
            invalid_bar_count=invalid_bar_count,
            suspended_bar_count=suspended_bar_count,
            source_hash=_manifest_hash(start_date, end_date, unique_symbols),
            quality_tag=quality_tag,
            warnings=warnings,
        )

    def dataset_manifest(
        self,
        *,
        start_date: str,
        end_date: str,
        symbols: Iterable[str],
    ) -> dict[str, Any]:
        unique_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        manifest_hash = _manifest_hash(start_date, end_date, unique_symbols)
        bar_count = 0
        try:
            statement = select(func.count(DailyBarSnapshot.id)).where(
                DailyBarSnapshot.trade_date >= start_date,
                DailyBarSnapshot.trade_date <= end_date,
            )
            if unique_symbols:
                statement = statement.where(DailyBarSnapshot.symbol.in_(unique_symbols))
            bar_count = int(self.db.execute(statement).scalar_one() or 0)
        except Exception:
            # Unit tests and dry-run providers may pass a non-SQLAlchemy db object.
            bar_count = 0
        return {
            "dataset_key": f"daily_bar_snapshots:{start_date}:{end_date}:{len(unique_symbols)}",
            "source_table": "daily_bar_snapshots",
            "source_hash": manifest_hash,
            "manifest_hash": manifest_hash,
            "data_version": DATA_PROVIDER_VERSION,
            "date_range_start": start_date,
            "date_range_end": end_date,
            "start_date": start_date,
            "end_date": end_date,
            "instrument_count": len(unique_symbols),
            "record_count": bar_count,
            "bar_count": bar_count,
            "adjustment_method": "forward",
            "quality_tag": "ok",
        }


def _bar_from_row(row: DailyBarSnapshot, *, previous_close: float | None = None) -> DailyBar:
    close_price = float(row.close_price or 0)
    pct_chg = float(row.pct_chg or 0)
    return DailyBar(
        symbol=row.symbol,
        trade_date=str(row.trade_date),
        open_price=float(row.open_price or 0),
        close_price=close_price,
        high_price=float(row.high_price or 0),
        low_price=float(row.low_price or 0),
        volume=float(row.volume or 0),
        amount=float(row.amount or 0),
        pct_chg=pct_chg,
        pre_close=_resolve_pre_close(row, close_price=close_price, pct_chg=pct_chg, previous_close=previous_close),
        instrument_type=str(row.instrument_type or "stock"),
        market=str(row.market or "CN"),
    )


def _resolve_pre_close(
    row: DailyBarSnapshot,
    *,
    close_price: float,
    pct_chg: float,
    previous_close: float | None,
) -> float:
    raw_pre_close = getattr(row, "pre_close", None)
    try:
        pre_close = float(raw_pre_close or 0)
    except (TypeError, ValueError):
        pre_close = 0.0
    if pre_close > 0:
        return pre_close
    denominator = 1 + pct_chg / 100
    if close_price > 0 and denominator > 0:
        return close_price / denominator
    if previous_close and previous_close > 0:
        return float(previous_close)
    return close_price


def _signal_from_low_buy_row(row: LowBuyResultSnapshot) -> BacktestSignal:
    payload = _json_dict(row.payload_json)
    return BacktestSignal(
        signal_date=str(row.latest_trade_date),
        symbol=str(row.symbol),
        strategy_key=str(row.strategy_key),
        score=float(row.score or payload.get("score") or 0),
        name=str(row.name or payload.get("name") or row.symbol),
        signal_state=str(row.buy_signal_state or payload.get("signal_state") or "watch"),
        entry_zone_low=_payload_float(payload, "entry_zone_low", "entry_low", "entry_plan_low"),
        entry_zone_high=_payload_float(payload, "entry_zone_high", "entry_high", "entry_plan_high"),
        stop_loss=_payload_float(payload, "stop_loss"),
        take_profit=_payload_float(payload, "take_profit"),
        max_holding_days=_payload_int(
            payload,
            "max_holding_days",
            default=strategy_max_holding_days(str(row.strategy_key)),
        ),
        position_pct=_payload_float(payload, "position_pct", "suggested_position_pct"),
        metadata=payload,
    )


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _payload_float(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _payload_int(payload: dict[str, Any], key: str, *, default: int) -> int:
    try:
        return int(payload.get(key) or default)
    except (TypeError, ValueError):
        return default


def _is_st_signal(signal: BacktestSignal) -> bool:
    name = (signal.name or signal.metadata.get("name") or "").upper()
    return "ST" in name or "退" in name


def _manifest_hash(start_date: str, end_date: str, symbols: Iterable[str]) -> str:
    material = "|".join(
        [
            "daily_bar_snapshots",
            DATA_PROVIDER_VERSION,
            "forward",
            str(start_date),
            str(end_date),
            *sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()}),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
