# Performance Next Round Final Development Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue optimizing frontend/backend production performance and online stability without changing strategy semantics or production ranking.

**Architecture:** This plan is measurement-first and split into independently verifiable batches. It improves observability and hot-read stability first, then reduces p95 for monitor/priority-board paths, then tightens frontend chunk budgets and performs a non-production 24M data-prep spike. All changes must be reversible and must preserve existing API contracts unless compatibility is explicitly maintained.

**Tech Stack:** FastAPI, SQLAlchemy, Redis/distributed cache helpers, Go BFF/market-read/scan-worker services, React, Vite, AntD, TanStack Query, Vitest, pytest, GitHub Actions, cloud deployment scripts.

---

## Current Baseline

Use the final online acceptance from `docs/reports/quote-cache-coverage-online-acceptance-2026-06-03.md` as the initial reference:

| Metric | Current Value |
| --- | ---: |
| quote cache coverage | `1051/1051 = 10000 bps` |
| Go market-read sample | `20/20`, missing `0`, `data_quality=fresh` |
| monitor_bff p95 | `34.103ms` |
| market_pulse p95 | `20.250ms` |
| priority_board p95 | `56.168ms` |
| watchlist_signals p95 | `22.227ms` |
| scan_worker_accept p95 | `270.605ms` |
| frontend max chunk | `126.46KB gzip` |
| frontend first_screen gzip | `319.95KB` |
| frontend total gzip | `797.06KB` |

Current warning signals:

- BFF partial timeout: `2`
- BFF partial status failure: `1`
- Go market-read unresolved misses: `9`
- Go market-read fallbacks: `3`
- First post-deploy acceptance had transient `scan_worker_accept` statuses `[202, 500]`; second run passed.

## Hard Boundaries

- Do not modify `strategy_policy`.
- Do not produce or wire `production_score`.
- Do not replace low-buy, priority board, front-row weighted, or any production ranking.
- Do not change strategy scoring formulas, stock selection rules, position rules, or backtest portfolio constraints.
- Do not add a Web background loop.
- Do not productionize whole-market parallel scan spike.
- Do not parallelize or reimplement `portfolio_backtest_metrics`.
- Do not calculate max5/max10 per month and merge them.
- Do not add framework-level dependencies.
- Do not allow live quote overlay to affect sorting or ranking fields.
- Missing data must be explicit: `stale`, `partial`, `no_data`, or `blocked`.
- Every optimization must be reversible, measurable, and attributable.

## Expected File Map

Backend and Go observability:

- Modify: `scripts/measure_cloud_go_rust_performance.py`
- Modify: `backend/app/api/routes/bff.py`
- Modify: `backend/app/services/bff/workspace_cache.py`
- Modify: `backend/app/services/performance/prometheus.py`
- Modify: `backend/app/services/performance/read_model_metrics.py`
- Modify: `go-services/bff-gateway/`
- Test: `backend/tests/test_cloud_performance_script.py`
- Test: `backend/tests/test_bff_routes.py`
- Test: Go tests under `go-services/bff-gateway/`

Market-read and quote cache:

- Modify: `backend/app/services/market_quote_cache_refresh.py`
- Modify: `backend/app/services/market/local_quote_cache.py`
- Modify: Go files under `go-services/market-read/`
- Test: `backend/tests/test_market_quote_cache_refresh.py`
- Test: `backend/tests/test_market_quote_cache_coverage.py`
- Test: Go tests under `go-services/market-read/`

Scan-worker:

- Modify: `scripts/measure_cloud_go_rust_performance.py`
- Modify: `go-services/scan-worker/cmd/scan-worker/main.go`
- Modify: `backend/app/api/routes/internal_scan_worker.py`
- Test: `backend/tests/test_cloud_performance_script.py`
- Test: `backend/tests/test_go_scan_worker_async.py`
- Test: `go-services/scan-worker/cmd/scan-worker/main_test.go`

Hot p95 and read model:

