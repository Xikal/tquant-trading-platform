from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, time as datetime_time, timedelta
from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import PaperAccount, PaperAgentRun
from app.services.market.trading_calendar import is_a_share_trading_day
from app.services.low_buy.service import LowBuyScreenerService
from app.services.paper.admission import AdmissionFilter
from app.services.paper.executor import PaperTradingExecutor
from app.services.paper.matching import PaperMatchingEngine
from app.services.paper.order import PaperOrderService
from app.services.paper.scheduler_accounts import (
    activate_auto_managed_accounts,
    get_account,
    get_active_account,
    get_active_accounts,
    get_positions_summary,
    get_today_orders,
)
from app.services.paper.scheduler_helpers import (
    _CycleAggregate,
    _beijing_now_naive,
    _blocking_reason,
    _is_database_busy,
    _normalize_beijing_datetime,
    _planned_order_summary,
    _position_values_by_symbol,
    _should_persist_blocked_run,
    _sized_order_summary_list,
)
from app.services.paper.scheduler_etf import build_sector_etf_t0_orders
from app.services.paper.scheduler_exit import build_exit_order_plan, build_exit_orders, build_smart_t_order_plan
from app.services.paper.scheduler_runs import finish_agent_run, record_cycle, start_agent_run
from app.services.paper.scheduler_state import AutoTraderState
from app.services.paper.scheduler_portfolio import apply_portfolio_weighting
from app.services.paper.sizing import PositionSizer, SizedOrder
from app.services.paper.strategy_phase_gate import apply_strategy_validation_phase
from app.services.sector_etf_t0 import SectorEtfT0Service
from app.services.user_sector_preferences import UserSectorPreferenceService

