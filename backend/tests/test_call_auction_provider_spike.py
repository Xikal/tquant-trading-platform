from __future__ import annotations

import json
import time
from datetime import datetime

from scripts import call_auction_provider_spike as spike


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _result(
    symbol: str,
    *,
    process_rows: int = 0,
    result_rows: int = 0,
    quality: str = "ok",
) -> spike.SpikeSymbolResult:
    return spike.SpikeSymbolResult(
        symbol=symbol,
        market=spike.market_for_symbol(symbol),
        instrument_type=spike.instrument_type_for_symbol(symbol),
        source=spike.SOURCE_NAME,
        status="ok" if quality == "ok" else quality,
        data_quality=quality,
        row_count=process_rows + result_rows,
        process_row_count=process_rows,
        result_row_count=result_rows,
        latency_ms=12,
        fields=("时间", "最新价", "成交量"),
        field_presence={"timestamp": True, "price": True, "matched_volume": True},
        latest_row={"时间": "2026-06-11 09:25:01", "最新价": 10.1},
        message="fixture",
    )


def test_window_before_spike_blocks_without_provider_call() -> None:
    called: list[str] = []

    def fetcher(symbol: str) -> spike.SpikeSymbolResult:
        called.append(symbol)
        return _result(symbol)

    report = spike.run_spike(
        symbols=["600000", "000001"],
        now=_dt("2026-06-11T09:01:00+08:00"),
        is_trading_day_func=lambda _date: True,
        fetcher=fetcher,
    )

    assert report["status"] == "blocked"
    assert report["conclusion"] == "blocked_by_window"
    assert report["phase_decision"]["g2_allowed"] is False
    assert called == []


def test_provider_ok_requires_process_and_result_rows() -> None:
    report = spike.run_spike(
        symbols=["600000", "000001", "510300"],
        now=_dt("2026-06-11T09:24:30+08:00"),
        is_trading_day_func=lambda _date: True,
        fetcher=lambda symbol: _result(symbol, process_rows=2, result_rows=1),
    )

    assert report["status"] == "ok"
    assert report["conclusion"] == "provider_ok"
    assert report["phase_decision"]["g2_allowed"] is True
    assert report["phase_decision"]["g4_allowed"] is True


def test_result_only_when_no_process_rows() -> None:
    report = spike.run_spike(
        symbols=["600000", "000001", "510300"],
        now=_dt("2026-06-11T09:25:05+08:00"),
        is_trading_day_func=lambda _date: True,
        fetcher=lambda symbol: _result(symbol, process_rows=0, result_rows=1),
    )

    assert report["status"] == "ok"
    assert report["conclusion"] == "result_only"
    assert report["phase_decision"]["g2_allowed"] is True
    assert report["phase_decision"]["g4_allowed"] is False


def test_provider_failed_when_failure_rate_is_high() -> None:
    def fetcher(symbol: str) -> spike.SpikeSymbolResult:
        if symbol == "600000":
            return _result(symbol, process_rows=1, result_rows=1)
        return _result(symbol, quality="provider_failed")

    report = spike.run_spike(
        symbols=["600000", "000001", "510300"],
        now=_dt("2026-06-11T09:24:30+08:00"),
        is_trading_day_func=lambda _date: True,
        fetcher=fetcher,
    )

    assert report["status"] == "provider_failed"
    assert report["conclusion"] == "provider_failed"
    assert report["summary"]["failure_rate"] > 0.4


def test_select_sample_symbols_keeps_market_and_etf_coverage() -> None:
    selected = spike.select_sample_symbols(
        ["000002", "600000", "510300", "300001", "600519"],
        sample_size=3,
    )

    assert selected == ["600000", "000002", "510300"]


def test_select_sample_symbols_backfills_missing_market_categories() -> None:
    selected = spike.select_sample_symbols(["510300", "510050", "512100"], sample_size=3)

    assert selected == ["600000", "000001", "510300"]
    assert spike.missing_sample_buckets(selected) == []


def test_select_sample_symbols_uses_official_fallback_floor() -> None:
    selected = spike.select_sample_symbols([], sample_size=30)

    assert len(selected) >= 10
    assert spike.missing_sample_buckets(selected) == []


