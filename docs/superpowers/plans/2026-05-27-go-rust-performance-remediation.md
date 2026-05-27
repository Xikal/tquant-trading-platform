# Go/Rust Production Performance Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the online Go/Rust production path pass the measured latency, reliability, and benchmark gates from the 2026-05-27 cloud test.

**Architecture:** Keep strategy semantics in Python reference code, but move slow user-facing reads to snapshot-first responses and make long scans asynchronous. Go BFF and market-read remain production entry points with explicit hit/fallback metrics; Rust remains the default compute path and gets a reproducible cloud benchmark gate.

**Tech Stack:** FastAPI, SQLAlchemy, Redis distributed cache, RuntimeTaskQueue, Go net/http services, Docker Compose, pytest, Go test/benchmark, Rust cargo/PyO3, shell/Python deployment scripts.

---

## Online Baseline From 2026-05-27

| Area | Measured Result | Status |
|---|---:|---|
| `/api/screeners/low-buy/priority-board?limit=12` | p95 3482.61ms | Failed |
| `/api/market/pulse` | p95 4189.81ms | Failed |
| Go scan-worker `/api/scan-worker/v1/run` | about 30s timeout samples | Failed |
| Direct Go BFF monitor cold request | p95 2019.53ms | Failed cold budget |
| Rust online small max_drawdown speedup | 2.06x | Below 5x gate |
| Cloud Go/Rust acceptance script | failed due missing source/dependency timeout | Environment failed |

Passing targets:

- `priority-board`: warm p95 <= 500ms, cold p95 <= 2000ms.
- `market/pulse`: warm p95 <= 500ms, cold p95 <= 1500ms.
- Go scan trigger API: p95 <= 500ms for accepted/job-status response; full scan may run in background.
- Direct Go BFF monitor: warm p95 <= 500ms, cold p95 <= 1500ms, partial response allowed with named source.
- Rust release benchmark: max_drawdown, rolling_mean, atr_wilder speedup >= 5x under the release acceptance script.
- Cloud acceptance script: self-contained in the release image or deploy bundle, not dependent on source directories missing from the container.

## File Structure

Modify:

- `backend/app/services/low_buy/priority_board.py`: prefer durable priority-board snapshot before expensive rebuild.
- `backend/app/services/low_buy/priority_cache.py`: add stale-response read path and cache status metadata.
- `backend/app/services/low_buy/priority_snapshot.py`: expose latest stored materialized priority snapshot helpers if existing helpers are insufficient.
- `backend/app/api/routes/screeners.py`: add `refresh=sync|async|cache` compatible query behavior without breaking default response fields.
- `backend/app/services/monitor_snapshot_cache.py`: make monitor snapshot store priority-board refresh state and use stale payload while refresh is queued.
- `backend/app/services/market/pulse_cache.py`: new pulse cache and stale snapshot helper.
- `backend/app/api/routes/market.py`: return snapshot-first pulse and queue async refresh on stale/miss.
- `backend/app/workers/runtime_worker.py`: add explicit `market_pulse_refresh` and async scan tasks.
- `backend/app/services/low_buy_materialization.py`: add async job enqueue/status helpers and prevent request-thread full scans.
- `backend/app/api/routes/internal_scan_worker.py`: return accepted job payload instead of blocking on full scan.
- `go-services/scan-worker/cmd/scan-worker/main.go`: add async accepted/status contract, job id propagation, metrics for accepted/completed/failed/fallback.
- `go-services/scan-worker/cmd/scan-worker/main_test.go`: cover accepted async contract and auth.
- `go-services/bff-gateway/cmd/bff-gateway/workspace_aggregate.go`: add per-source timeout budget, critical/non-critical source split, and pulse/monitor snapshot priority order.
- `go-services/bff-gateway/cmd/bff-gateway/main_test.go`: cover cold slow source partial response under budget.
- `scripts/verify_go_rust_performance_acceptance.py`: make paths configurable and container-friendly.
- `scripts/measure_cloud_go_rust_performance.py`: new cloud smoke/performance script that logs in, measures p50/p95, captures Go/Rust metrics deltas, and writes a JSON report.
- `Dockerfile`: optionally include Go/Rust acceptance source or a compact benchmark bundle in the image.
- `docker-compose.mysql.yml`: wire benchmark/deploy env vars and runtime timeouts.
- `docs/reports/`: store new performance reports after verification.

Tests:

- `backend/tests/test_priority_board_cache_fast_path.py`
- `backend/tests/test_market_pulse_cache_fast_path.py`
- `backend/tests/test_go_scan_worker_async.py`
- `backend/tests/test_cloud_performance_script.py`
- Existing Go service tests.
- Existing Rust parity/acceptance tests.

## Task 1: Priority Board Snapshot-First Fast Path

