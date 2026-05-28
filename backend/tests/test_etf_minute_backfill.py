from __future__ import annotations

import json
from argparse import Namespace

from app.models.schemas import KlineBar
from backend.scripts import backfill_etf_minute_history as script
from backend.scripts import etf_minute_akshare_provider as ak_provider


def test_etf_minute_backfill_resolves_only_t0_profiles() -> None:
    profiles = script.resolve_profiles(scope="symbols", raw_symbols="510300,512999")

    assert [item.symbol for item in profiles] == ["510300"]


def test_etf_minute_quality_is_partial_without_spread_or_premium_metadata() -> None:
    profile = script.resolve_profiles(scope="symbols", raw_symbols="518880")[0]
    bar = KlineBar(timestamp="2026-05-27 09:31", open=5, high=5.1, low=4.9, close=5, volume=1000, amount=5000)

    quote = script.quote_for_profile(profile, bar, source="tencent.minute")

    assert quote.data_quality == "partial_metadata"
    assert bar.tracking_index_symbol == profile.tracking_index
    assert bar.liquidity_tier == "thin"


def test_etf_minute_backfill_parses_kline_rows_without_future_fill() -> None:
    bars = script.parse_kline_rows(
        [
            "2026-04-28 09:35,4.000,4.050,4.060,3.990,1000,4050,0,0,0,0",
            "bad,row",
            "2026-04-28 09:40,4.050,0,4.060,4.030,1000,4050,0,0,0,0",
        ]
    )

    assert len(bars) == 1
    assert bars[0].timestamp == "2026-04-28 09:35"
    assert bars[0].close == 4.05


def test_etf_minute_backfill_falls_back_to_tencent(monkeypatch) -> None:
    def fake_fetch_json(url: str, params: dict[str, str]):
        if "trends2" in url:
            raise RuntimeError("eastmoney down")
        assert params["code"] == "sh510300"
        return {"data": {"sh510300": {"data": {"date": "20260428", "data": ["0931 4.01 100 401", "0932 4.02 180 724"]}}}}

    monkeypatch.setattr(script, "fetch_json", fake_fetch_json)

    result = script.fetch_etf_minute_bars(symbol="510300", start_date="2026-04-28", end_date="2026-04-28", period="1m")

    assert result.source == "tencent.minute"
    assert len(result.bars) == 2
    assert [item["source"] for item in result.provider_errors[:3]] == ["tushare.stk_mins", "eastmoney.etf_minute", "akshare.fund_etf_hist_min_em"]


def test_etf_minute_backfill_records_provider_errors_when_all_sources_fail(monkeypatch) -> None:
    monkeypatch.setattr(script, "fetch_json", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network down")))
    monkeypatch.setattr(script, "fetch_sina_jsonp", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("sina down")))
    monkeypatch.setattr(script, "fetch_tushare_etf_hist_minute_bars", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("tushare down")))
    monkeypatch.setattr(script, "fetch_akshare_etf_hist_minute_bars", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("akshare down")))

    result = script.fetch_etf_minute_bars(symbol="510300", start_date="2026-04-28", end_date="2026-04-28", period="1m")

    assert result.bars == []
    assert [item["source"] for item in result.provider_errors] == ["tushare.stk_mins", "eastmoney.etf_minute", "akshare.fund_etf_hist_min_em", "sina.kline", "tencent.minute", "eastmoney.trends2"]


def test_etf_minute_backfill_records_missing_tushare_token(monkeypatch) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.delenv("TUSHARE_API_TOKEN", raising=False)
    monkeypatch.delenv("TUSHARE_PRO_TOKEN", raising=False)
    monkeypatch.setattr(script, "fetch_json", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("stop after tushare")))
    monkeypatch.setattr(script, "fetch_sina_jsonp", lambda *args, **kwargs: [])

    result = script.fetch_etf_minute_bars(symbol="510300", start_date="2024-05-28", end_date="2024-05-28", period="5m")

    assert result.provider_errors[0] == {"source": "tushare.stk_mins", "message": "tushare token not configured"}


