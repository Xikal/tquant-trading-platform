# Hot Read P95 Stability Final Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the remaining hot-read performance targets after the previous frontend/backend optimization rounds: `priority_board` p95 `<40ms`, `monitor_bff` p95 `<30ms`, lower BFF partial warnings, lower Go market-read unresolved/fallback counters, and make Redis/cache failures fail-open instead of breaking online acceptance.

**Architecture:** This plan fixes the remaining unstable paths by isolating cache failures first, then materializing stable priority-board read models, then applying source-level BFF timeout budgets, and finally tightening quote-cache demand-set warmup. Live quote overlay remains display-only and never participates in production ranking.

**Tech Stack:** FastAPI, SQLAlchemy, Redis/distributed cache helpers, existing runtime-worker/runtime-scheduler, Go market-read/BFF services, React, TanStack Query, Vite, pytest, Vitest, GitHub Actions, cloud deployment scripts.

---

## Current Evidence

Use these reports as the measurement baseline:

- `docs/reports/quote-cache-coverage-online-acceptance-2026-06-03.md`
- `docs/reports/performance-next-round-baseline-2026-06-03.md`
- `docs/reports/performance-next-round-acceptance-2026-06-03.md`
- `docs/reports/gupiao-cloud-performance-2026-06-04-085113.json`

Known latest state:

| Metric | Current Best / Latest Evidence | Target |
| --- | ---: | ---: |
| frontend max chunk gzip | `105.42KB` | keep `<110KB` |
| quote cache coverage | `10000 bps` | keep `10000 bps` |
| Go market-read sample missing | `0/20` | keep `0` |
| `monitor_bff` p95 | best `16.345ms`, unstable latest acceptance `301.181ms` | stable `<30ms` |
| `priority_board` p95 | best `63.237ms`, unstable latest acceptance `211.840ms` | stable `<40ms` |
| `scan_worker_accept` p95 | best `157.386ms` | no true failure states |
| latest online sampling | failed with remote protocol error and Redis read timeout | no cache timeout should fail the whole run |

## Hard Boundaries

- Do not modify `strategy_policy`.
- Do not create, replace, or wire a new `production_score`.
- Do not replace low-buy, priority board, front-row weighted, or any production ranking.
- Do not change strategy scoring formulas, stock selection rules, position rules, or backtest portfolio constraints.
- Do not allow live quote overlay to affect sorting, ranking, `priority_score`, `production_score`, `buy_signal_state`, or `elite_watch_score`.
- Do not add a Web background loop.
- Refresh, warmup, materialization, and repair must run through runtime-worker/runtime-scheduler or existing worker paths.
- Do not add framework-level dependencies.
- Missing or degraded data must be explicit: `stale`, `partial`, `no_data`, `blocked`, or cache degradation warning.
- Every optimization must be feature-flagged or trivially reversible.

## Feature Flags

Add or reuse these flags with safe defaults:

| Flag | Default | Purpose |
| --- | --- | --- |
| `DISTRIBUTED_CACHE_FAIL_OPEN_ENABLED` | `true` | Redis read/write timeout should record degradation and continue when a fallback exists. |
| `PERFORMANCE_MEASUREMENT_RETRY_ENABLED` | `true` | Online measurement retries transient remote protocol errors once. |
| `PRIORITY_BOARD_STABLE_READ_MODEL_ENABLED` | `true` | Use stable priority-board read model cache. |
| `PRIORITY_BOARD_STABLE_READ_MODEL_TTL_SECONDS` | `45` | Stable read model TTL. |
| `PRIORITY_BOARD_LIVE_OVERLAY_CACHE_ENABLED` | `true` | Keep or extend existing live overlay short cache. |
| `MONITOR_BFF_SOURCE_BUDGET_ENABLED` | `true` | Enforce source-level timeout budget and partial degradation. |
| `QUOTE_CACHE_DEMAND_WARMUP_ENABLED` | `true` | Warm up the full hot demand set through runtime paths. |

## Expected File Map

Distributed cache and measurement:

- Modify: `backend/app/services/shared/distributed_cache.py`
- Modify: `backend/app/services/performance/prometheus.py`
- Modify: `scripts/measure_cloud_go_rust_performance.py`
- Test: `backend/tests/test_distributed_cache_fail_open.py`
- Test: `backend/tests/test_cloud_performance_script.py`

Priority-board read model:

- Create: `backend/app/services/low_buy/priority_board_read_model.py`
- Modify: `backend/app/services/low_buy/priority_board.py`
- Modify: `backend/app/services/read_models/live_quote_overlay.py`
- Modify: `backend/app/api/routes/screeners.py`
- Test: `backend/tests/test_priority_board_read_model.py`
- Test: `backend/tests/test_priority_board_cache_fast_path.py`
- Test: `backend/tests/test_low_buy_priority_board_strategy_variants.py`
- Test: `backend/tests/test_low_buy_production_scoring.py`

Monitor BFF source budgets:

- Modify: `backend/app/api/routes/bff.py`
- Modify: `backend/app/services/bff/workspace_cache.py`
- Modify: `backend/app/models/schema_defs/bff.py`
- Modify: `frontend/src/types/monitor.ts`
- Modify if contract changes: `docs/contracts/openapi.json`, `docs/contracts/openapi.hash`, `frontend/src/generated/api-types.ts`
- Test: `backend/tests/test_bff_monitor_workspace.py`
- Test: `frontend/src/features/trading-workspace/useMonitorData.test.ts`

Quote-cache demand warmup:

- Modify: `backend/app/services/market_quote_cache_refresh.py`
- Modify: `backend/app/services/market/local_quote_cache.py`
- Modify: `backend/app/workers/runtime_worker.py`
- Modify: `backend/app/runtime/background_jobs.py`
- Modify: Go files under `go-services/market-read/`
- Test: `backend/tests/test_market_quote_cache_refresh.py`
- Test: `backend/tests/test_market_quote_cache_coverage.py`
- Test: Go tests under `go-services/market-read/`

Reports:

- Create: `docs/reports/hot-read-p95-stability-baseline-2026-06-04.md`
- Create: `docs/reports/hot-read-p95-stability-acceptance-2026-06-04.md`

---

### Task 0: Working Tree Gate And Baseline Report

**Files:**
- Read: `AGENTS.md`
- Read: `docs/engineering-conventions.md`
- Read: `docs/reports/performance-next-round-acceptance-2026-06-03.md`
- Create: `docs/reports/hot-read-p95-stability-baseline-2026-06-04.md`

- [ ] **Step 1: Confirm working tree**

Run:

```bash
git status --short
```

Expected:

- If unrelated dirty files exist, record them and do not modify them.
- If files needed by this plan are dirty, inspect their diff before editing and only make minimal incremental changes.

- [ ] **Step 2: Read authority docs**

Run:

```bash
sed -n '1,220p' AGENTS.md
sed -n '1,260p' docs/engineering-conventions.md
sed -n '1,320p' docs/reports/performance-next-round-acceptance-2026-06-03.md
```

Expected:

- Confirm production ranking boundary.
- Confirm latest known p95, warning, quote coverage, and deployment evidence.

- [ ] **Step 3: Capture current online baseline**

Run:

```bash
python3 scripts/measure_cloud_go_rust_performance.py --samples 8 || true
```

Expected:

- A JSON file under `docs/reports/gupiao-cloud-performance-*.json`.
- If result is `ok=false`, record exact reason. Do not treat cache timeout or remote protocol error as valid p95 data.

- [ ] **Step 4: Write baseline report**

Create `docs/reports/hot-read-p95-stability-baseline-2026-06-04.md` with this exact structure:

```markdown
# Hot Read P95 Stability Baseline

Generated at: 2026-06-04 Asia/Shanghai

## Source

- Command: `python3 scripts/measure_cloud_go_rust_performance.py --samples 8 || true`
- JSON: `docs/reports/gupiao-cloud-performance-<timestamp>.json`
- Result: `<ok=true|ok=false>`

## Metrics

| Metric | Value |
| --- | ---: |
| quote cache coverage bps | <value or blocked> |
| Go market-read checked/returned/missing | <value or blocked> |
| monitor_bff p95 | <value or blocked> |
| priority_board p95 | <value or blocked> |
| scan_worker_accept statuses | <value or blocked> |
| BFF partial classified | <value or blocked> |
| Go market-read unresolved/fallback | <value or blocked> |

## Failure Or Blocked Reason

- <exact error, such as Redis timeout or remote protocol disconnect>

## Production Boundary

- No strategy rule, production ranking, `strategy_policy`, or `production_score` change.
```

- [ ] **Step 5: Commit baseline report**

Run:

```bash
git add docs/reports/hot-read-p95-stability-baseline-2026-06-04.md
git commit -m "docs: record hot read p95 stability baseline"
```

Expected:

- Commit contains only the baseline report.

---

### Task 1: Redis Cache Fail-Open And Measurement Retry

**Files:**
- Modify: `backend/app/services/shared/distributed_cache.py`
- Modify: `backend/app/services/performance/prometheus.py`
- Modify: `scripts/measure_cloud_go_rust_performance.py`
- Create: `backend/tests/test_distributed_cache_fail_open.py`
- Modify: `backend/tests/test_cloud_performance_script.py`

