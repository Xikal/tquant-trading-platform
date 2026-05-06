#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-18000}"
QA_DEEP="${QA_DEEP:-0}"
RUNTIME_DIR="$ROOT_DIR/.runtime"
BACKEND_LOG="$RUNTIME_DIR/qa_backend.log"
RUNTIME_ENV_PATH="$RUNTIME_DIR/runtime.env.qa"
QA_DB_PATH="$RUNTIME_DIR/qa_smoke.db"
QA_DB_URL="sqlite:///$QA_DB_PATH"
LOW_BUY_TEST_DB_PATH="$RUNTIME_DIR/qa_low_buy_persistence.db"
LOW_BUY_TEST_DB_URL="sqlite:///$LOW_BUY_TEST_DB_PATH"

mkdir -p "$RUNTIME_DIR"
rm -f "$QA_DB_PATH" "$QA_DB_PATH-shm" "$QA_DB_PATH-wal"

rm -f "$RUNTIME_ENV_PATH"

cd "$ROOT_DIR/frontend"
npm run build >/dev/null

cd "$ROOT_DIR/backend"
if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing backend virtualenv python at backend/.venv/bin/python" >&2
  exit 1
fi

DATABASE_URL="$QA_DB_URL" \
RUNTIME_ENV_PATH="$RUNTIME_ENV_PATH" \
BASE_ENV_PATH="$RUNTIME_DIR/nonexistent.env" \
AUTH_SECRET_KEY="qa-smoke-secret" \
ADMIN_API_TOKEN="qa-admin-token" \
RUNTIME_BACKGROUND_JOBS_ENABLED=false \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
  wait "$BACKEND_PID" >/dev/null 2>&1 || true
  rm -f "$RUNTIME_ENV_PATH"
  rm -f "$QA_DB_PATH" "$QA_DB_PATH-shm" "$QA_DB_PATH-wal"
  rm -f "$LOW_BUY_TEST_DB_PATH" "$LOW_BUY_TEST_DB_PATH-shm" "$LOW_BUY_TEST_DB_PATH-wal"
}
trap cleanup EXIT

for _ in $(seq 1 40); do
  if curl --max-time 2 -s "http://127.0.0.1:${BACKEND_PORT}/healthz" | grep -q '"status":"ok"'; then
    break
  fi
  sleep 1
done

if ! curl --max-time 2 -s "http://127.0.0.1:${BACKEND_PORT}/healthz" | grep -q '"status":"ok"'; then
  echo "Backend failed to become healthy. See $BACKEND_LOG" >&2
  exit 1
fi

AUTH_JSON="$(curl -sS -X POST "http://127.0.0.1:${BACKEND_PORT}/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"qa_smoke","password":"QaSmoke12345!","display_name":"QA Smoke"}')"
if python3 - <<'PY' "$AUTH_JSON"
import json, sys
payload = json.loads(sys.argv[1])
raise SystemExit(0 if "access_token" in payload else 1)
PY
then
  :
else
  AUTH_JSON="$(curl -sS -X POST "http://127.0.0.1:${BACKEND_PORT}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"qa_smoke","password":"QaSmoke12345!"}')"
fi
AUTH_TOKEN="$(python3 - <<'PY' "$AUTH_JSON"
import json, sys
print(json.loads(sys.argv[1]).get("access_token", ""))
PY
)"
if [[ -z "$AUTH_TOKEN" ]]; then
  echo "Failed to obtain QA auth token: $AUTH_JSON" >&2
  exit 1
fi
AUTH_HEADER=(-H "Authorization: Bearer $AUTH_TOKEN")
ADMIN_HEADER=(-H "X-Admin-Token: qa-admin-token")

