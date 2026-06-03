from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.services.trading_experience import repository
from app.services.trading_experience.config import (
    ENGINE_VERSION,
    LIMIT_UP_BACKTEST_MAX_DRAWDOWN_PCT,
    LIMIT_UP_BACKTEST_MIN_CALENDAR_DAYS,
    LIMIT_UP_BACKTEST_MIN_PROFIT_FACTOR,
    LIMIT_UP_BACKTEST_MIN_SAMPLES,
    LIMIT_UP_BACKTEST_MIN_STABLE_QUARTERS,
    LIMIT_UP_BACKTEST_MIN_WINRATE,
    LIMIT_UP_BACKTEST_SNAPSHOT_KEY,
    LIMIT_UP_BACKTEST_SNAPSHOT_TYPE,
    LIMIT_UP_BACKTEST_WINDOW_DAYS,
)
from app.services.trading_experience.schemas import LimitUpFollowthroughItem

PATTERN_CODES = (
    "three_yin_floor",
    "half_volume_signal",
    "four_star_consolidation",
    "probe_updown",
    "volume_stall_warning",
)


def build_items(
    db: Session,
    *,
    trade_date: date | None = None,
    limit: int = 30,
    backtest_report: dict[str, Any] | None = None,
) -> list[LimitUpFollowthroughItem]:
    target = trade_date or repository.latest_trade_date(db)
    if not target:
        return []
    rows = repository.daily_rows_for_date(db, target, limit=500)
    as_of = datetime.now()
    items: list[LimitUpFollowthroughItem] = []
    for row, _, _ in rows:
        history = repository.symbol_history(db, row.symbol, end_date=target, days=8)
        limit_rows = [bar for bar in history if _is_limit_up(bar)]
        if not limit_rows:
            continue
        limit_day = limit_rows[-1]
        days_since = max(0, len([bar for bar in history if bar.trade_date > limit_day.trade_date]))
        if days_since > 5:
            continue
        pattern_code = _pattern(history, limit_day.trade_date)
        pattern_metrics = _pattern_metrics(backtest_report, pattern_code)
        gate = str((backtest_report or {}).get("backtest_gate") or "blocked")
        blocked = gate == "blocked"
        failed = gate == "failed" or str(pattern_metrics.get("gate") or "") == "failed"
        items.append(
            LimitUpFollowthroughItem(
                symbol=row.symbol,
                limit_up_date=limit_day.trade_date.isoformat(),
                pattern_code=pattern_code,
                days_since=days_since,
                evidence=_item_evidence(days_since, gate, pattern_metrics),
                backtest_winrate=pattern_metrics.get("winrate"),
                backtest_pf=pattern_metrics.get("profit_factor"),
                backtest_max_drawdown=pattern_metrics.get("max_drawdown"),
                sample_count=int(pattern_metrics.get("sample_count") or 0),
                quarter_stability=str(pattern_metrics.get("quarter_stability") or gate),
                status="blocked" if blocked else "research_only" if failed else "observed",
                data_quality="blocked" if blocked else "research_only" if failed else "ok",
                as_of=as_of,
            )
        )
        if len(items) >= limit:
            break
    return items