logger = logging.getLogger(__name__)


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
        weighted_passed = apply_portfolio_weighting(
            db=db,
            account_id=account.id,
            candidates=report.passed,
        )
        sized = PositionSizer().calculate(
            candidates=weighted_passed,
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
                result = self._build_and_execute_blocked_exit_plan(
                    db=db,
                    account=account,
                    blocking_reason=blocking_reason,
                )
                should_persist = bool(result.get("executed")) or self._should_persist_blocked_run(
                    db,
                    account_id=account.id,
                    blocking_reason=blocking_reason,
                )
                if should_persist:
                    run = self._start_run(db, account_id=account.id, board=board)
                    status = "succeeded" if result.get("executed") else "skipped"
                    self._finish_run(db, run, status=status, response=result)
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
        phase_passed, phase_filtered = apply_strategy_validation_phase(db, report.passed)
        phase_passed = apply_portfolio_weighting(
            db=db,
            account_id=account.id,
            candidates=phase_passed,
        )
        filtered_candidates = [*report.filtered, *phase_filtered]
        exit_orders, exit_skip_reason = self._build_exit_order_plan(db, account)
        smart_t_orders = self._build_smart_t_order_plan(
            db=db,
            account=account,
            today_orders=today_orders,
            used_order_count=len(exit_orders),
            market_state=str(board.get("market_state") or ""),
        )
        orders = PositionSizer().calculate(
            candidates=phase_passed,
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
            used_order_count=len(exit_orders) + len(smart_t_orders) + len(orders),
        )
        planned_orders = [*exit_orders, *smart_t_orders, *orders, *etf_orders]
        if not planned_orders:
            summary = f"通过 {len(phase_passed)} 条，过滤 {len(filtered_candidates)} 条" if not phase_passed else "资金不足、候选不够或没有触发退出计划"
            skipped = [{"account_id": account.id, "reason": exit_skip_reason}] if exit_skip_reason else []
            return {
                "passed": len(phase_passed),
                "filtered": len(filtered_candidates),
                "executed": [],
                "skipped": skipped,
                "summary": summary,
                "exit_order_count": len(exit_orders),
                "smart_t_order_count": len(smart_t_orders),
                "buy_order_count": len(orders),
                "sector_etf_t0_order_count": len(etf_orders),
                "filtered_reasons": [
                    {"symbol": item.symbol, "score": item.priority_score, "reason": item.reason}
                    for item in filtered_candidates[:5]
                ],
            }
        result = self._execute_orders(db=db, account_id=account.id, orders=planned_orders)
        skipped = list(result.get("skipped") or [])
        if exit_skip_reason:
            skipped.append({"account_id": account.id, "source": "auto_exit", "reason": exit_skip_reason})
        return {
            **result,
            "skipped": skipped,
            "passed": len(phase_passed),
            "filtered": len(filtered_candidates),
            "exit_order_count": len(exit_orders),
            "smart_t_order_count": len(smart_t_orders),
            "buy_order_count": len(orders),
            "sector_etf_t0_order_count": len(etf_orders),
        }

    def _build_and_execute_blocked_exit_plan(
        self,
        *,
        db: Session,
        account: PaperAccount,
        blocking_reason: str,
    ) -> dict[str, Any]:
        exit_orders, exit_skip_reason = self._build_exit_order_plan(db, account)
        if not exit_orders:
            skipped_reason = exit_skip_reason or blocking_reason
            return {
                "passed": 0,
                "filtered": 0,
                "executed": [],
                "skipped": [{"account_id": account.id, "source": "auto_exit", "reason": skipped_reason}],
                "summary": f"账户风控阻断新增买入；自动退出未执行：{skipped_reason}",
                "risk_blocking_reason": blocking_reason,
                "exit_order_count": 0,
                "smart_t_order_count": 0,
                "buy_order_count": 0,
                "sector_etf_t0_order_count": 0,
            }
        result = self._execute_orders(db=db, account_id=account.id, orders=exit_orders)
        skipped = list(result.get("skipped") or [])
        return {
            **result,
            "skipped": skipped,
            "passed": 0,
            "filtered": 0,
            "summary": f"账户风控阻断新增买入；已优先执行自动退出 {len(result.get('executed') or [])} 条，跳过 {len(skipped)} 条。",
            "risk_blocking_reason": blocking_reason,
            "exit_order_count": len(exit_orders),
            "smart_t_order_count": 0,
            "buy_order_count": 0,
            "sector_etf_t0_order_count": 0,
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
        return get_active_account(db)

    def _get_active_accounts(self, db: Session) -> list[PaperAccount]:
        return get_active_accounts(db)

    def _get_account(self, db: Session, *, account_id: int) -> PaperAccount | None:
        return get_account(db, account_id=account_id)

    @staticmethod
    def _activate_auto_managed_accounts(db: Session, accounts: list[PaperAccount]) -> None:
        activate_auto_managed_accounts(db, accounts)

    @staticmethod
    def _blocking_reason(db: Session, account_id: int) -> str:
        return _blocking_reason(db, account_id)

    @staticmethod
    def _should_persist_blocked_run(db: Session, *, account_id: int, blocking_reason: str) -> bool:
        return _should_persist_blocked_run(db, account_id=account_id, blocking_reason=blocking_reason)

    def _get_positions_summary(self, db: Session, account: PaperAccount) -> list[dict[str, Any]]:
        return get_positions_summary(db, account)

    def _get_today_orders(self, db: Session, account_id: int) -> list[dict[str, Any]]:
        return get_today_orders(db, account_id)

    def _execute_orders(self, *, db: Session, account_id: int, orders: list[SizedOrder | dict[str, Any]]) -> dict[str, Any]:
        executor = PaperTradingExecutor(PaperOrderService(db, PaperMatchingEngine()))
        return executor.execute_plan(
            account_id=account_id,
            planned_orders=[item.to_plan_dict() if isinstance(item, SizedOrder) else item for item in orders],
            max_orders=self.state.max_orders_per_cycle,
            dry_run=self.state.dry_run,
        )

    def _build_exit_orders(self, db: Session, account: PaperAccount) -> list[dict[str, Any]]:
        return build_exit_orders(db=db, account=account)

    def _build_exit_order_plan(self, db: Session, account: PaperAccount) -> tuple[list[dict[str, Any]], str]:
        return build_exit_order_plan(db=db, account=account)

    def _build_smart_t_order_plan(
        self,
        *,
        db: Session,
        account: PaperAccount,
        today_orders: list[dict[str, Any]],
        used_order_count: int,
        market_state: str = "",
    ) -> list[dict[str, Any]]:
        return build_smart_t_order_plan(
            db=db,
            account=account,
            today_orders=today_orders,
            used_order_count=used_order_count,
            max_orders=self.state.max_orders_per_cycle,
            market_state=market_state,
        )

    def _build_sector_etf_t0_orders(
        self,
        *,
        db: Session,
        account: PaperAccount,
        board: dict[str, Any],
        today_orders: list[dict[str, Any]],
        used_order_count: int,
    ) -> list[dict[str, Any]]:
        return build_sector_etf_t0_orders(
            db=db,
            account=account,
            board=board,
            today_orders=today_orders,
            used_order_count=used_order_count,
            max_orders_per_cycle=self.state.max_orders_per_cycle,
            etf_service_cls=SectorEtfT0Service,
        )

    def _start_run(self, db: Session, *, account_id: int, board: dict[str, Any]) -> PaperAgentRun:
        return start_agent_run(db, account_id=account_id, board=board, state=self.state)

    def _finish_run(
        self,
        db: Session,
        run: PaperAgentRun,
        *,
        status: str,
        response: dict[str, Any],
        error: str = "",
    ) -> None:
        finish_agent_run(db, run, status=status, response=response, error=error)

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
        record_cycle(
            self.state,
            passed=passed,
            filtered=filtered,
            summary=summary,
            executed=executed,
            skipped=skipped,
        )

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
