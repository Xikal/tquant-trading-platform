# Late Session Recommendation Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent late-session recommendation board that derives from the existing production `priority_board`, performs lightweight 14:50-14:57 confirmation, and preserves the current production ranking contract.

**Architecture:** Keep the existing modular-monolith shape. Add a side-by-side low-buy domain service, schema, cache/snapshot adapter, runtime task, API route, and frontend display module; do not modify production strategy semantics or the default priority board path. Web requests read cache or perform bounded derivation only; scheduled/runtime work handles snapshot writes.

**Tech Stack:** FastAPI, SQLAlchemy session dependencies, existing low-buy services, runtime worker task queue, Redis/read-model cache where already available, SolidJS/Vite frontend-next, pytest, vitest, Playwright.

---

## 0. Authority, Boundaries, And Source Docs

Authority files:

- `AGENTS.md`
- `docs/engineering-conventions.md`
- `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`
- `docs/late-session-recommendation-board-requirements-2026-06-13.md`

Hard boundaries:

- Do not modify `backend/app/services/low_buy/strategy_policy.py`.
- Do not change `production_score`, production strategy admission, default `priority_board` sorting, or default `priority_board` response semantics.
- Do not deploy, cut traffic, restart services, change production config, or run destructive commands from this plan.
- Do not implement auto trading. The feature is recommendation/observation only.
- Do not run full-market low-buy scans from Web requests.
- Do not let frontend recompute production ranking or late-session state; frontend displays backend order and backend states.

Current code anchors verified on 2026-06-13:

- Strategy tiers live in `backend/app/services/low_buy/strategy_policy.py`.
- Intraday/VWAP helpers live in `backend/app/services/low_buy/intraday_confirmation.py`.
- Existing API route is `backend/app/api/routes/screeners.py` at `GET /low-buy/priority-board`.
- Runtime worker dispatch lives in `backend/app/workers/runtime_worker.py`.
- Current monitor frontend lives in `frontend-next/src/features/monitor-action/`.

## 1. File Structure

Create backend schema and low-buy service files:

- Create `backend/app/models/schema_defs/late_session_board.py`
  - Pydantic response contract for `late-session-board`.
  - Enums for snapshot slot, board status, item state, and degradation reason.
- Create `backend/app/services/low_buy/late_session_policy.py`
  - Local whitelist constants and pure policy helpers.
  - Imports from `strategy_policy.py` are read-only.
- Create `backend/app/services/low_buy/late_session_board.py`
  - Core derivation service.
  - Reads existing priority board payload, user sector exclusions, quote/minute/market context, and produces late-session response.
  - No DB writes.
- Create `backend/app/services/low_buy/late_session_cache.py`
  - Cache key, TTL, read/write wrapper, stable payload serialization.
  - User filtering uses `user_filter_hash` and does not mutate global snapshot.
- Create `backend/app/services/low_buy/late_session_tasks.py`
  - Runtime task entrypoint for `late_session_recommendation_refresh`.
  - Handles slot idempotency, timeout/degradation payload, and snapshot write through cache adapter.

Modify backend entrypoints:

- Modify `backend/app/api/routes/screeners.py`
  - Add `GET /api/screeners/low-buy/late-session-board`.
  - Reuse existing auth and admin refresh gating style from `priority_board`.
- Modify `backend/app/workers/runtime_worker.py`
  - Add task dispatch to `late_session_tasks.refresh_late_session_recommendation`.
- Modify the runtime scheduler only if the repo already exposes an approved low-risk scheduling registry for 14:50/14:55/14:57 jobs.
  - If no stable registry is found, stop after task support and document the manual enqueue command in the acceptance report.

Create backend tests:

- Create `backend/tests/test_late_session_board_policy.py`
- Create `backend/tests/test_late_session_board_service.py`
- Create `backend/tests/test_late_session_board_api.py`
- Create `backend/tests/test_late_session_runtime_task.py`

Create frontend files:

- Create `frontend-next/src/features/monitor-action/lateSessionBoardModel.ts`
- Create `frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts`
- Create `frontend-next/src/features/monitor-action/LateSessionBoardPanel.tsx`
- Modify `frontend-next/src/features/monitor-action/MonitorActionPage.tsx`
- Modify `frontend-next/src/features/monitor-action/monitor-action.css`
- Modify `frontend-next/src/shared/api/queryKeys.ts`
- Modify `frontend-next/src/shared/api/client.ts`

