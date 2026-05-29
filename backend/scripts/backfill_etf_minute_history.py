from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
DEFAULT_REPORT_OUTPUT = ROOT_DIR / "docs" / "reports" / "etf-minute-backfill-latest.json"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.schemas import KlineBar, QuoteSnapshot
from app.services.etf.universe import EtfProfile, list_etf_profiles
from app.services.market.minute_bar_store import MinuteBarSnapshotStore
from app.services.market.shared import guess_market, to_secid
try:
    from .etf_minute_akshare_provider import fetch_akshare_etf_hist_minute_bars, fetch_tushare_etf_hist_minute_bars
    from .etf_minute_backfill_helpers import ProviderCandidate, enrich_etf_bars, execution_quality_summary, minute_data_quality, select_best_candidate
except ImportError:  # pragma: no cover
    from etf_minute_akshare_provider import fetch_akshare_etf_hist_minute_bars, fetch_tushare_etf_hist_minute_bars
    from etf_minute_backfill_helpers import ProviderCandidate, enrich_etf_bars, execution_quality_summary, minute_data_quality, select_best_candidate


@dataclass(frozen=True)
class EtfMinuteBackfillResult:
    symbol: str
    name: str
    category: str
    status: str
    rows: int = 0
    period: str = "5m"
    source: str = ""
    data_quality: str = ""
    message: str = ""
    provider_errors: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class FetchResult:
    source: str
    bars: list[KlineBar]
    provider_errors: list[dict[str, str]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="补齐可 T0 ETF 分钟线到 minute_bar_snapshots")
    parser.add_argument("--start-date", default="", help="开始日期 YYYY-MM-DD；为空时按 months 计算")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--period", choices=("1m", "5m", "15m", "30m", "60m"), default="5m")
    parser.add_argument("--scope", choices=("t0-etf", "symbols"), default="t0-etf")
    parser.add_argument("--symbols", default="", help="scope=symbols 时使用，逗号分隔 ETF 代码")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-partial", action="store_true", help="即使部分 ETF 失败也返回 0；报告仍标记 partial_data")
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    start_date = args.start_date or (date.fromisoformat(args.end_date) - timedelta(days=max(args.months, 1) * 31 + 90)).isoformat()
    profiles = resolve_profiles(scope=args.scope, raw_symbols=args.symbols)
    if args.limit > 0:
        profiles = profiles[: args.limit]
    if not profiles:
        raise SystemExit("未解析到可补数 ETF")
    results = backfill_profiles(profiles=profiles, start_date=start_date, end_date=args.end_date, args=args)
    totals = summarize_results(results)
    report = build_report(args=args, start_date=start_date, profiles=profiles, results=results, totals=totals)
    write_report(Path(args.report_output), report)
    print(json.dumps({"report": str(args.report_output), "totals": totals}, ensure_ascii=False, indent=2), flush=True)
    return 0 if args.allow_partial or not totals.get("error") else 2


def resolve_profiles(*, scope: str, raw_symbols: str) -> list[EtfProfile]:
    profiles = [item for item in list_etf_profiles() if item.same_day_sell_allowed]
    if scope == "symbols":
        wanted = {item.strip() for item in raw_symbols.split(",") if item.strip()}
        if not wanted:
            raise SystemExit("scope=symbols 时必须提供 --symbols")
        profiles = [item for item in profiles if item.symbol in wanted]
    return sorted(profiles, key=lambda item: item.symbol)


def backfill_profiles(
    *,
    profiles: list[EtfProfile],
    start_date: str,
    end_date: str,
    args: argparse.Namespace,
) -> list[EtfMinuteBackfillResult]:
    workers = min(max(1, int(args.workers or 1)), len(profiles))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                backfill_profile,
                profile,
                start_date=start_date,
                end_date=end_date,
                period=args.period,
                sleep_seconds=max(float(args.sleep or 0.0), 0.0),
                force=bool(args.force),
            )
            for profile in profiles
        ]
        return [future.result() for future in as_completed(futures)]


