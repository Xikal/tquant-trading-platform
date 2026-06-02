from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_today
from app.models.entities import DailyBarSnapshot, Instrument
from app.models.schema_defs.key_levels import KeyLevelCandidate, KeyLevelResult
from app.repositories.low_buy.daily_history import DailyBarRow, DailyHistoryRepository
from app.services.intraday_key_levels import IntradayKeyLevelService
from app.services.key_levels.anchored_vwap import build_anchored_vwap_candidates
from app.services.key_levels.ma_levels import MaLevels, calculate_ma_levels
from app.services.key_levels.score import clamp_score, distance_pct, zone_for_price
from app.services.key_levels.swing_levels import build_swing_candidates
from app.services.key_levels.volume_profile import build_volume_profile_candidates
from app.services.market_data import MarketDataService

ENGINE_VERSION = "akey-level-v1"
MIN_DAILY_ROWS = 20
MARKET_INDEX_SYMBOLS = ("000300", "000001", "399001", "399006", "000905", "000852")


class AKeyLevelEngine:
    def __init__(self, db: Session, market_data: MarketDataService | None = None) -> None:
        self.db = db
        self.market_data = market_data or MarketDataService()
        self.repository = DailyHistoryRepository(db)

    def build_stock(
        self,
        symbol: str,
        *,
        trade_date: str | None = None,
        lookback_days: int = 120,
        include_intraday: bool = False,
        threshold_pct: float = 0.3,
    ) -> KeyLevelResult:
        symbol = symbol.strip()
        rows = self._load_rows(symbol, trade_date=trade_date, lookback_days=lookback_days)
        instrument = self._instrument(symbol)
        return self._build_from_rows(
            symbol=symbol,
            name=getattr(instrument, "name", "") or "",
            scope="stock",
            rows=rows,
            include_intraday=include_intraday,
            threshold_pct=threshold_pct,
        )

    def build_sector(
        self,
        sector_key: str,
        *,
        trade_date: str | None = None,
        lookback_days: int = 120,
        include_intraday: bool = False,
    ) -> KeyLevelResult:
        sector_key = sector_key.strip()
        symbols = self._sector_symbols(sector_key, limit=30)
        rows_by_symbol = {
            symbol: self._load_rows(symbol, trade_date=trade_date, lookback_days=lookback_days)
            for symbol in symbols
        }
        rows = _build_proxy_rows(rows_by_symbol, instrument_type="sector")
        result = self._build_from_rows(
            symbol=sector_key,
            name=sector_key,
            scope="sector",
            rows=rows,
            include_intraday=include_intraday,
        )
        if result.data_quality == "ok":
            result.data_quality = "research_only"
            result.warnings.append("板块关键位使用成分股等权代理序列，作为研究观察口径。")
        return result

    def build_market(
        self,
        *,
        trade_date: str | None = None,
        lookback_days: int = 120,
        include_intraday: bool = False,
    ) -> KeyLevelResult:
        index_symbol = self._market_index_symbol()
        if index_symbol:
            rows = self._load_rows(index_symbol, trade_date=trade_date, lookback_days=lookback_days)
            instrument = self._instrument(index_symbol)
            symbol = index_symbol
            name = getattr(instrument, "name", "") or "核心指数"
        else:
            stock_symbols = self._stock_symbols(limit=80)
            rows_by_symbol = {
                symbol: self._load_rows(symbol, trade_date=trade_date, lookback_days=lookback_days)
                for symbol in stock_symbols
            }
            rows = _build_proxy_rows(rows_by_symbol, instrument_type="market")
            symbol = "market"
            name = "大盘等权代理"
        result = self._build_from_rows(
            symbol=symbol,
            name=name,
            scope="market",
            rows=rows,
            include_intraday=include_intraday,
        )
        if result.data_quality == "ok" and symbol == "market":
            result.data_quality = "research_only"
            result.warnings.append("大盘关键位使用股票等权代理序列，作为研究观察口径。")
        return result

    def build_intraday(
        self,
        symbol: str,
        *,
        threshold_pct: float = 0.3,
    ) -> KeyLevelResult:
        return self.build_stock(symbol, include_intraday=True, threshold_pct=threshold_pct)

    def with_intraday(self, result: KeyLevelResult, *, threshold_pct: float = 0.3) -> KeyLevelResult:
        if result.scope != "stock" or result.latest_price <= 0:
            return result
        candidates = _merge_candidates([
            *result.key_level_candidates,
            *self._intraday_candidates(result.symbol, result.latest_price, threshold_pct),
        ])
        support = _nearest_candidate(candidates, result.latest_price, "support")
        resistance = _nearest_candidate(candidates, result.latest_price, "resistance")
        return result.model_copy(
            update={
                "intraday_included": True,
                "support_price": support.price if support else None,
                "support_zone_low": support.zone_low if support else None,
                "support_zone_high": support.zone_high if support else None,
                "support_distance_pct": distance_pct(result.latest_price, support.price) if support else None,
                "support_strength": support.strength_score if support else 0,
                "support_level_type": support.level_type if support else "",
                "resistance_price": resistance.price if resistance else None,
                "resistance_zone_low": resistance.zone_low if resistance else None,
                "resistance_zone_high": resistance.zone_high if resistance else None,
                "resistance_distance_pct": distance_pct(result.latest_price, resistance.price) if resistance else None,
                "resistance_strength": resistance.strength_score if resistance else 0,
                "resistance_level_type": resistance.level_type if resistance else "",
                "key_level_candidates": candidates,
                "explanation": _explanation(support=support, resistance=resistance, latest_price=result.latest_price),
            }
        )

    def _build_from_rows(
        self,
        *,
        symbol: str,
        name: str,
        scope: str,
        rows: list[DailyBarRow],
        include_intraday: bool,
        threshold_pct: float = 0.3,
    ) -> KeyLevelResult:
        if len(rows) < MIN_DAILY_ROWS:
            return _empty_result(
                symbol=symbol,
                name=name,
                scope=scope,
                trade_date=str(rows[-1].trade_date) if rows else beijing_today().isoformat(),
                latest_price=float(rows[-1].close_price or 0.0) if rows else 0.0,
                reason="日线样本不足，关键位仅能保持观察。",
            )
        if any(row.is_suspended or row.is_delisted for row in rows[-3:]):
            return _empty_result(
                symbol=symbol,
                name=name,
                scope=scope,
                trade_date=str(rows[-1].trade_date),
                latest_price=float(rows[-1].close_price or 0.0),
                reason="近期停牌或退市状态导致关键位不可用。",
                data_quality="blocked",
            )
        latest_price = float(rows[-1].close_price or 0.0)
        ma_levels = calculate_ma_levels([float(row.close_price or 0.0) for row in rows])
        candidates = _ma_candidates(ma_levels, latest_price)
        candidates.extend(build_swing_candidates(rows, latest_price))
        candidates.extend(build_volume_profile_candidates(rows, latest_price))
        candidates.extend(build_anchored_vwap_candidates(rows, latest_price))
        if include_intraday and scope == "stock":
            candidates.extend(self._intraday_candidates(symbol, latest_price, threshold_pct))
        candidates = _merge_candidates(candidates)
        support = _nearest_candidate(candidates, latest_price, "support")
        resistance = _nearest_candidate(candidates, latest_price, "resistance")
        return KeyLevelResult(
            symbol=symbol,
            name=name,
            scope=scope,  # type: ignore[arg-type]
            trade_date=str(rows[-1].trade_date),
            latest_price=round(latest_price, 4),
            engine_version=ENGINE_VERSION,
            as_of=str(rows[-1].trade_date),
            adjust_mode="qfq",
            intraday_included=include_intraday,
            support_price=support.price if support else None,
            support_zone_low=support.zone_low if support else None,
            support_zone_high=support.zone_high if support else None,
            support_distance_pct=distance_pct(latest_price, support.price) if support else None,
            support_strength=support.strength_score if support else 0,
            support_level_type=support.level_type if support else "",
            resistance_price=resistance.price if resistance else None,
            resistance_zone_low=resistance.zone_low if resistance else None,
            resistance_zone_high=resistance.zone_high if resistance else None,
            resistance_distance_pct=distance_pct(latest_price, resistance.price) if resistance else None,
            resistance_strength=resistance.strength_score if resistance else 0,
            resistance_level_type=resistance.level_type if resistance else "",
            ma5=ma_levels.ma5,
            ma10=ma_levels.ma10,
            ma20=ma_levels.ma20,
            ma30=ma_levels.ma30,
            ma60=ma_levels.ma60,
            close_to_ma5=distance_pct(latest_price, ma_levels.ma5 or 0),
            close_to_ma10=distance_pct(latest_price, ma_levels.ma10 or 0),
            close_to_ma20=distance_pct(latest_price, ma_levels.ma20 or 0),
            close_to_ma30=distance_pct(latest_price, ma_levels.ma30 or 0),
            close_to_ma60=distance_pct(latest_price, ma_levels.ma60 or 0),
            trend_above_ma30=latest_price >= ma_levels.ma30 if ma_levels.ma30 else None,
            trend_above_ma60=latest_price >= ma_levels.ma60 if ma_levels.ma60 else None,
            key_level_candidates=candidates,
            data_quality="ok" if support or resistance else "research_only",
            explanation=_explanation(support=support, resistance=resistance, latest_price=latest_price),
            warnings=[] if support or resistance else ["未形成足够清晰的支撑或压力区，仅观察。"],
        )

    def _load_rows(self, symbol: str, *, trade_date: str | None, lookback_days: int) -> list[DailyBarRow]:
        latest_trade_date = trade_date or self.repository.latest_trade_date_for_symbol(symbol)
        if not latest_trade_date:
            return []
        start_date = _parse_date(latest_trade_date) - timedelta(days=max(lookback_days * 2, 90))
        return self.repository.fetch_rows(symbol, start_date.isoformat(), latest_trade_date)

    def _instrument(self, symbol: str) -> Instrument | None:
        return self.db.execute(select(Instrument).where(Instrument.symbol == symbol).limit(1)).scalar_one_or_none()

    def _sector_symbols(self, sector_key: str, *, limit: int) -> list[str]:
        rows = self.db.execute(
            select(Instrument.symbol)
            .where(Instrument.sector_name == sector_key, Instrument.instrument_type == "stock")
            .order_by(Instrument.symbol.asc())
            .limit(limit)
        ).scalars()
        return [str(row) for row in rows]

    def _stock_symbols(self, *, limit: int) -> list[str]:
        rows = self.db.execute(
            select(Instrument.symbol)
            .where(Instrument.instrument_type == "stock")
            .order_by(Instrument.symbol.asc())
            .limit(limit)
        ).scalars()
        return [str(row) for row in rows]

    def _market_index_symbol(self) -> str | None:
        row = self.db.execute(
            select(Instrument.symbol)
            .where(Instrument.symbol.in_(MARKET_INDEX_SYMBOLS), Instrument.instrument_type == "index")
            .order_by(Instrument.symbol.asc())
            .limit(1)
        ).scalar_one_or_none()
        return str(row) if row else None

    def _intraday_candidates(self, symbol: str, latest_price: float, threshold_pct: float) -> list[KeyLevelCandidate]:
        try:
            response = IntradayKeyLevelService(self.market_data).build(symbol, threshold_pct=threshold_pct)
        except Exception:
            return []
        candidates: list[KeyLevelCandidate] = []
        for level in response.levels:
            price = float(level.price or 0)
            if price <= 0:
                continue
            direction = "support" if price <= latest_price else "resistance"
            zone_low, zone_high = zone_for_price(price, 0.003)
            candidates.append(
                KeyLevelCandidate(
                    price=round(price, 4),
                    zone_low=zone_low,
                    zone_high=zone_high,
                    direction=direction,  # type: ignore[arg-type]
                    level_type=_intraday_level_type(str(level.level_type)),
                    strength_score=clamp_score(42),
                    evidence=[level.level_text or "盘中关键位"],
                    invalid_condition=(
                        f"跌破 {zone_low:.2f} 且未收回，盘中支撑降级"
                        if direction == "support"
                        else f"接近 {zone_high:.2f} 盘中压力，观察能否站稳"
                    ),
                    invalidate_below=zone_low if direction == "support" else None,
                    invalidate_volume_x=1.3,
                )
            )
        return candidates


