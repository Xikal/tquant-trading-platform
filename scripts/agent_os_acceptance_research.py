from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

try:
    from .agent_os_acceptance_common import DEFAULT_BENCHMARK_REPORT, DEFAULT_STRATEGY_REPORT
except ImportError:
    from agent_os_acceptance_common import DEFAULT_BENCHMARK_REPORT, DEFAULT_STRATEGY_REPORT
from app.models.entities import DailyBarSnapshot, LowBuyResultSnapshot
from app.services.agent_daily_workflow_service import AgentDailyWorkflowService
from app.services.market.openbb_adapter import OpenBBDataAdapter
from research.backtest.benchmark import write_benchmark_report
from research.backtest.strategy_validation import write_strategy_validation_report
from research.data_sync.tquant_to_qlib import qlib_status


def run_feishu_daily_push(db: Session) -> tuple[str, str, dict[str, Any]]:
    service = AgentDailyWorkflowService()
    response = service.push_daily_report(db, channel="feishu")
    if not response.sent and "not configured" in response.message:
        return "not_configured", response.message, response.model_dump()
    status = "ok" if response.ok else "failed"
    message = "飞书日报已推送。" if response.sent else response.message
    return status, message, response.model_dump()


def run_qlib_report(
    db: Session,
    *,
    dataset_path: Path,
    lookback_days: int,
    strategy_keys: list[str] | None,
) -> tuple[str, str, dict[str, Any]]:
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    frame = _export_strategy_samples(db, lookback_days=max(20, lookback_days), strategy_keys=strategy_keys)
    frame.to_csv(dataset_path, index=False)
    strategy_report = DEFAULT_STRATEGY_REPORT
    benchmark_report = DEFAULT_BENCHMARK_REPORT
    write_strategy_validation_report(dataset_path, strategy_report, strategy_keys=strategy_keys)
    write_benchmark_report(dataset_path, benchmark_report)
    data = {
        "qlib": qlib_status(),
        "dataset_path": str(dataset_path),
        "strategy_report_path": str(strategy_report),
        "benchmark_report_path": str(benchmark_report),
        "sample_count": int(len(frame)),
        "strategies": sorted(frame["strategy_key"].dropna().unique().tolist()) if not frame.empty else [],
        "columns": frame.columns.tolist(),
    }
    if frame.empty:
        return "empty", "本地未找到可计算 forward return 的策略样本，已生成空报告。", data
    return "ok", "qlib 标准指标报告已生成。", data


def run_openbb_check() -> tuple[str, str, dict[str, Any]]:
    adapter = OpenBBDataAdapter(timeout=3)
    quote_symbols = ["AAPL", "MSFT", "SPY"]
    quotes = [adapter.quote(symbol).__dict__ for symbol in quote_symbols]
    macro = adapter.macro_status(["CPIAUCSL", "DGS10", "GDP"])
    available_quotes = sum(1 for item in quotes if item.get("available"))
    status = "ok" if available_quotes or macro.get("status") == "ok" else "degraded"
    return status, "OpenBB 可选数据源已完成真实探测与降级验收。", {
        "adapter_status": adapter.status(),
        "quotes": quotes,
        "macro": macro,
        "degrade_rule": "OpenBB 失败只标记 degraded，不阻断 A 股核心策略链路。",
    }


def load_priority_symbols(db: Session, *, limit: int) -> list[str]:
    latest_date = (
        db.execute(select(LowBuyResultSnapshot.latest_trade_date).order_by(desc(LowBuyResultSnapshot.latest_trade_date)).limit(1))
        .scalars()
        .first()
    )
    if not latest_date:
        return ["510300", "159915", "588000"]
    rows = (
        db.execute(
            select(LowBuyResultSnapshot.symbol)
            .where(LowBuyResultSnapshot.latest_trade_date == latest_date)
            .order_by(desc(LowBuyResultSnapshot.score))
            .limit(max(1, min(limit, 20)))
        )
        .scalars()
        .all()
    )
    symbols = [str(item) for item in rows if item]
    return symbols[:limit] or ["510300", "159915", "588000"]


