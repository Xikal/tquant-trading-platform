from __future__ import annotations

import logging
import json
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, time as datetime_time, timedelta
from math import floor
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.timezone import BEIJING_TZ, beijing_now
from app.models.entities import PaperAccount, PaperAgentRun, PaperOrder, PaperPosition, RiskEvent, User
from app.services.market.trading_calendar import is_a_share_trading_day
from app.services.market_data import MarketDataService
from app.services.low_buy.holding_policy import strategy_holding_policy
from app.services.low_buy.service import LowBuyScreenerService
from app.services.paper.admission import AdmissionFilter
from app.services.paper.executor import PaperTradingExecutor
from app.services.paper.matching import PaperMatchingEngine
from app.services.paper.order import PaperOrderService
from app.services.paper.position import PaperPositionService
from app.services.paper.sizing import PositionSizer, SizedOrder
from app.services.quant.runtime_parameters import get_market_sector_etf_t0
from app.services.sector_etf_t0 import SectorEtfT0Service
from app.services.user_sector_preferences import UserSectorPreferenceService

logger = logging.getLogger(__name__)


@dataclass
class AutoTraderState:
    running: bool = False
    dry_run: bool = True
    interval_seconds: int = 120
    max_orders_per_cycle: int = 5
    min_score: int = 75
    last_cycle_at: str = ""
    last_cycle_duration_ms: float = 0.0
    last_cycle_passed: int = 0
    last_cycle_filtered: int = 0
    last_cycle_executed: int = 0
    last_cycle_skipped: int = 0
    last_cycle_summary: str = ""
    total_cycles: int = 0
    total_executed: int = 0
    total_errors: int = 0
    circuit_open: bool = False
    circuit_reason: str = ""
    circuit_since: str = ""
    heartbeat_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PaperAutoTrader:
    """In-process automatic paper-trading loop.

    The loop only consumes existing priority-board signals and uses the paper
    trading services for risk checks, matching and settlement. It never changes
    strategy logic and defaults to dry-run.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.state = AutoTraderState(
            dry_run=bool(config.get("dry_run", True)),
            interval_seconds=int(config.get("interval_seconds", 120)),
            max_orders_per_cycle=int(config.get("max_orders_per_cycle", 5)),
            min_score=int(config.get("min_score", 75)),
        )
        self._consecutive_errors = 0
        self._circuit_until: datetime | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.state.running:
            return
        self._stop_event.clear()
        self.state.running = True
        self._thread = threading.Thread(target=self.run_loop, name="paper-auto-trader", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop_event.set()
        self.state.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.state.heartbeat_at = _beijing_now_naive().isoformat(timespec="seconds")
            try:
                if not is_trading_time():
                    self._sleep(60)
                    continue
                if self._circuit_open():
                    self._sleep(30)
                    continue
                self._run_one_cycle_with_retry()
                self._consecutive_errors = 0
            except Exception:
                logger.exception("自动交易循环异常")
                self.state.total_errors += 1
                self._consecutive_errors += 1
                if self._consecutive_errors >= 3:
                    self._open_circuit("连续 3 次循环异常")
            self._sleep(max(self.state.interval_seconds, 1))
        self.state.running = False

    def run_once_for_preview(self, *, db: Session, limit: int = 20, account_id: int | None = None) -> dict[str, Any]:
        board = self._fetch_priority_board(db=db, limit=limit)
        if not board["items"]:
            return {"error": "无优先级信号", "will_buy": [], "filtered": [], "summary": "无优先级信号"}
        account = self._get_account(db, account_id=account_id) if account_id else self._get_active_account(db)
        if account is None:
            return {"error": "无活跃模拟账户", "will_buy": [], "filtered": [], "summary": "无活跃模拟账户"}
        positions = self._get_positions_summary(db, account)
        today_orders = self._get_today_orders(db, account.id)
        report = AdmissionFilter(min_score=self.state.min_score).evaluate(
            signals=board["items"],
            existing_positions=positions,
            today_orders=today_orders,
            market_direction=board.get("directional_bias"),
            excluded_sectors=UserSectorPreferenceService(db).get_excluded_sector_set(account.user_id)
            if account.user_id
            else set(),
        )
        sized = PositionSizer().calculate(
            candidates=report.passed,
            total_assets=float(account.total_assets or 0),
            available_cash=float(account.cash_available or 0),
            max_orders=self.state.max_orders_per_cycle,
            current_positions=_position_values_by_symbol(positions),
        )
        etf_orders = self._build_sector_etf_t0_orders(
            db=db,
            account=account,
            board=board,
            today_orders=today_orders,
            used_order_count=len(sized),
        )
        return {
            "market_state": board.get("market_state", ""),
            "directional_bias": board.get("directional_bias", "neutral"),
            "will_buy": [*_sized_order_summary_list(sized), *[_planned_order_summary(item) for item in etf_orders]],
            "sector_etf_t0_will_buy": [_planned_order_summary(item) for item in etf_orders],
            "sector_etf_t0_order_count": len(etf_orders),
            "filtered": [
                {"symbol": item.symbol, "score": item.priority_score, "reason": item.reason}
                for item in report.filtered
            ],
            "summary": report.summary,
        }

    def _run_one_cycle(self) -> None:
        started = time.monotonic()
        try:
            with SessionLocal() as db:
                board = self._fetch_priority_board(db=db, limit=20)
                if not board["items"]:
                    self._record_cycle(passed=0, filtered=0, summary="无优先级信号")
                    return

                accounts = self._get_active_accounts(db)
                if not accounts:
                    self._record_cycle(passed=0, filtered=0, summary="无活跃模拟账户")
                    return

                aggregate = _CycleAggregate()
                for account in accounts:
                    result = self._run_account_cycle(db=db, account=account, board=board)
                    aggregate.add(result)
                self._record_cycle(
                    passed=aggregate.passed,
                    filtered=aggregate.filtered,
                    summary=aggregate.summary(),
                    executed=aggregate.executed,
                    skipped=aggregate.skipped,
                )
        finally:
            self.state.last_cycle_duration_ms = round((time.monotonic() - started) * 1000, 1)

    def _run_account_cycle(self, *, db: Session, account: PaperAccount, board: dict[str, Any]) -> dict[str, Any]:
        run: PaperAgentRun | None = None
        try:
            blocking_reason = self._blocking_reason(db, account.id)
            if blocking_reason:
                result = {
                    "passed": 0,
                    "filtered": 0,
                    "executed": [],
                    "skipped": [{"account_id": account.id, "reason": blocking_reason}],
                    "summary": f"账户风控阻断：{blocking_reason}",
                }
                if self._should_persist_blocked_run(db, account_id=account.id, blocking_reason=blocking_reason):
                    run = self._start_run(db, account_id=account.id, board=board)
                    self._finish_run(db, run, status="skipped", response=result)
                return result
            run = self._start_run(db, account_id=account.id, board=board)
            result = self._build_and_execute_account_plan(db=db, account=account, board=board)
            status = "succeeded" if result.get("executed") else "skipped"
            self._finish_run(db, run, status=status, response=result)
            return result
        except Exception as exc:
            db.rollback()
            if run is not None:
                persisted = db.get(PaperAgentRun, run.id)
                if persisted:
                    self._finish_run(db, persisted, status="failed", response={}, error=str(exc))
            logger.exception("模拟账户自动交易失败 account_id=%s", account.id)
            return {
                "passed": 0,
                "filtered": 0,
                "executed": [],
                "skipped": [{"account_id": account.id, "reason": "账户自动交易失败"}],
                "summary": "账户自动交易失败",
            }

    def _build_and_execute_account_plan(self, *, db: Session, account: PaperAccount, board: dict[str, Any]) -> dict[str, Any]:
        positions = self._get_positions_summary(db, account)
        today_orders = self._get_today_orders(db, account.id)
        report = AdmissionFilter(min_score=self.state.min_score).evaluate(
            signals=board["items"],
            existing_positions=positions,
            today_orders=today_orders,
            market_direction=board.get("directional_bias"),
            excluded_sectors=UserSectorPreferenceService(db).get_excluded_sector_set(account.user_id)
            if account.user_id
            else set(),
        )
        exit_orders = self._build_exit_orders(db, account)
        orders = PositionSizer().calculate(
            candidates=report.passed,
            total_assets=float(account.total_assets or 0),
            available_cash=float(account.cash_available or 0),
            max_orders=self.state.max_orders_per_cycle,
            current_positions=_position_values_by_symbol(positions),
        )
        etf_orders = self._build_sector_etf_t0_orders(
            db=db,
            account=account,
            board=board,
            today_orders=today_orders,
            used_order_count=len(exit_orders) + len(orders),
        )
        planned_orders = [*exit_orders, *orders, *etf_orders]
        if not planned_orders:
            summary = report.summary if not report.passed else "资金不足、候选不够或没有触发退出计划"
            return {
                "passed": len(report.passed),
                "filtered": len(report.filtered),
                "executed": [],
                "skipped": [],
                "summary": summary,
                "exit_order_count": len(exit_orders),
                "buy_order_count": len(orders),
                "sector_etf_t0_order_count": len(etf_orders),
                "filtered_reasons": [
                    {"symbol": item.symbol, "score": item.priority_score, "reason": item.reason}
                    for item in report.filtered[:5]
                ],
            }
        result = self._execute_orders(db=db, account_id=account.id, orders=planned_orders)
        return {
            **result,
            "passed": len(report.passed),
            "filtered": len(report.filtered),
            "exit_order_count": len(exit_orders),
            "buy_order_count": len(orders),
            "sector_etf_t0_order_count": len(etf_orders),
        }

    def _run_one_cycle_with_retry(self) -> None:
        retry_delays = (1, 2, 4)
        for attempt, delay in enumerate((0, *retry_delays), start=1):
            if delay:
                self._sleep(delay)
            try:
                self._run_one_cycle()
                return
            except OperationalError as exc:
                if not _is_database_busy(exc):
                    raise
                if attempt > len(retry_delays):
                    self._record_cycle(passed=0, filtered=0, summary="数据库忙，本轮跳过")
                    return
                logger.warning("自动交易数据库忙，准备重试：%s", exc)

    def _fetch_priority_board(self, *, db: Session, limit: int) -> dict[str, Any]:
        board = LowBuyScreenerService().priority_board(db=db, limit=limit)
        return {
            "items": [item.model_dump() for item in getattr(board, "items", [])],
            "market_state": getattr(board, "market_state", ""),
            "directional_bias": getattr(board, "directional_bias", "neutral"),
        }

    def _get_active_account(self, db: Session) -> PaperAccount | None:
        accounts = self._get_active_accounts(db)
        return accounts[0] if accounts else None

    def _get_active_accounts(self, db: Session) -> list[PaperAccount]:
        accounts = (
            db.execute(
                select(PaperAccount)
                .outerjoin(User, PaperAccount.user_id == User.id)
                .where(PaperAccount.status.in_(["active", "paused"]))
                .where(
                    (PaperAccount.user_id.is_(None))
                    | ((User.is_active.is_(True)) & (User.can_paper_trade.is_(True)))
                )
                .order_by(PaperAccount.id.asc())
            )
            .scalars()
            .all()
        )
        self._activate_auto_managed_accounts(db, accounts)
        return accounts

    def _get_account(self, db: Session, *, account_id: int) -> PaperAccount | None:
        account = db.execute(
            select(PaperAccount)
            .where(PaperAccount.id == account_id)
            .where(PaperAccount.status.in_(["active", "paused"]))
        ).scalar_one_or_none()
        self._activate_auto_managed_accounts(db, [account] if account else [])
        return account

    @staticmethod
    def _activate_auto_managed_accounts(db: Session, accounts: list[PaperAccount]) -> None:
        blocked_ids = _blocking_account_ids(db, [account.id for account in accounts])
        changed = False
        for account in accounts:
            if account.id in blocked_ids:
                continue
            if account.status == "paused":
                account.status = "active"
                db.add(account)
                changed = True
        if changed:
            db.commit()

    @staticmethod
    def _blocking_reason(db: Session, account_id: int) -> str:
        return _blocking_reason(db, account_id)

    @staticmethod
    def _should_persist_blocked_run(db: Session, *, account_id: int, blocking_reason: str) -> bool:
        return _should_persist_blocked_run(db, account_id=account_id, blocking_reason=blocking_reason)

    def _get_positions_summary(self, db: Session, account: PaperAccount) -> list[dict[str, Any]]:
        rows = db.execute(
            select(PaperPosition).where(PaperPosition.account_id == account.id, PaperPosition.quantity > 0)
        ).scalars().all()
        total_assets = max(float(account.total_assets or 0), 1.0)
        now = _beijing_now_naive()
        return [
            {
                "symbol": row.symbol,
                "hold_days": max((now - row.opened_at).days, 0) if row.opened_at else 0,
                "position_pct": float(row.market_value or 0) / total_assets * 100,
                "market_value": float(row.market_value or 0),
            }
            for row in rows
        ]

    def _get_today_orders(self, db: Session, account_id: int) -> list[dict[str, Any]]:
        start = datetime.combine(_beijing_now_naive().date(), datetime_time.min)
        rows = db.execute(
            select(PaperOrder).where(
                PaperOrder.account_id == account_id,
                PaperOrder.created_at >= start,
            )
        ).scalars().all()
        return [{"symbol": row.symbol, "status": row.status, "side": row.side, "source": row.source} for row in rows]

    def _execute_orders(self, *, db: Session, account_id: int, orders: list[SizedOrder | dict[str, Any]]) -> dict[str, Any]:
        executor = PaperTradingExecutor(PaperOrderService(db, PaperMatchingEngine()))
        return executor.execute_plan(
            account_id=account_id,
            planned_orders=[item.to_plan_dict() if isinstance(item, SizedOrder) else item for item in orders],
            max_orders=self.state.max_orders_per_cycle,
            dry_run=self.state.dry_run,
        )

    def _build_exit_orders(self, db: Session, account: PaperAccount) -> list[dict[str, Any]]:
        positions = PaperPositionService(db).get_positions(account.id)
        if not positions:
            return []
        prices = self._latest_prices([row.symbol for row in positions])
        orders: list[dict[str, Any]] = []
        now = _beijing_now_naive()
        for row in positions:
            price = prices.get(row.symbol) or float(row.latest_price or 0)
            quantity = _exit_quantity(row, price=price, now=now)
            if quantity <= 0:
                continue
            reason = _exit_reason(row, price=price, now=now)
            strategy_key = _primary_strategy_from_position(row) or "paper_exit_plan"
            orders.append({
                "symbol": row.symbol,
                "name": row.name or row.symbol,
                "side": "sell",
                "order_type": "market",
                "quantity": quantity,
                "price": price,
                "current_price": price,
                "quote_time": now,
                "source": "auto_exit",
                "strategy_key": strategy_key,
                "reason": reason,
                "signal_snapshot": {"exit_reason": reason, "cost_basis": float(row.cost_basis or 0), "strategy_key": strategy_key},
            })
        return orders

    def _build_sector_etf_t0_orders(
        self,
        *,
        db: Session,
        account: PaperAccount,
        board: dict[str, Any],
        today_orders: list[dict[str, Any]],
        used_order_count: int,
    ) -> list[dict[str, Any]]:
        params = _sector_etf_t0_params()
        if not bool(params.get("paper_auto_enabled", True)):
            return []
        if str(board.get("market_state") or "") in set(params.get("paper_auto_blocked_market_states") or []):
            return []
        remaining_slots = min(
            max(int(params.get("paper_auto_max_orders") or 0), 0),
            max(self.state.max_orders_per_cycle - used_order_count, 0),
        )
        if remaining_slots <= 0 or float(account.cash_available or 0) <= 0:
            return []
        today_symbols = _today_order_symbols(today_orders)
        etf_service = SectorEtfT0Service(market_data=MarketDataService(), low_buy=None)
        if db is not None:
            acceptance = etf_service.historical_acceptance(db, params=params)
            if not acceptance.get("production_ready"):
                logger.info(
                    "ETF T+0 自动执行未通过统计验收：settled=%s success_rate=%.2f p=%.4f",
                    acceptance.get("settled_count"),
                    float(acceptance.get("success_rate_pct") or 0.0),
                    float(acceptance.get("p_value") or 1.0),
                )
                return []
        response = etf_service.build_from_priority_board(
            board,
            limit=max(remaining_slots * 2, 2),
        )
        orders: list[dict[str, Any]] = []
        cash_budget = float(account.cash_available or 0) * _float_param(params, "paper_auto_cash_pct", 0.12)
        min_confidence = _float_param(params, "paper_auto_min_confidence", 68.0)
        min_edge = _float_param(params, "paper_auto_min_edge_pct", 0.9)
        now = _beijing_now_naive()
        for item in response.opportunities:
            if len(orders) >= remaining_slots:
                break
            if item.etf_symbol in today_symbols or item.bias != "positive_t":
                continue
            if item.confidence < min_confidence or item.expected_edge_pct < min_edge or item.last_price <= 0:
                continue
            quantity = _round_lot(cash_budget / item.last_price)
            if quantity < 100:
                continue
            orders.append(
                {
                    "symbol": item.etf_symbol,
                    "name": item.etf_name,
                    "side": "buy",
                    "order_type": "market",
                    "quantity": quantity,
                    "price": item.last_price,
                    "current_price": item.last_price,
                    "quote_time": now,
                    "source": "auto_sector_etf_t0",
                    "strategy_key": "sector_etf_t0",
                    "reason": f"自动调入: 行业ETF T+0，{item.reason}",
                    "signal_snapshot": {
                        **item.model_dump(),
                        "strategy_key": "sector_etf_t0",
                        "market_state": board.get("market_state"),
                        "position_cap_source": "sector_etf_t0_cash_budget",
                        "position_cap_reason": f"ETF T+0 单笔使用可用资金约 {cash_budget:.0f} 元上限",
                    },
                }
            )
        return orders

    def _latest_prices(self, symbols: list[str]) -> dict[str, float]:
        try:
            quotes = MarketDataService().get_quotes_batch(symbols)
        except Exception:
            logger.warning("自动退出计划批量行情失败，回退持仓最新价", exc_info=True)
            return {}
        return {symbol: float(quote.last_price or 0) for symbol, quote in quotes.items() if float(quote.last_price or 0) > 0}

    def _start_run(self, db: Session, *, account_id: int, board: dict[str, Any]) -> PaperAgentRun:
        row = PaperAgentRun(
            account_id=account_id,
            provider="paper_auto_trader",
            run_type="auto_trade_cycle",
            status="running",
            request_json=json.dumps(
                {
                    "dry_run": self.state.dry_run,
                    "max_orders_per_cycle": self.state.max_orders_per_cycle,
                    "min_score": self.state.min_score,
                    "signal_count": len(board.get("items") or []),
                    "market_state": board.get("market_state"),
                    "directional_bias": board.get("directional_bias"),
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def _finish_run(
        self,
        db: Session,
        run: PaperAgentRun,
        *,
        status: str,
        response: dict[str, Any],
        error: str = "",
    ) -> None:
        run.status = status
        run.response_json = json.dumps(response, ensure_ascii=False, default=str)
        run.error_message = error[:240]
        db.add(run)
        db.commit()

    def _is_trading_time(self, now: datetime | None = None) -> bool:
        return is_trading_time(now)

    def _circuit_open(self) -> bool:
        if self._circuit_until and _beijing_now_naive() < self._circuit_until:
            return True
        if self._circuit_until:
            logger.info("自动交易熔断器恢复")
            self._circuit_until = None
            self._consecutive_errors = 0
            self.state.circuit_open = False
            self.state.circuit_reason = ""
        return False

    def _open_circuit(self, reason: str) -> None:
        now = _beijing_now_naive()
        self._circuit_until = now + timedelta(seconds=300)
        self.state.circuit_open = True
        self.state.circuit_reason = reason
        self.state.circuit_since = now.isoformat(timespec="seconds")
        logger.warning("自动交易熔断器开启：%s，暂停至 %s", reason, self._circuit_until)

    def _record_cycle(self, *, passed: int, filtered: int, summary: str, executed: int = 0, skipped: int = 0) -> None:
        self.state.last_cycle_at = _beijing_now_naive().isoformat(timespec="seconds")
        self.state.last_cycle_passed = passed
        self.state.last_cycle_filtered = filtered
        self.state.last_cycle_executed = executed
        self.state.last_cycle_skipped = skipped
        self.state.last_cycle_summary = summary
        self.state.total_cycles += 1
        self.state.total_executed += executed
        if executed > 0:
            logger.info("自动交易循环：%s，通过%d，执行%d", summary, passed, executed)
        elif passed > 0:
            logger.info("自动交易循环：%s，通过%d，跳过%d", summary, passed, skipped)

    def _sleep(self, seconds: int) -> None:
        self._stop_event.wait(max(seconds, 0))


_auto_trader: PaperAutoTrader | None = None
_auto_trader_lock = threading.Lock()


def get_auto_trader() -> PaperAutoTrader | None:
    return _auto_trader


def build_auto_trader_config(settings: Any, *, dry_run: bool | None = None) -> dict[str, Any]:
    return {
        "dry_run": settings.paper_auto_trading_dry_run if dry_run is None else dry_run,
        "interval_seconds": settings.paper_auto_trading_interval,
        "max_orders_per_cycle": settings.paper_auto_trading_max_orders,
        "min_score": settings.paper_auto_trading_min_score,
    }


def ensure_auto_trader(config: dict[str, Any], *, now: datetime | None = None) -> PaperAutoTrader | None:
    """Keep paper auto-trading available during A-share trading sessions."""

    if not is_trading_time(now):
        return get_auto_trader()
    return start_auto_trader(config)


def start_auto_trader(config: dict[str, Any]) -> PaperAutoTrader:
    global _auto_trader
    with _auto_trader_lock:
        if _auto_trader and _auto_trader.state.running:
            return _auto_trader
        _auto_trader = PaperAutoTrader(config)
        _auto_trader.start()
        return _auto_trader


def stop_auto_trader() -> None:
    with _auto_trader_lock:
        if _auto_trader:
            _auto_trader.stop()


def is_trading_time(now: datetime | None = None) -> bool:
    current = _normalize_beijing_datetime(now)
    if not is_a_share_trading_day(current.date()):
        return False
    current_time = current.time()
    return (
        datetime_time(9, 30) <= current_time <= datetime_time(11, 30)
        or datetime_time(13, 0) <= current_time <= datetime_time(14, 58)
    )


def _sized_order_summary(order: SizedOrder) -> dict[str, Any]:
    return {
        "symbol": order.symbol,
        "name": order.name,
        "score": order.signal_snapshot.get("priority_score", 0),
        "quantity": order.quantity,
        "price": float(order.current_price),
        "strategy_key": order.strategy_key,
        "reason": order.reason,
    }


def _sized_order_summary_list(orders: list[SizedOrder]) -> list[dict[str, Any]]:
    return [_sized_order_summary(item) for item in orders]


def _planned_order_summary(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": order.get("symbol", ""),
        "name": order.get("name", ""),
        "quantity": int(order.get("quantity") or 0),
        "price": float(order.get("price") or 0.0),
        "source": order.get("source", ""),
        "strategy_key": order.get("strategy_key", ""),
        "reason": order.get("reason", ""),
        "signal_snapshot": order.get("signal_snapshot", {}),
    }


def _position_values_by_symbol(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        str(row.get("symbol") or ""): float(row.get("market_value") or 0)
        for row in rows
        if row.get("symbol")
    }


class _CycleAggregate:
    def __init__(self) -> None:
        self.accounts = 0
        self.passed = 0
        self.filtered = 0
        self.executed = 0
        self.skipped = 0

    def add(self, result: dict[str, Any]) -> None:
        self.accounts += 1
        self.passed += int(result.get("passed") or 0)
        self.filtered += int(result.get("filtered") or 0)
        self.executed += len(result.get("executed") or [])
        self.skipped += len(result.get("skipped") or [])

    def summary(self) -> str:
        return f"处理 {self.accounts} 个模拟账户，执行 {self.executed} 条，跳过 {self.skipped} 条。"


def _exit_quantity(row: PaperPosition, *, price: float, now: datetime) -> int:
    available = int(row.available_quantity or 0)
    if available < 100 or price <= 0:
        return 0
    cost = float(row.cost_basis or 0)
    if cost <= 0:
        return 0
    pnl_pct = (price - cost) / cost * 100
    hold_days = max((now - row.opened_at).days, 0) if row.opened_at else 0
    if _is_sector_etf_t0_position(row):
        params = _sector_etf_t0_params()
        if pnl_pct >= _float_param(params, "paper_auto_take_profit_pct", 1.2):
            return _round_lot(available)
        if pnl_pct <= _float_param(params, "paper_auto_stop_loss_pct", -0.8):
            return _round_lot(available)
        if hold_days >= 1 and pnl_pct < _float_param(params, "paper_auto_time_exit_min_pct", 0.4):
            return _round_lot(available)
        return 0
    if pnl_pct <= -3.0:
        return _round_lot(available)
    if _time_stop_triggered(row, pnl_pct=pnl_pct, hold_days=hold_days):
        return _round_lot(available)
    if hold_days >= 3 and pnl_pct < 0:
        return _round_lot(available)
    if pnl_pct >= 5.0:
        return _round_lot(max(100, floor(available * 0.7)))
    return 0


def _exit_reason(row: PaperPosition, *, price: float, now: datetime) -> str:
    cost = float(row.cost_basis or 0)
    pnl_pct = (price - cost) / cost * 100 if cost > 0 else 0.0
    hold_days = max((now - row.opened_at).days, 0) if row.opened_at else 0
    if _is_sector_etf_t0_position(row):
        params = _sector_etf_t0_params()
        if pnl_pct >= _float_param(params, "paper_auto_take_profit_pct", 1.2):
            return f"ETF T+0 自动止盈: 浮盈{pnl_pct:.2f}%，兑现板块价差"
        if pnl_pct <= _float_param(params, "paper_auto_stop_loss_pct", -0.8):
            return f"ETF T+0 自动止损: 浮亏{pnl_pct:.2f}%，停止试错"
        if hold_days >= 1 and pnl_pct < _float_param(params, "paper_auto_time_exit_min_pct", 0.4):
            return f"ETF T+0 时间退出: 隔日未达价差目标，先退出"
        return "ETF T+0 自动退出计划"
    if pnl_pct <= -3.0:
        return f"自动退出: 跌破模拟止损线，浮亏{pnl_pct:.2f}%"
    if _time_stop_triggered(row, pnl_pct=pnl_pct, hold_days=hold_days):
        policy = strategy_holding_policy(_primary_strategy_from_position(row))
        return f"自动退出: 已持有{hold_days}天，超过{policy.brief}验证窗口，按时间规则退出"
    if hold_days >= 3 and pnl_pct < 0:
        return f"自动退出: 持有{hold_days}天仍未转强，按时间止损"
    if pnl_pct >= 5.0:
        return f"自动止盈: 浮盈{pnl_pct:.2f}%，先兑现大部分仓位"
    return "自动退出计划"


def _round_lot(quantity: int | float) -> int:
    return int(floor(float(quantity) / 100) * 100)


def _time_stop_triggered(row: PaperPosition, *, pnl_pct: float, hold_days: int) -> bool:
    strategy = _primary_strategy_from_position(row)
    policy = strategy_holding_policy(strategy)
    if hold_days < int(policy.max_holding_days):
        return False
    return pnl_pct < 2.0


def _primary_strategy_from_position(row: PaperPosition) -> str:
    try:
        values = json.loads(row.strategy_sources or "[]")
    except Exception:
        values = []
    if isinstance(values, list) and values:
        return str(values[0] or "")
    if isinstance(values, str):
        return values
    return ""


def _is_sector_etf_t0_position(row: PaperPosition) -> bool:
    return _primary_strategy_from_position(row) == "sector_etf_t0"


def _sector_etf_t0_params() -> dict[str, Any]:
    from app.services.market.parameter_defaults import MARKET_SECTOR_ETF_T0_DEFAULTS

    values = get_market_sector_etf_t0()
    return {**MARKET_SECTOR_ETF_T0_DEFAULTS, **values} if isinstance(values, dict) else dict(MARKET_SECTOR_ETF_T0_DEFAULTS)


def _float_param(params: dict[str, Any], key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return float(fallback)


def _today_order_symbols(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row.get("symbol") or "").strip()
        for row in rows
        if row.get("symbol") and str(row.get("status") or "") in {"pending", "filled", "partial"}
    }


def _is_database_busy(exc: OperationalError) -> bool:
    message = str(exc).lower()
    return "database is locked" in message or "database is busy" in message or "lock wait timeout" in message


def _blocking_account_ids(db: Session, account_ids: list[int]) -> set[int]:
    if not account_ids:
        return set()
    rows = db.execute(
        select(RiskEvent.account_id).where(
            RiskEvent.account_id.in_(account_ids),
            RiskEvent.status == "open",
            RiskEvent.severity.in_(["high", "critical"]),
        )
    ).scalars().all()
    return {int(account_id) for account_id in rows if account_id is not None}


def _blocking_reason(db: Session, account_id: int) -> str:
    row = (
        db.execute(
            select(RiskEvent)
            .where(
                RiskEvent.account_id == account_id,
                RiskEvent.status == "open",
                RiskEvent.severity.in_(["high", "critical"]),
            )
            .order_by(RiskEvent.triggered_at.desc(), RiskEvent.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    return str(row.message or "").strip() if row is not None else ""


def _should_persist_blocked_run(db: Session, *, account_id: int, blocking_reason: str) -> bool:
    since = _beijing_now_naive() - timedelta(minutes=15)
    recent_runs = (
        db.execute(
            select(PaperAgentRun)
            .where(
                PaperAgentRun.account_id == account_id,
                PaperAgentRun.run_type == "auto_trade_cycle",
                PaperAgentRun.status == "skipped",
                PaperAgentRun.created_at >= since,
            )
            .order_by(PaperAgentRun.id.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    if not recent_runs:
        return True
    for run in recent_runs:
        try:
            payload = json.loads(run.response_json or "{}")
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        skipped = payload.get("skipped")
        if not isinstance(skipped, list):
            continue
        for item in skipped:
            if isinstance(item, dict) and str(item.get("reason") or "").strip() == blocking_reason:
                return False
    return True


def _normalize_beijing_datetime(value: datetime | None = None) -> datetime:
    if value is None:
        return _beijing_now_naive()
    if value.tzinfo is not None:
        return value.astimezone(BEIJING_TZ).replace(tzinfo=None)
    return value


def _beijing_now_naive() -> datetime:
    return beijing_now().replace(tzinfo=None)
