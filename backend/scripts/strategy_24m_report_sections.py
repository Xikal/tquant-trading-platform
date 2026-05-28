from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from sqlalchemy import case, func, select

from app.models.entities import DailyBarSnapshot, MarketModelObservation, MinuteBarSnapshot, PaperOrder, PaperTrade
from app.services.etf.t0_backtest import run_etf_t0_research_report
from app.services.etf.universe import list_etf_profiles
from app.services.paper.smart_t_backtest import SmartTBacktestService

try:
    from .strategy_24m_report_metrics import avg, pct
except ImportError:
    from strategy_24m_report_metrics import avg, pct


MIN_ETF_T0_TRADE_DAY_COVERAGE_PCT = 85.0


def smart_t_section(db, *, args, source: dict[str, Any], latest_completed: str) -> dict[str, Any]:
    actual_start = str(source.get("daily_min_trade_date") or args.start)
    start_date = max(args.start, actual_start)
    end_date = latest_completed or str(source.get("daily_max_trade_date") or "")
    if not end_date:
        return {"status": "blocked_by_data", "strategy_key": "smart_t", "strategy_title": "个股底仓 SmartT 洗盘加仓日线代理验证", "notes": ["本地 daily_bar_snapshots 为空，SmartT 无法验证。"], "report": {}}
    try:
        payload = asdict(SmartTBacktestService(db).run(start_date=start_date, end_date=end_date, forward_days=3, sample_limit=50))
    except Exception as exc:  # pragma: no cover - report generator must preserve other strategy output
        return {"status": "failed", "strategy_key": "smart_t", "strategy_title": "个股底仓 SmartT 洗盘加仓日线代理验证", "notes": [f"SmartT 日线代理验证执行失败：{exc}"], "report": {}}
    if int(payload.get("signal_count") or 0) <= 0:
        status = "no_signal_samples"
    elif int(payload.get("washout_signal_count") or 0) <= 0:
        status = "no_washout_samples"
    else:
        status = "daily_proxy_completed"
    notes = list(payload.get("notes") or [])
    notes.append("SmartT 当前按日线代理验证洗盘加仓机会，不等同于分钟级真实做T成交验收。")
    return {"status": status, "strategy_key": "smart_t", "strategy_title": "个股底仓 SmartT 洗盘加仓日线代理验证", "notes": notes, "report": payload}


def etf_t0_section(db, *, start: str, end: str) -> dict[str, Any]:
    profiles = [profile for profile in list_etf_profiles() if profile.same_day_sell_allowed]
    symbols = [profile.symbol for profile in profiles]
    minute_count = int(db.execute(select(func.count(MinuteBarSnapshot.id))).scalar_one() or 0)
    expected_days = _expected_trade_days(db, start=start, end=end)
    ranges = _minute_ranges(db, symbols=symbols, start=start, end=end)
    accepted = [symbol for symbol, row in ranges.items() if _trade_day_coverage_pct(row["trade_days"], expected_days) >= MIN_ETF_T0_TRADE_DAY_COVERAGE_PCT]
    reports = []
    for profile in profiles:
        row = ranges.get(profile.symbol, {"rows": 0, "trade_days": 0, "actual_start": "", "actual_end": ""})
        coverage_pct = _trade_day_coverage_pct(row["trade_days"], expected_days)
        if coverage_pct < MIN_ETF_T0_TRADE_DAY_COVERAGE_PCT:
            reports.append(
                {
                    "symbol": profile.symbol,
                    "name": profile.name,
                    "category": profile.category.value,
                    "same_day_sell_allowed": profile.same_day_sell_allowed,
                    "trade_count": 0,
                    "sample_count": row["rows"],
                    "trade_days": row["trade_days"],
                    "trade_day_coverage_pct": coverage_pct,
                    "actual_start": row["actual_start"],
                    "actual_end": row["actual_end"],
                    "status": "insufficient_window_minute_coverage" if row["rows"] else "no_minute_data",
                    "notes": ["窗口内 ETF 分钟线交易日覆盖不足，不能作为 24 个月 T0 验收。"],
                }
            )
            continue
        report = run_etf_t0_research_report(symbol=profile.symbol, name=profile.name, bars=_minute_bars_for_symbol(db, profile.symbol, start=start, end=end)).to_dict()
        report["trade_day_coverage_pct"] = coverage_pct
        reports.append(report)
    status = "completed" if len(accepted) == len(profiles) and profiles else ("partial_minute_coverage" if minute_count else "blocked_by_data")
    return {
        "status": status,
        "strategy_key": "etf_t0",
        "strategy_title": "ETF T0 分钟级做T",
        "eligible_profile_count": len(profiles),
        "minute_bar_count": minute_count,
        "window_minute_bar_count": sum(row["rows"] for row in ranges.values()),
        "symbols_with_minutes": sum(1 for row in ranges.values() if row["rows"] > 0),
        "accepted_symbol_count": len(accepted),
        "expected_trade_day_count": expected_days,
        "min_trade_day_coverage_pct": MIN_ETF_T0_TRADE_DAY_COVERAGE_PCT,
        "reports": reports,
        "notes": [
            "ETF T0 必须用窗口内分钟线和 ETF 专用费用模型验收；近端短窗口分钟线只能作为数据探针。",
            f"当前验收要求每个 T0 ETF 至少覆盖 {MIN_ETF_T0_TRADE_DAY_COVERAGE_PCT}% 的窗口交易日。",
        ],
    }


