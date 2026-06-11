from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import signal
import threading
import time
from typing import Any, Callable, Iterable

from app.core.database import SessionLocal
from app.services.auction.provider_spike_report import write_report
from app.services.auction.provider_spike_utils import (
    PROCESS_START,
    RESULT_START,
    WINDOW_END,
    build_window_status as _build_window_status,
    classify_bucket,
    dedupe_symbols,
    extract_row_time,
    instrument_type_for_symbol,
    json_safe_dict,
    latency_ms,
    market_for_symbol,
    normalize_beijing_datetime,
    parse_beijing_datetime,
    row_has_any,
)
from app.core.timezone import beijing_now
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.trading_calendar import is_a_share_trading_day
from app.services.market_quote_cache_refresh import build_quote_cache_demand_symbols

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover
    ak = None


SOURCE_NAME = "akshare.stock_zh_a_hist_pre_min_em"
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 3.0
MIN_OFFICIAL_SAMPLE_SIZE = 10
REQUIRED_SAMPLE_BUCKETS = ("sh_stock", "sz_stock", "etf")
SAMPLE_BUCKET_LABELS = {
    "sh_stock": "沪市股票",
    "sz_stock": "深市股票",
    "etf": "ETF",
    "other": "其他",
}
FALLBACK_COVERAGE_SYMBOLS = (
    "600000",
    "000001",
    "510300",
    "600519",
    "000333",
    "159915",
    "601318",
    "300750",
    "510050",
    "600030",
    "000858",
    "512100",
)


class ProviderCallTimeout(BaseException):
    pass


@dataclass(frozen=True)
class WindowStatus:
    status: str
    in_window: bool
    is_trading_day: bool
    checked_at: str
    trade_date: str
    window_start: str
    window_end: str
    message: str


@dataclass(frozen=True)
class SpikeSymbolResult:
    symbol: str
    market: str
    instrument_type: str
    source: str
    status: str
    data_quality: str
    row_count: int = 0
    process_row_count: int = 0
    result_row_count: int = 0
    latency_ms: int = 0
    fields: tuple[str, ...] = ()
    field_presence: dict[str, bool] | None = None
    latest_row: dict[str, Any] | None = None
    message: str = ""


Fetcher = Callable[[str], SpikeSymbolResult]


