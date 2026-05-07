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
from app.services.low_buy.shared import LOW_BUY_RESULT_VERSION
from app.services.quant.parameter_version_service import DEFAULT_QUANT_PARAMETERS


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
                reason=order.reason or order.reject_reason,
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
        result_payload = _compact_result_payload(result)
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


def _compact_result_payload(result: BacktestResult) -> dict[str, Any]:
    """Keep run detail light; normalized tables store curves, orders and trades."""

    return {
        "version": result.version,
        "status": result.status,
        "partial": result.partial,
        "config": result.config,
        "dataset_manifest": result.dataset_manifest,
        "data_quality": result.data_quality.__dict__,
        "metrics": result.metrics,
        "attribution": result.attribution,
        "counts": {
            "equity_points": len(result.equity_curve),
            "orders": len(result.orders),
            "trades": len(result.trades),
        },
    }


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
        params = DEFAULT_QUANT_PARAMETERS
    else:
        version = str(row.version or "unknown")
        scope = str(row.scope or "global")
        params = _deep_merge(DEFAULT_QUANT_PARAMETERS, _json_dict(row.params_json))
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