def sector_etf_t0_section(db, *, source: dict[str, Any]) -> dict[str, Any]:
    observations = db.execute(select(MarketModelObservation).where(MarketModelObservation.model_key == "sector_etf_t0").order_by(MarketModelObservation.trade_date.asc(), MarketModelObservation.id.asc())).scalars().all()
    settled = [row for row in observations if row.outcome_status == "settled"]
    successful = [row for row in settled if json_dict(row.payload_json).get("outcome", {}).get("success") is True]
    orders = db.execute(select(func.count(PaperOrder.id), func.sum(case((PaperOrder.status == "filled", 1), else_=0)), func.min(PaperOrder.created_at), func.max(PaperOrder.created_at)).where(PaperOrder.strategy_key == "sector_etf_t0")).one()
    trades = db.execute(select(func.count(PaperTrade.id), func.count(func.distinct(PaperTrade.account_id)), func.min(PaperTrade.trade_time), func.max(PaperTrade.trade_time)).where(PaperTrade.strategy_key == "sector_etf_t0")).one()
    minute_count = int(source.get("minute_bar_count") or 0)
    if minute_count <= 0:
        status = "blocked_by_minute_data"
    elif not observations and not int(trades[0] or 0):
        status = "no_shadow_or_trade_samples"
    elif len(settled) < 30:
        status = "insufficient_shadow_samples"
    else:
        status = "shadow_observation_completed"
    return {
        "status": status,
        "strategy_key": "sector_etf_t0",
        "strategy_title": "行业 ETF 替代做T",
        "sample_count": len(observations),
        "settled_count": len(settled),
        "pending_count": sum(1 for row in observations if row.outcome_status == "pending"),
        "success_count": len(successful),
        "success_rate_pct": pct(len(successful), len(settled)),
        "avg_confidence": avg(row.confidence for row in observations),
        "avg_expected_edge_pct": avg(row.expected_edge_pct for row in observations),
        "simulated_order_count": int(orders[0] or 0),
        "simulated_filled_order_count": int(orders[1] or 0),
        "simulated_trade_count": int(trades[0] or 0),
        "simulated_account_count": int(trades[1] or 0),
        "first_order_at": str(orders[2] or ""),
        "last_order_at": str(orders[3] or ""),
        "first_trade_at": str(trades[2] or ""),
        "last_trade_at": str(trades[3] or ""),
        "minute_bar_count": minute_count,
        "notes": [
            "sector_etf_t0 是监控/模拟盘里的行业 ETF 替代做T策略，不属于低吸 PLAYBOOKS。",
            "当前报告只读统计影子观察和模拟盘成交，不生成新委托，不修改参数。",
            "分钟线或 Shadow 样本不足时，不能完成行业 ETF 替代做T 24 个月验收。",
        ],
    }