Create research and acceptance artifacts:

- Create `backend/scripts/late_session_board_backtest.py`
- Create `docs/reports/late-session-recommendation-board-local-acceptance-2026-06-13.md`

## 2. Parallel Development Model

After Task 1 defines the backend contract, work can split:

- Agent A, Backend domain: Tasks 1-3.
- Agent B, API/runtime/cache: Tasks 4-6. Depends on Task 1 schema.
- Agent C, Frontend: Tasks 7-8. Can start after Task 1 response examples are committed.
- Agent D, Research/QA: Tasks 9-10. Can start with fixture payloads from Task 1 and complete after Task 6.

Integration order:

1. Task 1 contract.
2. Tasks 2 and 3 service/cache.
3. Tasks 4 and 5 API/runtime.
4. Tasks 7 and 8 frontend.
5. Tasks 9 and 10 acceptance.

## 3. Task Plan

### Task 1: Backend Contract And Policy Guard

**Files:**

- Create: `backend/app/models/schema_defs/late_session_board.py`
- Create: `backend/app/services/low_buy/late_session_policy.py`
- Test: `backend/tests/test_late_session_board_policy.py`

- [ ] Step 1: Write the failing policy tests.

```python
# backend/tests/test_late_session_board_policy.py
from app.services.low_buy.late_session_policy import (
    FORMAL_LATE_SESSION_STRATEGIES,
    LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES,
    classify_late_session_strategy,
    late_session_strategy_allowed_for_formal,
)


def test_formal_late_session_strategy_whitelist_is_narrow():
    assert FORMAL_LATE_SESSION_STRATEGIES == {
        "first_board",
        "volume_shrink",
        "late_session_strong_support",
    }
    assert late_session_strategy_allowed_for_formal("first_board") is True
    assert late_session_strategy_allowed_for_formal("volume_shrink") is True
    assert late_session_strategy_allowed_for_formal("late_session_strong_support") is True
    assert late_session_strategy_allowed_for_formal("classic_retrace") is False
    assert late_session_strategy_allowed_for_formal("deep_pullback") is False


def test_low_sample_strategy_is_capped_not_promoted():
    assert LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES == {"late_session_strong_support"}
    assert classify_late_session_strategy("late_session_strong_support") == "auxiliary_capped"
    assert classify_late_session_strategy("first_board") == "core"
    assert classify_late_session_strategy("classic_retrace") == "research_only"
```

- [ ] Step 2: Run the policy tests and verify they fail because the new module does not exist.

Run:

```bash
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_late_session_board_policy.py
```

Expected: `ModuleNotFoundError: No module named 'app.services.low_buy.late_session_policy'`.

- [ ] Step 3: Implement the contract schema and policy helper.

```python
# backend/app/models/schema_defs/late_session_board.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LateSessionSnapshotSlot(str, Enum):
    PREVIEW_1450 = "preview_1450"
    SNAPSHOT_1455 = "snapshot_1455"
    FINAL_1457 = "final_1457"
    LATEST = "latest"


class LateSessionBoardStatus(str, Enum):
    OK = "ok"
    PARTIAL_DATA = "partial_data"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class LateSessionItemState(str, Enum):
    LATE_CONFIRMED = "late_confirmed"
    LATE_WATCH = "late_watch"
    LATE_REJECTED = "late_rejected"
    LATE_UNAVAILABLE = "late_unavailable"


class LateSessionDegradationReason(str, Enum):
    BLOCKED_BY_MATERIALIZATION = "blocked_by_materialization"
    QUOTE_UNAVAILABLE = "quote_unavailable"
    MINUTE_DATA_MISSING = "minute_data_missing"
    VWAP_UNAVAILABLE = "vwap_unavailable"
    MARKET_CONTEXT_MISSING = "market_context_missing"
    PARTIAL_DATA = "partial_data"
    REFRESH_QUEUED = "refresh_queued"
    SNAPSHOT_FAILED = "snapshot_failed"
    FINAL_SNAPSHOT_FAILED = "final_snapshot_failed"


class LateSessionBoardItemOut(BaseModel):
    symbol: str
    name: str = ""
    strategy_key: str = ""
    strategy_layer: str = ""
    priority_score: float | None = None
    production_score: float | None = None
    buy_signal_state: str = ""
    late_session_state: LateSessionItemState
    late_session_score: float = 0.0
    late_session_reason: str = ""
    vwap: float | None = None
    latest_price: float | None = None
    above_vwap: bool | None = None
    late_session_strength: bool | None = None
    low_rising: bool | None = None
    risk_tags: list[str] = Field(default_factory=list)
    reject_reasons: list[str] = Field(default_factory=list)
    quote_timestamp: str = ""
    snapshot_slot: LateSessionSnapshotSlot
    source: dict[str, Any] = Field(default_factory=dict)


class LateSessionBoardResponse(BaseModel):
    trade_date: str = ""
    snapshot_slot: LateSessionSnapshotSlot
    generated_at: datetime
    source_priority_board_epoch: str = ""
    status: LateSessionBoardStatus
    items: list[LateSessionBoardItemOut] = Field(default_factory=list)
    data_quality: str = ""
    data_quality_tags: list[str] = Field(default_factory=list)
    degradation_reason: str = ""
    next_refresh_at: str = ""
    refresh_mode: str = "cache"
    source: dict[str, Any] = Field(default_factory=dict)
```