**Bottleneck:** `priority-board` can synchronously rebuild low-buy candidates, intraday confirmation, leader enrichment, family sections, portfolio risk, and distributed cache state. Cache misses or external data failures create multi-second tails.

**Structural fix:** Default route returns the latest valid priority-board response from Redis/SystemSetting/materialized snapshot immediately. If the cache is stale or missing, enqueue `low_buy_materialization_refresh` and return the latest stale-but-labelled board with `data_quality=stale|partial`, `refresh_status=queued`, and a warning. Only `refresh=sync` may run the full rebuild in the request thread, and it should be admin/internal only if exposed.

**Files:**
- Modify: `backend/app/services/low_buy/priority_cache.py`
- Modify: `backend/app/services/low_buy/priority_board.py`
- Modify: `backend/app/api/routes/screeners.py`
- Modify: `backend/app/services/monitor_snapshot_cache.py`
- Test: `backend/tests/test_priority_board_cache_fast_path.py`

- [ ] **Step 1: Add failing test for stale cache fast return**

Create `backend/tests/test_priority_board_cache_fast_path.py`:

```python
from __future__ import annotations

from types import SimpleNamespace

from app.models.schemas import LowBuyPriorityBoardResponse
from app.services.low_buy.priority_board import LowBuyPriorityBoardMixin


class _Service(LowBuyPriorityBoardMixin):
    _priority_response_cache_ttl = 1
    _priority_base_cache_ttl = 1

    def __init__(self) -> None:
        self._priority_response_cache = {}
        self._priority_base_cache = {}
        import threading

        self._cache_lock = threading.Lock()
        self.rebuild_count = 0

    def _build_priority_base_snapshot(self, db, limit):  # noqa: ANN001
        self.rebuild_count += 1
        raise AssertionError("request fast path must not rebuild priority board")


def test_priority_board_fast_path_returns_latest_stale_without_rebuild(monkeypatch):
    service = _Service()
    stale = LowBuyPriorityBoardResponse(
        updated_at="2026-05-27 09:30:00",
        latest_trade_date="2026-05-26",
        total_candidates=0,
        items=[],
        warnings=["缓存已过期，后台正在刷新。"],
    )

    monkeypatch.setattr(
        "app.services.low_buy.priority_board.get_priority_response_cache",
        lambda _service, _key, allow_stale=False: stale if allow_stale else None,
    )
    queued = []
    monkeypatch.setattr(
        "app.services.low_buy.priority_board.enqueue_low_buy_materialization",
        lambda db, reason, commit=False: queued.append(reason),
    )
    monkeypatch.setattr(
        "app.services.low_buy.priority_board.published_low_buy_trade_date",
        lambda db: "2026-05-27",
    )

    result = service.priority_board(SimpleNamespace(), limit=12)

    assert result.latest_trade_date == "2026-05-26"
    assert result.warnings
    assert queued == ["priority_board_cache_miss"]
    assert service.rebuild_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/j/Documents/gupiao/backend
pytest tests/test_priority_board_cache_fast_path.py -q
```

Expected: FAIL because `get_priority_response_cache(..., allow_stale=True)` and route-level stale metadata do not exist yet.

- [ ] **Step 3: Implement stale cache read and async refresh**

Update `backend/app/services/low_buy/priority_cache.py` so `get_priority_response_cache` accepts `allow_stale: bool = False` and returns expired distributed/local payload when requested:

```python
def get_priority_response_cache(service, cache_key: str, *, allow_stale: bool = False) -> LowBuyPriorityBoardResponse | None:
    now = time.monotonic()
    stale_local: LowBuyPriorityBoardResponse | None = None
    with service._cache_lock:
        cached = service._priority_response_cache.get(cache_key)
        if cached is not None:
            expires_at, payload = cached
            parsed = LowBuyPriorityBoardResponse.model_validate_json(payload) if isinstance(payload, str) else deepcopy(payload)
            if expires_at > now:
                return parsed
            stale_local = parsed
            if not allow_stale:
                service._priority_response_cache.pop(cache_key, None)
    distributed = get_text_cache(_distributed_key(cache_key))
    if distributed:
        payload = LowBuyPriorityBoardResponse.model_validate_json(distributed)
        with service._cache_lock:
            service._priority_response_cache[cache_key] = (
                time.monotonic() + service._priority_response_cache_ttl,
                distributed,
            )
        return payload
    return stale_local if allow_stale else None
```

Update `backend/app/services/low_buy/priority_board.py` to enqueue refresh and return stale cache before rebuilding:

```python
from app.services.low_buy_materialization import enqueue_low_buy_materialization


def priority_board(self, db: Session, limit: int = 12) -> LowBuyPriorityBoardResponse:
    target_trade_date = published_low_buy_trade_date(db) or expected_low_buy_trade_date(db)
    cache_key = f"date={target_trade_date}:limit={limit}"
    cached_response = self._get_priority_response_cache(cache_key)
    if cached_response is not None:
        return cached_response

    stale_response = self._get_priority_response_cache(cache_key, allow_stale=True)
    if stale_response is not None:
        enqueue_low_buy_materialization(db, reason="priority_board_cache_miss", commit=False)
        warnings = list(getattr(stale_response, "warnings", []) or [])
        warning = "优先榜正在后台刷新，当前先展示最近一次可用结果。"
        if warning not in warnings:
            warnings.append(warning)
        return stale_response.model_copy(update={"warnings": warnings})

    enqueue_low_buy_materialization(db, reason="priority_board_cache_empty", commit=False)
    base_snapshot = self._load_priority_base_snapshot(db=db, limit=limit)
    ...
```

Update method signature:

```python
def _get_priority_response_cache(self, cache_key: str, *, allow_stale: bool = False) -> LowBuyPriorityBoardResponse | None:
    return get_priority_response_cache(self, cache_key, allow_stale=allow_stale)
```

- [ ] **Step 4: Add route refresh mode without breaking clients**

In `backend/app/api/routes/screeners.py`, keep the current default compatible but add query mode:

```python
refresh: str = Query(default="cache", pattern="^(cache|async|sync)$")
```

Behavior:

- `cache`: use snapshot-first priority board.
- `async`: enqueue refresh and return current snapshot.
- `sync`: existing full rebuild path, restricted to admin/internal if permission helpers exist; otherwise do not expose sync publicly.

- [ ] **Step 5: Run focused tests**

```bash
cd /Users/j/Documents/gupiao/backend
pytest tests/test_priority_board_cache_fast_path.py tests/test_monitor_routes.py tests/test_low_buy_standardization.py -q
```

Expected: PASS.

**Measured result target:** online `priority-board` p95 <= 500ms warm and <= 2000ms cold. Cache miss response must include warning/refresh status rather than blocking for a full scan.

**Remaining risk:** stale board can be shown during market data outages. This is acceptable only if the warning and data quality are explicit and auto-refresh is observable.

## Task 2: Market Pulse Snapshot-First Response

**Bottleneck:** `/api/market/pulse` synchronously calls breadth, sector strength, and autofill. On external market data/cache miss, the page waits several seconds.

**Structural fix:** Store pulse events as the authoritative read model. The route returns the latest `MarketPulseEvent` first if it is within a short freshness window; stale/miss queues `market_pulse_refresh` and returns a partial/stale payload. Manual refresh uses `refresh=sync` or a separate POST endpoint.

**Files:**
- Create: `backend/app/services/market/pulse_cache.py`
- Modify: `backend/app/api/routes/market.py`
- Modify: `backend/app/workers/runtime_worker.py`
- Test: `backend/tests/test_market_pulse_cache_fast_path.py`

- [ ] **Step 1: Add failing tests for cached pulse and async miss**

Create `backend/tests/test_market_pulse_cache_fast_path.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta

from app.models.entities import MarketPulseEvent
from app.services.market.pulse_cache import latest_pulse_or_placeholder


def test_latest_pulse_or_placeholder_returns_stored_event(db_session):
    row = MarketPulseEvent(
        trade_date="2026-05-27",
        pulse_level="defensive",
        data_quality="partial",
        pulse_text="市场偏弱，先防守。",
        suggested_action="少交易，等确认。",
        payload_json='{"updated_at":"2026-05-27 10:30:00","data_quality":"partial","pulse_level":"defensive","pulse_text":"市场偏弱，先防守。","suggested_action":"少交易，等确认。","partial_errors":[]}',
    )
    db_session.add(row)
    db_session.commit()

    pulse, needs_refresh = latest_pulse_or_placeholder(db_session, trade_date="2026-05-27")

    assert pulse.pulse_level == "defensive"
    assert pulse.pulse_text == "市场偏弱，先防守。"
    assert needs_refresh is False


def test_latest_pulse_or_placeholder_queues_refresh_when_missing(db_session):
    pulse, needs_refresh = latest_pulse_or_placeholder(db_session, trade_date="2026-05-27")

    assert pulse.data_quality in {"partial", "unavailable"}
    assert pulse.partial_errors
    assert needs_refresh is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/j/Documents/gupiao/backend
pytest tests/test_market_pulse_cache_fast_path.py -q
```

Expected: FAIL because `pulse_cache.py` does not exist.

- [ ] **Step 3: Implement pulse cache helper**

Create `backend/app/services/market/pulse_cache.py`:

```python
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now, beijing_now_string
from app.models.entities import MarketPulseEvent
from app.models.schema_defs.market import IntradayMarketPulse

FRESH_SECONDS = 180


def latest_pulse_or_placeholder(db: Session, *, trade_date: str) -> tuple[IntradayMarketPulse, bool]:
    row = db.execute(
        select(MarketPulseEvent)
        .where(MarketPulseEvent.trade_date == trade_date)
        .order_by(MarketPulseEvent.created_at.desc(), MarketPulseEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return _placeholder("unavailable", "暂时没有可用的盘中 pulse。", "等待后台刷新。"), True
    payload = _json_dict(row.payload_json)
    pulse = IntradayMarketPulse.model_validate(
        {
            "updated_at": payload.get("updated_at") or beijing_now_string(),
            "data_quality": payload.get("data_quality") or row.data_quality or "partial",
            "data_quality_text": payload.get("data_quality_text") or "盘中 pulse 使用最近一次快照",
            "market_strength_text": payload.get("market_strength_text") or "",
            "leader_strength_text": payload.get("leader_strength_text") or "",
            "emotion_text": payload.get("emotion_text") or "",
            "hourly_snapshot_text": payload.get("hourly_snapshot_text") or "",
            "pulse_level": payload.get("pulse_level") or row.pulse_level or "unknown",
            "pulse_text": payload.get("pulse_text") or row.pulse_text or "",
            "suggested_action": payload.get("suggested_action") or row.suggested_action or "",
            "partial_errors": payload.get("partial_errors") or [],
            "market_breadth_summary": payload.get("market_breadth_summary") or {},
            "leader_strength_summary": payload.get("leader_strength_summary") or {},
            "emotion_summary": payload.get("emotion_summary") or {},
            "hourly_snapshot_summary": payload.get("hourly_snapshot_summary") or {},
            "autofill_details": payload.get("autofill_details") or [],
        }
    )
    created_at = getattr(row, "created_at", None)
    is_stale = bool(created_at and beijing_now() - created_at > timedelta(seconds=FRESH_SECONDS))
    if is_stale and pulse.data_quality == "fresh":
        pulse = pulse.model_copy(update={"data_quality": "stale", "data_quality_text": "盘中 pulse 使用最近一次快照，后台正在刷新。"})
    return pulse, is_stale


def _placeholder(quality: str, text: str, action: str) -> IntradayMarketPulse:
    return IntradayMarketPulse(
        updated_at=beijing_now_string(),
        data_quality=quality,
        data_quality_text="盘中 pulse 暂不可用",
        market_strength_text="市场强弱待确认",
        leader_strength_text="龙头强度待确认",
        emotion_text="情绪温度待确认",
        hourly_snapshot_text="小时快照待确认",
        pulse_level=quality,
        pulse_text=text,
        suggested_action=action,
        partial_errors=[{"source": "pulse_snapshot", "detail": "后台正在刷新盘中 pulse"}],
    )


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
```

- [ ] **Step 4: Route uses cache by default and queues refresh**

In `backend/app/api/routes/market.py`, change `/pulse` to:

```python
@router.get("/pulse", response_model=IntradayMarketPulse)
def market_pulse(
    refresh: Annotated[str, Query(pattern="^(cache|async|sync)$")] = "cache",
    db: Session = Depends(get_db),
) -> IntradayMarketPulse:
    if refresh != "sync":
        pulse, needs_refresh = latest_pulse_or_placeholder(db, trade_date=beijing_today().isoformat())
        if needs_refresh or refresh == "async":
            RuntimeTaskQueue(db).enqueue(
                RuntimeTaskCreate(
                    task_type="market_pulse_refresh",
                    payload={"trade_date": beijing_today().isoformat(), "reason": f"market_pulse_{refresh}"},
                    priority=55,
                    idempotency_key=f"market_pulse_refresh:{beijing_today().isoformat()}",
                    max_attempts=2,
                )
            )
        return pulse
    return _build_market_pulse_sync(db)
```

Extract current synchronous logic into `_build_market_pulse_sync(db)`.

- [ ] **Step 5: Runtime worker refreshes and records pulse**

In `backend/app/workers/runtime_worker.py`, add:

```python
if task_type == "market_pulse_refresh":
    from app.api.routes.market import _build_market_pulse_sync
    from app.services.market.pulse_history import record_market_pulse_event

    pulse = _build_market_pulse_sync(db)
    record_market_pulse_event(db, pulse)
    db.commit()
    return {"ok": True, "data_quality": str(pulse.data_quality), "pulse_level": pulse.pulse_level}
```

- [ ] **Step 6: Run focused tests**

```bash
cd /Users/j/Documents/gupiao/backend
pytest tests/test_market_pulse_cache_fast_path.py tests/test_market_routes.py tests/test_market_hourly_snapshot.py -q
```

Expected: PASS.

**Measured result target:** `/api/market/pulse` p95 <= 500ms warm, <= 1500ms cold. Partial/stale responses must include `partial_errors` naming missing sources.

**Remaining risk:** event freshness depends on runtime-worker health. Alert when no fresh pulse event has been written for 5 minutes during trading hours.

## Task 3: Go Scan-Worker Async Accepted Contract