def data_and_test_gaps(coverage: dict[str, Any], etf_t0: dict[str, Any], sector_etf_t0: dict[str, Any], smart_t: dict[str, Any], strategies: list[dict[str, Any]]) -> list[str]:
    gaps = []
    if coverage["status"] != "complete":
        gaps.append(coverage["warning"])
    if etf_t0["status"] != "completed":
        gaps.append("ETF T0 分钟线窗口交易日覆盖不足，无法完成 24 个月分钟级验收。")
    if sector_etf_t0["status"] != "shadow_observation_completed":
        gaps.append("sector_etf_t0 缺少分钟线或稳定影子/模拟成交样本，无法完成行业 ETF 替代做T 24 个月验收。")
    if smart_t["status"] != "daily_proxy_completed":
        gaps.append("SmartT 当前未形成可验收的洗盘加仓样本，仍需补齐信号样本或分钟级验证。")
    if any(item["sample_count"] == 0 for item in strategies):
        gaps.append("部分策略无样本，需确认是否为策略门槛过严、数据不足或策略被降级为观察。")
    gaps.append("建议补充本报告脚本的回归测试，锁定 T+1 执行约束和报告字段结构。")
    return [item for item in gaps if item]


def production_conclusion(strategies: list[dict[str, Any]], etf_t0: dict[str, Any], sector_etf_t0: dict[str, Any], smart_t: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    qualified = [item for item in strategies if item["filled_count"] >= 30 and item["profit_factor"] >= 1.0 and item["avg_trade_return_pct"] >= 0]
    etf_ready = etf_t0["status"] == "completed"
    return {
        "complete_24m_acceptance": coverage["status"] == "complete",
        "etf_t0_acceptance": etf_ready,
        "sector_etf_t0_acceptance": sector_etf_t0["status"] == "shadow_observation_completed",
        "smart_t_acceptance": smart_t["status"] == "daily_proxy_completed",
        "paper_observation_candidates": [{"strategy_key": item["strategy_key"], "strategy_title": item["strategy_title"]} for item in qualified[:8]],
        "production_ready": False,
        "reason": "日线策略已可形成 24 个月研究基线；ETF T0、Shadow 样本和 Walk-forward 仍未全部验收，不能直接生产放行。" if not etf_ready else "已有研究基线，但仍需 Walk-forward、Shadow 和风控灰度验收后才可考虑生产观察。",
    }


def _expected_trade_days(db, *, start: str, end: str) -> int:
    return int(db.execute(select(func.count(func.distinct(DailyBarSnapshot.trade_date))).where(DailyBarSnapshot.instrument_type == "stock", DailyBarSnapshot.trade_date >= start, DailyBarSnapshot.trade_date <= end)).scalar_one() or 0)


def _minute_ranges(db, *, symbols: list[str], start: str, end: str) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}
    rows = db.execute(select(MinuteBarSnapshot.symbol, func.count(MinuteBarSnapshot.id), func.count(func.distinct(MinuteBarSnapshot.trade_date)), func.min(MinuteBarSnapshot.trade_date), func.max(MinuteBarSnapshot.trade_date)).where(MinuteBarSnapshot.symbol.in_(symbols), MinuteBarSnapshot.trade_date >= start, MinuteBarSnapshot.trade_date <= end).group_by(MinuteBarSnapshot.symbol)).all()
    return {str(row[0]): {"rows": int(row[1] or 0), "trade_days": int(row[2] or 0), "actual_start": str(row[3] or ""), "actual_end": str(row[4] or "")} for row in rows}


def _trade_day_coverage_pct(actual: int, expected: int) -> float:
    return round(float(actual) / float(expected) * 100.0, 2) if expected else 0.0


def _minute_bars_for_symbol(db, symbol: str, *, start: str, end: str):
    from app.models.schemas import KlineBar

    rows = db.execute(select(MinuteBarSnapshot).where(MinuteBarSnapshot.symbol == symbol, MinuteBarSnapshot.trade_date >= start, MinuteBarSnapshot.trade_date <= end).order_by(MinuteBarSnapshot.bar_timestamp.asc())).scalars().all()
    return [KlineBar(timestamp=row.bar_timestamp, open=float(row.open_price or 0.0), high=float(row.high_price or 0.0), low=float(row.low_price or 0.0), close=float(row.close_price or 0.0), volume=float(row.volume or 0.0), amount=float(row.amount or 0.0)) for row in rows]


def json_dict(value: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(value or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