def test_sample_coverage_blocks_when_sample_size_is_too_small() -> None:
    called: list[str] = []

    def fetcher(symbol: str) -> spike.SpikeSymbolResult:
        called.append(symbol)
        return _result(symbol, process_rows=1, result_rows=1)

    report = spike.run_spike(
        symbols=["600000", "000001"],
        now=_dt("2026-06-11T09:24:30+08:00"),
        is_trading_day_func=lambda _date: True,
        fetcher=fetcher,
    )

    assert report["status"] == "blocked"
    assert report["conclusion"] == "blocked_by_sample_coverage"
    assert report["summary"]["missing_sample_buckets"] == ["etf"]
    assert called == []


def test_inspect_pre_min_records_detects_process_result_and_fields() -> None:
    analysis = spike.inspect_pre_min_records(
        [
            {"时间": "2026-06-11 09:20:01", "最新价": 10.0, "成交量": 100},
            {"时间": "2026-06-11 09:25:01", "最新价": 10.2, "成交额": 1020},
        ]
    )

    assert analysis["row_count"] == 2
    assert analysis["process_row_count"] == 1
    assert analysis["result_row_count"] == 1
    assert analysis["field_presence"]["timestamp"] is True
    assert analysis["field_presence"]["price"] is True
    assert analysis["field_presence"]["matched_volume"] is True
    assert analysis["field_presence"]["amount"] is True


def test_inspect_pre_min_records_accepts_minute_timestamps() -> None:
    analysis = spike.inspect_pre_min_records(
        [
            {"时间": "09:20", "最新价": 10.0, "成交量": 100},
            {"时间": "2026-06-11 09:25", "最新价": 10.2, "成交额": 1020},
        ]
    )

    assert analysis["process_row_count"] == 1
    assert analysis["result_row_count"] == 1
    assert analysis["field_presence"]["timestamp"] is True


def test_provider_timeout_returns_failed_result() -> None:
    def slow_fetcher(symbol: str) -> spike.SpikeSymbolResult:
        time.sleep(0.05)
        return _result(symbol, process_rows=1, result_rows=1)

    report = spike.run_spike(
        symbols=["600000", "000001", "510300"],
        now=_dt("2026-06-11T09:24:30+08:00"),
        is_trading_day_func=lambda _date: True,
        fetcher=slow_fetcher,
        provider_timeout_seconds=0.001,
    )

    assert report["status"] == "provider_failed"
    assert report["summary"]["called_count"] == 3
    assert all("timeout" in item["message"] for item in report["records"])


def test_run_spike_stops_launching_calls_after_window_end() -> None:
    called: list[str] = []
    clock_values = iter(
        [
            _dt("2026-06-11T09:24:30+08:00"),
            _dt("2026-06-11T09:25:31+08:00"),
        ]
    )

    def fetcher(symbol: str) -> spike.SpikeSymbolResult:
        called.append(symbol)
        return _result(symbol, process_rows=1, result_rows=1)

    report = spike.run_spike(
        symbols=["600000", "000001", "510300"],
        now=_dt("2026-06-11T09:24:30+08:00"),
        is_trading_day_func=lambda _date: True,
        fetcher=fetcher,
        clock=lambda: next(clock_values),
    )

    assert report["status"] == "blocked"
    assert report["conclusion"] == "blocked_by_window"
    assert report["summary"]["called_count"] == 1
    assert called == ["600000"]


def test_write_report_outputs_markdown_and_json(tmp_path) -> None:
    report = spike.run_spike(
        symbols=["600000", "000001", "510300"],
        now=_dt("2026-06-11T09:24:30+08:00"),
        is_trading_day_func=lambda _date: True,
        fetcher=lambda symbol: _result(symbol, process_rows=1, result_rows=1),
    )
    markdown_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"

    spike.write_report(report, markdown_path=markdown_path, json_path=json_path)

    assert "集合竞价 Provider Spike 报告" in markdown_path.read_text(encoding="utf-8")
    stored = json.loads(json_path.read_text(encoding="utf-8"))
    assert stored["conclusion"] == "provider_ok"