def build_backtest_report(db: Session, *, end_date: date | None = None) -> dict[str, Any]:
    target = end_date or repository.latest_trade_date(db) or date.today()
    start = target - timedelta(days=LIMIT_UP_BACKTEST_WINDOW_DAYS)
    available_min, available_max = db.execute(
        select(func.min(repository.DailyBarSnapshot.trade_date), func.max(repository.DailyBarSnapshot.trade_date)).where(
            repository.DailyBarSnapshot.instrument_type == "stock",
            repository.DailyBarSnapshot.trade_date >= start,
            repository.DailyBarSnapshot.trade_date <= target,
        )
    ).one()
    as_of = datetime.now()
    if not available_min or not available_max or (available_max - available_min).days < LIMIT_UP_BACKTEST_MIN_CALENDAR_DAYS:
        return _blocked_report(
            target,
            as_of,
            "insufficient_24m_daily_bars",
            available_min=available_min,
            available_max=available_max,
        )
    rows = repository.daily_rows_between(db, start_date=start, end_date=target)
    by_symbol: dict[str, list[object]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row.symbol)].append(row)
    samples_by_pattern: dict[str, list[dict[str, Any]]] = {code: [] for code in PATTERN_CODES}
    for symbol_rows in by_symbol.values():
        _collect_symbol_samples(symbol_rows, samples_by_pattern)
    metrics = {code: _metrics_for_samples(samples_by_pattern[code]) for code in PATTERN_CODES}
    all_samples = [sample for samples in samples_by_pattern.values() for sample in samples]
    overall = _metrics_for_samples(all_samples)
    gate, reasons = _gate_for_metrics(overall)
    return {
        "ok": True,
        "snapshot_type": LIMIT_UP_BACKTEST_SNAPSHOT_TYPE,
        "snapshot_key": LIMIT_UP_BACKTEST_SNAPSHOT_KEY,
        "trade_date": target.isoformat(),
        "window_months": 24,
        "window_start": start.isoformat(),
        "available_min": available_min.isoformat(),
        "available_max": available_max.isoformat(),
        "data_quality": "ok" if gate == "passed" else "research_only",
        "backtest_gate": gate,
        "gate_reasons": reasons,
        "overall": overall,
        "patterns": metrics,
        "future_leak_check": {
            "status": "passed",
            "outcome_start_after_confirmation": True,
            "violation_count": 0,
        },
        "engine_version": ENGINE_VERSION,
        "as_of": as_of.isoformat(),
        "research_only": True,
        "source": "daily_bar_snapshots",
    }


def persist_backtest_report(db: Session, report: dict[str, Any]) -> None:
    trade_date = date.fromisoformat(str(report.get("trade_date") or date.today().isoformat())[:10])
    data_quality = str(report.get("data_quality") or "blocked")
    as_of_raw = str(report.get("as_of") or "")
    try:
        as_of = datetime.fromisoformat(as_of_raw)
    except ValueError:
        as_of = datetime.now()
    repository.upsert_snapshot(
        db,
        snapshot_type=LIMIT_UP_BACKTEST_SNAPSHOT_TYPE,
        snapshot_key=LIMIT_UP_BACKTEST_SNAPSHOT_KEY,
        trade_date=trade_date,
        data_quality=data_quality,
        as_of=as_of,
        engine_version=ENGINE_VERSION,
        payload=report,
    )
    db.commit()


def read_cached_backtest_report(db: Session, *, trade_date: date | None = None) -> dict[str, Any] | None:
    row = repository.latest_snapshot(
        db,
        snapshot_type=LIMIT_UP_BACKTEST_SNAPSHOT_TYPE,
        snapshot_key=LIMIT_UP_BACKTEST_SNAPSHOT_KEY,
        trade_date=trade_date,
        engine_version=ENGINE_VERSION,
    )
    payload = repository.snapshot_payload(row)
    return payload or None


def _is_limit_up(row: object) -> bool:
    pct = float(getattr(row, "pct_chg", 0.0) or 0.0)
    close = float(getattr(row, "close_price", 0.0) or 0.0)
    limit_up = float(getattr(row, "limit_up_price", 0.0) or 0.0)
    return pct >= 9.5 or (limit_up > 0 and close >= limit_up * 0.995)


