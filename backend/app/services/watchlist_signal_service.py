from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import logging
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.entities import Watchlist
from app.models.schemas import AnalysisRequest
from app.repositories.watchlist_signals import WatchlistSignalSnapshotRepository
from app.services.analysis_service import AnalysisService
from app.services.market_data import MarketDataService, guess_instrument_type, guess_market
from app.services.settings_service import SettingsService
from app.services.watchlist_t1 import refresh_watchlist_t1_availability

logger = logging.getLogger(__name__)


class WatchlistSignalService:
    _refresh_lock = threading.Lock()
    _refresh_execution_lock = threading.Lock()
    _refresh_deadline = 0.0
    _snapshot_ttl_seconds = 20.0

    def __init__(self) -> None:
        self.market_data = MarketDataService()
        self._allow_parallel_analysis = not get_settings().database_url.startswith("sqlite")

    def list_signals(self, db: Session) -> list[dict]:
        if refresh_watchlist_t1_availability(db, model=Watchlist, today=datetime.now().date()):
            self.refresh_snapshots(force=True)
        rows = self._list_watchlist_rows(db)
        if not rows:
            return []

        snapshots = self._load_snapshot_payloads(db, rows)
        if self._should_refresh(rows, snapshots):
            self.ensure_background_refresh(force=False)

        if len(snapshots) < len(rows):
            self.ensure_background_refresh(force=True)

        return [self._public_snapshot_payload(snapshots.get(row.symbol, self._empty_snapshot_from_row(row))) for row in rows]

    def build_live_signals(self, db: Session, rows: list) -> list[dict]:
        if not rows:
            return []
        runtime_settings = SettingsService(db).get_payload()
        payloads = self._compute_snapshot_payloads(rows, runtime_settings)
        return [
            self._public_snapshot_payload(payloads.get(row.symbol, self._empty_snapshot_from_row(row)))
            for row in rows
        ]

    def fallback_signals_for_rows(self, rows: list, reason: str = "监控信号缓存仍在准备中。") -> list[dict]:
        """Build non-blocking watchlist cards for monitor fallbacks.

        The desktop monitor endpoint must not perform per-symbol analysis on the
        request thread.  These payloads keep the UI usable while a background
        refresh fills the richer signal cache.
        """

        return [
            self._public_snapshot_payload(self._fallback_snapshot_from_row(row, reason))
            for row in rows
        ]

    def ensure_background_refresh(self, force: bool = False) -> bool:
        now = time.monotonic()
        with self._refresh_lock:
            if not force and self._refresh_deadline > now:
                return False
            self._refresh_deadline = now + max(self._snapshot_ttl_seconds, 30.0)
        thread = threading.Thread(target=self._refresh_in_background, daemon=True)
        thread.start()
        return True

    def refresh_snapshots(self, force: bool = False) -> None:
        now = time.monotonic()
        with self._refresh_lock:
            if not force and self._refresh_deadline > now:
                return
            self._refresh_deadline = now + max(self._snapshot_ttl_seconds, 30.0)
        self._refresh_with_new_session()

    def invalidate_symbol(self, symbol: str) -> None:
        with SessionLocal() as db:
            WatchlistSignalSnapshotRepository(db).delete_symbol(symbol)
            db.commit()

    def _refresh_in_background(self) -> None:
        try:
            self._refresh_with_new_session()
        except Exception:
            logger.exception("watchlist signal background refresh failed")
        finally:
            with self._refresh_lock:
                self._refresh_deadline = 0.0

    def _refresh_with_new_session(self) -> None:
        with self._refresh_execution_lock:
            for attempt in range(2):
                try:
                    self._refresh_session_once()
                    return
                except StaleDataError:
                    if attempt == 1:
                        raise
                    logger.info("watchlist signal snapshot refresh retried after concurrent update")

    def _refresh_session_once(self) -> None:
        with SessionLocal() as db:
            refresh_watchlist_t1_availability(db, model=Watchlist, today=datetime.now().date())
            rows = self._list_watchlist_rows(db)
            repository = WatchlistSignalSnapshotRepository(db)
            if not rows:
                repository.delete_except([])
                db.commit()
                return

            runtime_settings = SettingsService(db).get_payload()
            payloads = self._compute_snapshot_payloads(rows, runtime_settings)
            serialized_payloads = {
                symbol: json.dumps(payload, ensure_ascii=False)
                for symbol, payload in payloads.items()
            }
            repository.upsert_many(serialized_payloads)
            repository.delete_except([row.symbol for row in rows])
            db.commit()

    def _compute_snapshot_payloads(self, rows: list[Watchlist], runtime_settings) -> dict[str, dict]:
        try:
            quote_map = self.market_data.get_quotes_batch([row.symbol for row in rows])
        except Exception:
            quote_map = {}

        def build_item(index: int, row: Watchlist) -> tuple[int, dict]:
            preloaded_quote = quote_map.get(row.symbol)
            try:
                with SessionLocal() as item_db:
                    service = AnalysisService()
                    result = service.analyze(
                        item_db,
                        AnalysisRequest(
                            symbol=row.symbol,
                            base_position=row.base_position,
                            available_position=row.available_position,
                            cost_basis=row.cost_basis,
                            include_ai=False,
                            include_events=False,
                            include_microstructure=False,
                        ),
                        persist=False,
                        runtime_settings=runtime_settings,
                        lightweight=True,
                        preloaded_quote=preloaded_quote,
                )
                display_name = self._display_name(
                    symbol=row.symbol,
                    stored_name=row.name,
                    resolved_names=[result.instrument.name, result.quote.name],
                )
                payload = {
                    "symbol": row.symbol,
                    "name": display_name,
                    "base_position": row.base_position,
                    "available_position": row.available_position,
                    "cost_basis": row.cost_basis,
                    "memo": row.memo,
                    "signal": result.suggestion.model_dump(),
                    "quote": result.quote.model_dump(),
                    "rules": result.rules.model_dump(),
                    "error": None,
                }
            except Exception as exc:
                message = f"信号计算失败: {exc}"
                fallback_name = self._display_name(
                    symbol=row.symbol,
                    stored_name=row.name,
                    resolved_names=[getattr(preloaded_quote, "name", "") if preloaded_quote is not None else ""],
                )
                payload = {
                    "symbol": row.symbol,
                    "name": fallback_name,
                    "base_position": row.base_position,
                    "available_position": row.available_position,
                    "cost_basis": row.cost_basis,
                    "memo": row.memo,
                    "signal": self._fallback_signal_payload(message),
                    "quote": (
                        preloaded_quote.model_dump()
                        if preloaded_quote is not None
                        else self._fallback_quote_payload(row.symbol, row.name or row.symbol)
                    ),
                    "rules": self._fallback_rule_payload(row.symbol),
                    "error": message,
                }
            return index, payload

        if len(rows) == 0:
            return {}
        if len(rows) == 1:
            return {row.symbol: build_item(index, row)[1] for index, row in enumerate(rows)}

        ordered_payloads: list[dict | None] = [None] * len(rows)
        max_workers = min(max(2, len(rows)), 10)
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="watchlist-signal") as executor:
            futures = [executor.submit(build_item, index, row) for index, row in enumerate(rows)]
            for future in as_completed(futures):
                try:
                    index, payload = future.result()
                    ordered_payloads[index] = payload
                except Exception:
                    logger.warning("watchlist signal build failed", exc_info=True)
        return {
            payload["symbol"]: payload
            for payload in ordered_payloads
            if payload is not None
        }

    def _load_snapshot_payloads(self, db: Session, rows: list[Watchlist]) -> dict[str, dict]:
        repository = WatchlistSignalSnapshotRepository(db)
        snapshots = repository.fetch_by_symbols([row.symbol for row in rows])
        payloads: dict[str, dict] = {}
        for snapshot in snapshots:
            try:
                payload = json.loads(snapshot.payload_json or "{}")
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            payloads[snapshot.symbol] = payload
            payload["_snapshot_updated_at"] = snapshot.updated_at.isoformat() if snapshot.updated_at else ""
        return payloads

    @staticmethod
    def _public_snapshot_payload(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if not key.startswith("_")}

    def _should_refresh(self, rows: list[Watchlist], snapshots: dict[str, dict]) -> bool:
        if len(snapshots) < len(rows):
            return True
        cutoff = datetime.now().timestamp() - self._snapshot_ttl_seconds
        for row in rows:
            payload = snapshots.get(row.symbol)
            if not payload:
                return True
            try:
                updated_at = datetime.fromisoformat(payload.get("_snapshot_updated_at", ""))
            except Exception:
                return True
            if updated_at.timestamp() < cutoff:
                return True
        return False

    @staticmethod
    def _list_watchlist_rows(db: Session) -> list[Watchlist]:
        return db.execute(select(Watchlist).order_by(Watchlist.id.desc())).scalars().all()

    def _empty_snapshot_from_row(self, row: Watchlist) -> dict:
        return self._fallback_snapshot_from_row(row, "监控信号缓存仍在准备中。")

    def _fallback_snapshot_from_row(self, row: Watchlist, reason: str) -> dict:
        return {
            "symbol": row.symbol,
            "name": self._display_name(symbol=row.symbol, stored_name=row.name, resolved_names=[]),
            "base_position": row.base_position,
            "available_position": row.available_position,
            "cost_basis": row.cost_basis,
            "memo": row.memo,
            "signal": self._fallback_signal_payload(reason),
            "quote": self._fallback_quote_payload(row.symbol, row.name or row.symbol),
            "rules": self._fallback_rule_payload(row.symbol),
            "error": reason,
        }

    @staticmethod
    def _fallback_quote_payload(symbol: str, name: str) -> dict:
        market = guess_market(symbol)
        instrument_type = guess_instrument_type(symbol, name)
        return {
            "symbol": symbol,
            "name": name or symbol,
            "market": market,
            "instrument_type": instrument_type,
            "last_price": 0.0,
            "change_pct": 0.0,
            "change_amount": 0.0,
            "open_price": 0.0,
            "high_price": 0.0,
            "low_price": 0.0,
            "prev_close": 0.0,
            "volume": 0.0,
            "amount": 0.0,
            "turnover_rate": None,
            "volume_ratio": None,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @staticmethod
    def _fallback_signal_payload(error_message: str) -> dict:
        return {
            "action": "hold",
            "entry_price": None,
            "exit_price": None,
            "position_pct": 0.0,
            "stop_loss": None,
            "risk_level": "high",
            "signal_score": 0.0,
            "tradability_score": 0.0,
            "confidence": 0.0,
            "expected_profit_pct": 0.0,
            "scenario": "signal_snapshot_pending",
            "reasons": ["监控缓存正在刷新，暂时按观望处理。"],
            "blocking_rules": [error_message],
            "take_profit": None,
            "strategy_notes": "稍后会自动刷新为最新监控结果。",
            "plain_action_text": "今天别动",
            "plain_action_reason": error_message,
            "plain_execution_text": "监控信号还在刷新，先不要按旧数据操作。",
            "plain_invalid_condition": "刷新失败期间只做风险控制，不做新增交易。",
        }

    @staticmethod
    def _fallback_rule_payload(symbol: str) -> dict:
        return {
            "symbol": symbol,
            "turnaround_mode": "t1",
            "supports_positive_t": True,
            "supports_negative_t": True,
            "same_day_sell_allowed": False,
            "requires_base_position": True,
            "notes": "监控缓存准备中时返回默认制度说明。",
        }

    @staticmethod
    def _display_name(*, symbol: str, stored_name: str | None, resolved_names: list[str | None]) -> str:
        cleaned_symbol = symbol.strip()
        stored = (stored_name or "").strip()
        if stored and stored != cleaned_symbol:
            return stored
        for name in resolved_names:
            cleaned = (name or "").strip()
            if cleaned and cleaned != cleaned_symbol:
                return cleaned
        return stored or cleaned_symbol