READY_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/readyz")"
INSTRUMENTS_JSON="$(curl -sS "${AUTH_HEADER[@]}" "http://127.0.0.1:${BACKEND_PORT}/api/instruments?keyword=510300&kind=all&page=1&page_size=5")"
SETTINGS_UPDATE_JSON="$(curl -sS -X PUT "http://127.0.0.1:${BACKEND_PORT}/api/settings" "${AUTH_HEADER[@]}" "${ADMIN_HEADER[@]}" -H "Content-Type: application/json" -d '{"llm_api_key":"qa-key-123","llm_base_url":"https://api.qa.local/v1","llm_model":"qa-model","data_source":"qa_feed","data_source_base_url":"https://data.qa.local","database_url":"mysql+pymysql://qa:pass@127.0.0.1:3306/t_quant?charset=utf8mb4","strategy_min_profit_stock_pct":3.2,"strategy_min_profit_etf_pct":1.6}')"
UPSERT_WATCHLIST_JSON="$(curl -sS -X POST "http://127.0.0.1:${BACKEND_PORT}/api/watchlist" "${AUTH_HEADER[@]}" -H "Content-Type: application/json" -d '{"symbol":"510300","name":"沪深300ETF","base_position":1200,"available_position":800,"cost_basis":3.456,"memo":"QA底仓"}')"
ANALYZE_JSON="$(curl --max-time 75 -sS -X POST "http://127.0.0.1:${BACKEND_PORT}/api/analyze" "${AUTH_HEADER[@]}" -H "Content-Type: application/json" -d '{"symbol":"510300","prefer_strategy":"auto","base_position":1000,"available_position":1000,"include_ai":false,"include_events":false,"include_microstructure":false}')"
SETTINGS_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/settings" "${AUTH_HEADER[@]}" "${ADMIN_HEADER[@]}")"
RUNTIME_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/settings/runtime" "${AUTH_HEADER[@]}" "${ADMIN_HEADER[@]}")"
WATCHLIST_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/watchlist/signals" "${AUTH_HEADER[@]}")"
LOW_BUY_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/screeners/low-buy?limit=12&scan_limit=24" "${AUTH_HEADER[@]}")"
LOW_BUY_BREAKOUT_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/screeners/low-buy?strategy=limit_up_breakout_retrace&limit=12&scan_limit=24" "${AUTH_HEADER[@]}")"
LOW_BUY_QUOTES_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/screeners/low-buy/quotes?symbols=510300" "${AUTH_HEADER[@]}")"
if [[ "$QA_DEEP" == "1" ]]; then
  BACKTEST_JSON="$(curl --max-time 90 -sS -X POST "http://127.0.0.1:${BACKEND_PORT}/api/backtests" -H "Content-Type: application/json" -d '{"symbol":"510300","lookback_bars":180,"bar_period":"5m","initial_position":1000,"walk_forward_windows":3}')"
  REPLAYS_JSON="$(curl --max-time 20 -sS "http://127.0.0.1:${BACKEND_PORT}/api/replays")"
else
  BACKTEST_JSON="{}"
  REPLAYS_JSON="[]"
fi

python3 - <<'PY' "$READY_JSON" "$INSTRUMENTS_JSON" "$SETTINGS_UPDATE_JSON" "$UPSERT_WATCHLIST_JSON" "$ANALYZE_JSON" "$SETTINGS_JSON" "$RUNTIME_JSON" "$WATCHLIST_JSON" "$LOW_BUY_JSON" "$LOW_BUY_BREAKOUT_JSON" "$LOW_BUY_QUOTES_JSON" "$BACKTEST_JSON" "$REPLAYS_JSON"
import json
import sys

ready = json.loads(sys.argv[1])
instruments = json.loads(sys.argv[2])
settings_update = json.loads(sys.argv[3])
watchlist_upsert = json.loads(sys.argv[4])
analysis = json.loads(sys.argv[5])
settings = json.loads(sys.argv[6])
runtime = json.loads(sys.argv[7])
watchlist = json.loads(sys.argv[8])
low_buy = json.loads(sys.argv[9])
low_buy_breakout = json.loads(sys.argv[10])
low_buy_quotes = json.loads(sys.argv[11])
backtest = json.loads(sys.argv[12])
replays = json.loads(sys.argv[13])