def run_spike(
    *,
    symbols: list[str],
    now: datetime | None = None,
    is_trading_day_func: Callable[[Any], bool] = is_a_share_trading_day,
    fetcher: Fetcher | None = None,
    sleep_seconds: float = 0.0,
    provider_timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    current = normalize_beijing_datetime(now or beijing_now())
    active_clock = clock or (beijing_now if now is None else lambda: current)
    window = build_window_status(current, is_trading_day_func=is_trading_day_func)
    sample = select_sample_symbols(symbols, sample_size=len(symbols))
    if not window.in_window:
        return build_report(
            now=current,
            window=window,
            symbols=sample,
            records=[],
            conclusion="blocked_by_window",
            status="blocked",
            message=window.message,
        )
    if not sample:
        return build_report(
            now=current,
            window=window,
            symbols=[],
            records=[],
            conclusion="blocked_by_sample_coverage",
            status="blocked",
            message="无可用于 spike 的目标标的。",
        )
    missing_buckets = missing_sample_buckets(sample)
    if missing_buckets:
        missing_labels = ", ".join(SAMPLE_BUCKET_LABELS[item] for item in missing_buckets)
        return build_report(
            now=current,
            window=window,
            symbols=sample,
            records=[],
            conclusion="blocked_by_sample_coverage",
            status="blocked",
            message=f"样本缺少必要覆盖：{missing_labels}。",
        )
    active_fetcher = fetcher or fetch_akshare_pre_min_symbol
    records: list[SpikeSymbolResult] = []
    stopped_by_window = False
    for symbol in sample:
        if normalize_beijing_datetime(active_clock()).time() > WINDOW_END:
            stopped_by_window = True
            break
        records.append(
            fetch_symbol_with_timeout(
                symbol,
                active_fetcher,
                timeout_seconds=provider_timeout_seconds,
            )
        )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    if stopped_by_window and len(records) < len(sample):
        conclusion = "blocked_by_window"
        status = "blocked"
        message = "窗口已结束，已停止后续 provider 调用，样本未完整。"
    else:
        conclusion, status, message = evaluate_conclusion(records)
    return build_report(
        now=current,
        window=window,
        symbols=sample,
        records=records,
        conclusion=conclusion,
        status=status,
        message=message,
    )


def load_target_symbols(*, raw_symbols: str = "", sample_size: int = 30) -> list[str]:
    if raw_symbols.strip():
        return select_sample_symbols(raw_symbols.split(","), sample_size=sample_size)
    try:
        with SessionLocal() as db:
            symbols = build_quote_cache_demand_symbols(db)
    except Exception:
        symbols = []
    return select_sample_symbols(symbols, sample_size=sample_size)


def select_sample_symbols(symbols: Iterable[str], *, sample_size: int) -> list[str]:
    cleaned = dedupe_symbols(symbols)
    if sample_size <= 0:
        return []
    if sample_size >= len(REQUIRED_SAMPLE_BUCKETS):
        cleaned = ensure_sample_coverage_candidates(cleaned, sample_size=sample_size)
    buckets: dict[str, list[str]] = {"sh_stock": [], "sz_stock": [], "etf": [], "other": []}
    for symbol in cleaned:
        buckets[classify_bucket(symbol)].append(symbol)
    selected: list[str] = []
    for bucket in ("sh_stock", "sz_stock", "etf"):
        if buckets[bucket]:
            selected.append(buckets[bucket][0])
    for symbol in cleaned:
        if len(selected) >= sample_size:
            break
        if symbol not in selected:
            selected.append(symbol)
    return selected[:sample_size]


def ensure_sample_coverage_candidates(symbols: list[str], *, sample_size: int) -> list[str]:
    candidates = list(symbols)
    seen = set(candidates)
    target_floor = min(sample_size, MIN_OFFICIAL_SAMPLE_SIZE)
    for fallback in FALLBACK_COVERAGE_SYMBOLS:
        if not missing_sample_buckets(candidates) and len(candidates) >= target_floor:
            break
        if fallback not in seen:
            candidates.append(fallback)
            seen.add(fallback)
    return candidates


def sample_coverage(symbols: Iterable[str]) -> dict[str, bool]:
    buckets = {bucket: False for bucket in REQUIRED_SAMPLE_BUCKETS}
    for symbol in dedupe_symbols(symbols):
        bucket = classify_bucket(symbol)
        if bucket in buckets:
            buckets[bucket] = True
    return buckets


def missing_sample_buckets(symbols: Iterable[str]) -> list[str]:
    coverage = sample_coverage(symbols)
    return [bucket for bucket in REQUIRED_SAMPLE_BUCKETS if not coverage[bucket]]


def fetch_symbol_with_timeout(
    symbol: str,
    fetcher: Fetcher,
    *,
    timeout_seconds: float,
) -> SpikeSymbolResult:
    started = time.perf_counter()
    if timeout_seconds <= 0 or threading.current_thread() is not threading.main_thread():
        try:
            return fetcher(symbol)
        except Exception as exc:
            return spike_error(symbol, str(exc)[:240], started=started)
    previous_handler = signal.getsignal(signal.SIGALRM)

    def handle_timeout(_signal_number: int, _frame: Any) -> None:
        raise ProviderCallTimeout()

    try:
        signal.signal(signal.SIGALRM, handle_timeout)
        signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
        return fetcher(symbol)
    except ProviderCallTimeout:
        return spike_error(symbol, f"provider timeout after {timeout_seconds:.2f}s", started=started)
    except Exception as exc:
        return spike_error(symbol, str(exc)[:240], started=started)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def fetch_akshare_pre_min_symbol(symbol: str) -> SpikeSymbolResult:
    started = time.perf_counter()
    if ak is None:
        return spike_error(symbol, "akshare unavailable", started=started)
    try:
        frame = ak.stock_zh_a_hist_pre_min_em(symbol=symbol, start_time="09:19:30", end_time="09:25:30")
        records = [] if frame is None or getattr(frame, "empty", False) else frame.to_dict("records")
        analysis = inspect_pre_min_records(records)
        quality = quality_from_analysis(analysis)
        provider_result = ProviderResult(
            quality=provider_quality(quality),
            source=SOURCE_NAME,
            data=analysis if quality != "no_data" else None,
            message=analysis["message"],
            latency_ms=latency_ms(started),
        )
        status = "ok" if quality == "ok" else quality
        return SpikeSymbolResult(
            symbol=symbol,
            market=market_for_symbol(symbol),
            instrument_type=instrument_type_for_symbol(symbol),
            source=provider_result.source,
            status=status,
            data_quality=quality,
            row_count=int(analysis["row_count"]),
            process_row_count=int(analysis["process_row_count"]),
            result_row_count=int(analysis["result_row_count"]),
            latency_ms=provider_result.latency_ms,
            fields=tuple(analysis["fields"]),
            field_presence=dict(analysis["field_presence"]),
            latest_row=dict(analysis["latest_row"]),
            message=provider_result.message,
        )
    except ProviderCallTimeout:
        raise
    except Exception as exc:
        return spike_error(symbol, str(exc)[:240], started=started)


def inspect_pre_min_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    safe_records = [json_safe_dict(row) for row in records if isinstance(row, dict)]
    fields = sorted({str(key) for row in safe_records for key in row})
    process_count = 0
    result_count = 0
    timestamp_count = 0
    for row in safe_records:
        row_time = extract_row_time(row)
        if row_time is None:
            continue
        timestamp_count += 1
        if PROCESS_START <= row_time < RESULT_START:
            process_count += 1
        if RESULT_START <= row_time <= WINDOW_END:
            result_count += 1
    field_presence = {
        "timestamp": timestamp_count > 0,
        "price": any(row_has_any(row, ("最新价", "价格", "成交价", "收盘", "close", "price")) for row in safe_records),
        "matched_volume": any(row_has_any(row, ("成交量", "匹配量", "volume", "vol")) for row in safe_records),
        "amount": any(row_has_any(row, ("成交额", "amount")) for row in safe_records),
        "unmatched_volume": any(row_has_any(row, ("未匹配", "未成交", "撤单", "unmatched")) for row in safe_records),
    }
    if not safe_records:
        message = "provider 返回空数据。"
    elif field_presence["price"] and field_presence["timestamp"]:
        message = "provider 返回价格和时间字段。"
    else:
        message = "provider 返回数据但核心字段不完整。"
    return {
        "row_count": len(safe_records),
        "process_row_count": process_count,
        "result_row_count": result_count,
        "fields": fields,
        "field_presence": field_presence,
        "latest_row": safe_records[-1] if safe_records else {},
        "message": message,
    }


def evaluate_conclusion(records: list[SpikeSymbolResult]) -> tuple[str, str, str]:
    if not records:
        return ("provider_failed", "provider_failed", "无 provider 调用结果。")
    usable = [item for item in records if item.data_quality in {"ok", "partial"}]
    failure_rate = 1.0 - (len(usable) / max(len(records), 1))
    has_process = any(item.process_row_count > 0 for item in usable)
    has_result = any(item.result_row_count > 0 for item in usable)
    if usable and has_process and has_result and failure_rate <= 0.4:
        return ("provider_ok", "ok", "provider 同时返回 9:20-9:25 过程行和 9:25 结果行。")
    if usable and has_result and failure_rate <= 0.4:
        return ("result_only", "ok", "provider 仅证明 9:25 结果可用，过程字段不足。")
    return ("provider_failed", "provider_failed", "provider 未能稳定返回 9:25 结果或失败率过高。")


def build_report(
    *,
    now: datetime,
    window: WindowStatus,
    symbols: list[str],
    records: list[SpikeSymbolResult],
    conclusion: str,
    status: str,
    message: str,
) -> dict[str, Any]:
    serial_records = [asdict(item) for item in records]
    fields = sorted({field for item in records for field in item.fields})
    usable_count = sum(1 for item in records if item.data_quality in {"ok", "partial"})
    return {
        "report": "call_auction_provider_spike",
        "generated_at": now.isoformat(timespec="seconds"),
        "status": status,
        "conclusion": conclusion,
        "message": message,
        "source": SOURCE_NAME,
        "symbols": symbols,
        "window": asdict(window),
        "summary": {
            "sample_size": len(symbols),
            "called_count": len(records),
            "usable_count": usable_count,
            "failure_count": max(len(records) - usable_count, 0),
            "failure_rate": round(1 - usable_count / max(len(records), 1), 4) if records else 0.0,
            "process_symbols": sum(1 for item in records if item.process_row_count > 0),
            "result_symbols": sum(1 for item in records if item.result_row_count > 0),
            "fields": fields,
            "sample_coverage": sample_coverage(symbols),
            "missing_sample_buckets": missing_sample_buckets(symbols),
        },
        "records": serial_records,
        "phase_decision": {
            "g2_allowed": conclusion in {"provider_ok", "result_only"},
            "g4_allowed": conclusion == "provider_ok",
            "reason": message,
        },
    }


def build_window_status(
    now: datetime,
    *,
    is_trading_day_func: Callable[[Any], bool] = is_a_share_trading_day,
) -> WindowStatus:
    return _build_window_status(now, WindowStatus, is_trading_day_func=is_trading_day_func)


def quality_from_analysis(analysis: dict[str, Any]) -> str:
    if int(analysis["row_count"]) <= 0:
        return "no_data"
    fields = analysis["field_presence"]
    if fields.get("price") and fields.get("timestamp"):
        return "ok"
    return "partial"


def provider_quality(data_quality: str) -> MarketDataQuality:
    if data_quality == "ok":
        return MarketDataQuality.FRESH
    if data_quality == "partial":
        return MarketDataQuality.ESTIMATED
    return MarketDataQuality.UNAVAILABLE


def spike_error(symbol: str, message: str, *, started: float) -> SpikeSymbolResult:
    return SpikeSymbolResult(
        symbol=symbol,
        market=market_for_symbol(symbol),
        instrument_type=instrument_type_for_symbol(symbol),
        source=SOURCE_NAME,
        status="provider_failed",
        data_quality="provider_failed",
        latency_ms=latency_ms(started),
        message=message,
    )