def _ma_candidates(ma_levels: MaLevels, latest_price: float) -> list[KeyLevelCandidate]:
    candidates: list[KeyLevelCandidate] = []
    for level_type, price, score in (
        ("ma5", ma_levels.ma5, 36),
        ("ma10", ma_levels.ma10, 38),
        ("ma20", ma_levels.ma20, 42),
        ("ma30", ma_levels.ma30, 50),
        ("ma60", ma_levels.ma60, 48),
    ):
        if not price or price <= 0:
            continue
        direction = "support" if price <= latest_price else "resistance"
        zone_low, zone_high = zone_for_price(price)
        candidates.append(
            KeyLevelCandidate(
                price=round(price, 4),
                zone_low=zone_low,
                zone_high=zone_high,
                direction=direction,  # type: ignore[arg-type]
                level_type=level_type,  # type: ignore[arg-type]
                strength_score=clamp_score(score),
                evidence=[f"{level_type.upper()} 均线"],
                invalid_condition=(
                    f"跌破 {zone_low:.2f} 且未收回，均线支撑降级"
                    if direction == "support"
                    else f"接近 {zone_high:.2f} 均线压力，观察能否站稳"
                ),
                invalidate_below=zone_low if direction == "support" else None,
                invalidate_volume_x=1.5,
            )
        )
    return candidates