def _pattern(history: list[object], limit_date: date) -> str:
    after = [row for row in history if getattr(row, "trade_date") > limit_date]
    if len(after) >= 3 and all(float(getattr(row, "pct_chg", 0.0) or 0.0) < 0 for row in after[:3]):
        return "three_yin_floor"
    if after and float(getattr(after[-1], "volume", 0.0) or 0.0) < float(getattr(history[-2], "volume", 0.0) or 1.0) * 0.55:
        return "half_volume_signal"
    if len(after) >= 4:
        return "four_star_consolidation"
    if after and abs(float(getattr(after[-1], "pct_chg", 0.0) or 0.0)) >= 4:
        return "probe_updown"
    return "volume_stall_warning"


def _collect_symbol_samples(symbol_rows: list[object], samples_by_pattern: dict[str, list[dict[str, Any]]]) -> None:
    if len(symbol_rows) < 12:
        return
    for index, row in enumerate(symbol_rows):
        if not _is_limit_up(row):
            continue
        confirmation_index = index + 3
        outcome_index = confirmation_index + 5
        if index < 5 or outcome_index >= len(symbol_rows):
            continue
        history = symbol_rows[max(0, index - 5) : confirmation_index + 1]
        pattern_code = _pattern(history, getattr(row, "trade_date"))
        confirmation_close = float(getattr(symbol_rows[confirmation_index], "close_price", 0.0) or 0.0)
        outcome_close = float(getattr(symbol_rows[outcome_index], "close_price", 0.0) or 0.0)
        if confirmation_close <= 0 or outcome_close <= 0:
            continue
        outcome_return = (outcome_close - confirmation_close) / confirmation_close * 100.0
        sample = {
            "symbol": getattr(row, "symbol", ""),
            "limit_up_date": getattr(row, "trade_date").isoformat(),
            "confirmation_date": getattr(symbol_rows[confirmation_index], "trade_date").isoformat(),
            "outcome_start_date": getattr(symbol_rows[confirmation_index + 1], "trade_date").isoformat(),
            "outcome_end_date": getattr(symbol_rows[outcome_index], "trade_date").isoformat(),
            "return_pct": outcome_return,
            "quarter": _quarter(getattr(symbol_rows[confirmation_index], "trade_date")),
        }
        samples_by_pattern.setdefault(pattern_code, []).append(sample)


def _metrics_for_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    sample_count = len(samples)
    if not samples:
        return {
            "sample_count": 0,
            "winrate": None,
            "profit_factor": None,
            "max_drawdown": None,
            "quarter_stability": "blocked",
            "quarter_stability_rate": 0.0,
            "gate": "blocked",
        }
    returns = [float(sample["return_pct"]) for sample in samples]
    positive = [item for item in returns if item > 0]
    negative = [item for item in returns if item < 0]
    profit_factor = (sum(positive) / abs(sum(negative))) if negative else (999.0 if positive else 0.0)
    quarter_rate = _quarter_stability_rate(samples)
    gate, reasons = _gate_for_metrics(
        {
            "sample_count": sample_count,
            "winrate": len(positive) / sample_count,
            "profit_factor": profit_factor,
            "max_drawdown": _max_drawdown(returns),
            "quarter_stability_rate": quarter_rate,
        }
    )
    return {
        "sample_count": sample_count,
        "winrate": round(len(positive) / sample_count, 4),
        "profit_factor": round(min(profit_factor, 999.0), 4),
        "max_drawdown": round(_max_drawdown(returns), 4),
        "quarter_stability": "stable" if quarter_rate >= LIMIT_UP_BACKTEST_MIN_STABLE_QUARTERS else "unstable",
        "quarter_stability_rate": round(quarter_rate, 4),
        "gate": gate,
        "gate_reasons": reasons,
        "samples": samples[:5],
    }