```python
# backend/app/services/low_buy/late_session_policy.py
from __future__ import annotations

from app.services.low_buy.strategy_policy import (
    CORE_STRATEGIES,
    LOW_SAMPLE_CAPPED_STRATEGIES,
    get_strategy_tier,
)

FORMAL_LATE_SESSION_STRATEGIES = frozenset(
    {
        "first_board",
        "volume_shrink",
        "late_session_strong_support",
    }
)
LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES = frozenset({"late_session_strong_support"})
LATE_SESSION_DEFAULT_LIMIT = 12
LATE_SESSION_SOURCE_CANDIDATE_LIMIT = 30


def late_session_strategy_allowed_for_formal(strategy_key: str) -> bool:
    return strategy_key in FORMAL_LATE_SESSION_STRATEGIES


def classify_late_session_strategy(strategy_key: str) -> str:
    if strategy_key in LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES or strategy_key in LOW_SAMPLE_CAPPED_STRATEGIES:
        return "auxiliary_capped"
    if strategy_key in CORE_STRATEGIES:
        return "core"
    if late_session_strategy_allowed_for_formal(strategy_key):
        return str(get_strategy_tier(strategy_key).value)
    return "research_only"


def late_session_score_cap(strategy_key: str, raw_score: float) -> float:
    score = max(0.0, min(float(raw_score or 0.0), 100.0))
    if strategy_key in LATE_SESSION_LOW_SAMPLE_CAPPED_STRATEGIES:
        return min(score, 72.0)
    return score
```

- [ ] Step 4: Run policy tests.

Run:

```bash
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_late_session_board_policy.py
```

Expected: all tests pass.

- [ ] Step 5: Commit.

```bash
git add backend/app/models/schema_defs/late_session_board.py backend/app/services/low_buy/late_session_policy.py backend/tests/test_late_session_board_policy.py
git commit -m "feat: add late session board contract"
```

### Task 2: Read-Only Derivation Service

**Files:**

- Create: `backend/app/services/low_buy/late_session_board.py`
- Test: `backend/tests/test_late_session_board_service.py`

- [ ] Step 1: Write service tests covering whitelist, missing data, VWAP rejection, market block, and confirmed item.

Use lightweight fixtures with plain dictionaries. Include these minimum test names:

```python
def test_late_session_board_filters_research_strategy_to_watch(): ...
def test_late_session_board_marks_missing_minutes_unavailable(): ...
def test_late_session_board_rejects_below_vwap(): ...
def test_late_session_board_market_block_prevents_formal_recommendation(): ...
def test_late_session_board_confirms_core_candidate_with_vwap_and_lows(): ...
def test_late_session_strong_support_score_is_capped(): ...
```

The confirmed fixture must use:

```python
candidate = {
    "symbol": "000001",
    "name": "平安银行",
    "strategy_key": "first_board",
    "priority_score": 88,
    "production_score": 82,
    "buy_signal_state": "observe",
}
minutes = [
    {"timestamp": "2026-06-13 14:50", "open": 10.0, "high": 10.1, "low": 9.98, "close": 10.05, "volume": 1000, "amount": 10050},
    {"timestamp": "2026-06-13 14:51", "open": 10.05, "high": 10.12, "low": 10.01, "close": 10.08, "volume": 1000, "amount": 10080},
    {"timestamp": "2026-06-13 14:52", "open": 10.08, "high": 10.14, "low": 10.03, "close": 10.11, "volume": 1000, "amount": 10110},
    {"timestamp": "2026-06-13 14:53", "open": 10.11, "high": 10.16, "low": 10.05, "close": 10.13, "volume": 1000, "amount": 10130},
    {"timestamp": "2026-06-13 14:54", "open": 10.13, "high": 10.18, "low": 10.07, "close": 10.16, "volume": 1000, "amount": 10160},
]
```

- [ ] Step 2: Run service tests and verify they fail because the service does not exist.

Run:

```bash
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_late_session_board_service.py
```

- [ ] Step 3: Implement minimal derivation service.

Required public API:

```python
def build_late_session_board(
    *,
    candidates: list[dict[str, object]],
    minute_bars_by_symbol: dict[str, list[object]],
    quotes_by_symbol: dict[str, dict[str, object]] | None = None,
    market_state: str | None = None,
    trade_date: str = "",
    snapshot_slot: LateSessionSnapshotSlot = LateSessionSnapshotSlot.LATEST,
    source_priority_board_epoch: str = "",
    limit: int = 12,
) -> LateSessionBoardResponse:
    ...
```

Implementation requirements:

- Convert dict minute bars to objects compatible with `build_intraday_confirmation`.
- Use `build_intraday_confirmation` for VWAP, `above_vwap`, `low_rising`, `late_session_strength`.
- `market_state == "block"` prevents `late_confirmed`.
- Missing minutes returns item state `late_unavailable`, reason `minute_data_missing`.
- Research/factor strategy returns `late_watch` at most.
- Preserve source candidate order for ties; do not sort by frontend fields.
- Limit response after derivation.

- [ ] Step 4: Run service tests.

Run:

```bash
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_late_session_board_service.py backend/tests/test_late_session_board_policy.py
```

Expected: all tests pass.

- [ ] Step 5: Commit.

```bash
git add backend/app/services/low_buy/late_session_board.py backend/tests/test_late_session_board_service.py
git commit -m "feat: derive late session board from priority candidates"
```

### Task 3: Cache And Snapshot Adapter

**Files:**

- Create: `backend/app/services/low_buy/late_session_cache.py`
- Test: `backend/tests/test_late_session_board_cache.py`

- [ ] Step 1: Write cache-key and immutability tests.

Minimum tests:

```python
def test_late_session_cache_key_includes_trade_date_slot_epoch_variant_and_user_filter(): ...
def test_final_snapshot_ttl_is_longer_than_preview(): ...
def test_user_filter_hash_changes_derived_cache_without_changing_global_key(): ...
def test_final_snapshot_payload_is_not_overwritten_by_live_overlay_after_close(): ...
```

- [ ] Step 2: Implement a small adapter with pure helpers first.

Required helpers:

```python
def late_session_cache_key(
    *,
    trade_date: str,
    slot: str,
    strategy_variant: str,
    source_epoch: str,
    user_filter_hash: str = "global",
) -> str:
    return f"late_session_board:{trade_date}:{slot}:{strategy_variant}:{source_epoch}:{user_filter_hash}"


def late_session_ttl_seconds(slot: str) -> int:
    if slot == "preview_1450":
        return 10 * 60
    if slot == "snapshot_1455":
        return 6 * 60 * 60
    if slot == "final_1457":
        return 7 * 24 * 60 * 60
    return 10 * 60
```

If the repo already has a cache abstraction for priority read models, wrap that abstraction. Do not introduce a new Redis client if an existing one is available.

- [ ] Step 3: Run cache tests.

Run:

```bash
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_late_session_board_cache.py
```

- [ ] Step 4: Commit.

```bash
git add backend/app/services/low_buy/late_session_cache.py backend/tests/test_late_session_board_cache.py
git commit -m "feat: add late session board cache keys"
```

### Task 4: API Route

**Files:**

