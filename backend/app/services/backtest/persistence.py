from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import case, delete, select, update
from sqlalchemy.orm import Session

from app.models.backtest_entities import (
    BacktestDailySnapshot,
    BacktestDataQuality,
    BacktestDatasetManifest,
    BacktestOrder as BacktestOrderEntity,
    BacktestTrade,
)
from app.models.entities import BacktestRun, QuantParameterSet
from app.services.backtest.data_provider import DATA_PROVIDER_VERSION
from app.services.backtest.engine import BACKTEST_ENGINE_VERSION, BacktestResult
from app.services.backtest.forward_path import FORWARD_PATH_FIELDS, enrich_trade_forward_path
from app.services.execution_model import build_backtest_execution_model_preview
from app.services.low_buy.shared import LOW_BUY_RESULT_VERSION
from app.services.quant.parameter_version_service import default_quant_parameters


_PROTECTED_TERMINAL_STATUSES = {"cancelled", "deleted", "failed", "timeout"}


class BacktestResultPersistence:
    """Persist a completed in-memory backtest result into normalized tables."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def persist(self, run: BacktestRun, result: BacktestResult) -> None:
        self.db.refresh(run)
        if _should_preserve_terminal_run(run, result):
            self.db.commit()
            return
        self._replace_run_outputs(run.id)
        manifest = self._create_manifest(result)
        self.db.add(manifest)
        self.db.flush()
        self._create_quality_row(run.id, manifest.id, result)
        persisted_orders = self._create_orders(run.id, result)
        self._create_trades(run.id, result, persisted_orders)
        self._create_equity_snapshots(run.id, result)
        self._update_run_summary(run, result, manifest.id)
        self.db.commit()

    def _replace_run_outputs(self, run_id: int) -> None:
        for model in (BacktestTrade, BacktestOrderEntity, BacktestDailySnapshot, BacktestDataQuality):
            self.db.execute(delete(model).where(model.run_id == run_id))

    def _create_manifest(self, result: BacktestResult) -> BacktestDatasetManifest:
        manifest = dict(result.dataset_manifest or {})
        quality = result.data_quality
        return BacktestDatasetManifest(
            dataset_key=str(manifest.get("dataset_key") or f"daily_bar_snapshots:{quality.start_date}:{quality.end_date}"),
            manifest_hash=str(manifest.get("manifest_hash") or manifest.get("source_hash") or quality.source_hash or ""),
            data_version=str(manifest.get("data_version") or quality.version),
            start_date=str(manifest.get("start_date") or quality.start_date),
            end_date=str(manifest.get("end_date") or quality.end_date),
            instrument_count=int(manifest.get("instrument_count") or quality.symbol_count),
            bar_count=int(manifest.get("bar_count") or manifest.get("record_count") or 0),
            quality_summary_json=_json_dumps(result.data_quality.__dict__),
            source_summary_json=_json_dumps(manifest),
        )

    def _create_quality_row(self, run_id: int, manifest_id: int, result: BacktestResult) -> None:
        quality = result.data_quality
        self.db.add(
            BacktestDataQuality(
                run_id=run_id,
                dataset_manifest_id=manifest_id,
                quality_tag=quality.quality_tag,
                issue_type="summary",
                severity="warning" if quality.warnings else "info",
                details_json=_json_dumps(quality.__dict__),
            )
        )

    def _create_orders(self, run_id: int, result: BacktestResult) -> list[tuple[Any, int]]:
        persisted_orders: list[tuple[Any, int]] = []
        for order in result.orders:
            row = BacktestOrderEntity(
                run_id=run_id,
                trade_date=order.trade_date,
                symbol=order.symbol,
                side=order.side,
                status=order.status,
                strategy_key=order.strategy_key,
                quantity=int(order.quantity or 0),
                filled_quantity=int(order.quantity or 0) if order.status == "filled" else 0,
                requested_price=float(order.requested_price if order.requested_price is not None else order.fill_price or 0.0),
                filled_price=float(order.fill_price or 0.0),
                reason=order.reject_reason or order.reason,
                payload_json=_json_dumps(order.__dict__),
            )
            self.db.add(row)
            self.db.flush()
            persisted_orders.append((order, row.id))
        return persisted_orders

    def _create_trades(self, run_id: int, result: BacktestResult, persisted_orders: list[tuple[Any, int]]) -> None:
        for trade in result.trades:
            gross_amount = float(trade.exit_price) * int(trade.quantity or 0)
            fee_amount = max(float(getattr(trade, "fee_amount", 0.0) or 0.0), 0.0)
            self.db.add(
                BacktestTrade(
                    run_id=run_id,
                    order_id=_matched_exit_order_id(trade, persisted_orders),
                    trade_date=trade.exit_date,
                    symbol=trade.symbol,
                    name=trade.name,
                    side="sell",
                    strategy_key=trade.strategy_key,
                    quantity=int(trade.quantity or 0),
                    price=float(trade.exit_price),
                    gross_amount=gross_amount,
                    fee_amount=fee_amount,
                    net_amount=gross_amount - fee_amount,
                    pnl_amount=float(trade.net_pnl),
                    pnl_pct=float(trade.return_pct),
                    holding_days=int(trade.holding_days or 0),
                    entry_reason="entry",
                    exit_reason=trade.exit_reason,
                    market_state=str(getattr(trade, "market_state", "") or ""),
                    sector=str(getattr(trade, "sector", "") or getattr(trade, "sector_name", "") or ""),
                    sector_name=str(getattr(trade, "sector_name", "") or getattr(trade, "sector", "") or ""),
                    payload_json=_json_dumps(trade.__dict__),
                )
            )

    def _create_equity_snapshots(self, run_id: int, result: BacktestResult) -> None:
        turnover_amounts = _turnover_amounts_by_date(result)
        previous_equity: float | None = None
        peak_equity = 0.0
        for item in result.equity_curve:
            equity = float(item.total_equity)
            peak_equity = max(peak_equity, equity)
            daily_return = 0.0 if previous_equity in (None, 0) else (equity / previous_equity - 1) * 100
            drawdown = 0.0 if peak_equity <= 0 else (equity / peak_equity - 1) * 100
            previous_equity = equity
            market_value = float(item.market_value)
            exposure = 0.0 if equity <= 0 else market_value / equity * 100
            turnover = 0.0 if equity <= 0 else turnover_amounts.get(item.trade_date, 0.0) / equity * 100
            self.db.add(
                BacktestDailySnapshot(
                    run_id=run_id,
                    trade_date=item.trade_date,
                    cash=float(item.cash),
                    market_value=market_value,
                    equity=equity,
                    daily_return_pct=daily_return,
                    drawdown_pct=drawdown,
                    exposure_pct=exposure,
                    turnover=turnover,
                    positions_count=int(item.position_count),
                    benchmark_symbol=str(getattr(item, "benchmark_symbol", "") or ""),
                    benchmark_close=float(getattr(item, "benchmark_close", 0.0) or 0.0),
                    benchmark_return_pct=float(getattr(item, "benchmark_return_pct", 0.0) or 0.0),
                    market_state=str(getattr(item, "market_state", "") or ""),
                    payload_json=_json_dumps(item.__dict__),
                )
            )

    def _update_run_summary(self, run: BacktestRun, result: BacktestResult, manifest_id: int) -> None:
        self.db.flush()
        self.db.refresh(run)
        if _should_preserve_terminal_run(run, result):
            if run.finished_at is None:
                run.finished_at = datetime.utcnow()
            if run.status == "cancelled":
                run.cancelled_at = run.cancelled_at or run.finished_at
            return
        metrics = dict(result.metrics or {})
        quant_parameter = _active_quant_parameter_metadata(self.db)
        result_payload = _compact_result_payload(result, db=self.db)
        result_payload["quant_parameter"] = quant_parameter
        finished_at = datetime.utcnow()
        values = {
            "status": result.status,
            "final_equity": float(metrics.get("final_equity") or run.final_equity or run.initial_cash or 0.0),
            "progress_pct": 100.0 if result.status == "succeeded" else max(float(run.progress_pct or 0.0), 0.0),
            "dataset_manifest_id": manifest_id,
            "engine_version": result.version or BACKTEST_ENGINE_VERSION,
            "strategy_version": str(LOW_BUY_RESULT_VERSION),
            "data_version": result.dataset_manifest.get("source_hash") or result.data_quality.source_hash or DATA_PROVIDER_VERSION,
            "fee_model_version": run.fee_model_version or "paper-fee-model-v1",
            "result_json": _json_dumps(result_payload),
            "finished_at": finished_at,
        }
        if result.status == "cancelled":
            values["cancelled_at"] = run.cancelled_at or finished_at
        updated = self.db.execute(
            update(BacktestRun)
            .where(
                BacktestRun.id == run.id,
                ~BacktestRun.status.in_(_PROTECTED_TERMINAL_STATUSES),
            )
            .values(**values)
        )
        if updated.rowcount != 1:
            self.db.refresh(run)
            if run.finished_at is None:
                run.finished_at = finished_at
            if run.status == "cancelled":
                run.cancelled_at = run.cancelled_at or run.finished_at
            return
        self.db.refresh(run)


def _should_preserve_terminal_run(run: BacktestRun, result: BacktestResult) -> bool:
    return str(run.status or "") in _PROTECTED_TERMINAL_STATUSES and run.status != result.status


def _matched_exit_order_id(trade: Any, persisted_orders: list[tuple[Any, int]]) -> int | None:
    """Map realized lot-level trades to the sell order that produced them."""

    for order, order_id in persisted_orders:
        if str(getattr(order, "status", "")) != "filled":
            continue
        if str(getattr(order, "side", "")) != "sell":
            continue
        if str(getattr(order, "symbol", "")) != str(getattr(trade, "symbol", "")):
            continue
        if str(getattr(order, "trade_date", "")) != str(getattr(trade, "exit_date", "")):
            continue
        if str(getattr(order, "strategy_key", "") or "") != str(getattr(trade, "strategy_key", "") or ""):
            continue
        fill_price = getattr(order, "fill_price", None)
        if fill_price is not None and round(float(fill_price), 4) != round(float(getattr(trade, "exit_price", 0.0)), 4):
            continue
        return order_id
    return None


def _compact_result_payload(result: BacktestResult, db: Session | None = None) -> dict[str, Any]:
    """Keep run detail light; normalized tables store curves, orders and trades."""

    return {
        "version": result.version,
        "status": result.status,
        "partial": result.partial,
        "config": result.config,
        "dataset_manifest": result.dataset_manifest,
        "data_quality": result.data_quality.__dict__,
        "metrics": result.metrics,
        "execution_model_preview": _build_execution_model_preview(result, db=db),
        "attribution": result.attribution,
        "counts": {
            "equity_points": len(result.equity_curve),
            "orders": len(result.orders),
            "trades": len(result.trades),
        },
    }


def _build_execution_model_preview(result: BacktestResult, db: Session | None = None) -> dict[str, Any]:
    try:
        enriched = [_trade_forward_path(item, db=db) for item in result.trades]
        blocked = next((item for item in enriched if item["status"] != "ok"), None)
        if blocked is not None:
            return _unavailable_execution_model_preview(str(blocked["status"] or "no_daily_return_path"))
        outcomes = [
            _trade_outcome_from_realized_trade(item["trade"], forward_path=item["values"])
            for item in enriched
        ]
        if outcomes:
            preview = build_backtest_execution_model_preview(outcomes)
            preview["forward_path_status"] = "ok"
            return preview
    except Exception:
        return _unavailable_execution_model_preview("preview_build_failed")
    return _unavailable_execution_model_preview("no_trade_outcomes")


def _trade_has_forward_path(item: Any) -> bool:
    return all(getattr(item, field, None) is not None for field in FORWARD_PATH_FIELDS)


def _trade_forward_path(item: Any, *, db: Session | None) -> dict[str, Any]:
    if _trade_has_forward_path(item):
        return {"status": "ok", "trade": item, "values": {field: _float_attr(item, field) for field in FORWARD_PATH_FIELDS}}
    if db is None:
        return {"status": "no_daily_return_path", "trade": item, "values": {}}
    result = enrich_trade_forward_path(db, item)
    return {"status": result.status, "trade": item, "values": result.values, "missing_days": result.missing_days}


def _unavailable_execution_model_preview(reason: str) -> dict[str, Any]:
    notes = [
        "execution_model preview unavailable for this run result.",
        "portfolio_backtest_metrics remains the final max5/max10 fact source.",
    ]
    if reason == "no_daily_return_path":
        notes[0] = "backtest realized trades do not include daily forward-return path fields, so parity preview is withheld."
    return {
        "ok": False,
        "mode": "parallel_preview",
        "source": "backtest",
        "event_counts": {},
        "max_5": {},
        "max_10": {},
        "parity": {"max_5": {}, "max_10": {}},
        "final_fact_source": "portfolio_backtest_metrics",
        "replacement_enabled": False,
        "blocked_reason": reason,
        "forward_path_status": reason,
        "notes": notes,
    }


def _trade_outcome_from_realized_trade(item: Any, *, forward_path: dict[str, float] | None = None):
    from scripts.low_buy_market_backtest_reporting import TradeOutcome

    path = forward_path or {field: _float_attr(item, field) for field in FORWARD_PATH_FIELDS}
    return_pct = _float_attr(item, "return_pct")
    return TradeOutcome(
        symbol=str(getattr(item, "symbol", "") or ""),
        name=str(getattr(item, "name", "") or ""),
        signal_date=str(getattr(item, "entry_date", "") or getattr(item, "exit_date", "") or ""),
        strategy_key=str(getattr(item, "strategy_key", "") or ""),
        buy_signal_state="buy_now",
        entry_price=float(getattr(item, "entry_price", 0.0) or 0.0),
        execution_status="filled",
        net_return_pct=return_pct,
        execution_exit_reason=str(getattr(item, "exit_reason", "") or "backtest_trade"),
        return_1d=float(path.get("return_1d") or 0.0),
        return_2d=float(path.get("return_2d") or 0.0),
        return_3d=float(path.get("return_3d") or 0.0),
        return_4d=float(path.get("return_4d") or 0.0),
        return_5d=float(path.get("return_5d") or 0.0),
        max_gain_5d=float(path.get("max_gain_5d") or 0.0),
        max_drawdown_5d=float(path.get("max_drawdown_5d") or 0.0),
        entry_trade_date=str(getattr(item, "entry_date", "") or ""),
        exit_trade_date=str(getattr(item, "exit_date", "") or ""),
    )


def _float_attr(item: Any, field: str) -> float:
    return float(getattr(item, field, 0.0) or 0.0)


def _active_quant_parameter_metadata(db: Session) -> dict[str, Any]:
    """Bind backtest output to the active quant parameter snapshot."""

    row = db.execute(
        select(QuantParameterSet)
        .where(QuantParameterSet.status == "active")
        .where(QuantParameterSet.scope.in_(["global", "low_buy"]))
        .order_by(case((QuantParameterSet.scope == "low_buy", 0), else_=1), QuantParameterSet.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        version = "default"
        scope = "global"
        params = default_quant_parameters()
    else:
        version = str(row.version or "unknown")
        scope = str(row.scope or "global")
        params = _deep_merge(default_quant_parameters(), _json_dict(row.params_json))
    payload = _json_dumps(params)
    return {
        "version": version,
        "scope": scope,
        "hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def _turnover_amounts_by_date(result: BacktestResult) -> dict[str, float]:
    output: dict[str, float] = {}
    for order in getattr(result, "orders", []) or []:
        if order.status != "filled" or order.fill_price is None or int(order.quantity or 0) <= 0:
            continue
        amount = float(order.fill_price) * int(order.quantity or 0)
        output[order.trade_date] = output.get(order.trade_date, 0.0) + amount
    return output


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, default_value in defaults.items():
        override_value = overrides.get(key)
        if isinstance(default_value, dict) and isinstance(override_value, dict):
            result[key] = _deep_merge(default_value, override_value)
        elif key in overrides:
            result[key] = override_value
        else:
            result[key] = default_value
    for key, value in overrides.items():
        if key not in result:
            result[key] = value
    return result