def _export_strategy_samples(
    db: Session,
    *,
    lookback_days: int,
    strategy_keys: list[str] | None,
) -> pd.DataFrame:
    trade_dates = _recent_trade_dates(db, lookback_days=lookback_days + 8)
    if not trade_dates:
        return _empty_strategy_samples()
    min_date = trade_dates[0]
    stmt = select(LowBuyResultSnapshot).where(LowBuyResultSnapshot.latest_trade_date >= min_date)
    if strategy_keys:
        stmt = stmt.where(LowBuyResultSnapshot.strategy_key.in_(strategy_keys))
    rows = db.execute(stmt.order_by(LowBuyResultSnapshot.latest_trade_date, LowBuyResultSnapshot.strategy_key)).scalars().all()
    if not rows:
        return _empty_strategy_samples()
    symbols = sorted({row.symbol for row in rows if row.symbol})
    bars = _load_daily_bars(db, symbols=symbols, min_date=min_date)
    records = [_strategy_sample_record(row, bars.get(row.symbol) or []) for row in rows]
    valid_records = [record for record in records if record is not None]
    if not valid_records:
        return _empty_strategy_samples()
    return pd.DataFrame.from_records(valid_records)


def _strategy_sample_record(
    row: LowBuyResultSnapshot,
    symbol_bars: list[DailyBarSnapshot],
) -> dict[str, Any] | None:
    index = _date_index(symbol_bars).get(row.latest_trade_date)
    if index is None:
        return None
    close0 = float(symbol_bars[index].close_price or 0.0)
    if close0 <= 0:
        return None
    forward = {horizon: _forward_return(symbol_bars, index, horizon, close0) for horizon in (1, 2, 3, 4, 5)}
    effective_horizon, effective_return = _effective_forward_return(forward)
    if forward[1] is None and forward[3] is None and forward[5] is None:
        return None
    payload = _json_loads(row.payload_json)
    return {
        "strategy_key": row.strategy_key,
        "symbol": row.symbol,
        "name": row.name,
        "trade_date": row.latest_trade_date,
        "buy_signal_state": row.buy_signal_state,
        "factor_score": float(row.score or payload.get("score") or 0.0),
        "return": effective_return,
        "return_1d": forward[1],
        "return_2d": forward[2],
        "return_3d": forward[3],
        "return_4d": forward[4],
        "return_5d": forward[5],
        "forward_return_1d": forward[1],
        "effective_return_horizon": effective_horizon,
        "close_price": close0,
        "priority_score": float(payload.get("priority_score") or row.score or 0.0),
        "market_state": str(payload.get("market_state") or payload.get("market_state_category") or ""),
        "industry": str(payload.get("sector_name") or payload.get("industry") or ""),
    }


def _recent_trade_dates(db: Session, *, lookback_days: int) -> list[str]:
    rows = (
        db.execute(
            select(DailyBarSnapshot.trade_date)
            .distinct()
            .order_by(desc(DailyBarSnapshot.trade_date))
            .limit(max(1, lookback_days))
        )
        .scalars()
        .all()
    )
    return sorted(str(item) for item in rows if item)


def _load_daily_bars(db: Session, *, symbols: list[str], min_date: str) -> dict[str, list[DailyBarSnapshot]]:
    if not symbols:
        return {}
    rows = (
        db.execute(
            select(DailyBarSnapshot)
            .where(DailyBarSnapshot.symbol.in_(symbols), DailyBarSnapshot.trade_date >= min_date)
            .order_by(DailyBarSnapshot.symbol, DailyBarSnapshot.trade_date)
        )
        .scalars()
        .all()
    )
    grouped: dict[str, list[DailyBarSnapshot]] = defaultdict(list)
    for row in rows:
        grouped[row.symbol].append(row)
    return dict(grouped)


def _date_index(bars: list[DailyBarSnapshot]) -> dict[str, int]:
    return {str(row.trade_date): index for index, row in enumerate(bars)}


def _forward_return(bars: list[DailyBarSnapshot], index: int, horizon: int, close0: float) -> float | None:
    target_index = index + horizon
    if target_index >= len(bars):
        return None
    close_n = float(bars[target_index].close_price or 0.0)
    if close_n <= 0:
        return None
    return round(close_n / close0 - 1.0, 6)


def _effective_forward_return(forward: dict[int, float | None]) -> tuple[int | None, float | None]:
    for horizon in (3, 2, 1, 4, 5):
        value = forward.get(horizon)
        if value is not None:
            return horizon, value
    return None, None


def _empty_strategy_samples() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "strategy_key",
            "symbol",
            "name",
            "trade_date",
            "buy_signal_state",
            "factor_score",
            "return",
            "return_1d",
            "return_2d",
            "return_3d",
            "return_4d",
            "return_5d",
            "forward_return_1d",
            "effective_return_horizon",
            "close_price",
            "priority_score",
            "market_state",
            "industry",
        ]
    )


def _json_loads(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