**Bottleneck:** Go scan-worker blocks on Python full scan. External provider retries and Python materialization can take 30-60s, causing timeouts and fallback pollution.

**Structural fix:** Go scan-worker becomes a production orchestration API, not a blocking full-scan API. `/run` creates a runtime task and returns `202 Accepted` with `job_id`, `status_url`, and current latest snapshot metadata. A `/status/{job_id}` endpoint reports queued/running/succeeded/failed. Snapshot writes continue to happen only inside Python reference materialization; latest is not replaced until reference publish succeeds.

**Files:**
- Modify: `backend/app/services/low_buy_materialization.py`
- Modify: `backend/app/api/routes/internal_scan_worker.py`
- Modify: `backend/app/workers/runtime_worker.py`
- Modify: `go-services/scan-worker/cmd/scan-worker/main.go`
- Modify: `go-services/scan-worker/cmd/scan-worker/main_test.go`
- Test: `backend/tests/test_go_scan_worker_async.py`

- [ ] **Step 1: Add Python async enqueue/status tests**

Create `backend/tests/test_go_scan_worker_async.py`:

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_internal_scan_worker_run_returns_accepted_job(monkeypatch):
    monkeypatch.setenv("TQUANT_INTERNAL_SERVICE_TOKEN", "test-token")
    client = TestClient(app)

    response = client.get(
        "/api/internal/scan-worker/v1/run?strategies=first_board&scan_limit=12&limit=5",
        headers={"X-Internal-Service-Token": "test-token"},
    )

    assert response.status_code in {200, 202}
    payload = response.json()
    assert payload["ok"] is True
    assert payload["accepted"] is True
    assert payload["job_id"]
    assert payload["strategy_engine"] == "python_reference"
    assert payload["production_write_enabled"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/j/Documents/gupiao/backend
pytest tests/test_go_scan_worker_async.py -q
```

Expected: FAIL because internal route currently blocks until materialization completes.

- [ ] **Step 3: Add enqueue helper**

In `backend/app/services/low_buy_materialization.py`, add:

```python
def enqueue_low_buy_materialization_run(
    db: Session,
    *,
    strategies: list[str],
    limit: int,
    scan_limit: int,
    reason: str,
) -> dict[str, Any]:
    expected = expected_low_buy_trade_date(db)
    task = RuntimeTaskQueue(db).enqueue(
        RuntimeTaskCreate(
            task_type=TASK_TYPE,
            payload={
                "expected_trade_date": expected,
                "strategies": strategies,
                "limit": max(1, min(int(limit), 500)),
                "scan_limit": max(1, min(int(scan_limit), 10000)),
                "reason": reason,
            },
            priority=30,
            idempotency_key=f"{TASK_TYPE}:{expected}:{','.join(sorted(strategies))}:{limit}:{scan_limit}",
            max_attempts=2,
        )
    )
    return {
        "ok": True,
        "accepted": True,
        "job_id": str(task.id),
        "task_type": TASK_TYPE,
        "expected_trade_date": expected,
    }
```

Update runtime worker `low_buy_materialization_refresh` branch to pass payload strategies:

```python
return refresh_latest_low_buy_materialization(
    limit=int(payload.get("limit") or 40),
    scan_limit=int(payload.get("scan_limit") or 480),
    strategies=[str(item) for item in payload.get("strategies") or []] or None,
)
```

- [ ] **Step 4: Internal route returns accepted**

In `backend/app/api/routes/internal_scan_worker.py`, replace blocking call with enqueue:

```python
from fastapi import status
from app.services.low_buy_materialization import enqueue_low_buy_materialization_run


@router.get("/run", status_code=status.HTTP_202_ACCEPTED)
def run_scan_worker_reference(...):
    strategy_list = [item.strip() for item in strategies.split(",") if item.strip()]
    result = enqueue_low_buy_materialization_run(
        db,
        strategies=strategy_list,
        limit=limit,
        scan_limit=scan_limit,
        reason=reason,
    )
    return {
        **result,
        "reason": reason,
        "production_scan_enabled": True,
        "production_write_enabled": True,
        "scan_worker_role": "go_orchestrated_reference",
        "strategy_engine": "python_reference",
        "ranking_consistency": {
            "checked": True,
            "status": "python_reference_order",
            "detail": "Go scan-worker enqueued the Python strategy reference and latest is published only after the reference write succeeds.",
        },
    }
```

- [ ] **Step 5: Go service accepts 202 and records accepted metric**

In `go-services/scan-worker/cmd/scan-worker/main.go`:

- Accept HTTP 202 as success.
- Do not increment `scanWrites` on accepted; add `scanAccepted`.
- Add metrics:

```go
var scanAccepted atomic.Int64
var scanCompleted atomic.Int64
```

In `metrics`:

```go
fmt.Sprintf("tquant_scan_worker_accepted_total %d", scanAccepted.Load()),
fmt.Sprintf("tquant_scan_worker_completed_total %d", scanCompleted.Load()),
```

In `runHandler`:

```go
if status == http.StatusAccepted {
    scanAccepted.Add(1)
    result["accepted"] = true
    result["production_write_enabled"] = true
    writeJSON(w, http.StatusAccepted, result)
    return
}
```

- [ ] **Step 6: Add Go async tests**

In `go-services/scan-worker/cmd/scan-worker/main_test.go`, add a test server returning 202:

```go
func TestRunHandlerAcceptsAsyncPythonReference(t *testing.T) {
    upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusAccepted)
        _, _ = w.Write([]byte(`{"ok":true,"accepted":true,"job_id":"42"}`))
    }))
    defer upstream.Close()

    cfg := config{pythonAPIBase: upstream.URL, internalToken: "token", timeout: time.Second}
    req := httptest.NewRequest(http.MethodGet, "/api/scan-worker/v1/run?strategies=first_board", nil)
    req.Header.Set("X-Internal-Service-Token", "token")
    rr := httptest.NewRecorder()

    internalOnly("token", runHandler(cfg, upstream.Client())).ServeHTTP(rr, req)

    if rr.Code != http.StatusAccepted {
        t.Fatalf("expected 202 accepted, got %d body=%s", rr.Code, rr.Body.String())
    }
    if !strings.Contains(rr.Body.String(), `"accepted":true`) {
        t.Fatalf("missing accepted payload: %s", rr.Body.String())
    }
}
```

- [ ] **Step 7: Run tests**

```bash
cd /Users/j/Documents/gupiao/backend
pytest tests/test_go_scan_worker_async.py -q
cd /Users/j/Documents/gupiao/go-services/scan-worker
go test ./...
```

Expected: PASS.

**Measured result target:** Go scan `/run` p95 <= 500ms and no request timeout. Full scan success/failure must be visible in runtime tasks and scan-worker accepted/completed/fallback metrics.

**Remaining risk:** The full materialization can still be slow. That is acceptable only after it is off the request path and latest snapshot is not polluted on failure.

## Task 4: Go BFF Cold-Start and Partial Source Budget

**Bottleneck:** Direct Go BFF monitor cold p95 exceeded budget because all monitor sources share the incoming request context and slow non-critical sources can extend the aggregate.

**Structural fix:** Give each source an explicit timeout budget and return partial data for non-critical sources when they exceed the budget. Fetch `monitor_snapshot` first or with a shorter critical path, then layer pulse/review/sector/hedge. Cache stale successful aggregate and use stale aggregate on cold miss when non-critical sources fail.

**Files:**
- Modify: `go-services/bff-gateway/cmd/bff-gateway/workspace_aggregate.go`
- Modify: `go-services/bff-gateway/cmd/bff-gateway/main.go`
- Modify: `go-services/bff-gateway/cmd/bff-gateway/main_test.go`

- [ ] **Step 1: Add Go test for slow non-critical source**

Add to `go-services/bff-gateway/cmd/bff-gateway/main_test.go`:

```go
func TestMonitorAggregateReturnsPartialWhenPulseIsSlow(t *testing.T) {
    upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        switch r.URL.Path {
        case "/api/monitor/snapshot":
            _, _ = w.Write([]byte(`{"updated_at":"2026-05-27 10:00:00","watchlist_signals":[],"priority_board":{"items":[]}}`))
        case "/api/market/pulse":
            time.Sleep(250 * time.Millisecond)
            _, _ = w.Write([]byte(`{"pulse_text":"late"}`))
        default:
            _, _ = w.Write([]byte(`{}`))
        }
    }))
    defer upstream.Close()

    cfg := config{
        pythonAPIBase: upstream.URL,
        internalToken: "token",
        sourceTimeout: 50 * time.Millisecond,
    }
    req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/monitor", nil)
    result := aggregateMonitorWorkspace(cfg, upstream.Client(), req)

    if result.status != http.StatusOK {
        t.Fatalf("expected ok, got %d", result.status)
    }
    if !bytes.Contains(result.body, []byte(`"source":"market_pulse"`)) {
        t.Fatalf("expected pulse partial error: %s", string(result.body))
    }
    if !bytes.Contains(result.body, []byte(`"monitor_snapshot"`)) {
        t.Fatalf("expected snapshot to remain present: %s", string(result.body))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/j/Documents/gupiao/go-services/bff-gateway
go test ./...
```

Expected: FAIL because config/source timeout field is not implemented.

- [ ] **Step 3: Implement source timeout**

Add to config:

```go
sourceTimeout time.Duration
```

Load with:

```go
sourceTimeout: durationSeconds("BFF_SOURCE_TIMEOUT_SECONDS", 1),
```

In `fetchRawSource`:

```go
ctx, cancel := context.WithTimeout(incoming.Context(), cfg.sourceTimeout)
defer cancel()
req, err := http.NewRequestWithContext(ctx, http.MethodGet, target.String(), nil)
```

Set production env in compose:

```yaml
BFF_SOURCE_TIMEOUT_SECONDS: ${BFF_SOURCE_TIMEOUT_SECONDS:-0.8}
```

- [ ] **Step 4: Make partial errors informative**

Change `partialError` to include elapsed/status:

```go
type partialError struct {
    Source string `json:"source"`
    Detail string `json:"detail"`
    ElapsedMs int64 `json:"elapsed_ms,omitempty"`
}
```

In `fetchSources`, measure per source and set details like `source timeout after 800ms`.

- [ ] **Step 5: Run Go tests**

```bash
cd /Users/j/Documents/gupiao/go-services/bff-gateway
go test ./...
```

Expected: PASS.

**Measured result target:** direct Go BFF monitor cold p95 <= 1500ms; warm p95 <= 500ms; cache hit rate >= 60%; partial source failures named and bounded.

**Remaining risk:** If the critical `monitor_snapshot` itself is slow because priority board cache is missing, Task 1 must already be deployed.

## Task 5: Cloud-Self-Contained Go/Rust Acceptance

**Bottleneck:** Online benchmark was not reproducible because app image did not include `go-services`, and cloud dependency download timed out.

**Structural fix:** Make acceptance runnable in one of two supported ways: source-bundle mode on host after deploy, or benchmark-bundle mode inside a dedicated container/image layer. The script must not hard-code missing paths or local `.venv`.

**Files:**
- Modify: `scripts/verify_go_rust_performance_acceptance.py`
- Create: `scripts/measure_cloud_go_rust_performance.py`
- Modify: `Dockerfile`
- Modify: `scripts/deploy_cloud_server.sh`
- Test: `backend/tests/test_cloud_performance_script.py`

- [ ] **Step 1: Add script path configurability test**

Create `backend/tests/test_cloud_performance_script.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


def test_acceptance_script_uses_env_project_root():
    script = Path(__file__).resolve().parents[1].parent / "scripts" / "verify_go_rust_performance_acceptance.py"
    source = script.read_text(encoding="utf-8")
    assert "TQUANT_ACCEPTANCE_PROJECT_ROOT" in source
    assert "BACKEND_PYTHON" in source
    assert "go-services" in source
```

- [ ] **Step 2: Update acceptance script**

At the top of `scripts/verify_go_rust_performance_acceptance.py`:

```python
PROJECT_ROOT = Path(os.environ.get("TQUANT_ACCEPTANCE_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
REPORT_PATH = Path(os.environ.get("TQUANT_ACCEPTANCE_REPORT_PATH", PROJECT_ROOT / "docs" / "reports" / "go-rust-performance-acceptance-2026-05-27.json")).resolve()
```

For Go checks, if source path is missing, return a clear failed result:

```python
if not cwd.exists():
    return {"ok": False, "name": name, "notes": f"missing source path: {cwd}"}
```

Add support for prebuilt Go test cache by respecting:

```python
GOMODCACHE = os.environ.get("GOMODCACHE")
GOPROXY = os.environ.get("GOPROXY", "https://goproxy.cn,direct")
```

- [ ] **Step 3: Add cloud measurement script**

Create `scripts/measure_cloud_go_rust_performance.py` that:

- SSHes to the host.
- Creates a temporary test user if needed.
- Measures endpoints with loopback URL.
- Captures `/metrics`, Go service metrics, Rust metrics deltas.
- Writes `docs/reports/gupiao-go-rust-runtime-performance-YYYY-MM-DD.json`.
- Exits non-zero when any hard threshold fails.

The thresholds must match the table in this plan.

- [ ] **Step 4: Include benchmark source or bundle**

Preferred low-risk option: deploy source bundle already copied by `scripts/deploy_cloud_server.sh`, then run acceptance from host path instead of inside app container.

If container mode is required, update `Dockerfile`:

```dockerfile
COPY go-services/ /app/go-services/
COPY scripts/verify_go_rust_performance_acceptance.py /app/scripts/
```

Keep this behind a build arg if image size becomes a concern:

```dockerfile
ARG INCLUDE_ACCEPTANCE_SOURCES=0
```

- [ ] **Step 5: Run tests and cloud acceptance**

```bash
cd /Users/j/Documents/gupiao/backend
pytest tests/test_cloud_performance_script.py -q
cd /Users/j/Documents/gupiao
python scripts/verify_go_rust_performance_acceptance.py
python scripts/measure_cloud_go_rust_performance.py --host 43.143.243.97 --key /Users/j/Downloads/gupiao.pem --base-url http://127.0.0.1:18090
```

Expected: all hard thresholds pass after Tasks 1-4.

**Measured result target:** benchmark script is reproducible on cloud. Rust release speedup >= 5x for benchmark-size arrays; Go quote benchmark passes ns/op, B/op, allocs/op thresholds.

**Remaining risk:** Network restrictions can still block dependency downloads. Use vendored module cache or build-time cached CI artifact if this happens again.

## Task 6: Deployment, Observability, and Final Gate

**Bottleneck:** Some degradations are visible only in logs/metrics after real traffic, not in unit tests.

**Structural fix:** Add a deployment gate that runs before and after rollout, captures p50/p95, cache hit rate, Go/Rust hit/fallback deltas, scan accepted/failure counts, and fails the deployment when hard thresholds regress.

**Files:**
- Modify: `scripts/quick_cloud_deploy.sh`
- Modify: `scripts/deploy_cloud_server.sh`
- Create or modify: `docs/reports/go-rust-performance-remediation-verification-2026-05-27.md`

- [ ] **Step 1: Add post-deploy performance command**

In `scripts/quick_cloud_deploy.sh`, add an optional flag:

```bash
--performance-verify
```

When set, run:

```bash
python scripts/measure_cloud_go_rust_performance.py \
  --host "$CLOUD_HOST" \
  --key "$SSH_KEY" \
  --base-url "http://127.0.0.1:${APP_PORT:-18090}"
```

- [ ] **Step 2: Add metric hard gates**

The performance script exits non-zero if:

- `priority-board` warm p95 > 500ms.
- `market/pulse` warm p95 > 500ms.
- Go scan `/run` p95 > 500ms.
- Go BFF cache hit rate < 0.60 after warmup.
- Go BFF fallback delta > 0 for healthy Python upstream.
- Rust fallback or error delta > 0 during Rust smoke.

- [ ] **Step 3: Run full local validation**

```bash
cd /Users/j/Documents/gupiao/frontend
npm run lint
npm run test -- --run
npm run build

cd /Users/j/Documents/gupiao/backend
pytest

cd /Users/j/Documents/gupiao/go-services/bff-gateway
go test ./...
cd /Users/j/Documents/gupiao/go-services/market-read-service
go test ./...
cd /Users/j/Documents/gupiao/go-services/scan-worker
go test ./...

cd /Users/j/Documents/gupiao/rust/tquant-rs
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 cargo test --no-default-features

cd /Users/j/Documents/gupiao
python scripts/verify_go_rust_performance_acceptance.py
```

Expected: PASS.

- [ ] **Step 4: Deploy and verify online**

```bash
cd /Users/j/Documents/gupiao
./scripts/quick_cloud_deploy.sh --performance-verify
```

Expected: deploy succeeds and performance script writes a new report under `docs/reports/`.

- [ ] **Step 5: Final report**

Create `docs/reports/go-rust-performance-remediation-verification-2026-05-27.md` with:

- Commit hash.
- Deploy time.
- Container health.
- API p50/p95 table.
- Go BFF/market/scan metrics before and after.
- Rust hit/fallback/error deltas.
- Acceptance script result.
- Remaining risks and rollback switch:
  - Clear `TQUANT_BFF_GATEWAY_URL` to fall back Python BFF.
  - Clear `TQUANT_MARKET_READ_SERVICE_URL` to fall back Python market read.
  - Set `TQUANT_GO_SCAN_ENABLED=false` to bypass Go scan orchestration.
  - Set `RUST_FINANCE_MATH_ENABLED=false` only for emergency math fallback.

**Measured result target:** deployment cannot be called complete unless the new online report marks all hard gates PASS.

**Remaining risk:** External A-share data providers may still fail. The product must return stale/partial snapshots quickly and make the missing source visible.

## Execution Order

1. Task 1: Priority-board fast path. This removes the biggest user-facing slow route.
2. Task 2: Pulse fast path. This fixes monitor first-screen long tail.
3. Task 3: Async scan-worker. This removes 30s request timeouts and keeps latest clean.
4. Task 4: Go BFF source budgets. This caps aggregate cold latency.
5. Task 5: Cloud acceptance environment. This makes Go/Rust benchmark reproducible.
6. Task 6: Deploy gate and final verification. This proves production performance.

## Acceptance Checklist

- [ ] `priority-board` p95 is within budget online.
- [ ] `market/pulse` p95 is within budget online.
- [ ] Go scan-worker `/run` returns accepted job within budget.
- [ ] Failed full scan does not replace latest priority snapshot.
- [ ] Go BFF monitor direct cold/warm budgets pass.
- [ ] Go BFF cache hit rate >= 60% after warmup.
- [ ] Go market-read quote/latest stay fresh and p95 < 100ms.
- [ ] Rust wheel imports in production image.
- [ ] Rust hit metrics increase during smoke.
- [ ] Rust fallback/error metrics do not increase during smoke.
- [ ] Rust release benchmark speedup >= 5x.
- [ ] Cloud acceptance script is self-contained and writes a report.