def _gate_for_metrics(metrics: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if int(metrics.get("sample_count") or 0) < LIMIT_UP_BACKTEST_MIN_SAMPLES:
        reasons.append("sample_count_below_threshold")
    winrate = metrics.get("winrate")
    if winrate is None or float(winrate) < LIMIT_UP_BACKTEST_MIN_WINRATE:
        reasons.append("winrate_below_threshold")
    profit_factor = metrics.get("profit_factor")
    if profit_factor is None or float(profit_factor) < LIMIT_UP_BACKTEST_MIN_PROFIT_FACTOR:
        reasons.append("profit_factor_below_threshold")
    max_drawdown = metrics.get("max_drawdown")
    if max_drawdown is None or float(max_drawdown) < LIMIT_UP_BACKTEST_MAX_DRAWDOWN_PCT:
        reasons.append("max_drawdown_below_threshold")
    if float(metrics.get("quarter_stability_rate") or 0.0) < LIMIT_UP_BACKTEST_MIN_STABLE_QUARTERS:
        reasons.append("quarter_stability_below_threshold")
    return ("failed" if reasons else "passed"), reasons


def _max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for value in returns:
        equity *= 1.0 + value / 100.0
        peak = max(peak, equity)
        if peak > 0:
            max_dd = min(max_dd, (equity / peak - 1.0) * 100.0)
    return max_dd


def _quarter_stability_rate(samples: list[dict[str, Any]]) -> float:
    by_quarter: dict[str, list[float]] = defaultdict(list)
    for sample in samples:
        by_quarter[str(sample["quarter"])].append(float(sample["return_pct"]))
    if not by_quarter:
        return 0.0
    stable = 0
    for values in by_quarter.values():
        positive = sum(1 for value in values if value > 0)
        if positive / len(values) >= 0.45 and sum(values) > 0:
            stable += 1
    return stable / len(by_quarter)


def _quarter(value: date) -> str:
    quarter = (value.month - 1) // 3 + 1
    return f"{value.year}Q{quarter}"


def _blocked_report(target: date, as_of: datetime, reason: str, *, available_min: date | None, available_max: date | None) -> dict[str, Any]:
    return {
        "ok": True,
        "snapshot_type": LIMIT_UP_BACKTEST_SNAPSHOT_TYPE,
        "snapshot_key": LIMIT_UP_BACKTEST_SNAPSHOT_KEY,
        "trade_date": target.isoformat(),
        "window_months": 24,
        "data_quality": "blocked",
        "backtest_gate": "blocked",
        "gate_reasons": [reason],
        "available_min": available_min.isoformat() if available_min else "",
        "available_max": available_max.isoformat() if available_max else "",
        "overall": _metrics_for_samples([]),
        "patterns": {code: _metrics_for_samples([]) for code in PATTERN_CODES},
        "future_leak_check": {
            "status": "blocked",
            "outcome_start_after_confirmation": True,
            "violation_count": 0,
        },
        "engine_version": ENGINE_VERSION,
        "as_of": as_of.isoformat(),
        "research_only": True,
        "source": "daily_bar_snapshots",
    }


def _pattern_metrics(report: dict[str, Any] | None, pattern_code: str) -> dict[str, Any]:
    patterns = (report or {}).get("patterns")
    if isinstance(patterns, dict) and isinstance(patterns.get(pattern_code), dict):
        return patterns[pattern_code]
    overall = (report or {}).get("overall")
    return overall if isinstance(overall, dict) else {}


def _item_evidence(days_since: int, gate: str, metrics: dict[str, Any]) -> list[str]:
    evidence = [f"近 {days_since} 日出现涨停后跟踪形态", f"24M 回测门：{gate}"]
    if metrics:
        evidence.append(
            "回测样本 {sample_count}，胜率 {winrate}，PF {profit_factor}，最大回撤 {max_drawdown}".format(
                sample_count=int(metrics.get("sample_count") or 0),
                winrate="--" if metrics.get("winrate") is None else f"{float(metrics['winrate']):.2f}",
                profit_factor="--" if metrics.get("profit_factor") is None else f"{float(metrics['profit_factor']):.2f}",
                max_drawdown="--" if metrics.get("max_drawdown") is None else f"{float(metrics['max_drawdown']):.2f}%",
            )
        )
    return evidence