- Modify: `backend/app/api/routes/bff.py`
- Modify: `backend/app/api/routes/screeners.py`
- Modify: `backend/app/services/bff/workspace_cache.py`
- Modify: `backend/app/services/low_buy/priority_cache.py`
- Modify: `backend/app/services/read_models/`
- Modify: `backend/app/services/performance/`
- Test: `backend/tests/test_read_model_materialization.py`
- Test: `backend/tests/test_read_model_live_overlay.py`
- Test: `backend/tests/test_performance_regression.py`
- Test: `backend/tests/test_backend_compute_query_guards.py`

Frontend chunk:

- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/features/monitor/`
- Modify: `frontend/src/features/strategy-tracking/`
- Modify: `frontend/src/features/paper/`
- Modify: `frontend/src/ui/icons/index.ts`
- Modify: `frontend/scripts/check-bundle-budget.mjs`
- Test: `frontend/src/**/*.test.ts`
- Test: `frontend/src/**/*.test.tsx`

24M spike:

- Modify: `backend/scripts/backtest_24m_precompute_spike.py`
- Modify only if needed: `backend/scripts/strategy_24m_backtest_report.py`
- Modify only if needed: `backend/scripts/low_buy_market_backtest_reporting.py`
- Test: `backend/tests/test_backend_performance_spikes.py`

Reports:

- Create: `docs/reports/performance-next-round-baseline-2026-06-03.md`
- Create: `docs/reports/performance-next-round-acceptance-2026-06-03.md`

---

### Task 0: Working Tree Gate And Baseline Freeze

**Files:**
- Create: `docs/reports/performance-next-round-baseline-2026-06-03.md`
- Read: `AGENTS.md`
- Read: `docs/engineering-conventions.md`
- Read: `docs/reports/quote-cache-coverage-online-acceptance-2026-06-03.md`

- [ ] **Step 1: Confirm working tree before edits**

Run:

```bash
git status --short
```

Expected:

- If unrelated dirty files exist, record them and do not modify them.
- If files needed by this plan are dirty, inspect their diff before changing them.

- [ ] **Step 2: Read required project guidance**

Run:

```bash
sed -n '1,220p' AGENTS.md
sed -n '1,260p' docs/engineering-conventions.md
sed -n '1,220p' docs/reports/quote-cache-coverage-online-acceptance-2026-06-03.md
```

Expected:

- Confirm production ranking and strategy boundaries.
- Confirm previous quote cache online acceptance numbers.

- [ ] **Step 3: Run cloud baseline**

Run:

```bash
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
```

Expected:

- A JSON file under `docs/reports/gupiao-cloud-performance-*.json`.
- Do not treat a transient scan-worker failure as a code failure before checking the response body and container status.

- [ ] **Step 4: Write the baseline report**

Create `docs/reports/performance-next-round-baseline-2026-06-03.md` with this structure:

```markdown
# Performance Next Round Baseline

Generated at: 2026-06-03 Asia/Shanghai

## Source

- Command: `python3 scripts/measure_cloud_go_rust_performance.py --samples 8`
- JSON: `docs/reports/gupiao-cloud-performance-<timestamp>.json`

## Online Metrics

| Metric | Value |
| --- | ---: |
| quote cache coverage bps | <value> |
| quote cache requested/cached | <requested>/<cached> |
| Go market-read checked/returned/missing | <checked>/<returned>/<missing> |
| monitor_bff p95 | <value> |
| market_pulse p95 | <value> |
| priority_board p95 | <value> |
| watchlist_signals p95 | <value> |
| scan_worker_accept p95 | <value> |

## Warnings

- BFF partial timeout: <value>
- BFF partial status: <value>
- Go market-read unresolved misses: <value>
- Go market-read fallbacks: <value>

## Blocked Or No Data

- <state exact reason here>

## Production Boundary