def test_etf_minute_backfill_falls_back_from_eastmoney_to_akshare(monkeypatch) -> None:
    monkeypatch.setattr(script, "fetch_tushare_etf_hist_minute_bars", lambda *args, **kwargs: [])
    monkeypatch.setattr(script, "fetch_json", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("eastmoney down")))
    monkeypatch.setattr(
        script,
        "fetch_akshare_etf_hist_minute_bars",
        lambda *args, **kwargs: [KlineBar(timestamp="2024-05-28 09:35", open=4, high=4.1, low=3.9, close=4.05, volume=100, amount=405)],
    )

    result = script.fetch_etf_minute_bars(symbol="510300", start_date="2024-05-28", end_date="2024-05-28", period="5m")

    assert result.source == "akshare.fund_etf_hist_min_em"
    assert result.bars[0].timestamp == "2024-05-28 09:35"
    assert [item["source"] for item in result.provider_errors] == ["tushare.stk_mins", "eastmoney.etf_minute"]


def test_etf_minute_backfill_parses_tencent_cumulative_rows() -> None:
    bars = script.parse_tencent_rows("20260428", ["0931 4.01 100 401", "0932 4.03 180 725"])

    assert [bar.timestamp for bar in bars] == ["2026-04-28 09:31", "2026-04-28 09:32"]
    assert bars[1].volume == 80
    assert bars[1].amount == 324


def test_etf_minute_backfill_parses_sina_rows() -> None:
    bars = script.parse_sina_rows(
        [
            {"day": "2026-04-28 09:35:00", "open": "4.00", "high": "4.06", "low": "3.99", "close": "4.05", "volume": "1000", "amount": "4050"},
            {"day": "2026-04-28 09:40:00", "open": "4.05", "high": "4.06", "low": "4.03", "close": "0", "volume": "1000", "amount": "4050"},
        ]
    )

    assert len(bars) == 1
    assert bars[0].timestamp == "2026-04-28 09:35"
    assert bars[0].close == 4.05


def test_etf_minute_akshare_provider_parses_records() -> None:
    bars = ak_provider.parse_akshare_etf_minute_records(
        [
            {"时间": "2024-05-28 09:35:00", "开盘": "4.00", "最高": "4.06", "最低": "3.99", "收盘": "4.05", "成交量": "1000", "成交额": "4050"},
            {"时间": "2024-05-28 09:40:00", "开盘": "4.05", "最高": "4.06", "最低": "4.03", "收盘": "0", "成交量": "1000", "成交额": "4050"},
        ]
    )

    assert len(bars) == 1
    assert bars[0].timestamp == "2024-05-28 09:35"
    assert bars[0].amount == 4050


def test_etf_minute_tushare_provider_parses_records() -> None:
    bars = ak_provider.parse_tushare_etf_minute_records(
        [
            {"ts_code": "510300.SH", "trade_time": "2024-05-28 09:35:00", "open": 4.0, "high": 4.06, "low": 3.99, "close": 4.05, "vol": 1000, "amount": 4050},
            {"ts_code": "510300.SH", "trade_time": "2024-05-28 09:40:00", "open": 4.0, "high": 4.06, "low": 3.99, "close": 0, "vol": 1000, "amount": 4050},
        ]
    )

    assert len(bars) == 1
    assert bars[0].timestamp == "2024-05-28 09:35"
    assert ak_provider.tushare_ts_code("510300") == "510300.SH"


def test_etf_minute_backfill_report_marks_partial_without_fake_prices(tmp_path) -> None:
    profile = script.resolve_profiles(scope="symbols", raw_symbols="510300")[0]
    results = [
        script.result_for(profile, "empty", period="5m", message="remote empty", provider_errors=[{"source": "eastmoney.etf_minute", "message": "empty"}]),
        script.result_for(profile, "error", period="5m", message="timeout"),
    ]
    report = script.build_report(
        args=Namespace(scope="symbols", end_date="2026-04-28", period="5m", workers=1, force=False, allow_partial=True),
        start_date="2026-04-28",
        profiles=[profile],
        results=results,
        totals=script.summarize_results(results),
    )
    output = tmp_path / "etf-minute.json"

    script.write_report(output, report)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "partial_data"
    assert len(payload["failed_symbols"]) == 2
    assert payload["failed_symbols"][0]["provider_errors"][0]["source"] == "eastmoney.etf_minute"
    assert "不生成伪分钟线" in payload["notes"][2]


def test_etf_minute_backfill_quality_summary_flags_bad_bars() -> None:
    bars = [
        KlineBar(timestamp="2026-04-28 09:35", open=4, high=4.1, low=3.9, close=4.05, volume=100, amount=405),
        KlineBar(timestamp="2026-04-28 09:40", open=4, high=3.9, low=4.1, close=4.02, volume=100, amount=402),
    ]

    assert script.quality_summary(bars) == "fresh:1,unavailable:1"