- Modify: `backend/app/api/routes/screeners.py`
- Test: `backend/tests/test_late_session_board_api.py`

- [ ] Step 1: Write API tests.

Minimum tests:

```python
def test_late_session_board_requires_login(client): ...
def test_late_session_board_cache_mode_does_not_trigger_full_scan(client, monkeypatch): ...
def test_late_session_board_async_mode_enqueues_light_task_only(client, monkeypatch): ...
def test_late_session_board_sync_mode_downgrades_to_async_without_admin(client, monkeypatch): ...
def test_late_session_board_degraded_response_has_complete_schema(client, monkeypatch): ...
```

Assertions:

- `GET /api/screeners/low-buy/late-session-board` unauthenticated returns current auth status, normally 401.
- `refresh=cache` never calls low-buy full scan or materialization.
- `refresh=async` enqueues `late_session_recommendation_refresh` only.
- `refresh=sync` requires the same admin style as priority board sync and otherwise falls back to async.

- [ ] Step 2: Add route beside `low_buy_priority_board_view`.

Endpoint:

```text
GET /api/screeners/low-buy/late-session-board
```

Query parameters:

```python
limit: int = Query(12, ge=3, le=30)
slot: str = Query("latest", pattern="^(preview_1450|snapshot_1455|final_1457|latest)$")
refresh: str = Query("cache", pattern="^(cache|async|sync)$")
strategy_variant: str = Query("baseline", pattern="^(baseline|front_row_weighted|front_row_only)$")
```

Route behavior:

- Reuse `get_current_user`, `get_db`, `UserSectorPreferenceService`.
- Compute effective refresh with a new helper mirroring `_priority_board_refresh_mode_for_web`.
- For `cache`, call late-session service/cache only.
- For `async`, enqueue `late_session_recommendation_refresh` and return latest cache or `refresh_queued`.
- For `sync`, allow only admin/internal; if denied, return async semantics.
- Apply user sector exclusion after global snapshot retrieval, with a user-filter cache key when caching.

- [ ] Step 3: Run API tests.

Run:

```bash
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_late_session_board_api.py
```

- [ ] Step 4: Regression-test priority board route.

Run:

```bash
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_priority_board_cache_fast_path.py backend/tests/test_priority_board_read_model.py
```

Expected: no priority board behavior regressions.

- [ ] Step 5: Commit.

```bash
git add backend/app/api/routes/screeners.py backend/tests/test_late_session_board_api.py
git commit -m "feat: expose late session board api"
```

### Task 5: Runtime Task

**Files:**

- Create: `backend/app/services/low_buy/late_session_tasks.py`
- Modify: `backend/app/workers/runtime_worker.py`
- Test: `backend/tests/test_late_session_runtime_task.py`

- [ ] Step 1: Write runtime task tests.

Minimum tests:

```python
def test_runtime_worker_dispatches_late_session_refresh(monkeypatch): ...
def test_late_session_task_uses_slot_specific_idempotency_key(): ...
def test_late_session_task_never_calls_full_market_scan(monkeypatch): ...
def test_late_session_task_records_degradation_when_source_board_missing(monkeypatch): ...
```

- [ ] Step 2: Implement `late_session_tasks.py`.

Required public function:

```python
def refresh_late_session_recommendation(db, payload: dict[str, object]) -> dict[str, object]:  # noqa: ANN001
    ...
```

Payload fields:

- `trade_date`
- `slot`
- `strategy_variant`
- `limit`
- `source_limit`
- `reason`

Result fields:

- `ok`
- `task_type`
- `slot`
- `trade_date`
- `item_count`
- `confirmed_count`
- `degradation_reason`
- `elapsed_ms`
- `worker_scope`

- [ ] Step 3: Add dispatch to `runtime_worker._execute_task`.

Add a narrow branch:

```python
if task_type == "late_session_recommendation_refresh":
    from app.services.low_buy.late_session_tasks import refresh_late_session_recommendation

    return refresh_late_session_recommendation(db, payload)
```

- [ ] Step 4: Run task tests.

Run:

```bash
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_late_session_runtime_task.py
```

- [ ] Step 5: Commit.

```bash
git add backend/app/services/low_buy/late_session_tasks.py backend/app/workers/runtime_worker.py backend/tests/test_late_session_runtime_task.py
git commit -m "feat: add late session runtime refresh task"
```