assert ready.get("status") == "ok", f"readyz not ok: {ready}"
assert ready.get("checks", {}).get("database") is True, "readyz database check failed"
assert isinstance(instruments.get("items"), list), "instruments.items should be list"
assert settings_update.get("settings", {}).get("llm_model") == "qa-model", "settings update failed"
assert watchlist_upsert.get("symbol") == "510300", "watchlist upsert failed"
assert "suggestion" in analysis, "analysis result missing suggestion"
assert analysis["suggestion"]["action"] in {"positive_t", "negative_t", "hold"}, "invalid action"
assert "ai" in analysis, "analysis result missing ai"
assert analysis["ai"]["enabled"] is False, "qa AI call should gracefully fall back with fake endpoint"
assert isinstance(settings.get("data_source"), str), "settings.data_source should be str"
assert settings["llm_api_key_configured"] is True, "llm_api_key not persisted"
assert settings["llm_api_key"] == "********", "llm_api_key should be masked"
assert settings["llm_base_url"] == "https://api.qa.local/v1", "llm_base_url not persisted"
assert settings["llm_model"] == "qa-model", "llm_model not persisted"
assert settings["database_url_configured"] is True, "database_url not persisted"
assert settings["database_url"].startswith("mysql+pymysql://qa:"), "database_url should be masked but keep driver/user"
assert settings["strategy_min_profit_stock_pct"] == 3.2, "stock min profit pct not persisted"
assert settings["strategy_min_profit_etf_pct"] == 1.6, "etf min profit pct not persisted"
for key in (
    "strategy_min_amount_stock",
    "strategy_min_amount_etf",
    "strategy_min_profit_stock_pct",
    "strategy_min_profit_etf_pct",
    "strategy_slippage_stock_bps",
    "strategy_slippage_etf_bps",
):
    assert key in settings, f"settings missing {key}"
for key in ("slippage_bps", "positive_threshold", "negative_threshold", "min_profit_pct", "expected_profit_pct"):
    assert key in analysis.get("metrics", {}), f"analysis.metrics missing {key}"
assert runtime.get("llm_configured") is True, "runtime llm status should be true"
assert runtime.get("runtime_env_exists") is True, "runtime env should exist after settings save"
assert runtime.get("ready_checks", {}).get("database") is True, "runtime database check should be true"
assert isinstance(watchlist, list), "watchlist signals should be list"
assert watchlist, "watchlist signals should contain the seeded QA symbol"
first = watchlist[0]
assert first["base_position"] == 1200, "watchlist signal missing base_position"
assert first["available_position"] == 800, "watchlist signal missing available_position"
assert first["memo"] == "QA底仓", "watchlist signal missing memo"
assert "expected_profit_pct" in first["signal"], "watchlist signal missing expected_profit_pct"
assert isinstance(low_buy.get("candidates"), list), "low_buy candidates should be list"
assert low_buy.get("strategy_key") == "first_board", "low_buy strategy_key mismatch"
assert isinstance(low_buy.get("confirmed_candidates"), list), "low_buy confirmed_candidates should be list"
assert "retracement_distribution" in low_buy, "low_buy missing retracement_distribution"
assert low_buy_breakout.get("strategy_key") == "limit_up_breakout_retrace", "low_buy breakout strategy_key mismatch"
assert low_buy_breakout.get("strategy_title") == "涨停突破回踩", "low_buy breakout strategy_title mismatch"
assert isinstance(low_buy_breakout.get("candidates"), list), "low_buy breakout candidates should be list"
if low_buy.get("full_scan_ready"):
    assert low_buy.get("scanned_count", 0) > 0, "low_buy scanned_count should be positive when full scan is ready"
else:
    assert low_buy.get("full_scan_in_progress") is True, "low_buy should report in-progress when full scan is not ready"
assert low_buy["filters"].get("scan_mode"), "low_buy scan_mode missing"
assert isinstance(low_buy.get("performance"), dict), "low_buy missing performance"
for key in ("signal_count", "evaluated_signals", "hit_rate", "avg_return_3d", "sector_attribution", "retracement_attribution"):
    assert key in low_buy["performance"], f"low_buy performance missing {key}"
assert "close_review_items" in low_buy, "low_buy missing close_review_items"
assert "close_review_trade_date" in low_buy, "low_buy missing close_review_trade_date"
assert isinstance(low_buy_quotes.get("items"), dict), "low_buy quotes items should be a dict"
assert "510300" in low_buy_quotes["items"], "low_buy quotes missing seeded symbol"
for key in ("in_entry_zone", "distance_to_entry_pct", "stop_confirmed", "buy_signal_state", "buy_signal_text", "buy_signal_hint"):
    assert key in low_buy_quotes["items"]["510300"], f"low_buy quote refresh missing {key}"