def _merge_candidates(candidates: list[KeyLevelCandidate]) -> list[KeyLevelCandidate]:
    merged: list[KeyLevelCandidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.direction, item.price)):
        existing = next(
            (
                item
                for item in merged
                if item.direction == candidate.direction
                and abs(item.price - candidate.price) / max(candidate.price, 0.01) <= 0.003
            ),
            None,
        )
        if existing is None:
            merged.append(candidate)
            continue
        evidence = list(dict.fromkeys([*existing.evidence, *candidate.evidence]))
        stronger = existing if existing.strength_score >= candidate.strength_score else candidate
        merged.remove(existing)
        merged.append(
            stronger.model_copy(
                update={
                    "strength_score": clamp_score(max(existing.strength_score, candidate.strength_score) + 8),
                    "evidence": evidence,
                    "zone_low": min(existing.zone_low, candidate.zone_low),
                    "zone_high": max(existing.zone_high, candidate.zone_high),
                }
            )
        )
    return sorted(merged, key=lambda item: abs(item.strength_score - 100), reverse=False)


def _nearest_candidate(
    candidates: list[KeyLevelCandidate],
    latest_price: float,
    direction: str,
) -> KeyLevelCandidate | None:
    same_direction = [item for item in candidates if item.direction == direction]
    if direction == "support":
        same_direction = [item for item in same_direction if item.price <= latest_price]
    elif direction == "resistance":
        same_direction = [item for item in same_direction if item.price >= latest_price]
    if not same_direction:
        return None
    return sorted(same_direction, key=lambda item: (abs(item.price - latest_price), -item.strength_score))[0]