### Task 6: Scheduler Hook Or Manual Enqueue Runbook

**Files:**

- Modify only if stable registry exists: `backend/app/runtime/background_jobs.py` or the repo's current runtime scheduling registry.
- Otherwise create: `docs/operations/late-session-board-runbook.md`
- Test: add targeted scheduler test only if code changed.

- [ ] Step 1: Inspect current scheduling registry.

Run:

```bash
rg -n "low_buy_materialization_refresh|monitor_snapshot_refresh|task_definitions_for_worker|enqueue" backend/app/runtime backend/app/services backend/app/workers
```

- [ ] Step 2: If a stable scheduler registry exists, add 14:50/14:55/14:57 enqueue definitions.

Task payloads:

```json
{"slot":"preview_1450","reason":"late_session_preview_1450","source_limit":30,"limit":12}
{"slot":"snapshot_1455","reason":"late_session_snapshot_1455","source_limit":30,"limit":12}
{"slot":"final_1457","reason":"late_session_final_1457","source_limit":30,"limit":12}
```

Idempotency keys:

```text
late_session_recommendation_refresh:{trade_date}:preview_1450
late_session_recommendation_refresh:{trade_date}:snapshot_1455
late_session_recommendation_refresh:{trade_date}:final_1457
```

- [ ] Step 3: If no stable registry exists, do not invent one. Write a runbook with manual enqueue examples and mark scheduling as a deployment-time follow-up.

Runbook must include:

- The three slots and target times.
- Example enqueue payloads.
- No restart/deploy instructions.
- Verification commands for local task execution only.

- [ ] Step 4: Run tests relevant to changed files.

If scheduler code changed:

```bash
PYTHONPATH=backend:. python -m pytest -q backend/tests/test_d5_scheduler_embed_gate.py backend/tests/test_late_session_runtime_task.py
```

If only runbook changed:

```bash
python - <<'PY'
from pathlib import Path
p = Path("docs/operations/late-session-board-runbook.md")
text = p.read_text()
assert "late_session_recommendation_refresh" in text
assert "docker restart" not in text
assert "deploy" not in text.lower()
PY
```

- [ ] Step 5: Commit.

```bash
git add backend/app/runtime docs/operations/late-session-board-runbook.md backend/tests/test_d5_scheduler_embed_gate.py backend/tests/test_late_session_runtime_task.py
git commit -m "feat: document late session refresh scheduling"
```

### Task 7: Frontend API Model

**Files:**

- Create: `frontend-next/src/features/monitor-action/lateSessionBoardModel.ts`
- Create: `frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts`
- Modify: `frontend-next/src/shared/api/client.ts`
- Modify: `frontend-next/src/shared/api/queryKeys.ts`

- [ ] Step 1: Write frontend model tests.

Minimum tests:

```ts
it("maps late_confirmed items without changing order", () => {});
it("maps partial_data and refresh_queued to visible degraded state", () => {});
it("does not emit banned trading-copy text", () => {});
it("supports slot labels for preview_1450 snapshot_1455 final_1457", () => {});
```

Banned expressions:

```ts
const banned = ["必涨", "建议买入", "立即买入"];
```

- [ ] Step 2: Implement `lateSessionBoardModel.ts`.

Exports:

```ts
export type LateSessionState = "late_confirmed" | "late_watch" | "late_rejected" | "late_unavailable";
export type LateSessionSlot = "preview_1450" | "snapshot_1455" | "final_1457" | "latest";
export interface LateSessionBoardItem { ... }
export interface LateSessionBoardModel { ... }
export function createLateSessionBoardModel(data: unknown): LateSessionBoardModel { ... }
export function lateSessionSlotLabel(slot: string): string { ... }
export function lateSessionStateLabel(state: string): string { ... }
```

Rules:

- Preserve backend `items` order.
- Do not calculate `late_session_state` in frontend.
- Show "尾盘确认", "尾盘观察", "不满足尾盘确认", "数据不足".
- Never use "必涨", "建议买入", or "立即买入".

- [ ] Step 3: Add API client method and query key.

Use existing `apiClient` style and add:

```ts
lateSessionBoard(params?: { limit?: number; slot?: string; refresh?: "cache" | "async" | "sync"; signal?: AbortSignal })
```

Query key:

```ts
lateSessionBoard: (slot = "latest") => ["screeners", "low-buy", "late-session-board", slot] as const
```

- [ ] Step 4: Run frontend model tests.

Run:

```bash
npm --prefix frontend-next test -- --run frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts
```

- [ ] Step 5: Commit.

```bash
git add frontend-next/src/features/monitor-action/lateSessionBoardModel.ts frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts frontend-next/src/shared/api/client.ts frontend-next/src/shared/api/queryKeys.ts
git commit -m "feat: add late session board frontend model"
```

### Task 8: Frontend Monitor Panel

**Files:**

- Create: `frontend-next/src/features/monitor-action/LateSessionBoardPanel.tsx`
- Modify: `frontend-next/src/features/monitor-action/MonitorActionPage.tsx`
- Modify: `frontend-next/src/features/monitor-action/monitor-action.css`
- Test: add or update a focused component/page test if a monitor-action test harness already exists.

- [ ] Step 1: Build the panel as a side-by-side module.

Panel requirements:

- Fetch `apiClient.lateSessionBoard({ limit: 12, slot: "latest", refresh: "cache" })`.
- Display slot, generated time, status, data-quality tags.
- Display item order exactly as backend order.
- Show `late_confirmed`, `late_watch`, `late_rejected`, and `late_unavailable` states.
- Empty/degraded states must be readable and not blank.
- No frontend recomputation of state or ranking.

- [ ] Step 2: Insert the panel in `MonitorActionPage.tsx`.

Placement:

- Place below market KPI/strategy summary and above or beside the priority rank list.
- Keep original priority list visible and unchanged.
- Do not rename existing priority-board tabs or lane semantics.

- [ ] Step 3: Add CSS with stable dimensions.

Rules:

- No nested cards.
- No page-wide one-color palette change.
- Use existing monitor card and panel classes where possible.
- Ensure long stock names and reasons wrap without overlap.

- [ ] Step 4: Run frontend tests and typecheck.

Run:

```bash
npm --prefix frontend-next test -- --run frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts
npm --prefix frontend-next run typecheck
```

- [ ] Step 5: Build frontend.

Run:

```bash
npm --prefix frontend-next run build
```

- [ ] Step 6: Optional local screenshot smoke if the app can run locally without deployment.

Run:

```bash
npm --prefix frontend-next run dev -- --host 127.0.0.1
```

Then use Playwright against `/next/monitor` and record:

- Panel visible.
- Priority board still visible.
- No console dynamic-import/chunk 404.
- No banned copy.

- [ ] Step 7: Commit.

```bash
git add frontend-next/src/features/monitor-action/LateSessionBoardPanel.tsx frontend-next/src/features/monitor-action/MonitorActionPage.tsx frontend-next/src/features/monitor-action/monitor-action.css
git commit -m "feat: show late session board on monitor"
```

### Task 9: Research Backtest Script

**Files:**

- Create: `backend/scripts/late_session_board_backtest.py`
- Create report when run: `docs/reports/late-session-board-backtest-YYYY-MM-DD.md`
- Test if script utilities are unit-testable: `backend/tests/test_late_session_board_backtest.py`

- [ ] Step 1: Implement CLI skeleton.

Required arguments:

```text
--start-date YYYY-MM-DD
--end-date YYYY-MM-DD
--limit 12
--source-limit 30
--output docs/reports/late-session-board-backtest-YYYY-MM-DD.md
```

- [ ] Step 2: Compare cohorts.

Cohorts:

- Original priority board top N.
- `late_confirmed`.
- `late_watch`.
- Rejected by late-session rules.

Metrics:

- T+1 open return.
- T+1 high return.
- T+1 10:30 high return.
- T+1 close return.
- T+2 close return.
- Win rate.
- PF.
- Average return.
- Max drawdown.
- Sample retention.
- Missing-data rate.

- [ ] Step 3: Add honesty guards.

The report must state:

- It does not use `max_gain` as tradable return.
- It discloses missing-data rate.
- It does not promote research/factor strategies into production.

- [ ] Step 4: Run script help.

Run:

```bash
PYTHONPATH=backend:. python backend/scripts/late_session_board_backtest.py --help
```

- [ ] Step 5: Commit.