- [ ] **Step 1: Write fail-open tests**

Create `backend/tests/test_distributed_cache_fail_open.py`:

```python
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.shared import distributed_cache


class TimeoutClient:
    def setex(self, *_args, **_kwargs):
        raise TimeoutError("Timeout reading from socket")

    def get(self, *_args, **_kwargs):
        raise TimeoutError("Timeout reading from socket")


def test_set_text_cache_fail_open_records_error(monkeypatch):
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(distributed_cache, "_client", lambda: TimeoutClient())
    monkeypatch.setattr(
        distributed_cache,
        "_record_cache_error",
        lambda operation, reason: events.append((operation, reason)),
    )

    result = distributed_cache.set_text_cache("k", "v", ttl_seconds=5, fail_open=True)

    assert result is False
    assert events == [("set", "timeout")]


def test_get_text_cache_fail_open_returns_none(monkeypatch):
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(distributed_cache, "_client", lambda: TimeoutClient())
    monkeypatch.setattr(
        distributed_cache,
        "_record_cache_error",
        lambda operation, reason: events.append((operation, reason)),
    )

    result = distributed_cache.get_text_cache("k", fail_open=True)

    assert result is None
    assert events == [("get", "timeout")]


def test_get_text_cache_can_still_raise_when_fail_open_disabled(monkeypatch):
    monkeypatch.setattr(distributed_cache, "_client", lambda: TimeoutClient())

    with pytest.raises(TimeoutError):
        distributed_cache.get_text_cache("k", fail_open=False)
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_distributed_cache_fail_open.py -q
```

Expected:

- Fails because `fail_open` arguments and `_record_cache_error` do not exist yet.

- [ ] **Step 3: Implement fail-open helpers**

Modify `backend/app/services/shared/distributed_cache.py`:

```python
from __future__ import annotations

from typing import Any

from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError

from app.core.config import get_settings
from app.services.performance.prometheus import record_cache_operation_error


def _cache_error_reason(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, (TimeoutError, RedisTimeoutError)) or "timeout" in text:
        return "timeout"
    if "connection" in text or "disconnect" in text:
        return "connection"
    return "redis_error"


def _record_cache_error(operation: str, reason: str) -> None:
    record_cache_operation_error(cache_name="distributed", operation=operation, reason=reason)


def set_text_cache(key: str, value: str, ttl_seconds: int, *, fail_open: bool | None = None) -> bool:
    should_fail_open = get_settings().distributed_cache_fail_open_enabled if fail_open is None else fail_open
    try:
        client = _client()
        if client is None:
            return False
        client.setex(key, max(int(ttl_seconds), 1), value)
        return True
    except (RedisError, OSError, TimeoutError) as exc:
        reason = _cache_error_reason(exc)
        _record_cache_error("set", reason)
        if should_fail_open:
            return False
        raise


def get_text_cache(key: str, *, fail_open: bool | None = None) -> str | None:
    should_fail_open = get_settings().distributed_cache_fail_open_enabled if fail_open is None else fail_open
    try:
        client = _client()
        if client is None:
            return None
        value = client.get(key)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)
    except (RedisError, OSError, TimeoutError) as exc:
        reason = _cache_error_reason(exc)
        _record_cache_error("get", reason)
        if should_fail_open:
            return None
        raise
```

Keep existing `_client()` and existing exports. If the file already has these functions, update only their bodies and signatures.

- [ ] **Step 4: Add config and metrics**

Modify the settings model in `backend/app/core/config.py`:

```python
distributed_cache_fail_open_enabled: bool = Field(default=True, alias="DISTRIBUTED_CACHE_FAIL_OPEN_ENABLED")
```

Modify `backend/app/services/performance/prometheus.py` to expose bounded counters:

```python
def record_cache_operation_error(*, cache_name: str, operation: str, reason: str) -> None:
    labels = {
        "cache": _bounded_label(cache_name, default="unknown"),
        "operation": _bounded_label(operation, default="unknown"),
        "reason": _bounded_label(reason, default="unknown"),
    }
    _increment_counter("tquant_cache_operation_errors_total", labels)
```

Use the existing counter helper style in that file. If `_bounded_label` or `_increment_counter` names differ, adapt to the local helpers and keep label cardinality bounded.

- [ ] **Step 5: Add measurement retry test**

Modify `backend/tests/test_cloud_performance_script.py` with a static guard:

```python
def test_cloud_measurement_retries_transient_remote_protocol_errors() -> None:
    script = read_repo_file("scripts/measure_cloud_go_rust_performance.py")

    assert "PERFORMANCE_MEASUREMENT_RETRY_ENABLED" in script
    assert "RemoteProtocolError" in script
    assert "Server disconnected without sending a response" in script
    assert "retrying transient online measurement" in script
```

- [ ] **Step 6: Implement measurement retry**

Modify `scripts/measure_cloud_go_rust_performance.py`:

```python
TRANSIENT_REMOTE_ERRORS = (
    "RemoteProtocolError",
    "Server disconnected without sending a response",
    "Timeout reading from socket",
    "Connection reset by peer",
)


def _is_transient_remote_measurement_error(stderr: str) -> bool:
    return any(token in stderr for token in TRANSIENT_REMOTE_ERRORS)
```

Wrap the remote measurement call so it retries once when `PERFORMANCE_MEASUREMENT_RETRY_ENABLED` is not false and stderr matches `_is_transient_remote_measurement_error`. The retry must preserve the first error in the JSON under `retry_errors`.

- [ ] **Step 7: Verify Task 1**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_distributed_cache_fail_open.py backend/tests/test_cloud_performance_script.py -q
```

Expected:

- All selected tests pass.

- [ ] **Step 8: Commit Task 1**

Run:

```bash
git add backend/app/core/config.py backend/app/services/shared/distributed_cache.py backend/app/services/performance/prometheus.py scripts/measure_cloud_go_rust_performance.py backend/tests/test_distributed_cache_fail_open.py backend/tests/test_cloud_performance_script.py
git commit -m "perf: fail open cache timeouts in hot reads"
```

---

### Task 2: Priority Board Stable Read Model Cache

**Files:**
- Create: `backend/app/services/low_buy/priority_board_read_model.py`
- Modify: `backend/app/services/low_buy/priority_board.py`
- Modify: `backend/app/api/routes/screeners.py`
- Create: `backend/tests/test_priority_board_read_model.py`
- Modify: `backend/tests/test_priority_board_cache_fast_path.py`

- [ ] **Step 1: Write read model tests**

Create `backend/tests/test_priority_board_read_model.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.services.low_buy import priority_board_read_model as read_model


def test_read_model_cache_key_includes_variant_date_and_user_filter_hash() -> None:
    key = read_model.priority_board_read_model_key(
        trade_date="2026-06-04",
        strategy_variant="default",
        cache_key="low-buy:priority:2026-06-04",
        user_filter_hash="abc123",
    )

    assert "2026-06-04" in key
    assert "default" in key
    assert "low-buy:priority:2026-06-04" in key
    assert "abc123" in key


def test_read_model_stores_and_loads_payload(monkeypatch) -> None:
    stored: dict[str, str] = {}
    monkeypatch.setattr(read_model, "set_text_cache", lambda key, value, ttl_seconds: stored.setdefault(key, value) is not None)
    monkeypatch.setattr(read_model, "get_text_cache", lambda key: stored.get(key))

    payload = {
        "items": [{"symbol": "600000", "priority_score": 88.0, "buy_signal_state": "observe"}],
        "data_quality": "fresh",
    }
    key = "priority-board:test"

    assert read_model.store_priority_board_read_model(key, payload, ttl_seconds=45) is True
    loaded = read_model.load_priority_board_read_model(key)

    assert loaded == payload


def test_read_model_rejects_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(read_model, "get_text_cache", lambda key: "{bad json")

    assert read_model.load_priority_board_read_model("priority-board:test") is None
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_priority_board_read_model.py -q
```

Expected:

- Fails because module does not exist.

- [ ] **Step 3: Implement read model helper**

Create `backend/app/services/low_buy/priority_board_read_model.py`:

```python
from __future__ import annotations

import json
from typing import Any

from app.services.shared.distributed_cache import get_text_cache, set_text_cache

READ_MODEL_VERSION = "v1"


def priority_board_read_model_key(
    *,
    trade_date: str,
    strategy_variant: str,
    cache_key: str,
    user_filter_hash: str = "global",
) -> str:
    return ":".join(
        [
            "priority_board_read_model",
            READ_MODEL_VERSION,
            str(trade_date or "unknown"),
            str(strategy_variant or "default"),
            str(cache_key or "none"),
            str(user_filter_hash or "global"),
        ]
    )


