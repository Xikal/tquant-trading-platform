from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import LowBuyResultSnapshot, LowBuyScanSnapshot


class LowBuyResultRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch_latest_trade_date(self, strategy_key: str | None = None) -> str | None:
        statement = select(LowBuyScanSnapshot.latest_trade_date)
        if strategy_key is not None:
            statement = statement.where(LowBuyScanSnapshot.strategy_key == strategy_key)
        return (
            self.db.execute(
                statement.order_by(
                    desc(LowBuyScanSnapshot.latest_trade_date),
                    desc(LowBuyScanSnapshot.updated_at),
                    desc(LowBuyScanSnapshot.id),
                ).limit(1)
            )
            .scalars()
            .first()
        )

    def fetch_scan_summary(self, latest_trade_date: str, strategy_key: str) -> LowBuyScanSnapshot | None:
        return (
            self.db.execute(
                select(LowBuyScanSnapshot).where(
                    LowBuyScanSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyScanSnapshot.strategy_key == strategy_key,
                )
            )
            .scalars()
            .first()
        )

    def fetch_latest_scan_summary(self, strategy_key: str) -> LowBuyScanSnapshot | None:
        return (
            self.db.execute(
                select(LowBuyScanSnapshot)
                .where(LowBuyScanSnapshot.strategy_key == strategy_key)
                .order_by(
                    desc(LowBuyScanSnapshot.latest_trade_date),
                    desc(LowBuyScanSnapshot.updated_at),
                    desc(LowBuyScanSnapshot.id),
                )
            )
            .scalars()
            .first()
        )

    def fetch_latest_scan_summary_on_or_before(
        self,
        strategy_key: str,
        latest_trade_date: str,
    ) -> LowBuyScanSnapshot | None:
        return (
            self.db.execute(
                select(LowBuyScanSnapshot)
                .where(
                    LowBuyScanSnapshot.strategy_key == strategy_key,
                    LowBuyScanSnapshot.latest_trade_date <= latest_trade_date,
                )
                .order_by(
                    desc(LowBuyScanSnapshot.latest_trade_date),
                    desc(LowBuyScanSnapshot.updated_at),
                    desc(LowBuyScanSnapshot.id),
                )
            )
            .scalars()
            .first()
        )

    def fetch_recent_scan_summaries(
        self,
        strategy_key: str,
        limit: int = 6,
    ) -> list[LowBuyScanSnapshot]:
        return (
            self.db.execute(
                select(LowBuyScanSnapshot)
                .where(LowBuyScanSnapshot.strategy_key == strategy_key)
                .order_by(
                    desc(LowBuyScanSnapshot.latest_trade_date),
                    desc(LowBuyScanSnapshot.updated_at),
                    desc(LowBuyScanSnapshot.id),
                )
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def fetch_existing_scan_dates(self, strategy_key: str, trade_dates: list[str]) -> set[str]:
        if not trade_dates:
            return set()
        return set(
            self.db.execute(
                select(LowBuyScanSnapshot.latest_trade_date).where(
                    LowBuyScanSnapshot.strategy_key == strategy_key,
                    LowBuyScanSnapshot.latest_trade_date.in_(trade_dates),
                )
            ).scalars()
        )

    def fetch_results(
        self,
        latest_trade_date: str,
        strategy_key: str,
        limit: int | None = None,
    ) -> list[LowBuyResultSnapshot]:
        statement = (
            select(LowBuyResultSnapshot)
            .where(
                LowBuyResultSnapshot.latest_trade_date == latest_trade_date,
                LowBuyResultSnapshot.strategy_key == strategy_key,
            )
            .order_by(LowBuyResultSnapshot.score.desc())
        )
        if limit is not None:
            statement = statement.limit(limit)
        return self.db.execute(statement).scalars().all()

    def fetch_results_for_symbols(
        self,
        latest_trade_date: str,
        strategy_key: str,
        symbols: list[str],
    ) -> list[LowBuyResultSnapshot]:
        if not symbols:
            return []
        return (
            self.db.execute(
                select(LowBuyResultSnapshot).where(
                    LowBuyResultSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyResultSnapshot.strategy_key == strategy_key,
                    LowBuyResultSnapshot.symbol.in_(symbols),
                )
            )
            .scalars()
            .all()
        )

    def fetch_results_for_symbols_on_dates(
        self,
        strategy_key: str,
        latest_trade_dates: list[str],
        symbols: list[str],
        signal_states: tuple[str, ...] | None = None,
    ) -> list[LowBuyResultSnapshot]:
        if not latest_trade_dates or not symbols:
            return []
        statement = select(LowBuyResultSnapshot).where(
            LowBuyResultSnapshot.strategy_key == strategy_key,
            LowBuyResultSnapshot.latest_trade_date.in_(latest_trade_dates),
            LowBuyResultSnapshot.symbol.in_(symbols),
        )
        if signal_states:
            statement = statement.where(LowBuyResultSnapshot.buy_signal_state.in_(signal_states))
        return self.db.execute(statement).scalars().all()

    def fetch_confirmed_results(
        self,
        latest_trade_date: str,
        strategy_key: str,
        limit: int,
    ) -> list[LowBuyResultSnapshot]:
        return (
            self.db.execute(
                select(LowBuyResultSnapshot)
                .where(
                    LowBuyResultSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyResultSnapshot.strategy_key == strategy_key,
                    LowBuyResultSnapshot.buy_signal_state.in_(("buy_now", "soft_buy_now")),
                )
                .order_by(LowBuyResultSnapshot.score.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def fetch_confirmed_results_for_dates(
        self,
        latest_trade_dates: list[str],
        strategy_key: str,
        limit_per_date: int = 999,
    ) -> list[LowBuyResultSnapshot]:
        if not latest_trade_dates:
            return []
        rows = (
            self.db.execute(
                select(LowBuyResultSnapshot)
                .where(
                    LowBuyResultSnapshot.latest_trade_date.in_(latest_trade_dates),
                    LowBuyResultSnapshot.strategy_key == strategy_key,
                    LowBuyResultSnapshot.buy_signal_state.in_(("buy_now", "soft_buy_now")),
                )
                .order_by(
                    LowBuyResultSnapshot.latest_trade_date.asc(),
                    LowBuyResultSnapshot.score.desc(),
                )
            )
            .scalars()
            .all()
        )
        if limit_per_date <= 0:
            return rows
        counts: dict[str, int] = {}
        limited: list[LowBuyResultSnapshot] = []
        for row in rows:
            trade_date = str(row.latest_trade_date)
            count = counts.get(trade_date, 0)
            if count >= limit_per_date:
                continue
            limited.append(row)
            counts[trade_date] = count + 1
        return limited

    def fetch_reviewable_results(
        self,
        latest_trade_date: str,
        strategy_key: str,
        limit: int = 999,
    ) -> list[LowBuyResultSnapshot]:
        return (
            self.db.execute(
                select(LowBuyResultSnapshot)
                .where(
                    LowBuyResultSnapshot.latest_trade_date == latest_trade_date,
                    LowBuyResultSnapshot.strategy_key == strategy_key,
                    LowBuyResultSnapshot.buy_signal_state.in_(("buy_now", "soft_buy_now", "observe_confirmed", "near_entry")),
                )
                .order_by(LowBuyResultSnapshot.score.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def replace_materialized_scan(
        self,
        latest_trade_date: str,
        strategy_key: str,
        summary: LowBuyScanSnapshot,
        results: list[LowBuyResultSnapshot],
    ) -> None:
        self.db.execute(
            delete(LowBuyResultSnapshot).where(
                LowBuyResultSnapshot.latest_trade_date == latest_trade_date,
                LowBuyResultSnapshot.strategy_key == strategy_key,
            )
        )
        self.db.execute(
            delete(LowBuyScanSnapshot).where(
                LowBuyScanSnapshot.latest_trade_date == latest_trade_date,
                LowBuyScanSnapshot.strategy_key == strategy_key,
            )
        )
        self.db.add(summary)
        for row in results:
            self.db.add(row)