```bash
git add backend/scripts/late_session_board_backtest.py backend/tests/test_late_session_board_backtest.py
git commit -m "feat: add late session board backtest report"
```

### Task 10: Acceptance, Regression, And Guard Report

**Files:**

- Create: `docs/reports/late-session-recommendation-board-local-acceptance-2026-06-13.md`

- [ ] Step 1: Run backend targeted tests.

Run:

```bash
PYTHONPATH=backend:. python -m pytest -q \
  backend/tests/test_late_session_board_policy.py \
  backend/tests/test_late_session_board_service.py \
  backend/tests/test_late_session_board_cache.py \
  backend/tests/test_late_session_board_api.py \
  backend/tests/test_late_session_runtime_task.py \
  backend/tests/test_priority_board_cache_fast_path.py \
  backend/tests/test_priority_board_read_model.py \
  backend/tests/test_strategy_engine_production_gate_guards.py
```

- [ ] Step 2: Run frontend checks.

Run:

```bash
npm --prefix frontend-next test -- --run frontend-next/src/features/monitor-action/lateSessionBoardModel.test.ts
npm --prefix frontend-next run typecheck
npm --prefix frontend-next run build
```

- [ ] Step 3: Verify protected file is untouched.

Run:

```bash
git diff -- backend/app/services/low_buy/strategy_policy.py
```

Expected: empty output.

- [ ] Step 4: Verify no production semantic changes are hidden in priority-board files.

Run:

```bash
git diff -- backend/app/services/low_buy/priority_board.py backend/app/services/low_buy/priority_scoring.py backend/app/services/low_buy/production_scoring.py backend/app/services/low_buy/priority_response.py
```

Expected: either empty output or only import/adapter changes explicitly documented in the acceptance report.

- [ ] Step 5: Write acceptance report.

Report sections:

- Scope implemented.
- Commands run and pass/fail status.
- API contract summary.
- Backend degradation behavior.
- Frontend states verified.
- Priority-board compatibility result.
- Files intentionally untouched.
- Deployment status: not deployed.
- Remaining authorization-required work.

- [ ] Step 6: Final git status.

Run:

```bash
git status --short
```

- [ ] Step 7: Commit acceptance report.

```bash
git add docs/reports/late-session-recommendation-board-local-acceptance-2026-06-13.md
git commit -m "docs: record late session board acceptance"
```

## 4. Stop Conditions

Stop and report before continuing if any of these happen:

- A task requires editing `backend/app/services/low_buy/strategy_policy.py`.
- A task requires changing `production_score` or default `priority_board` sorting semantics.
- A Web request path would need to trigger full-market scan to pass.
- Scheduler integration requires deployment config, service restart, or production env changes.
- Tests show existing priority board order changed under equivalent inputs.
- Frontend implementation requires hiding the existing priority board.

## 5. Final Acceptance Gates

The feature is locally complete only when all are true:

- `GET /api/screeners/low-buy/late-session-board` exists and is auth-protected.
- Cache mode is read-only and does not call full scan.
- Async mode queues only `late_session_recommendation_refresh`.
- Runtime task derives from materialized priority candidates only.
- `late_confirmed` requires usable quote/minute/VWAP and non-blocked market context.
- Missing quote/minute/VWAP/market context returns explicit degradation and no formal recommendation.
- Frontend shows the late-session board without changing priority-board order.
- No banned copy appears: `必涨`, `建议买入`, `立即买入`.
- `backend/app/services/low_buy/strategy_policy.py` has no diff.
- No deployment, restart, traffic cutover, production config write, or production cleanup was executed.

## 6. Self-Review Notes

Spec coverage:

- Independent API: Task 4.
- Strategy whitelist and research isolation: Tasks 1-2.
- 14:50/14:55/14:57 slots: Tasks 3, 5, 6, 7.
- Snapshot/cache semantics: Task 3.
- Runtime task: Task 5.
- Frontend `/next/monitor`: Tasks 7-8.
- Backtest/research comparison: Task 9.
- Performance and no full-scan guard: Tasks 2, 4, 5, 10.
- Hard production boundaries: Sections 0, 4, 5 and Task 10.

Known follow-up requiring user authorization:

- Production deployment.
- Runtime scheduler activation in production.
- Any notification integration.
- Any promotion of late-session output into stronger production display or trading workflow.