def backfill_profile(
    profile: EtfProfile,
    *,
    start_date: str,
    end_date: str,
    period: str,
    sleep_seconds: float,
    force: bool,
) -> EtfMinuteBackfillResult:
    try:
        if not force and coverage_exists(symbol=profile.symbol, start_date=start_date, end_date=end_date, period=period):
            return result_for(profile, "skip", period=period, message="coverage exists")
        fetched = fetch_etf_minute_bars(profile=profile, start_date=start_date, end_date=end_date, period=period)
        bars = enrich_etf_bars(profile, fetched.bars)
        if not bars:
            return result_for(profile, "empty", period=period, message="remote empty", provider_errors=fetched.provider_errors)
        quote = quote_for_profile(profile, bars[-1], source=fetched.source)
        with SessionLocal() as db:
            count = MinuteBarSnapshotStore(db).persist(
                quote,
                bars,
                bar_period=period,
                skip_older_than_latest=False,
            )
        time.sleep(sleep_seconds)
        quality = execution_quality_summary(profile, bars)
        return result_for(profile, "ok", rows=count, period=period, source=fetched.source, data_quality=quality, provider_errors=fetched.provider_errors)
    except Exception as exc:
        return result_for(profile, "error", period=period, message=str(exc)[:220])


def fetch_etf_minute_bars(*, symbol: str = "", profile: EtfProfile | None = None, start_date: str, end_date: str, period: str) -> FetchResult:
    symbol_value = profile.symbol if profile else symbol
    provider_errors: list[dict[str, str]] = []
    candidates: list[ProviderCandidate] = []
    for source, fetcher in minute_fetchers(period):
        try:
            bars = fetcher(symbol=symbol_value, start_date=start_date, end_date=end_date, period=period)
        except Exception as exc:
            provider_errors.append({"source": source, "message": str(exc)[:180]})
            continue
        if bars:
            candidates.append(ProviderCandidate(source, enrich_etf_bars(profile, bars) if profile else bars))
            provider_errors.append({"source": source, "message": f"candidate:{len(bars)} bars/{candidates[-1].trade_days} trade_days"})
            continue
        provider_errors.append({"source": source, "message": "empty"})
    best = select_best_candidate(candidates)
    return FetchResult(source=best.source, bars=best.bars, provider_errors=provider_errors) if best else FetchResult(source="", bars=[], provider_errors=provider_errors)


def minute_fetchers(period: str):
    yield "tushare.stk_mins", fetch_tushare_etf_hist_minute_bars
    yield "eastmoney.etf_minute", fetch_eastmoney_etf_minute_bars
    yield "akshare.fund_etf_hist_min_em", fetch_akshare_etf_hist_minute_bars
    yield "sina.kline", fetch_sina_minute_bars
    if period == "1m":
        yield "tencent.minute", fetch_tencent_minute_bars
        yield "eastmoney.trends2", fetch_eastmoney_trend_bars


def fetch_eastmoney_etf_minute_bars(*, symbol: str, start_date: str, end_date: str, period: str) -> list[KlineBar]:
    if period == "1m":
        return fetch_eastmoney_trend_bars(symbol=symbol, start_date=start_date, end_date=end_date, period=period)
    payload = fetch_json(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": period.removesuffix("m"),
            "fqt": "0",
            "secid": to_secid(symbol),
            "beg": start_date.replace("-", ""),
            "end": end_date.replace("-", ""),
        },
    )
    return parse_kline_rows((payload.get("data") or {}).get("klines") or [])


def fetch_eastmoney_trend_bars(*, symbol: str, start_date: str, end_date: str, period: str) -> list[KlineBar]:  # noqa: ARG001
    payload = fetch_json(
        "https://push2his.eastmoney.com/api/qt/stock/trends2/get",
        {
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "ndays": "5",
            "iscr": "0",
            "secid": to_secid(symbol),
        },
    )
    return filter_bars(parse_trend_rows((payload.get("data") or {}).get("trends") or []), start_date, end_date)