- No strategy rule, production ranking, `strategy_policy`, or `production_score` change.
```

- [ ] **Step 5: Commit baseline report**

Run:

```bash
git add docs/reports/performance-next-round-baseline-2026-06-03.md
git commit -m "docs: record next performance baseline"
```

Expected:

- Commit succeeds.

---

### Task 1: BFF Partial Warning Attribution

**Files:**
- Modify: `backend/app/api/routes/bff.py`
- Modify: `backend/app/services/bff/workspace_cache.py`
- Modify: `backend/app/services/performance/prometheus.py`
- Modify: Go files under `go-services/bff-gateway/`
- Test: `backend/tests/test_bff_routes.py`
- Test: Go tests under `go-services/bff-gateway/`

- [ ] **Step 1: Add failing tests for source attribution**

Add or extend tests so partial errors include:

```python
def test_bff_partial_errors_include_source_reason_and_status(client, monkeypatch):
    response = client.get("/api/bff/v1/workspace/monitor?priority_limit=12&sector_limit=8&per_sector_limit=8&hedge_limit=4")
    body = response.json()
    partial_errors = body.get("partial_errors") or []
    for item in partial_errors:
        assert "source" in item
        assert "reason" in item
        assert "fallback_source" in item
        assert "status_code" in item or "timeout_ms" in item
```

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_bff_routes.py -q
```

Expected:

- New test fails before implementation if attribution fields are missing.

- [ ] **Step 2: Implement BFF partial attribution**

Add a normalized partial error shape:

```python
{
    "source": source_name,
    "reason": reason,
    "status_code": status_code,
    "timeout_ms": timeout_ms,
    "fallback_source": fallback_source,
    "message": message,
}
```

Rules:

- Preserve main payload even when one source is partial.
- Do not clear main data because of `partial_errors`.
- Keep previous fields for backward compatibility when existing clients expect them.

- [ ] **Step 3: Add metrics by source/reason**

Expose source/reason counters in `/metrics`, for example:

```text
tquant_bff_partial_source_failures_total{source="priority_board",reason="timeout"} 1
```

Keep cardinality bounded:

- `source` must be from a known finite set.
- `reason` must be one of `timeout`, `status`, `decode`, `schema_mismatch`, `other`.

- [ ] **Step 4: Run BFF tests**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_bff_routes.py backend/tests/test_performance_regression.py -q
```

Expected:

- Tests pass.
- Main payload remains non-empty on partial source failure.

- [ ] **Step 5: Commit BFF attribution**

Run:

```bash
git add backend/app/api/routes/bff.py backend/app/services/bff backend/app/services/performance backend/tests/test_bff_routes.py backend/tests/test_performance_regression.py go-services/bff-gateway
git commit -m "perf: attribute bff partial warnings"
```

---

### Task 2: Go Market-Read Fallback And Unresolved Diagnosis

**Files:**
- Modify: `backend/app/services/market_quote_cache_refresh.py`
- Modify: `backend/app/services/market/local_quote_cache.py`
- Modify: Go files under `go-services/market-read/`
- Test: `backend/tests/test_market_quote_cache_refresh.py`
- Test: `backend/tests/test_market_quote_cache_coverage.py`
- Test: Go tests under `go-services/market-read/`

- [ ] **Step 1: Add failing tests for unresolved reasons**

Add tests that assert unresolved symbols include a reason:

```python
def test_quote_cache_unresolved_reason_sample_is_bounded():
    # Build or call the helper that produces coverage diagnostics.
    diagnostics = {
        "unresolved_symbols_sample": [
            {"symbol": "999999", "reason": "invalid_symbol"}
        ]
    }
    assert diagnostics["unresolved_symbols_sample"][0]["reason"] in {
        "not_in_cache",
        "no_daily_bar",
        "invalid_symbol",
        "stale_only",
    }
```

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_quote_cache_refresh.py backend/tests/test_market_quote_cache_coverage.py -q
```

Expected:

- Fails until diagnostics exist.

- [ ] **Step 2: Implement unresolved reason diagnostics**

Return bounded samples:

```python
{
    "unresolved_symbols_sample": [
        {"symbol": symbol, "reason": reason}
    ]
}
```

Reason rules:

- `invalid_symbol`: symbol is not a 6-digit A-share/ETF symbol expected by current path.
- `not_in_cache`: Redis/local quote cache has no value.
- `no_daily_bar`: MySQL daily fallback has no latest daily bar.
- `stale_only`: only stale data exists and caller requested fresh-only behavior.

- [ ] **Step 3: Keep quote cache demand coverage hot set complete**

Ensure target set still includes:

- watchlist
- priority board
- paper holdings
- monitor sector members
- strategy tracking symbols