all_candidates = low_buy["confirmed_candidates"] + low_buy["candidates"]
for candidate in all_candidates:
    assert "execution_ready" in candidate, "low_buy candidate missing execution_ready"
    assert "execution_note" in candidate, "low_buy candidate missing execution_note"
distribution_keys = set(low_buy["retracement_distribution"].keys())
if low_buy.get("full_scan_ready"):
    assert any(key in distribution_keys for key in ("2天", "3天", "4天")), "low_buy retracement distribution should include 2/3/4-day samples"
if backtest:
    for key in ("symbol", "total_trades", "win_rate", "profit_factor", "walk_forward_score", "trades"):
        assert key in backtest, f"backtest missing {key}"
    assert backtest["symbol"] == "510300", "backtest symbol mismatch"
    assert isinstance(backtest["trades"], list), "backtest trades should be list"
assert isinstance(replays, list), "replays should be list"
print("qa-smoke:ok")
PY

if ! rg -q '^LLM_MODEL=' "$RUNTIME_ENV_PATH"; then
  echo "runtime.env missing LLM_MODEL after settings save" >&2
  exit 1
fi

if ! rg -q '^DATABASE_URL=' "$RUNTIME_ENV_PATH"; then
  echo "runtime.env missing DATABASE_URL after settings save" >&2
  exit 1
fi

python3 - <<'PY' "$QA_DB_PATH"
import sqlite3
import sys

database_path = sys.argv[1]
connection = sqlite3.connect(database_path)
try:
    table = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='minute_bar_snapshots'"
    ).fetchone()
    assert table, "minute_bar_snapshots table missing"
    row = connection.execute(
        "SELECT COUNT(*) FROM minute_bar_snapshots WHERE symbol = ?",
        ("510300",),
    ).fetchone()
    assert row and row[0] > 0, "minute_bar_snapshots has no rows for 510300"
finally:
    connection.close()
print("qa-minute-snapshot:ok")
PY

DATABASE_URL="$LOW_BUY_TEST_DB_URL" .venv/bin/python - <<'PY'
from datetime import datetime

import pandas as pd
from sqlalchemy import select

from app.core.database import SessionLocal, init_db
from app.models.entities import (
    DailyBarSnapshot,
    LowBuyCloseReviewSnapshot,
    LowBuyPoolSnapshot,
    LowBuyResultSnapshot,
    LowBuyScanSnapshot,
    LowBuyStrategyPerformanceSnapshot,
    LowBuyStrategyPerformanceWindowSnapshot,
)
from app.models.schemas import LowBuyCloseReviewItemOut, LowBuyScreenerResponse
from app.services.low_buy_screener import (
    BoardCandidate,
    LOW_BUY_RESULT_VERSION,
    LowBuyScreenerService,
)

init_db()
service = LowBuyScreenerService()
service._daily_history_cache.clear()
service._screen_cache.clear()

trade_dates = pd.bdate_range("2026-01-05", "2026-04-17")
fake_history = pd.DataFrame(
    {
        "date": trade_dates.strftime("%Y-%m-%d"),
        "open": [10 + index * 0.02 for index in range(len(trade_dates))],
        "close": [10.1 + index * 0.02 for index in range(len(trade_dates))],
        "high": [10.2 + index * 0.02 for index in range(len(trade_dates))],
        "low": [9.9 + index * 0.02 for index in range(len(trade_dates))],
        "volume": [1_000_000 + index * 1_000 for index in range(len(trade_dates))],
        "amount": [20_000_000 + index * 20_000 for index in range(len(trade_dates))],
    }
)

def fake_call_akshare(func, *args, **kwargs):
    if getattr(func, "__name__", "") == "stock_zh_a_daily":
        return fake_history.copy()
    raise RuntimeError(f"unexpected akshare call: {getattr(func, '__name__', repr(func))}")

service.market_data._call_akshare = fake_call_akshare
service.market_data._to_sina_symbol = lambda symbol: f"sz{symbol}" if symbol.startswith(("0", "3")) else f"sh{symbol}"

