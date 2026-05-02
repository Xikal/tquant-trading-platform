from __future__ import annotations

from dataclasses import dataclass
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot, Instrument, LowBuyStrategyPoolSnapshot
from app.repositories.low_buy import DailyHistoryRepository, LowBuyStrategyPoolRepository
from app.services.low_buy.shared import BoardCandidate
from app.services.low_buy.strategy_pool_config import STRATEGY_POOL_SNAPSHOT_VERSION, strategy_pool_profile


@dataclass(frozen=True)
class DailyPoolBar:
    symbol: str
    trade_date: str
    open_price: float
    close_price: float
    high_price: float
    low_price: float
    volume: float
    amount: float
    pct_chg: float


class StrategyPoolBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = LowBuyStrategyPoolRepository(db)

    def load_persisted(
        self,
        *,
        strategy: str,
        latest_trade_date: str,
        scan_limit: int,
    ) -> list[BoardCandidate] | None:
        profile = strategy_pool_profile(strategy)
        rows = self.repository.fetch(
            latest_trade_date=latest_trade_date,
            pool_key=profile.pool_key,
            strategy_key=strategy,
        )
        if not rows:
            return None
        rows = [row for row in rows if row.pool_version == STRATEGY_POOL_SNAPSHOT_VERSION]
        if not rows:
            return None
        return [
            BoardCandidate(
                symbol=row.symbol,
                name=row.name or row.symbol,
                board_date=row.anchor_date,
                board_count=row.board_count,
                amount=row.amount,
                industry=row.industry,
            )
            for row in rows[: self.pool_limit(strategy=strategy, scan_limit=scan_limit)]
        ]

    def build_from_ranked(
        self,
        *,
        strategy: str,
        ranked_pool: list[BoardCandidate],
        scan_limit: int,
    ) -> list[BoardCandidate]:
        return _dedupe_board_candidates(ranked_pool)[: self.pool_limit(strategy=strategy, scan_limit=scan_limit)]

    def build_from_daily_history(
        self,
        *,
        strategy: str,
        latest_trade_date: str,
        scan_limit: int,
        hot_industries: list[str],
        board_window_days: int,
        retracement_days_max: int,
    ) -> list[BoardCandidate]:
        recent_dates = [
            item
            for item in DailyHistoryRepository(self.db).fetch_recent_trade_dates(board_window_days + 8)
            if item <= latest_trade_date
        ]
        if len(recent_dates) < 8:
            return []
        rows_by_symbol = self._load_daily_rows_by_symbol(
            recent_dates=recent_dates,
            hot_industries=hot_industries,
        )
        date_index = {trade_date: index for index, trade_date in enumerate(recent_dates)}
        candidates: list[BoardCandidate] = []
        for rows in rows_by_symbol.values():
            candidate = self._build_daily_candidate(
                strategy=strategy,
                latest_trade_date=latest_trade_date,
                rows=rows,
                date_index=date_index,
                retracement_days_max=retracement_days_max,
            )
            if candidate is not None:
                candidates.append(candidate)
        candidates.sort(key=lambda item: (item.amount, item.board_date), reverse=True)
        return candidates[: self.pool_limit(strategy=strategy, scan_limit=scan_limit)]

    def persist(
        self,
        *,
        latest_trade_date: str,
        strategy: str,
        candidates: list[BoardCandidate],
    ) -> None:
        profile = strategy_pool_profile(strategy)
        rows = [
            LowBuyStrategyPoolSnapshot(
                latest_trade_date=latest_trade_date,
                pool_key=profile.pool_key,
                strategy_key=strategy,
                symbol=item.symbol,
                name=item.name,
                industry=item.industry,
                anchor_date=item.board_date,
                anchor_type=profile.source,
                rank_score=float(item.amount or 0.0) / 100000000,
                amount=float(item.amount or 0.0),
                board_count=int(item.board_count or 1),
                source=profile.source,
                pool_version=STRATEGY_POOL_SNAPSHOT_VERSION,
                features_json=json.dumps(
                    {
                        "pool_title": profile.title,
                        "pool_key": profile.pool_key,
                        "source": profile.source,
                        "pool_version": STRATEGY_POOL_SNAPSHOT_VERSION,
                    },
                    ensure_ascii=False,
                ),
            )
            for item in candidates
        ]
        self.repository.replace(
            latest_trade_date=latest_trade_date,
            pool_key=profile.pool_key,
            strategy_key=strategy,
            rows=rows,
        )

    @staticmethod
    def pool_limit(*, strategy: str, scan_limit: int) -> int:
        profile = strategy_pool_profile(strategy)
        requested = max(scan_limit, 1)
        return min(requested, profile.max_size)

    def _load_daily_rows_by_symbol(
        self,
        *,
        recent_dates: list[str],
        hot_industries: list[str],
    ) -> dict[str, list[tuple[DailyPoolBar, str, str]]]:
        instruments_by_symbol = self._load_instruments_by_symbol(hot_industries)
        if not instruments_by_symbol:
            return {}

        rows_by_symbol: dict[str, list[tuple[DailyPoolBar, str, str]]] = {}
        for chunk in _chunks(list(instruments_by_symbol), size=800):
            statement = (
                select(
                    DailyBarSnapshot.symbol,
                    DailyBarSnapshot.trade_date,
                    DailyBarSnapshot.open_price,
                    DailyBarSnapshot.close_price,
                    DailyBarSnapshot.high_price,
                    DailyBarSnapshot.low_price,
                    DailyBarSnapshot.volume,
                    DailyBarSnapshot.amount,
                    DailyBarSnapshot.pct_chg,
                )
                .where(
                    DailyBarSnapshot.symbol.in_(chunk),
                    DailyBarSnapshot.trade_date.in_(recent_dates),
                    DailyBarSnapshot.instrument_type == "stock",
                )
                .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
            )
            for row in self.db.execute(statement).all():
                (
                    symbol,
                    trade_date,
                    open_price,
                    close_price,
                    high_price,
                    low_price,
                    volume,
                    amount,
                    pct_chg,
                ) = row
                name, industry = instruments_by_symbol.get(str(symbol), (str(symbol), ""))
                bar = DailyPoolBar(
                    symbol=str(symbol),
                    trade_date=str(trade_date),
                    open_price=float(open_price or 0.0),
                    close_price=float(close_price or 0.0),
                    high_price=float(high_price or 0.0),
                    low_price=float(low_price or 0.0),
                    volume=float(volume or 0.0),
                    amount=float(amount or 0.0),
                    pct_chg=float(pct_chg or 0.0),
                )
                rows_by_symbol.setdefault(bar.symbol, []).append((bar, name, industry))
        return rows_by_symbol

    def _load_instruments_by_symbol(self, hot_industries: list[str]) -> dict[str, tuple[str, str]]:
        hot_set = {item.strip() for item in hot_industries if item.strip()}
        statement = (
            select(
                Instrument.symbol,
                Instrument.name,
                Instrument.sector_name,
            )
            .where(Instrument.instrument_type == "stock")
            .order_by(Instrument.symbol.asc())
        )
        if hot_set:
            statement = statement.where(Instrument.sector_name.in_(hot_set))
        instruments: dict[str, tuple[str, str]] = {}
        for symbol, name, sector_name in self.db.execute(statement).all():
            if _is_st_or_delist_name(str(name or "")):
                continue
            industry = str(sector_name or "").strip()
            instruments[str(symbol)] = (str(name or symbol), industry)
        return instruments

    def _build_daily_candidate(
        self,
        *,
        strategy: str,
        latest_trade_date: str,
        rows: list[tuple[DailyPoolBar, str, str]],
        date_index: dict[str, int],
        retracement_days_max: int,
    ) -> BoardCandidate | None:
        if not rows:
            return None
        latest_bar, latest_name, latest_industry = rows[-1]
        if latest_bar.trade_date != latest_trade_date:
            return None
        if not latest_daily_bar_matches_strategy_pool(strategy, latest_bar):
            return None
        latest_index = date_index.get(latest_trade_date)
        if latest_index is None:
            return None
        for index in range(len(rows) - 2, -1, -1):
            anchor, _, _ = rows[index]
            anchor_index = date_index.get(anchor.trade_date)
            if anchor_index is None:
                continue
            retracement_days = latest_index - anchor_index
            if retracement_days < 1:
                continue
            if retracement_days > retracement_days_max:
                break
            prior_rows = [row for row, _, _ in rows[max(0, index - 5) : index]]
            if daily_anchor_matches_strategy_pool(strategy, anchor, prior_rows):
                return BoardCandidate(
                    symbol=latest_bar.symbol,
                    name=latest_name or latest_bar.symbol,
                    board_date=anchor.trade_date,
                    board_count=1,
                    amount=float(latest_bar.amount or anchor.amount or 0.0),
                    industry=latest_industry,
                )
        return None