Do not add production ranking fields or modify priority board order.

- [ ] **Step 4: Run market-read tests**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_quote_cache_refresh.py backend/tests/test_market_quote_cache_coverage.py -q
cd go-services/market-read && go test ./...
```

Expected:

- Quote cache tests pass.
- Go market-read tests pass.

- [ ] **Step 5: Commit market-read diagnostics**

Run:

```bash
git add backend/app/services/market_quote_cache_refresh.py backend/app/services/market/local_quote_cache.py backend/tests/test_market_quote_cache_refresh.py backend/tests/test_market_quote_cache_coverage.py go-services/market-read
git commit -m "perf: diagnose market read unresolved symbols"
```

---

### Task 3: Scan-Worker Acceptance Stability

**Files:**
- Modify: `scripts/measure_cloud_go_rust_performance.py`
- Modify: `go-services/scan-worker/cmd/scan-worker/main.go`
- Modify: `backend/app/api/routes/internal_scan_worker.py`
- Test: `backend/tests/test_cloud_performance_script.py`
- Test: `backend/tests/test_go_scan_worker_async.py`
- Test: `go-services/scan-worker/cmd/scan-worker/main_test.go`

- [ ] **Step 1: Add tests for non-2xx body parsing**

Extend script guard tests:

```python
def test_cloud_measurement_scan_accept_reads_non_2xx_body():
    source = Path("scripts/measure_cloud_go_rust_performance.py").read_text(encoding="utf-8")
    assert "HTTPError" in source
    assert "exc.read()" in source
    assert "busy" in source or "duplicate" in source
```

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_cloud_performance_script.py -q
```

Expected:

- Fails until script captures non-2xx body.

- [ ] **Step 2: Normalize scan-worker statuses**

Use these accepted states:

```text
accepted
queued
busy
duplicate
fallback_available
failed
```

Only `failed` with real Python reference or scan-worker failure should count as a failure.

- [ ] **Step 3: Modify cloud measurement scan accept logic**

Rules:

- If HTTP status is 202 and body has `accepted=true`, record `202`.
- If body says `busy` or `duplicate`, record a non-fatal status such as `202` plus detail.
- If HTTP status is 500 but body says `busy` or `duplicate`, do not fail the whole report; record it under `scan_worker_accept.notes`.
- If body is missing or indicates real failure, record failure.

- [ ] **Step 4: Run scan-worker tests**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_cloud_performance_script.py backend/tests/test_go_scan_worker_async.py -q
cd go-services/scan-worker && go test ./...
```

Expected:

- Python and Go tests pass.

- [ ] **Step 5: Commit scan-worker stability**

Run:

```bash
git add scripts/measure_cloud_go_rust_performance.py backend/app/api/routes/internal_scan_worker.py backend/tests/test_cloud_performance_script.py backend/tests/test_go_scan_worker_async.py go-services/scan-worker
git commit -m "perf: stabilize scan worker acceptance checks"
```

---

### Task 4: Hot Endpoint P95 Optimization

**Files:**
- Modify: `backend/app/api/routes/bff.py`
- Modify: `backend/app/api/routes/screeners.py`
- Modify: `backend/app/services/bff/workspace_cache.py`
- Modify: `backend/app/services/low_buy/priority_cache.py`
- Modify: `backend/app/services/read_models/`
- Modify: `backend/app/services/performance/`
- Test: `backend/tests/test_read_model_materialization.py`
- Test: `backend/tests/test_read_model_live_overlay.py`
- Test: `backend/tests/test_performance_regression.py`
- Test: `backend/tests/test_backend_compute_query_guards.py`

- [ ] **Step 1: Add response metrics tests**

Assert hot routes expose:

- item count
- response bytes
- serialization ms
- read model hit/miss
- live overlay hit/miss

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_performance_regression.py backend/tests/test_read_model_materialization.py -q
```

Expected:

- Fails if route-level metrics are not recorded.

- [ ] **Step 2: Improve priority board cache hit path**

Rules:

- Use existing `priority-response-v1` semantics.
- Do not reorder items.
- Do not modify `score`, `priority_score`, `production_score`, `buy_signal_state`, or ranking fields.
- Live quote overlay may update only display quote fields.