history = service._load_daily_history("000001", "2026-04-17", history_window_days=180)
assert history is not None and len(history) >= 60, "daily history should load from fake remote source"

with SessionLocal() as db:
    stored_count = len(
        db.execute(
            select(DailyBarSnapshot).where(DailyBarSnapshot.symbol == "000001")
        ).scalars().all()
    )
    assert stored_count >= 60, "daily bar snapshots were not persisted"

    service._persist_pool(
        db=db,
        latest_trade_date="2026-04-17",
        pooled_candidates={
            "000001": BoardCandidate(
                symbol="000001",
                name="平安银行",
                board_date="2026-04-14",
                board_count=1,
                amount=123000000.0,
                industry="银行",
            )
        },
    )
    persisted_pool = service._load_persisted_pool(
        db=db,
        latest_trade_date="2026-04-17",
    )
    assert persisted_pool is not None and "000001" in persisted_pool, "pool snapshots were not persisted"
    pool_rows = len(
        db.execute(
            select(LowBuyPoolSnapshot).where(LowBuyPoolSnapshot.latest_trade_date == "2026-04-17")
        ).scalars().all()
    )
    assert pool_rows == 1, "low buy pool snapshot row count mismatch"

    payload = LowBuyScreenerResponse(
        strategy_key="first_board",
        strategy_title="首板回调",
        strategy_subtitle="",
        strategy_logic="",
        requested_mode="full",
        response_mode="full",
        as_of_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        latest_trade_date="2026-04-17",
        pool_size=100,
        scanned_count=80,
        matched_count=5,
        requested_scan_limit=48,
        active_scan_limit=480,
        full_scan_ready=True,
        full_scan_in_progress=False,
        full_scan_updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        retracement_distribution={"2天": 10},
        filters={
            "_result_version": LOW_BUY_RESULT_VERSION,
            "market_regime": "缩量无主线",
            "market_state": "low_volume_wait",
            "market_state_strength": 0.0,
            "regime_confidence": 0.0,
            "state_persistence_days": 0,
            "transition_risk": 0.0,
            "breadth_ready": False,
            "emotion_ready": False,
            "market_bonus": 0.0,
            "hot_industries_json": "[]",
            "hot_industry_source": "qa",
            "hot_industry_source_text": "QA",
            "limit_up_count": 0,
            "board_height": 0,
            "promotion_ratio": 0.0,
            "broken_board_ratio": 0.0,
            "high_flyer_retreat_ratio": 0.0,
            "stock_up_ratio": 0.0,
            "stock_median_change": 0.0,
            "style_divergence": 0.0,
            "hot_turnover": 0.0,
            "hot_overlap_ratio": 0.0,
            "previous_board_height": 0,
            "promotion_break_gap": 0.0,
            "promotion_break_pressure": 0.0,
            "high_flyer_gap_speed": 0.0,
            "distribution_pressure": 0.0,
            "mainline_lifecycle_state": "unknown",
            "mainline_lifecycle_text": "未知",
            "structure_mode": "qa",
        },
        strategy_notes=[],
        performance=None,
        confirmed_candidates=[],
        history_sections=[],
        candidates=[],
    )
    service._save_persisted_full_result(
        db=db,
        payload=payload,
        limit=16,
        include_history=False,
    )
    loaded = service._load_cached_full_result(
        db=db,
        strategy="first_board",
        latest_trade_date="2026-04-17",
        limit=16,
        include_history=False,
    )
    assert loaded is not None, "persisted full scan result did not load back"
    assert loaded.response_mode == "full", "persisted full scan response_mode mismatch"
    scan_snapshot = db.execute(
        select(LowBuyScanSnapshot).where(
            LowBuyScanSnapshot.latest_trade_date == "2026-04-17",
            LowBuyScanSnapshot.strategy_key == "first_board",
        )
    ).scalar_one_or_none()
    assert scan_snapshot is not None, "materialized low buy scan snapshot missing"
    result_rows = db.execute(
        select(LowBuyResultSnapshot).where(
            LowBuyResultSnapshot.latest_trade_date == "2026-04-17",
            LowBuyResultSnapshot.strategy_key == "first_board",
        )
    ).scalars().all()
    assert isinstance(result_rows, list), "materialized low buy result rows query failed"
    performance_payload = service._empty_strategy_performance(target_profit_pct=3.0, lookback_days=5)
    service._save_strategy_performance_snapshot(
        db=db,
        strategy="first_board",
        latest_trade_date="2026-04-17",
        payload=performance_payload,
    )
    performance_snapshot = db.execute(
        select(LowBuyStrategyPerformanceSnapshot).where(
            LowBuyStrategyPerformanceSnapshot.latest_trade_date == "2026-04-17",
            LowBuyStrategyPerformanceSnapshot.strategy_key == "first_board",
        )
    ).scalar_one_or_none()
    performance_window_snapshot = db.execute(
        select(LowBuyStrategyPerformanceWindowSnapshot).where(
            LowBuyStrategyPerformanceWindowSnapshot.latest_trade_date == "2026-04-17",
            LowBuyStrategyPerformanceWindowSnapshot.strategy_key == "first_board",
            LowBuyStrategyPerformanceWindowSnapshot.lookback_days == performance_payload.lookback_days,
        )
    ).scalar_one_or_none()
    assert performance_snapshot is not None or performance_window_snapshot is not None, "materialized low buy performance snapshot missing"
    close_review_item = LowBuyCloseReviewItemOut(
        symbol="000001",
        name="平安银行",
        signal_state="near_entry",
        signal_text="接近买点",
        review_trade_date="2026-04-17",
        close_price=12.345,
        change_pct=1.23,
        amplitude_pct=3.21,
        entry_zone_low=12.0,
        entry_zone_high=12.4,
        stop_loss=11.6,
        entry_distance_pct=0.0,
        entry_distance_text="收盘落在买点区内",
        close_vs_stop_pct=6.42,
        review_level="neutral",
        review_text="收盘进入买点区，但确认还差一步。",
    )
    service._save_close_review_snapshot(
        db=db,
        strategy="first_board",
        latest_trade_date="2026-04-17",
        items=[close_review_item],
    )
    close_review_rows = db.execute(
        select(LowBuyCloseReviewSnapshot).where(
            LowBuyCloseReviewSnapshot.latest_trade_date == "2026-04-17",
            LowBuyCloseReviewSnapshot.strategy_key == "first_board",
        )
    ).scalars().all()
    assert len(close_review_rows) == 1, "materialized low buy close review snapshot missing"
    attached_payload = service._attach_close_review_snapshot(
        db=db,
        payload=payload,
        review_trade_date="2026-04-17",
    )
    assert attached_payload.close_review_items, "close review snapshot did not attach back to payload"