def load_priority_board_read_model(key: str) -> dict[str, Any] | None:
    raw = get_text_cache(key)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def store_priority_board_read_model(key: str, payload: dict[str, Any], *, ttl_seconds: int) -> bool:
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    return set_text_cache(key, raw, ttl_seconds=ttl_seconds)
```

- [ ] **Step 4: Add settings**

Modify `backend/app/core/config.py`:

```python
priority_board_stable_read_model_enabled: bool = Field(default=True, alias="PRIORITY_BOARD_STABLE_READ_MODEL_ENABLED")
priority_board_stable_read_model_ttl_seconds: int = Field(default=45, alias="PRIORITY_BOARD_STABLE_READ_MODEL_TTL_SECONDS")
```

- [ ] **Step 5: Wire read model after stable board construction**

Modify `backend/app/services/low_buy/priority_board.py`:

- Build stable board exactly as before.
- Before returning, serialize the stable response with `model_dump(mode="json")`.
- Cache only stable fields. Do not include live quote overlay fields that can alter with latest price.
- On cache hit, reconstruct the existing response schema and set `data_quality` to the cached payload value.

The read model must never recompute or alter:

- `priority_score`
- `production_score`
- `buy_signal_state`
- `elite_watch_score`
- item ordering

- [ ] **Step 6: Add parity test**

Modify `backend/tests/test_priority_board_cache_fast_path.py`:

```python
def test_priority_board_read_model_preserves_ranking_fields(monkeypatch):
    # Build one uncached response, then force read-model hit.
    # Compare symbol order and key strategy fields.
    original = service.get_priority_board(...)
    cached = service.get_priority_board(...)

    def key_fields(response):
        return [
            (
                item.symbol,
                item.priority_score,
                item.production_score,
                item.buy_signal_state,
                item.elite_watch_score,
            )
            for item in response.items
        ]

    assert key_fields(cached) == key_fields(original)
```

Replace `service.get_priority_board(...)` with the local helper pattern already used in the file. Do not introduce a fake strategy result that violates existing production rules.

- [ ] **Step 7: Verify Task 2**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_priority_board_read_model.py \
  backend/tests/test_priority_board_cache_fast_path.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_low_buy_production_scoring.py \
  -q
```

Expected:

- All selected tests pass.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add backend/app/core/config.py backend/app/services/low_buy/priority_board_read_model.py backend/app/services/low_buy/priority_board.py backend/tests/test_priority_board_read_model.py backend/tests/test_priority_board_cache_fast_path.py
git commit -m "perf: cache stable priority board read model"
```

---

### Task 3: Monitor BFF Source Timeout Budgets And Partial Degradation

**Files:**
- Modify: `backend/app/api/routes/bff.py`
- Modify: `backend/app/services/bff/workspace_cache.py`
- Modify: `backend/app/models/schema_defs/bff.py`
- Modify if needed: `frontend/src/types/monitor.ts`
- Modify if needed: `docs/contracts/openapi.json`
- Modify if needed: `frontend/src/generated/api-types.ts`
- Modify: `backend/tests/test_bff_monitor_workspace.py`

- [ ] **Step 1: Add BFF source-budget test**

Modify `backend/tests/test_bff_monitor_workspace.py`:

```python
def test_monitor_bff_degrades_slow_noncritical_source(monkeypatch, client, auth_headers):
    monkeypatch.setenv("MONITOR_BFF_SOURCE_BUDGET_ENABLED", "true")

    def slow_review_source(*_args, **_kwargs):
        raise TimeoutError("review source exceeded 80ms budget")

    monkeypatch.setattr("app.api.routes.bff.build_monitor_review_summary", slow_review_source)

    response = client.get("/api/bff/v1/workspace/monitor", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["priority_board"]["items"] is not None
    assert body["partial_errors"]
    assert any(error["source"] == "review" and error["reason"] == "timeout" for error in body["partial_errors"])
```

Adapt `client` and `auth_headers` to the fixtures already present in the file.

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_bff_monitor_workspace.py::test_monitor_bff_degrades_slow_noncritical_source -q
```

Expected:

- Fails because the source budget/degradation behavior is not present or not specific enough.

- [ ] **Step 3: Add source classification helper**

Modify `backend/app/api/routes/bff.py`:

```python
NONCRITICAL_MONITOR_SOURCES = {
    "review",
    "hourly_snapshot_history",
    "extended_diagnostics",
}

CRITICAL_MONITOR_SOURCES = {
    "priority_board",
    "market_pulse",
    "watchlist_signals",
    "runtime_quality",
}


def _partial_error(source: str, reason: str, message: str, *, timeout_ms: int | None = None) -> dict[str, object]:
    return {
        "source": source,
        "reason": reason,
        "message": message[:240],
        "timeout_ms": timeout_ms,
    }
```

- [ ] **Step 4: Enforce noncritical source degradation**

In the monitor BFF builder, wrap each noncritical source with a helper:

```python
def _safe_monitor_source(source: str, callback, default, partial_errors: list[dict[str, object]], timeout_ms: int):
    try:
        return callback()
    except TimeoutError as exc:
        partial_errors.append(_partial_error(source, "timeout", str(exc), timeout_ms=timeout_ms))
        return default
    except Exception as exc:
        partial_errors.append(_partial_error(source, "error", str(exc), timeout_ms=timeout_ms))
        return default
```

Use defaults that preserve the response shape:

- review status: empty status with `status="partial"`
- review reports: `[]`
- hourly history: `[]`
- extended diagnostics: `{}` or `None` according to existing schema

Critical sources should keep their existing behavior, but if they degrade through an existing fallback, they must add `partial_errors`.

- [ ] **Step 5: Ensure frontend displays partial warnings without blanking**

If `frontend/src/types/monitor.ts` does not include `partial_errors`, add:

```ts
export type MonitorPartialError = {
  source: string
  reason: string
  message?: string
  timeout_ms?: number | null
}
```

Ensure `frontend/src/features/trading-workspace/useMonitorData.ts` preserves `partial_errors` from the BFF payload. Do not hide `stale`, `data_quality`, or `snapshot_warning`.

- [ ] **Step 6: Regenerate contracts if schema changed**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python scripts/export_openapi.py
cd frontend && npm run api:check
```

Expected:

- OpenAPI hash and generated types are current.

- [ ] **Step 7: Verify Task 3**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_bff_monitor_workspace.py -q
cd frontend && npm run api:check && npm run lint && npm test -- --run
```

Expected:

- BFF tests and frontend checks pass.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add backend/app/api/routes/bff.py backend/app/services/bff/workspace_cache.py backend/app/models/schema_defs/bff.py backend/tests/test_bff_monitor_workspace.py frontend/src/types/monitor.ts frontend/src/features/trading-workspace/useMonitorData.ts docs/contracts/openapi.json docs/contracts/openapi.hash frontend/src/generated/api-types.ts
git commit -m "perf: degrade slow monitor bff sources"
```

If some listed files are unchanged, omit them from `git add`.

---

### Task 4: Quote Cache Demand Warmup And Go Market-Read Reason Reduction

**Files:**
- Modify: `backend/app/services/market_quote_cache_refresh.py`
- Modify: `backend/app/services/market/local_quote_cache.py`
- Modify: `backend/app/workers/runtime_worker.py`
- Modify: `backend/app/runtime/background_jobs.py`
- Modify: Go files under `go-services/market-read/`
- Modify: `backend/tests/test_market_quote_cache_refresh.py`
- Modify: `backend/tests/test_market_quote_cache_coverage.py`

- [ ] **Step 1: Add demand-set coverage test**

Modify `backend/tests/test_market_quote_cache_refresh.py`:

```python
def test_quote_cache_warmup_includes_all_hot_demand_sets(monkeypatch):
    captured: list[str] = []

    monkeypatch.setattr("app.services.market_quote_cache_refresh.priority_board_symbols", lambda db: ["600000"])
    monkeypatch.setattr("app.services.market_quote_cache_refresh.monitor_board_symbols", lambda db: ["600001"])
    monkeypatch.setattr("app.services.market_quote_cache_refresh.watchlist_symbols", lambda db: ["600002"])
    monkeypatch.setattr("app.services.market_quote_cache_refresh.paper_position_symbols", lambda db: ["600003"])
    monkeypatch.setattr("app.services.market_quote_cache_refresh.strategy_tracking_symbols", lambda db: ["600004"])
    monkeypatch.setattr("app.services.market_quote_cache_refresh.sector_hot_member_symbols", lambda db: ["600005"])

    symbols = build_quote_cache_demand_symbols(db=None)

    assert symbols == ["600000", "600001", "600002", "600003", "600004", "600005"]
```

Adapt imports and helper names to local style. The important contract is that all six hot demand sets are included and de-duplicated in stable order.

- [ ] **Step 2: Run demand-set test and confirm failure**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_quote_cache_refresh.py::test_quote_cache_warmup_includes_all_hot_demand_sets -q
```

Expected:

- Fails until `build_quote_cache_demand_symbols` exists or includes all sets.

- [ ] **Step 3: Implement demand-set builder**

Modify `backend/app/services/market_quote_cache_refresh.py`:

```python
def build_quote_cache_demand_symbols(db: Session) -> list[str]:
    groups = [
        priority_board_symbols(db),
        monitor_board_symbols(db),
        watchlist_symbols(db),
        paper_position_symbols(db),
        strategy_tracking_symbols(db),
        sector_hot_member_symbols(db),
    ]
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        for symbol in group:
            value = str(symbol or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
    return result
```

Each source helper must return `[]` on missing data, not raise. Do not change ranking or strategy filtering.

- [ ] **Step 4: Ensure warmup is worker-owned**

Modify `backend/app/runtime/background_jobs.py` to schedule quote warmup through the existing runtime scheduler. Do not add a Web loop.

Modify `backend/app/workers/runtime_worker.py` to execute the warmup task by calling the existing quote-cache refresh service with `build_quote_cache_demand_symbols(db)`.

- [ ] **Step 5: Add unresolved reason enum in Go market-read**

In `go-services/market-read/`, classify misses into bounded reasons:

- `not_in_demand_set`
- `cache_write_failed`
- `cache_read_miss`
- `mysql_fallback_missing`
- `stale_quote`
- `schema_mismatch`

Batch Redis reads and MySQL fallbacks. Do not add per-symbol SQL fallback loops.

- [ ] **Step 6: Verify Task 4**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_market_quote_cache_refresh.py \
  backend/tests/test_market_quote_cache_coverage.py \
  -q

find go-services/market-read -name '*_test.go' -print0 | xargs -0 -I{} dirname {} | sort -u | xargs -I{} sh -c 'cd "{}" && go test ./...'
```

Expected:

- Backend quote-cache tests pass.
- Go market-read tests pass.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
git add backend/app/services/market_quote_cache_refresh.py backend/app/services/market/local_quote_cache.py backend/app/workers/runtime_worker.py backend/app/runtime/background_jobs.py backend/tests/test_market_quote_cache_refresh.py backend/tests/test_market_quote_cache_coverage.py go-services/market-read
git commit -m "perf: warm quote cache from hot demand sets"
```

---

### Task 5: Full Local Verification And OpenAPI Sync

**Files:**
- Modify if changed: `docs/contracts/openapi.json`
- Modify if changed: `docs/contracts/openapi.hash`
- Modify if changed: `frontend/src/generated/api-types.ts`
- Create or update: `docs/reports/hot-read-p95-stability-acceptance-2026-06-04.md`

- [ ] **Step 1: Run backend full suite**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
```

Expected:

- All tests pass.

- [ ] **Step 2: Run frontend full suite**

Run:

```bash
cd frontend
npm run api:check
npm run lint
npm test -- --run
npm run build
npm run analyze
```

Expected:

- API contract, lint, tests, build, and analyze pass.
- Largest chunk remains `<110KB` gzip.

- [ ] **Step 3: Check diff hygiene**

Run:

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

Expected:

- `git diff --check` has no output.
- Dirty files are only files changed by this plan.

- [ ] **Step 4: Write local acceptance section**

Create or update `docs/reports/hot-read-p95-stability-acceptance-2026-06-04.md`:

```markdown
# Hot Read P95 Stability Acceptance

Generated at: 2026-06-04 Asia/Shanghai

## Completed Tasks

- Task 1: Redis cache fail-open and measurement retry
- Task 2: Priority board stable read model cache
- Task 3: Monitor BFF source timeout budgets
- Task 4: Quote cache demand warmup and Go market-read reason reduction

## Local Validation

| Command | Result |
| --- | --- |
| `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q` | <result> |
| `cd frontend && npm run api:check` | <result> |
| `cd frontend && npm run lint` | <result> |
| `cd frontend && npm test -- --run` | <result> |
| `cd frontend && npm run build` | <result> |
| `cd frontend && npm run analyze` | <result> |
| `git diff --check` | <result> |

## Production Boundary

- No `strategy_policy` change.
- No `production_score` creation or replacement.
- No production ranking replacement.
- Live quote overlay remains display-only.
```

- [ ] **Step 5: Commit local acceptance**

Run:

```bash
git add docs/reports/hot-read-p95-stability-acceptance-2026-06-04.md docs/contracts/openapi.json docs/contracts/openapi.hash frontend/src/generated/api-types.ts
git commit -m "docs: record hot read p95 local acceptance"
```

If generated contract files are unchanged, omit them.

---

### Task 6: Deploy And Online Acceptance

**Files:**
- Update: `docs/reports/hot-read-p95-stability-acceptance-2026-06-04.md`

- [ ] **Step 1: Push to main**

Run:

```bash
git push origin HEAD:main
```

Expected:

- Push succeeds.
- GitHub Actions starts a new run.

- [ ] **Step 2: Watch CI/deploy**

Run:

```bash
gh run list --branch main --limit 5
gh run watch <run-id> --interval 30 --exit-status
```

Expected:

- `backend`: success
- `frontend`: success
- `go-rust`: success
- `deploy`: success

If deploy fails due to transient SSH/SCP or Docker registry errors, inspect logs and extend the existing retry logic in `scripts/cloud_ssh_lib.sh` or `scripts/deploy_cloud_server.sh`. Do not change application logic for deploy-only failures.

- [ ] **Step 3: Run two online acceptance rounds**

Run:

```bash
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
```

Expected:

- Both runs complete.
- If a run returns `ok=false`, inspect the JSON and classify the failure:
  - cache timeout
  - remote protocol disconnect
  - true endpoint p95 regression
  - true API failure
  - Go market-read missing
  - scan-worker true failure state

- [ ] **Step 4: Update online acceptance report**

Append this section to `docs/reports/hot-read-p95-stability-acceptance-2026-06-04.md`:

```markdown
## Online Deployment

| Item | Result |
| --- | --- |
| GitHub Actions run | `<run-id>` |
| deploy job | `<success|failure>` |
| deployed head | `<sha>` |

## Online Acceptance

| Metric | Baseline | Round 1 | Round 2 | Verdict |
| --- | ---: | ---: | ---: | --- |
| quote cache coverage bps | <baseline> | <value> | <value> | <pass/fail> |
| Go market-read missing | <baseline> | <value> | <value> | <pass/fail> |
| monitor_bff p95 | <baseline> | <value> | <value> | <pass/fail> |
| priority_board p95 | <baseline> | <value> | <value> | <pass/fail> |
| scan_worker_accept statuses | <baseline> | <value> | <value> | <pass/fail> |
| BFF partial warnings | <baseline> | <value> | <value> | <pass/fail> |
| Go unresolved/fallback | <baseline> | <value> | <value> | <pass/fail> |

## Success Criteria

- `priority_board` p95 stable `<40ms`: <pass/fail>
- `monitor_bff` p95 stable `<30ms`: <pass/fail>
- quote cache coverage `10000 bps`: <pass/fail>
- Go market-read missing `0`: <pass/fail>
- Redis/cache timeout does not fail whole run: <pass/fail>
- deploy job success: <pass/fail>

## Remaining Risks

- <risk or none>

## Rollback

- Set `DISTRIBUTED_CACHE_FAIL_OPEN_ENABLED=false` to restore strict cache errors.
- Set `PRIORITY_BOARD_STABLE_READ_MODEL_ENABLED=false` to bypass stable read model cache.
- Set `MONITOR_BFF_SOURCE_BUDGET_ENABLED=false` to restore previous BFF source behavior.
- Set `QUOTE_CACHE_DEMAND_WARMUP_ENABLED=false` to restore previous quote warmup scope.
- Redeploy previous successful commit if a production regression appears.
```

- [ ] **Step 5: Commit and push final report**

Run:

```bash
git add docs/reports/hot-read-p95-stability-acceptance-2026-06-04.md
git commit -m "docs: record hot read p95 online acceptance"
git push origin HEAD:main
```

Expected:

- Final report is committed and pushed.

---

## Final Verification Commands

Run all commands before final delivery:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q

cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run lint
npm test -- --run
npm run build
npm run analyze

cd /Users/j/Documents/gupiao
git diff --check
git status --short
git push origin HEAD:main

python3 scripts/measure_cloud_go_rust_performance.py --samples 8
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
```

## Final Deliverables

1. Code changes for cache fail-open, priority-board read model cache, monitor BFF source budgets, and quote-cache demand warmup.
2. `docs/reports/hot-read-p95-stability-baseline-2026-06-04.md`.
3. `docs/reports/hot-read-p95-stability-acceptance-2026-06-04.md`.
4. Local validation command results.
5. GitHub Actions deploy run result.
6. Two online acceptance rounds.
7. Before/after percentage deltas for each metric.
8. Remaining risk list and rollback instructions.
9. Explicit conclusion that production sorting was not affected.

## Success Criteria

- `priority_board` p95 is stable `<40ms` across two online rounds.
- `monitor_bff` p95 is stable `<30ms` across two online rounds.
- quote cache coverage remains `10000 bps`.
- Go market-read sample missing remains `0`.
- Go market-read unresolved/fallback counters drop by at least `50%` from the chosen baseline, or all remaining increments are classified with bounded reasons.
- Redis/cache timeout does not fail the whole measurement run.
- Frontend largest chunk remains `<110KB` gzip.
- All local tests pass.
- Deploy job succeeds.
- No production ranking impact.

## Notes For Future Optimization

If `priority_board` remains above `40ms` after this plan, do not keep stacking cache layers. The next plan should split the payload: first screen returns top N items and summary only, while long-tail details lazy-load behind a separate endpoint. That follow-up must preserve item ordering and production strategy fields.