- [ ] **Step 3: Improve monitor BFF read model hit path**

Rules:

- Preserve all API fields.
- Keep `partial_errors` explicit.
- Avoid rebuilding stable structure when cache hit is fresh.
- Keep live overlay separate from structure ordering.

- [ ] **Step 4: Run hot path tests**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_read_model_materialization.py \
  backend/tests/test_read_model_live_overlay.py \
  backend/tests/test_performance_regression.py \
  backend/tests/test_backend_compute_query_guards.py -q
```

Expected:

- Tests pass.
- Golden output remains consistent except explicitly allowed live quote fields.

- [ ] **Step 5: Commit hot p95 work**

Run:

```bash
git add backend/app/api/routes/bff.py backend/app/api/routes/screeners.py backend/app/services/bff backend/app/services/low_buy/priority_cache.py backend/app/services/read_models backend/app/services/performance backend/tests/test_read_model_materialization.py backend/tests/test_read_model_live_overlay.py backend/tests/test_performance_regression.py backend/tests/test_backend_compute_query_guards.py
git commit -m "perf: improve hot read model hit paths"
```

---

### Task 5: Frontend Chunk Second Pass

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/features/monitor/`
- Modify: `frontend/src/features/strategy-tracking/`
- Modify: `frontend/src/features/paper/`
- Modify: `frontend/src/ui/icons/index.ts`
- Modify: `frontend/scripts/check-bundle-budget.mjs`
- Test: frontend tests as needed

- [ ] **Step 1: Capture frontend baseline**

Run:

```bash
cd frontend && npm run analyze
```

Record:

- max chunk gzip
- first_screen gzip
- total gzip
- top chunks

- [ ] **Step 2: Prevent icon bucket regressions**

Run:

```bash
cd frontend && rg '@ant-design/icons"' src
```

Expected:

- No direct bucket imports.
- Icons should come from `frontend/src/ui/icons/index.ts`.

- [ ] **Step 3: Split or lazy-load the largest chunk**

Rules:

- Target max chunk `<110KB gzip`.
- first_screen must remain `<330KB gzip`.
- total gzip must not increase more than `5KB`.
- Do not add npm dependencies.
- Do not wrap every small component; only lazy-load genuinely heavy page-level panels.

- [ ] **Step 4: Run frontend validation**

Run:

```bash
cd frontend
npm run api:check
npm run lint
npm test -- --run
npm run build
npm run analyze
npm run check:bundle-budget
```

Expected:

- All commands pass.
- Bundle targets pass.

- [ ] **Step 5: Commit frontend chunk work**

Run:

```bash
git add frontend/vite.config.ts frontend/src frontend/scripts frontend/package.json frontend/package-lock.json
git commit -m "perf: reduce frontend heavy chunks"
```

---

### Task 6: 24M Real Data Prep Spike

**Files:**
- Modify: `backend/scripts/backtest_24m_precompute_spike.py`
- Modify only if needed: `backend/scripts/strategy_24m_backtest_report.py`
- Modify only if needed: `backend/scripts/low_buy_market_backtest_reporting.py`
- Test: `backend/tests/test_backend_performance_spikes.py`
- Report: include results in `docs/reports/performance-next-round-acceptance-2026-06-03.md`

- [ ] **Step 1: Add golden test for 24M prep parity**

The test must assert:

- PF equal
- average trade return equal
- max5 equal
- max10 equal
- max drawdown equal
- trade_count equal

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_backend_performance_spikes.py -q
```

Expected:

- Fails until real prep spike output has parity fields.

- [ ] **Step 2: Optimize only data preparation**

Allowed:

- batch reads
- payload normalization
- `TradeOutcome` construction
- duplicate input caching

Forbidden:

- changing `portfolio_backtest_metrics`
- month/date partitioned max5/max10 aggregation
- modifying portfolio constraints

- [ ] **Step 3: Run 24M spike**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backtest_24m_precompute_spike.py --count 240
```

Expected:

- Golden metrics equal.
- If real data prep wall-clock drop is `<20%`, do not recommend productionization.

- [ ] **Step 4: Commit 24M spike**

Run:

```bash
git add backend/scripts/backtest_24m_precompute_spike.py backend/scripts/strategy_24m_backtest_report.py backend/scripts/low_buy_market_backtest_reporting.py backend/tests/test_backend_performance_spikes.py
git commit -m "perf: assess 24m data prep acceleration"
```

---

### Task 7: Final Local Validation

**Files:**
- Create: `docs/reports/performance-next-round-acceptance-2026-06-03.md`

- [ ] **Step 1: Run backend full suite**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
```

Expected:

- Full backend suite passes.

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

- All frontend commands pass.

- [ ] **Step 3: Run diff checks**

Run:

```bash
git diff --check
git status --short
```

Expected:

- `git diff --check` passes.
- `git status --short` contains only intentional changes.

- [ ] **Step 4: Commit final local report shell**

Create `docs/reports/performance-next-round-acceptance-2026-06-03.md` with sections:

```markdown
# Performance Next Round Acceptance

## Baseline

## Changes

## Local Validation

## Deployment

## Online Acceptance

## Metric Deltas

## 24M Spike

## Risks And Follow-ups

## Production Ranking Impact
```

Run:

```bash
git add docs/reports/performance-next-round-acceptance-2026-06-03.md
git commit -m "docs: prepare next performance acceptance report"
```

---

### Task 8: Deploy And Online Acceptance

**Files:**
- Update: `docs/reports/performance-next-round-acceptance-2026-06-03.md`

- [ ] **Step 1: Push to main**

Run:

```bash
git push origin HEAD:main
```

Expected:

- GitHub Actions starts on `main`.

- [ ] **Step 2: Monitor CI and deploy**

Run:

```bash
gh run list --branch main --limit 5 --json databaseId,headSha,status,conclusion,name,createdAt,url
```

Then for the new run:

```bash
gh run view <run-id> --json status,conclusion,jobs,url,headSha
```

Expected:

- `backend`: success
- `frontend`: success
- `go-rust`: success
- `deploy`: success

- [ ] **Step 3: Run two online acceptance passes**

Run:

```bash
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
```

Expected:

- Both reports are `ok=true`, or every failure is explicitly diagnosed with blocker status.

- [ ] **Step 4: Update final acceptance report**

Update `docs/reports/performance-next-round-acceptance-2026-06-03.md` with:

- baseline metrics
- final metrics
- percentage deltas
- quote cache coverage
- Go market-read fallback/unresolved
- BFF partial warning source breakdown
- scan_worker_accept stability
- frontend bundle comparison
- 24M spike result
- unresolved risks
- rollback path
- production ranking impact

- [ ] **Step 5: Commit and push final report**

Run:

```bash
git add docs/reports/performance-next-round-acceptance-2026-06-03.md
git commit -m "docs: record next performance acceptance"
git push origin HEAD:main
```

Expected:

- Final report is committed.
- If this docs-only push triggers CI/deploy, monitor it to success.

---

## Success Criteria

- quote cache coverage remains `10000 bps`.
- Go market-read sample missing remains `0`.
- `scan_worker_accept` has no real failure status across two online acceptance passes.
- `priority_board` p95 is `<40ms`.
- `monitor_bff` p95 is `<30ms`.
- frontend max chunk is `<110KB gzip`.
- Backend and frontend test suites pass.
- GitHub Actions deploy job succeeds.
- Final report explicitly states no production ranking impact.

## Rollback Plan

- Disable live overlay: `READ_MODEL_LIVE_OVERLAY_ENABLED=false`.
- Disable response payload metrics: `RESPONSE_PAYLOAD_METRICS_ENABLED=false`.
- Disable Rust finance path: `rust_finance_math_enabled=false`.
- Revert quote cache refresh changes if coverage or freshness regresses.
- Revert `frontend/vite.config.ts` if chunk split causes runtime issue.
- Use cloud release backup or revert the latest commit and push `main` if deployment regresses.

## Self-Review

- Spec coverage: P0-P7 requirements are represented as Tasks 0-8.
- Placeholder scan: no `TODO`, `TBD`, or unspecified implementation-only steps remain.
- Type consistency: status names and metric names are fixed in this plan and should be reused in implementation.