print("qa-low-buy-persistence:ok")
PY

.venv/bin/python - <<'PY'
import app.services.quant_engine as qe_module
from app.services.ai_service import AiService
from app.models.schemas import (
    AnalysisRequest,
    KlineBar,
    MicrostructureSnapshot,
    QuoteSnapshot,
    SectorSnapshot,
    TradingRuleOut,
)
from app.services.quant_engine import QuantEngine

qe_module.closes_from_bars = lambda bars: [10.0] * 80
qe_module.moving_average = lambda closes, period: 10.0
qe_module.rsi = lambda closes, period: 50.0
qe_module.macd = lambda closes: (0.1, 0.05, 0.2)
qe_module.vwap = lambda bars: 10.0
qe_module.atr = lambda bars, period: 0.035
qe_module.volume_ratio = lambda bars, period: 1.8
qe_module.intraday_amplitude = lambda bars: 4.0
qe_module.trend_slope = lambda closes, period: 0.2
qe_module.obv = lambda bars: 1000.0

quote = QuoteSnapshot(
    symbol="510300",
    name="沪深300ETF",
    market="SH",
    instrument_type="etf",
    last_price=10.0,
    change_pct=1.0,
    change_amount=0.1,
    open_price=9.95,
    high_price=10.2,
    low_price=9.8,
    prev_close=9.9,
    volume=2_000_000,
    amount=4_000_000_000,
    turnover_rate=None,
    volume_ratio=1.8,
    timestamp="2026-04-09 10:30:00",
)
bars = [
    KlineBar(
        timestamp="2026-04-09 10:30:00",
        open=9.98,
        close=10.0,
        high=10.2,
        low=9.8,
        volume=100000,
        amount=1000000,
        amplitude=4.0,
        change_pct=0.2,
        turnover=0.4,
    )
]
rules = TradingRuleOut(
    symbol="510300",
    turnaround_mode="t1",
    supports_positive_t=True,
    supports_negative_t=True,
    same_day_sell_allowed=False,
    requires_base_position=True,
    notes="QA synthetic rule",
)
sector = SectorSnapshot(
    sector_name="宽基ETF",
    sector_strength=82.0,
    market_strength=76.0,
    alignment_score=80.0,
    notes="QA synthetic sector",
)
micro = MicrostructureSnapshot(
    available=True,
    buy_pressure=70.0,
    sell_pressure=30.0,
    large_order_flow=12.0,
    notes="QA synthetic microstructure",
)
request = AnalysisRequest(
    symbol="510300",
    prefer_strategy="positive_t",
    base_position=1000,
    available_position=1000,
    include_ai=False,
    include_events=False,
    include_microstructure=True,
)
risk_config = {
    "risk_max_single_loss_pct": 1.0,
    "strategy_min_amount_stock": 0.0,
    "strategy_min_amount_etf": 0.0,
    "strategy_min_amplitude_pct": 0.1,
    "strategy_max_amplitude_pct": 15.0,
    "strategy_max_atr_pct": 10.0,
    "strategy_open_phase_min_tradability": 0.0,
    "strategy_min_profit_pct": 3.0,
    "strategy_min_profit_stock_pct": 3.0,
    "strategy_min_profit_etf_pct": 3.0,
    "strategy_slippage_stock_bps": 1.0,
    "strategy_slippage_etf_bps": 1.0,
}
metrics, suggestion, _, _ = QuantEngine().evaluate(
    quote=quote,
    bars=bars,
    rules=rules,
    sector=sector,
    events=[],
    microstructure=micro,
    request=request,
    risk_config=risk_config,
)
assert suggestion.action == "hold", suggestion
assert metrics["expected_profit_pct"] < metrics["min_profit_pct"], metrics
assert suggestion.blocking_rules, "low-profit synthetic signal should be blocked"