def fetch_tencent_minute_bars(*, symbol: str, start_date: str, end_date: str, period: str) -> list[KlineBar]:
    if period != "1m":
        return []
    payload = fetch_json(
        "https://ifzq.gtimg.cn/appstock/app/minute/query",
        {"code": tencent_symbol(symbol)},
    )
    raw = ((payload.get("data") or {}).get(tencent_symbol(symbol)) or {}).get("data") or {}
    return filter_bars(parse_tencent_rows(raw.get("date") or "", raw.get("data") or []), start_date, end_date)


def fetch_sina_minute_bars(*, symbol: str, start_date: str, end_date: str, period: str) -> list[KlineBar]:
    payload = fetch_sina_jsonp(
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData",
        {"symbol": tencent_symbol(symbol), "scale": period.removesuffix("m"), "ma": "no", "datalen": "1970"},
    )
    if not isinstance(payload, list):
        return []
    return filter_bars(parse_sina_rows(payload), start_date, end_date)


def fetch_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
    try:
        response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception:
        query = urllib.parse.urlencode(params, safe=",:")
        request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - controlled market data URL
            return json.loads(response.read().decode("utf-8", errors="ignore"))


def fetch_sina_jsonp(url: str, params: dict[str, str]) -> Any:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"})
    response = session.get(url, params=params, timeout=15)
    response.raise_for_status()
    text = response.text
    if "=(" in text:
        text = text.split("=(", 1)[1].rsplit(");", 1)[0]
    return json.loads(text)


def parse_kline_rows(rows: Iterable[str]) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for raw in rows:
        parts = str(raw).split(",")
        if len(parts) < 7:
            continue
        bars.append(build_bar(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]))
    return [bar for bar in bars if bar.close > 0]


def parse_trend_rows(rows: Iterable[str]) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for raw in rows:
        parts = str(raw).split(",")
        if len(parts) < 7:
            continue
        bars.append(build_bar(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]))
    return [bar for bar in bars if bar.close > 0]


def parse_tencent_rows(trade_date: str, rows: Iterable[str]) -> list[KlineBar]:
    day = str(trade_date or "")
    if len(day) < 8:
        return []
    trade_day = f"{day[:4]}-{day[4:6]}-{day[6:8]}"
    bars: list[KlineBar] = []
    previous_close = 0.0
    previous_volume = 0.0
    previous_amount = 0.0
    for raw in rows:
        parts = str(raw).split()
        if len(parts) < 4:
            continue
        hhmm = parts[0]
        close_price = safe_float(parts[1])
        cumulative_volume = safe_float(parts[2])
        cumulative_amount = safe_float(parts[3])
        if len(hhmm) != 4 or close_price <= 0:
            continue
        volume = max(cumulative_volume - previous_volume, 0.0)
        amount = max(cumulative_amount - previous_amount, 0.0)
        open_price = previous_close or close_price
        bars.append(
            KlineBar(
                timestamp=f"{trade_day} {hhmm[:2]}:{hhmm[2:]}",
                open=open_price,
                close=close_price,
                high=max(open_price, close_price),
                low=min(open_price, close_price),
                volume=volume,
                amount=amount,
            )
        )
        previous_close = close_price
        previous_volume = cumulative_volume
        previous_amount = cumulative_amount
    return bars


def parse_sina_rows(rows: Iterable[dict[str, Any]]) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        bars.append(
            build_bar(
                str(raw.get("day") or ""),
                raw.get("open"),
                raw.get("close"),
                raw.get("high"),
                raw.get("low"),
                raw.get("volume"),
                raw.get("amount"),
            )
        )
    return [bar for bar in bars if bar.close > 0]


def build_bar(timestamp: str, open_price: str, close_price: str, high_price: str, low_price: str, volume: str, amount: str) -> KlineBar:
    close_value = safe_float(close_price)
    return KlineBar(
        timestamp=str(timestamp)[:16],
        open=safe_float(open_price) or close_value,
        close=close_value,
        high=safe_float(high_price) or close_value,
        low=safe_float(low_price) or close_value,
        volume=safe_float(volume),
        amount=safe_float(amount),
    )


def safe_float(value: Any) -> float:
    try:
        if value in (None, "", "-", "--"):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def filter_bars(bars: list[KlineBar], start_date: str, end_date: str) -> list[KlineBar]:
    start = f"{start_date} 00:00"
    end = f"{end_date} 23:59"
    return [bar for bar in bars if start <= bar.timestamp <= end]