def latest_daily_bar_matches_strategy_pool(strategy: str, latest_bar: DailyPoolBar) -> bool:
    close_position = _daily_close_position(latest_bar)
    if strategy == "late_session_strong_support":
        return latest_bar.amount >= 100_000_000 and -2.5 <= latest_bar.pct_chg <= 6.8 and close_position >= 0.48
    if strategy == "core_midcap_vwap_ma5_retrace":
        return latest_bar.amount >= 180_000_000 and -5.0 <= latest_bar.pct_chg <= 3.2
    if strategy == "sector_mainline_first_divergence_low_buy":
        return latest_bar.amount >= 120_000_000 and -7.0 <= latest_bar.pct_chg <= 3.5
    return True


def daily_anchor_matches_strategy_pool(
    strategy: str,
    anchor: DailyPoolBar,
    prior_rows: list[DailyPoolBar],
) -> bool:
    if anchor.close_price <= 0 or anchor.open_price <= 0:
        return False
    avg_volume = sum(row.volume for row in prior_rows) / max(len(prior_rows), 1) if prior_rows else 0.0
    volume_ratio = anchor.volume / max(avg_volume, 1.0)
    strong_body = anchor.close_price >= anchor.open_price * 1.035 or anchor.pct_chg >= 3.0
    volume_ok = volume_ratio >= 1.15 or anchor.amount >= 180_000_000
    if strategy == "sector_mainline_first_divergence_low_buy":
        return strong_body and volume_ok and anchor.pct_chg >= 4.0
    return strong_body and volume_ok


def _daily_close_position(bar: DailyPoolBar) -> float:
    daily_range = max(float(bar.high_price or 0.0) - float(bar.low_price or 0.0), 0.01)
    return (float(bar.close_price or 0.0) - float(bar.low_price or 0.0)) / daily_range


def _is_st_or_delist_name(name: str) -> bool:
    upper_name = name.upper()
    return "ST" in upper_name or name.startswith("退市")


def _chunks(items: list[str], *, size: int) -> list[list[str]]:
    if size <= 0:
        return [items]
    return [items[index : index + size] for index in range(0, len(items), size)]


def _dedupe_board_candidates(items: list[BoardCandidate]) -> list[BoardCandidate]:
    seen: set[str] = set()
    result: list[BoardCandidate] = []
    for item in items:
        if item.symbol in seen:
            continue
        seen.add(item.symbol)
        result.append(item)
    return result