invalid_quote = QuoteSnapshot(
    symbol="510300",
    name="沪深300ETF",
    market="SH",
    instrument_type="etf",
    last_price=0.0,
    change_pct=-100.0,
    change_amount=-4.5,
    open_price=0.0,
    high_price=0.0,
    low_price=0.0,
    prev_close=4.5,
    volume=0.0,
    amount=0.0,
    turnover_rate=None,
    volume_ratio=None,
    timestamp="2026-04-09 09:22:00",
)
invalid_metrics, invalid_suggestion, _, _ = QuantEngine().evaluate(
    quote=invalid_quote,
    bars=bars,
    rules=rules,
    sector=sector,
    events=[],
    microstructure=micro,
    request=request,
    risk_config=risk_config,
)
assert invalid_suggestion.action == "hold", invalid_suggestion
assert invalid_suggestion.blocking_rules == [
    "当前处于开盘前/集合竞价阶段，建议等待 09:30 后连续竞价再做T。"
], invalid_suggestion.blocking_rules
assert AiService._resolve_request_mode("https://api.minimaxi.com/anthropic") == "anthropic"
assert (
    AiService._resolve_endpoint("https://api.minimaxi.com/anthropic", "anthropic")
    == "https://api.minimaxi.com/anthropic/v1/messages"
)
anthropic_body = AiService._build_request_body(
    "anthropic",
    "MiniMax-M2.7",
    {"symbol": "510300", "signal": "hold"},
    "QA system prompt",
    max_tokens=1536,
)
assert anthropic_body["max_tokens"] == 1536, anthropic_body
assert anthropic_body["messages"][0]["content"][0]["type"] == "text", anthropic_body
assert anthropic_body["messages"][0]["content"][0]["text"], anthropic_body
assert AiService._resolve_request_mode("https://api.minimaxi.com/v1") == "openai"
assert (
    AiService._resolve_endpoint("https://api.minimaxi.com/v1", "openai")
    == "https://api.minimaxi.com/v1/chat/completions"
)
print("qa-threshold:ok")
PY

echo "Smoke test passed."
