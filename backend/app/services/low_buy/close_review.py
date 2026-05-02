from __future__ import annotations

from app.models.entities import LowBuyCloseReviewSnapshot
from app.repositories.low_buy import (
    LowBuyCloseReviewRepository,
    LowBuyResultRepository,
)
from app.services.low_buy.shared import (
    LowBuyCandidateOut,
    LowBuyCloseReviewItemOut,
    Session,
    datetime,
)


class LowBuyCloseReviewMixin:
    _close_review_states = ("buy_now", "soft_buy_now", "near_entry")

    def _attach_close_review_snapshot(
        self,
        db: Session,
        payload,
        review_trade_date: str,
        build_if_missing: bool = False,
    ):
        snapshot = self._load_close_review_snapshot(
            db=db,
            strategy=payload.strategy_key,
            latest_trade_date=review_trade_date,
        )
        if snapshot is None and build_if_missing:
            self._build_close_review_snapshot(
                db=db,
                strategy=payload.strategy_key,
                latest_trade_date=review_trade_date,
            )
            snapshot = self._load_close_review_snapshot(
                db=db,
                strategy=payload.strategy_key,
                latest_trade_date=review_trade_date,
            )
        if snapshot is None:
            return payload
        return payload.model_copy(
            update={
                "close_review_trade_date": review_trade_date,
                "close_review_updated_at": snapshot["updated_at"],
                "close_review_items": snapshot["items"],
            }
        )

    def _load_close_review_snapshot(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
    ) -> dict[str, object] | None:
        rows = LowBuyCloseReviewRepository(db).fetch(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
        )
        if not rows:
            return None
        items: list[LowBuyCloseReviewItemOut] = []
        updated_at = ""
        for row in rows:
            try:
                items.append(LowBuyCloseReviewItemOut.model_validate_json(row.payload_json))
            except Exception:
                continue
            if row.updated_at is not None:
                row_timestamp = row.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                updated_at = max(updated_at, row_timestamp)
        return {"items": items, "updated_at": updated_at}

    def _build_close_review_snapshot(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
    ) -> list[LowBuyCloseReviewItemOut]:
        self._ensure_historical_materialization(db=db, strategy=strategy, trade_dates=[latest_trade_date])
        rows = LowBuyResultRepository(db).fetch_reviewable_results(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
        )
        items = self._build_close_review_items(rows=rows, latest_trade_date=latest_trade_date)
        self._save_close_review_snapshot(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            items=items,
        )
        return items

    def _build_close_review_items(
        self,
        rows: list[LowBuyCloseReviewSnapshot | object],
        latest_trade_date: str,
    ) -> list[LowBuyCloseReviewItemOut]:
        items: list[LowBuyCloseReviewItemOut] = []
        for row in rows:
            payload_json = getattr(row, "payload_json", "")
            if not payload_json:
                continue
            try:
                candidate = LowBuyCandidateOut.model_validate_json(payload_json)
            except Exception:
                continue
            history = self._load_daily_history(
                symbol=candidate.symbol,
                latest_trade_date=latest_trade_date,
                history_window_days=80,
            )
            if history is None or history.empty:
                continue
            matches = history.index[history["date"] == latest_trade_date].tolist()
            if not matches:
                continue
            items.append(
                self._build_close_review_item(
                    candidate=candidate,
                    latest_bar=history.iloc[matches[-1]],
                    latest_trade_date=latest_trade_date,
                )
            )
        items.sort(
            key=lambda item: (
                self._signal_rank(item.signal_state),
                item.change_pct,
                -item.entry_distance_pct,
            ),
            reverse=True,
        )
        return items

    def _build_close_review_item(
        self,
        candidate: LowBuyCandidateOut,
        latest_bar,
        latest_trade_date: str,
    ) -> LowBuyCloseReviewItemOut:
        close_price = round(float(latest_bar["close"]), 3)
        pct_chg = round(float(latest_bar["pct_chg"]), 2)
        high_price = float(latest_bar["high"])
        low_price = float(latest_bar["low"])
        amplitude_pct = round(self._close_review_amplitude_pct(close_price, pct_chg, high_price, low_price), 2)
        entry_position = self._entry_position(candidate, close_price)
        entry_distance_pct = self._distance_to_entry_zone_pct(candidate, close_price)
        close_vs_stop_pct = round(
            ((close_price / max(candidate.stop_loss, 0.01)) - 1) * 100,
            2,
        )
        review_level, review_text = self._resolve_close_review(candidate, entry_position, close_vs_stop_pct)
        return LowBuyCloseReviewItemOut(
            symbol=candidate.symbol,
            name=candidate.name,
            signal_state=candidate.buy_signal_state,
            signal_text=candidate.buy_signal_text,
            review_trade_date=latest_trade_date,
            close_price=close_price,
            change_pct=pct_chg,
            amplitude_pct=amplitude_pct,
            entry_zone_low=round(candidate.entry_zone_low, 3),
            entry_zone_high=round(candidate.entry_zone_high, 3),
            stop_loss=round(candidate.stop_loss, 3),
            entry_distance_pct=round(entry_distance_pct, 3),
            entry_distance_text=self._close_review_entry_text(entry_position, entry_distance_pct),
            close_vs_stop_pct=close_vs_stop_pct,
            review_level=review_level,
            review_text=review_text,
        )

    def _save_close_review_snapshot(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        items: list[LowBuyCloseReviewItemOut],
    ) -> None:
        rows = [
            LowBuyCloseReviewSnapshot(
                latest_trade_date=latest_trade_date,
                strategy_key=strategy,
                symbol=item.symbol,
                signal_state=item.signal_state,
                payload_json=item.model_dump_json(),
            )
            for item in items
        ]
        LowBuyCloseReviewRepository(db).replace(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
            rows=rows,
        )
        db.commit()

    @staticmethod
    def _close_review_amplitude_pct(
        close_price: float,
        pct_chg: float,
        high_price: float,
        low_price: float,
    ) -> float:
        denominator = 1 + pct_chg / 100
        if close_price <= 0 or denominator <= 0:
            return 0.0
        prev_close = close_price / denominator
        if prev_close <= 0:
            return 0.0
        return ((high_price - low_price) / prev_close) * 100

    @staticmethod
    def _close_review_entry_text(entry_position: str, entry_distance_pct: float) -> str:
        if entry_position == "in_zone":
            return "收盘落在买点区内"
        if entry_position == "near_above_zone":
            return f"高于买点区 {entry_distance_pct:.2f}%"
        if entry_position == "above_zone":
            return f"高于买点区 {entry_distance_pct:.2f}%"
        if entry_position == "below_zone":
            return f"低于买点区 {entry_distance_pct:.2f}%"
        if entry_position == "below_stop":
            return "收盘逼近或跌破止损位"
        return "买点位置待确认"

    @staticmethod
    def _resolve_close_review(
        candidate: LowBuyCandidateOut,
        entry_position: str,
        close_vs_stop_pct: float,
    ) -> tuple[str, str]:
        if close_vs_stop_pct <= 0.3 or entry_position == "below_stop":
            return "risk", "收盘已逼近或跌破止损位，次日不再按低吸逻辑处理。"
        if candidate.buy_signal_state in {"buy_now", "soft_buy_now"}:
            if entry_position == "in_zone":
                return "good", "收盘仍停留在买点区内，次日重点看承接是否延续。"
            if entry_position == "near_above_zone":
                return "neutral", "收盘略高于买点区，次日不追高，只等回踩确认。"
            if entry_position == "below_zone":
                return "neutral", "收盘跌穿买点区但未失守止损，次日先看止跌再决定。"
            return "neutral", "收盘已经抬离买点区，次日只看回踩承接，不直接追价。"
        if entry_position == "in_zone":
            return "neutral", "收盘进入买点区，但确认还差一步，次日先看止跌和承接。"
        if entry_position == "below_zone":
            return "risk", "收盘跌入买点区下方，说明分歧偏大，次日不能机械抄底。"
        return "neutral", "收盘仍在买点区上方，结构还在，但继续等价格回踩到位。"