def tencent_symbol(symbol: str) -> str:
    prefix = "sh" if guess_market(symbol) == "SH" else "sz"
    return f"{prefix}{symbol}"


def coverage_exists(*, symbol: str, start_date: str, end_date: str, period: str) -> bool:
    from sqlalchemy import func, select
    from app.models.entities import MinuteBarSnapshot

    with SessionLocal() as db:
        row = db.execute(
            select(func.min(MinuteBarSnapshot.trade_date), func.max(MinuteBarSnapshot.trade_date), func.count(MinuteBarSnapshot.id)).where(
                MinuteBarSnapshot.symbol == symbol,
                MinuteBarSnapshot.bar_period == period,
            )
        ).one()
    return bool(row[2]) and str(row[0]) <= start_date and str(row[1]) >= end_date


def quote_for_profile(profile: EtfProfile, bar: KlineBar, *, source: str) -> QuoteSnapshot:
    enrich_etf_bars(profile, [bar])
    return QuoteSnapshot(
        symbol=profile.symbol,
        name=profile.name,
        market=guess_market(profile.symbol),
        instrument_type="etf",
        last_price=bar.close,
        change_pct=0.0,
        change_amount=0.0,
        open_price=bar.open,
        high_price=bar.high,
        low_price=bar.low,
        prev_close=0.0,
        volume=bar.volume,
        amount=bar.amount,
        timestamp=bar.timestamp,
        data_source=source,
        data_quality=minute_data_quality(profile=profile, bar=bar),
    )

def result_for(
    profile: EtfProfile,
    status: str,
    *,
    rows: int = 0,
    period: str,
    source: str = "",
    data_quality: str = "",
    message: str = "",
    provider_errors: list[dict[str, str]] | None = None,
) -> EtfMinuteBackfillResult:
    return EtfMinuteBackfillResult(profile.symbol, profile.name, profile.category.value, status, rows, period, source, data_quality, message, provider_errors or [])


def summarize_results(results: list[EtfMinuteBackfillResult]) -> dict[str, int]:
    totals = {"ok": 0, "skip": 0, "empty": 0, "error": 0}
    for item in results:
        totals[item.status] = totals.get(item.status, 0) + 1
    return totals


def quality_summary(bars: list[KlineBar]) -> str:
    fresh = sum(1 for bar in bars if bar.close > 0 and bar.high >= bar.low and bar.volume >= 0 and bar.amount >= 0)
    unavailable = len(bars) - fresh
    return f"fresh:{fresh}" if unavailable == 0 else f"fresh:{fresh},unavailable:{unavailable}"


def build_report(*, args: argparse.Namespace, start_date: str, profiles: list[EtfProfile], results: list[EtfMinuteBackfillResult], totals: dict[str, int]) -> dict[str, Any]:
    failed = [item for item in results if item.status in {"error", "empty"}]
    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "status": "completed" if not failed else "partial_data",
        "config": {
            "scope": args.scope,
            "symbol_count": len(profiles),
            "start_date": start_date,
            "end_date": args.end_date,
            "period": args.period,
            "workers": args.workers,
            "force": args.force,
            "allow_partial": args.allow_partial,
        },
        "totals": totals,
        "results": [asdict(item) for item in sorted(results, key=lambda row: row.symbol)],
        "failed_symbols": [asdict(item) for item in sorted(failed, key=lambda row: row.symbol)],
        "notes": [
            "仅补 ETF universe 中 same_day_sell_allowed=true 的标的，避免把所有 ETF 错当 T+0。",
            "5m/15m/30m/60m 优先 Tushare/Eastmoney/AkShare 历史分钟线，可 fallback 到 Sina 近端 K 线；1m 可额外 fallback 到 Tencent/Eastmoney 近端趋势源。",
            "未取到远端数据时只写 partial_data/error/empty，不生成伪分钟线。",
            "盘口价差、折溢价等执行元数据只写真实字段；缺失时标记 partial_metadata，不能通过生产门禁。",
        ],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