def _build_proxy_rows(rows_by_symbol: dict[str, list[DailyBarRow]], *, instrument_type: str) -> list[DailyBarRow]:
    by_date: dict[str, list[DailyBarRow]] = {}
    for rows in rows_by_symbol.values():
        for row in rows:
            by_date.setdefault(str(row.trade_date), []).append(row)
    proxy_rows: list[DailyBarRow] = []
    for trade_date, rows in sorted(by_date.items()):
        if len(rows) < 2:
            continue
        proxy_rows.append(
            DailyBarRow(
                trade_date=trade_date,
                open_price=round(sum(float(row.open_price or 0) for row in rows) / len(rows), 4),
                close_price=round(sum(float(row.close_price or 0) for row in rows) / len(rows), 4),
                high_price=round(sum(float(row.high_price or 0) for row in rows) / len(rows), 4),
                low_price=round(sum(float(row.low_price or 0) for row in rows) / len(rows), 4),
                volume=sum(float(row.volume or 0) for row in rows),
                amount=sum(float(row.amount or 0) for row in rows),
                pct_chg=round(sum(float(row.pct_chg or 0) for row in rows) / len(rows), 4),
                adjusted_mode="qfq",
                data_quality="research_only",
                source=f"{instrument_type}_proxy",
            )
        )
    return proxy_rows


def _empty_result(
    *,
    symbol: str,
    name: str,
    scope: str,
    trade_date: str,
    latest_price: float,
    reason: str,
    data_quality: str = "insufficient",
) -> KeyLevelResult:
    return KeyLevelResult(
        symbol=symbol,
        name=name,
        scope=scope,  # type: ignore[arg-type]
        trade_date=trade_date,
        latest_price=round(latest_price, 4),
        engine_version=ENGINE_VERSION,
        as_of=trade_date,
        adjust_mode="qfq",
        intraday_included=False,
        data_quality=data_quality,  # type: ignore[arg-type]
        explanation="数据不足，仅观察。",
        warnings=[reason],
    )


def _explanation(
    *,
    support: KeyLevelCandidate | None,
    resistance: KeyLevelCandidate | None,
    latest_price: float,
) -> str:
    parts: list[str] = []
    if support:
        pct = distance_pct(latest_price, support.price)
        parts.append(f"离最近支撑约 {abs(pct or 0):.2f}%，来源：{'、'.join(support.evidence[:3])}。")
    if resistance:
        pct = distance_pct(latest_price, resistance.price)
        parts.append(f"离最近压力约 {abs(pct or 0):.2f}%，来源：{'、'.join(resistance.evidence[:3])}。")
    if not parts:
        return "关键位不清晰，数据仅用于观察。"
    return "".join(parts) + "仅用于观察和风控提醒。"


def _intraday_level_type(level_type: str):
    mapping = {
        "vwap": "intraday_vwap",
        "open": "open",
        "prev_close": "prev_close",
        "round_number": "round_number",
    }
    return mapping.get(level_type, "round_number")


def _parse_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])
