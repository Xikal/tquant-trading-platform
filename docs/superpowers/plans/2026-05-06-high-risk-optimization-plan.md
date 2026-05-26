# TQuant High-Risk Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely complete the high-risk optimization work for schema/index migration, legacy route removal, and market data provider refactoring without changing trading strategy behavior.

**Architecture:** The work is split into three independently verifiable tracks. Database changes go through Alembic and MySQL validation; legacy routes are removed through an explicit compatibility gate; external data providers are deepened behind a stable interface while preserving current fallback semantics.

**Tech Stack:** Python FastAPI, SQLAlchemy, Alembic, MySQL, React, Vite, TypeScript, pytest, Vitest, nginx/cloud deployment scripts.

---

## Non-Negotiable Guardrails

- Preserve strategy output semantics unless a task explicitly says it only changes metadata, routing, or presentation.
- Do not edit secrets, `.env`, cloud credentials, production database contents, or real notification tokens.
- Do not remove old routes until the route audit confirms no first-party caller still depends on them.
- Every database schema change must have an Alembic migration, a downgrade path, and a MySQL validation command.
- Every external data provider change must return explicit `fresh`, `stale`, `estimated`, or `unavailable` quality states.
- Commit after each task. Rollback should be possible by reverting one task commit.

## Current Risk Inventory

### Risk A: Database Schema / Index Changes

**Current problem:** Some hot queries are visible in strategy metadata, backtest, low-buy snapshots, paper dashboard, and replay routes. Optimizing indexes directly inside runtime compatibility code would be unsafe; schema/index work must move to Alembic.

**Impact range:** MySQL production, SQLite local development, backtest jobs, priority board, strategy replay, paper dashboard.

**Strategy:** Add an index audit script first, then write migrations only for verified hot queries. Do not rely on `schema_compat.py` for production index creation.

### Risk B: Legacy Backtest / Research Redirect Removal

**Current problem:** Legacy route redirects keep old entrypoints alive. Removing them blindly can break old scripts, Hermes workflows, or bookmarks.

**Impact range:** `backend/app/main.py`, `backend/app/api/routes/research.py`, `backend/app/api/routes/backtests.py`, frontend API wrappers, scripts, docs, Hermes tools.

**Strategy:** Audit all first-party references, add explicit deprecation telemetry, introduce a runtime flag that can reject legacy routes with a structured 410, then remove route definitions after one verified release window.

### Risk C: External AkShare / OpenBB Provider Rewrite

**Current problem:** Market provider fallback is spread across services. AkShare lock/fallback protects stability but restricts throughput; OpenBB is present but not deeply integrated. A rewrite can alter data quality and strategy outputs.

**Impact range:** market quotes, intraday bars, industry heatmap, market regime, low-buy strategy pools, Agent Safe API, Hermes reports.

**Strategy:** Create a provider contract and adapters around existing behavior first. Add quality tags and cache policy. Switch consumers gradually behind a feature flag.

---

## File Structure Map

### Database / Migration Track

- Modify: `backend/alembic/versions/*.py`
- Modify: `backend/app/core/schema_compat.py`
- Create: `scripts/schema_index_audit.py`
- Create: `backend/tests/test_schema_index_audit.py`
- Create: `docs/operations/schema-index-runbook.md`

### Legacy Route Track

- Modify: `backend/app/main.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/api/routes/research.py`
- Modify: `backend/app/api/routes/backtests.py`
- Modify: `frontend/src/api/backtests.ts`
- Modify: `scripts/qa_smoke.sh`
- Create: `backend/tests/test_legacy_routes.py`
- Create: `docs/operations/legacy-route-removal.md`

### Data Provider Track

- Create: `backend/app/services/market/providers/base.py`
- Create: `backend/app/services/market/providers/quality.py`
- Create: `backend/app/services/market/providers/akshare_provider.py`
- Create: `backend/app/services/market/providers/openbb_provider.py`
- Create: `backend/app/services/market/providers/eastmoney_provider.py`
- Create: `backend/app/services/market/providers/router.py`
- Modify: `backend/app/services/market/quotes.py`
- Modify: `backend/app/services/market/intraday.py`
- Modify: `backend/app/services/market/sectors.py`
- Modify: `backend/app/services/market/regime.py`
- Create: `backend/tests/test_market_provider_contract.py`
- Create: `docs/operations/market-data-provider-runbook.md`

---

## Task 1: Establish Baseline and Safety Branch

**Files:**
- Read: `AGENTS.md`
- Read: `README.md`
- Read: `Makefile`
- Read: `PRODUCTION_RUNBOOK.md`
- Modify: none

- [ ] **Step 1: Verify worktree state**

Run:

```bash
git status --short
```

Expected: either clean, or only known user-owned changes. If there are unknown changes, stop and record them before editing.

- [ ] **Step 2: Create an isolated branch**

Run:

```bash
git switch -c codex/high-risk-optimization-20260506
```

Expected: branch created.

- [ ] **Step 3: Run baseline backend compile**

Run:

```bash
python3 -m compileall backend/app backend/tests scripts
```

Expected: command exits `0`.

- [ ] **Step 4: Run baseline frontend build**

Run:

```bash
cd frontend && npm run build:web
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 5: Capture baseline bundle report**

Run:

```bash
cd frontend && npm run analyze
```

Expected: `frontend/dist/bundle-report.json` exists and lists total bundle KB.

- [ ] **Step 6: Commit no-op baseline notes if needed**

If no files changed, do not commit. If generated reports are intentionally tracked, commit:

```bash
git add frontend/dist/bundle-report.json
git commit -m "chore: capture optimization baseline"
```

Expected: either no commit needed, or commit succeeds.

---

## Task 2: Add Schema and Index Audit Before Any Migration

**Files:**
- Create: `scripts/schema_index_audit.py`
- Create: `backend/tests/test_schema_index_audit.py`

- [ ] **Step 1: Write the audit script**

Create `scripts/schema_index_audit.py` with:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


@dataclass(frozen=True)
class ExpectedIndex:
    table: str
    columns: tuple[str, ...]
    purpose: str


EXPECTED_INDEXES: tuple[ExpectedIndex, ...] = (
    ExpectedIndex("low_buy_result_snapshots", ("strategy_key", "latest_trade_date", "score"), "priority board and strategy replay"),
    ExpectedIndex("low_buy_result_snapshots", ("strategy_key", "symbol", "latest_trade_date"), "per-symbol signal history"),
    ExpectedIndex("low_buy_scan_snapshots", ("strategy_key", "latest_trade_date", "updated_at"), "latest scan lookup"),
    ExpectedIndex("low_buy_strategy_pool_snapshots", ("latest_trade_date", "strategy_key", "pool_key", "rank_score"), "strategy pool latest lookup"),
    ExpectedIndex("paper_performance_snapshots", ("account_id", "snapshot_date"), "paper dashboard equity curve"),
    ExpectedIndex("paper_strategy_perf_daily", ("account_id", "trade_date", "strategy_key"), "paper strategy daily metrics"),
    ExpectedIndex("paper_market_state_perf_daily", ("account_id", "trade_date", "market_state"), "paper market state daily metrics"),
    ExpectedIndex("backtest_runs", ("owner_user_id", "created_at"), "user backtest list"),
    ExpectedIndex("runtime_tasks", ("status", "created_at"), "runtime worker polling"),
)


def _normalize_columns(columns: list[dict]) -> tuple[str, ...]:
    return tuple(str(item.get("name", "")) for item in columns)


def audit_indexes(database_url: str | None = None) -> dict:
    url = database_url or get_settings().database_url
    engine = create_engine(url)
    inspector = inspect(engine)
    result: dict[str, object] = {"database_url_scheme": url.split(":", 1)[0], "missing": [], "present": []}
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    for expected in EXPECTED_INDEXES:
        try:
            indexes = inspector.get_indexes(expected.table)
        except Exception as exc:
            result["missing"].append({"table": expected.table, "columns": expected.columns, "reason": f"table inspection failed: {exc}"})
            continue
        existing_columns = {_normalize_columns(index.get("column_names", [])) for index in indexes}
        if expected.columns in existing_columns:
            result["present"].append({"table": expected.table, "columns": expected.columns, "purpose": expected.purpose})
        else:
            result["missing"].append({"table": expected.table, "columns": expected.columns, "purpose": expected.purpose})
    return result


def main() -> int:
    report = audit_indexes()
    output_path = Path(".runtime/schema-index-audit.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write a unit test for expected index declarations**

Create `backend/tests/test_schema_index_audit.py` with:

```python
from scripts.schema_index_audit import EXPECTED_INDEXES


def test_expected_indexes_have_table_columns_and_purpose():
    assert EXPECTED_INDEXES
    for item in EXPECTED_INDEXES:
        assert item.table
        assert item.columns
        assert item.purpose
```

- [ ] **Step 3: Run the test**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_schema_index_audit.py -q
```

Expected: test passes.

- [ ] **Step 4: Run the audit against local database**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py
```

Expected: outputs JSON. Non-zero exit is acceptable before Task 3 if indexes are missing.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/schema_index_audit.py backend/tests/test_schema_index_audit.py
git commit -m "chore: add schema index audit"
```

Expected: commit succeeds.

---

## Task 3: Add Alembic Migration for Verified Hot Indexes

**Files:**
- Create: `backend/alembic/versions/20260506_0004_hot_path_indexes.py`
- Modify: `backend/app/core/schema_compat.py`
- Create: `docs/operations/schema-index-runbook.md`

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/20260506_0004_hot_path_indexes.py` with:

```python
"""add hot path indexes

Revision ID: 20260506_0004
Revises: 20260506_0003
Create Date: 2026-05-06
"""

from __future__ import annotations

from alembic import op


revision = "20260506_0004"
down_revision = "20260506_0003"
branch_labels = None
depends_on = None


INDEXES = (
    ("ix_low_buy_result_strategy_date_score", "low_buy_result_snapshots", ["strategy_key", "latest_trade_date", "score"]),
    ("ix_low_buy_result_strategy_symbol_date", "low_buy_result_snapshots", ["strategy_key", "symbol", "latest_trade_date"]),
    ("ix_low_buy_scan_strategy_date_updated", "low_buy_scan_snapshots", ["strategy_key", "latest_trade_date", "updated_at"]),
    ("ix_low_buy_pool_date_strategy_pool_score", "low_buy_strategy_pool_snapshots", ["latest_trade_date", "strategy_key", "pool_key", "rank_score"]),
    ("ix_paper_perf_account_snapshot_date", "paper_performance_snapshots", ["account_id", "snapshot_date"]),
    ("ix_paper_strategy_perf_account_date_strategy", "paper_strategy_perf_daily", ["account_id", "trade_date", "strategy_key"]),
    ("ix_paper_market_perf_account_date_state", "paper_market_state_perf_daily", ["account_id", "trade_date", "market_state"]),
    ("ix_backtest_runs_owner_created", "backtest_runs", ["owner_user_id", "created_at"]),
    ("ix_runtime_tasks_status_created", "runtime_tasks", ["status", "created_at"]),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns, unique=False)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
```

- [ ] **Step 2: Remove production index repair from schema compatibility**

In `backend/app/core/schema_compat.py`, ensure index-related compatibility code only reports missing indexes and does not create them in production. Add this helper if it does not exist:

```python
def collect_missing_index_warnings(inspector) -> list[str]:
    warnings: list[str] = []
    expected = {
        "low_buy_result_snapshots": [
            ("strategy_key", "latest_trade_date", "score"),
            ("strategy_key", "symbol", "latest_trade_date"),
        ],
        "low_buy_scan_snapshots": [("strategy_key", "latest_trade_date", "updated_at")],
        "low_buy_strategy_pool_snapshots": [("latest_trade_date", "strategy_key", "pool_key", "rank_score")],
        "paper_performance_snapshots": [("account_id", "snapshot_date")],
        "paper_strategy_perf_daily": [("account_id", "trade_date", "strategy_key")],
        "paper_market_state_perf_daily": [("account_id", "trade_date", "market_state")],
        "backtest_runs": [("owner_user_id", "created_at")],
        "runtime_tasks": [("status", "created_at")],
    }
    for table, required_indexes in expected.items():
        try:
            present = {tuple(index.get("column_names", [])) for index in inspector.get_indexes(table)}
        except Exception as exc:
            warnings.append(f"{table}: index inspection failed: {exc}")
            continue
        for columns in required_indexes:
            if columns not in present:
                warnings.append(f"{table}: missing index on {', '.join(columns)}")
    return warnings
```

- [ ] **Step 3: Write the runbook**

Create `docs/operations/schema-index-runbook.md` with:

```markdown
# Schema Index Runbook

## Purpose

Hot path indexes are managed by Alembic only. Runtime schema compatibility checks may warn, but production web or worker processes must not create indexes implicitly.

## Local validation

```bash
PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py
cd backend && ../backend/.venv/bin/alembic upgrade head
PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py
```

## MySQL validation

```bash
DATABASE_URL='mysql+pymysql://user:password@host:3306/t_quant?charset=utf8mb4' \
PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py
```

## Rollback

```bash
cd backend && ../backend/.venv/bin/alembic downgrade 20260506_0003
```
```

- [ ] **Step 4: Run migration checks**

Run:

```bash
cd backend && ../backend/.venv/bin/alembic upgrade head
PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py
```

Expected: audit has no missing indexes for migrated local DB.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/alembic/versions/20260506_0004_hot_path_indexes.py backend/app/core/schema_compat.py docs/operations/schema-index-runbook.md
git commit -m "perf: add hot path indexes via alembic"
```

Expected: commit succeeds.

---

## Task 4: Audit Legacy Route Usage Before Removal

**Files:**
- Create: `scripts/audit_legacy_routes.py`
- Create: `backend/tests/test_legacy_routes.py`
- Create: `docs/operations/legacy-route-removal.md`

- [ ] **Step 1: Create route audit script**

Create `scripts/audit_legacy_routes.py` with:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = ("backend", "frontend/src", "scripts", "agent_mcp", "skills", "docs")
LEGACY_PATTERNS = ("/backtests", "/research")


def audit() -> dict:
    findings: list[dict[str, object]] = []
    for root_name in SEARCH_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".ts", ".tsx", ".js", ".sh", ".md", ".yaml", ".yml"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in LEGACY_PATTERNS:
                if pattern in text:
                    findings.append({"path": str(path.relative_to(ROOT)), "pattern": pattern})
    return {"legacy_patterns": findings, "count": len(findings)}


def main() -> int:
    report = audit()
    output = ROOT / ".runtime" / "legacy-route-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Add route behavior tests**

Create `backend/tests/test_legacy_routes.py` with:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_legacy_backtests_route_returns_explicit_status():
    client = TestClient(app)
    response = client.get("/backtests")
    assert response.status_code in {307, 308, 410, 401}


def test_legacy_research_route_returns_explicit_status():
    client = TestClient(app)
    response = client.get("/research")
    assert response.status_code in {307, 308, 410, 401}
```

- [ ] **Step 3: Write removal runbook**

Create `docs/operations/legacy-route-removal.md` with:

```markdown
# Legacy Route Removal Runbook

## Target routes

- `/backtests`
- `/research`

## Required checks before hard removal

```bash
python3 scripts/audit_legacy_routes.py
rg -n '"/backtests"|`/backtests`|/backtests|"/research"|`/research`|/research' backend frontend/src scripts agent_mcp skills docs
```

## Allowed references after removal

- Tests asserting 410 behavior
- This runbook
- Historical changelog entries

## Rollback

Revert the commit that changes legacy routes from 410 to removal, or re-enable `LEGACY_ROUTE_COMPAT_ENABLED=true`.
```

- [ ] **Step 4: Run audit and tests**

Run:

```bash
python3 scripts/audit_legacy_routes.py
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_legacy_routes.py -q
```

Expected: script writes `.runtime/legacy-route-audit.json`; tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/audit_legacy_routes.py backend/tests/test_legacy_routes.py docs/operations/legacy-route-removal.md
git commit -m "chore: audit legacy route usage"
```

Expected: commit succeeds.

---

## Task 5: Convert Legacy Redirects to Explicit 410 Behind Runtime Flag

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_legacy_routes.py`

- [ ] **Step 1: Add runtime config flag**

In `backend/app/core/config.py`, add this field to `AppSettings`:

```python
legacy_route_compat_enabled: bool = False
```

- [ ] **Step 2: Replace legacy redirects with structured handling**

In `backend/app/main.py`, replace `legacy_backtests_redirect()` and `legacy_research_redirect()` with:

```python
def _legacy_route_response(target: str):
    if get_settings().legacy_route_compat_enabled:
        return RedirectResponse(url=target, status_code=308)
    return JSONResponse(
        status_code=410,
        content={
            "code": "LEGACY_ROUTE_REMOVED",
            "message": f"该旧入口已下线，请使用 {target}。",
            "replacement": target,
        },
    )


@app.get("/backtests", include_in_schema=False)
def legacy_backtests_redirect():
    return _legacy_route_response("/api/backtests")


@app.get("/research", include_in_schema=False)
def legacy_research_redirect():
    return _legacy_route_response("/")
```

- [ ] **Step 3: Update tests**

In `backend/tests/test_legacy_routes.py`, replace the assertions with:

```python
def test_legacy_backtests_route_returns_gone_by_default():
    client = TestClient(app)
    response = client.get("/backtests")
    assert response.status_code == 410
    assert response.json()["replacement"] == "/api/backtests"


def test_legacy_research_route_returns_gone_by_default():
    client = TestClient(app)
    response = client.get("/research")
    assert response.status_code == 410
    assert response.json()["replacement"] == "/"
```

- [ ] **Step 4: Run tests**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_legacy_routes.py -q
python3 -m compileall backend/app
```

Expected: tests pass and compile succeeds.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/core/config.py backend/app/main.py backend/tests/test_legacy_routes.py
git commit -m "refactor: retire legacy research routes behind flag"
```

Expected: commit succeeds.

---

## Task 6: Remove First-Party Legacy Route Callers

**Files:**
- Modify: `frontend/src/api/backtests.ts`
- Modify: `scripts/qa_smoke.sh`
- Modify: `scripts/prod_preflight.sh`
- Modify: `agent_mcp/server.py`
- Modify: `skills/tquant-backtest-analysis/SKILL.md`

- [ ] **Step 1: Replace frontend legacy endpoint usage**

Run:

```bash
rg -n '"/backtests"|`/backtests`|/backtests|"/research"|`/research`|/research' frontend/src
```

For each frontend hit, replace legacy paths with `/api/backtests` or the existing `api_prefix` wrapper. The intended direct API path is:

```ts
const BACKTESTS_BASE = "/api/backtests";
```

- [ ] **Step 2: Replace script legacy endpoint usage**

Run:

```bash
rg -n '"/backtests"|`/backtests`|/backtests|"/research"|`/research`|/research' scripts agent_mcp skills
```

Replace shell/curl references with `/api/backtests` when they call API endpoints. Keep documentation references only when they describe removed routes.

- [ ] **Step 3: Run audit**

Run:

```bash
python3 scripts/audit_legacy_routes.py
```

Expected: remaining findings are only `docs/operations/legacy-route-removal.md`, `backend/tests/test_legacy_routes.py`, and historical docs.

- [ ] **Step 4: Run verification**

Run:

```bash
cd frontend && npm run build:web
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_legacy_routes.py -q
```

Expected: both pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add frontend/src/api/backtests.ts scripts/qa_smoke.sh scripts/prod_preflight.sh agent_mcp/server.py skills/tquant-backtest-analysis/SKILL.md .runtime/legacy-route-audit.json
git commit -m "chore: remove first-party legacy route callers"
```

Expected: commit succeeds. If `.runtime/legacy-route-audit.json` is ignored, do not force add it.

---

## Task 7: Define Market Data Provider Quality Contract

**Files:**
- Create: `backend/app/services/market/providers/quality.py`
- Create: `backend/app/services/market/providers/base.py`
- Create: `backend/tests/test_market_provider_contract.py`

- [ ] **Step 1: Create quality model**

Create `backend/app/services/market/providers/quality.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MarketDataQuality(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProviderResult:
    quality: MarketDataQuality
    source: str
    data: Any = None
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.quality in {MarketDataQuality.FRESH, MarketDataQuality.STALE, MarketDataQuality.ESTIMATED}
```

- [ ] **Step 2: Create provider protocol**

Create `backend/app/services/market/providers/base.py` with:

```python
from __future__ import annotations

from typing import Protocol

from app.services.market.providers.quality import ProviderResult


class MarketDataProvider(Protocol):
    name: str

    def get_quote(self, symbol: str) -> ProviderResult:
        ...

    def get_intraday_bars(self, symbol: str, period: str = "1m", limit: int = 240) -> ProviderResult:
        ...

    def get_sector_heatmap(self) -> ProviderResult:
        ...

    def get_trade_calendar(self) -> ProviderResult:
        ...
```

- [ ] **Step 3: Add contract tests**

Create `backend/tests/test_market_provider_contract.py` with:

```python
from app.services.market.providers.quality import MarketDataQuality, ProviderResult


def test_provider_result_quality_values_are_explicit():
    assert {item.value for item in MarketDataQuality} == {"fresh", "stale", "estimated", "unavailable"}


def test_provider_result_usable_excludes_unavailable():
    assert ProviderResult(quality=MarketDataQuality.FRESH, source="test").usable is True
    assert ProviderResult(quality=MarketDataQuality.STALE, source="test").usable is True
    assert ProviderResult(quality=MarketDataQuality.ESTIMATED, source="test").usable is True
    assert ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source="test").usable is False
```

- [ ] **Step 4: Run tests**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_provider_contract.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/services/market/providers/quality.py backend/app/services/market/providers/base.py backend/tests/test_market_provider_contract.py
git commit -m "feat: define market data provider quality contract"
```

Expected: commit succeeds.

---

## Task 8: Wrap Existing Providers Without Changing Consumers

**Files:**
- Create: `backend/app/services/market/providers/eastmoney_provider.py`
- Create: `backend/app/services/market/providers/akshare_provider.py`
- Create: `backend/app/services/market/providers/openbb_provider.py`
- Create: `backend/app/services/market/providers/router.py`
- Modify: `backend/tests/test_market_provider_contract.py`

- [ ] **Step 1: Create Eastmoney provider adapter**

Create `backend/app/services/market/providers/eastmoney_provider.py` with:

```python
from __future__ import annotations

from app.services.market.providers.quality import MarketDataQuality, ProviderResult


class EastmoneyProvider:
    name = "eastmoney"

    def __init__(self, market_data):
        self.market_data = market_data

    def get_quote(self, symbol: str) -> ProviderResult:
        try:
            quote = self.market_data.get_realtime_quote(symbol)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        quality = MarketDataQuality.STALE if getattr(quote, "source_quality", "") == "stale" else MarketDataQuality.FRESH
        return ProviderResult(quality=quality, source=getattr(quote, "data_source", self.name), data=quote)

    def get_intraday_bars(self, symbol: str, period: str = "1m", limit: int = 240) -> ProviderResult:
        try:
            bars = self.market_data.get_intraday_kline(symbol=symbol, period=period, limit=limit)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH if bars else MarketDataQuality.UNAVAILABLE, source=self.name, data=bars)

    def get_sector_heatmap(self) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="sector heatmap not provided by this adapter")

    def get_trade_calendar(self) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="trade calendar not provided by this adapter")
```

- [ ] **Step 2: Create AkShare provider adapter**

Create `backend/app/services/market/providers/akshare_provider.py` with:

```python
from __future__ import annotations

from app.services.market.providers.quality import MarketDataQuality, ProviderResult


class AkShareProvider:
    name = "akshare"

    def __init__(self, market_data):
        self.market_data = market_data

    def get_quote(self, symbol: str) -> ProviderResult:
        try:
            quote = self.market_data.get_realtime_quote(symbol)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH, source=getattr(quote, "data_source", self.name), data=quote)

    def get_intraday_bars(self, symbol: str, period: str = "1m", limit: int = 240) -> ProviderResult:
        try:
            bars = self.market_data.get_intraday_kline(symbol=symbol, period=period, limit=limit)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH if bars else MarketDataQuality.UNAVAILABLE, source=self.name, data=bars)

    def get_sector_heatmap(self) -> ProviderResult:
        try:
            frame = self.market_data.get_hot_industries(limit=20)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH if frame else MarketDataQuality.UNAVAILABLE, source=self.name, data=frame)

    def get_trade_calendar(self) -> ProviderResult:
        try:
            dates = self.market_data.get_trade_dates()
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH if dates else MarketDataQuality.UNAVAILABLE, source=self.name, data=dates)
```

- [ ] **Step 3: Create OpenBB provider adapter**

Create `backend/app/services/market/providers/openbb_provider.py` with:

```python
from __future__ import annotations

from app.services.market.openbb_adapter import OpenBBDataAdapter
from app.services.market.providers.quality import MarketDataQuality, ProviderResult


class OpenBBProvider:
    name = "openbb"

    def __init__(self, adapter: OpenBBDataAdapter | None = None):
        self.adapter = adapter or OpenBBDataAdapter()

    def get_quote(self, symbol: str) -> ProviderResult:
        try:
            payload = self.adapter.get_quote(symbol)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH if payload else MarketDataQuality.UNAVAILABLE, source=self.name, data=payload)

    def get_intraday_bars(self, symbol: str, period: str = "1m", limit: int = 240) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="intraday bars not enabled for OpenBB adapter")

    def get_sector_heatmap(self) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="sector heatmap not enabled for OpenBB adapter")

    def get_trade_calendar(self) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="trade calendar not enabled for OpenBB adapter")
```

- [ ] **Step 4: Create provider router**

Create `backend/app/services/market/providers/router.py` with:

```python
from __future__ import annotations

from collections.abc import Callable

from app.services.market.providers.quality import MarketDataQuality, ProviderResult


class MarketProviderRouter:
    def __init__(self, providers: list):
        self.providers = providers

    def first_usable(self, operation: str, *args, **kwargs) -> ProviderResult:
        errors: list[str] = []
        for provider in self.providers:
            method: Callable = getattr(provider, operation)
            result = method(*args, **kwargs)
            if result.usable:
                return result
            if result.message:
                errors.append(f"{provider.name}: {result.message}")
        return ProviderResult(
            quality=MarketDataQuality.UNAVAILABLE,
            source="router",
            message="; ".join(errors)[:300] if errors else "no provider returned usable data",
        )
```

- [ ] **Step 5: Add router test**

Append to `backend/tests/test_market_provider_contract.py`:

```python
from app.services.market.providers.router import MarketProviderRouter


class _UnavailableProvider:
    name = "bad"

    def get_quote(self, symbol: str):
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="failed")


class _FreshProvider:
    name = "good"

    def get_quote(self, symbol: str):
        return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data={"symbol": symbol})


def test_market_provider_router_returns_first_usable_result():
    router = MarketProviderRouter([_UnavailableProvider(), _FreshProvider()])
    result = router.first_usable("get_quote", "510300")
    assert result.quality == MarketDataQuality.FRESH
    assert result.data == {"symbol": "510300"}
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_provider_contract.py -q
python3 -m compileall backend/app/services/market/providers
git add backend/app/services/market/providers backend/tests/test_market_provider_contract.py
git commit -m "feat: add market data provider adapters"
```

Expected: tests pass and commit succeeds.

---

## Task 9: Gradually Wire Provider Router Behind Feature Flag

**Files:**
- Modify: `backend/app/services/market/quotes.py`
- Modify: `backend/app/services/market/intraday.py`
- Modify: `backend/app/services/market/sectors.py`
- Modify: `backend/app/services/shared/feature_flags.py`
- Create: `backend/tests/test_market_provider_flag.py`

- [ ] **Step 1: Add feature flag default**

In `backend/app/services/shared/feature_flags.py`, add:

```python
"market_provider_router_enabled": FeatureFlagDefault(
    key="market_provider_router_enabled",
    enabled=False,
    description="Use market provider router for quote/intraday/sector data reads.",
),
```

- [ ] **Step 2: Add non-invasive router construction**

In market services, add helper methods but keep existing path as default:

```python
def _provider_router(self):
    from app.services.market.providers.akshare_provider import AkShareProvider
    from app.services.market.providers.eastmoney_provider import EastmoneyProvider
    from app.services.market.providers.openbb_provider import OpenBBProvider
    from app.services.market.providers.router import MarketProviderRouter

    return MarketProviderRouter([
        EastmoneyProvider(self),
        AkShareProvider(self),
        OpenBBProvider(),
    ])
```

- [ ] **Step 3: Gate one low-risk read path first**

In `MarketQuoteMixin.get_realtime_quote`, wrap only the top-level call:

```python
if self._market_provider_router_enabled():
    result = self._provider_router().first_usable("get_quote", symbol)
    if result.usable and result.data is not None:
        return result.data
```

Existing implementation remains after this block.

- [ ] **Step 4: Add flag helper**

Add:

```python
def _market_provider_router_enabled(self) -> bool:
    from app.core.database import SessionLocal
    from app.services.shared.feature_flags import feature_enabled

    with SessionLocal() as db:
        return feature_enabled(db, "market_provider_router_enabled", False)
```

- [ ] **Step 5: Add tests**

Create `backend/tests/test_market_provider_flag.py` with:

```python
from app.services.shared.feature_flags import list_feature_flags


def test_market_provider_router_flag_exists(db_session):
    keys = {item.key for item in list_feature_flags(db_session)}
    assert "market_provider_router_enabled" in keys
```

- [ ] **Step 6: Run verification and commit**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_provider_contract.py backend/tests/test_market_provider_flag.py -q
python3 -m compileall backend/app/services/market backend/app/services/shared
git add backend/app/services/market backend/app/services/shared/feature_flags.py backend/tests/test_market_provider_flag.py
git commit -m "feat: gate market provider router behind feature flag"
```

Expected: tests pass and commit succeeds.

---

## Task 10: Preserve Data Quality in API Responses

**Files:**
- Modify: `backend/app/models/schema_defs/agent.py`
- Modify: `backend/app/models/schema_defs/market.py`
- Modify: `backend/app/services/agent_context_service.py`
- Modify: `backend/app/services/market/regime.py`
- Create: `backend/tests/test_market_data_quality_fields.py`

- [ ] **Step 1: Add quality fields to response schemas**

Add these optional fields to market-facing schemas that already return data source information:

```python
data_quality: str = "fresh"
data_quality_message: str = ""
```

Use the exact string values `fresh`, `stale`, `estimated`, `unavailable`.

- [ ] **Step 2: Map provider quality to outputs**

Where provider results are used, set:

```python
payload["data_quality"] = result.quality.value
payload["data_quality_message"] = result.message
```

When existing non-router paths are used, set:

```python
payload["data_quality"] = "fresh"
payload["data_quality_message"] = ""
```

- [ ] **Step 3: Add tests**

Create `backend/tests/test_market_data_quality_fields.py` with:

```python
from app.services.market.providers.quality import MarketDataQuality


def test_market_data_quality_values_are_frontend_safe():
    assert [item.value for item in MarketDataQuality] == ["fresh", "stale", "estimated", "unavailable"]
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_data_quality_fields.py -q
python3 -m compileall backend/app
git add backend/app/models/schema_defs backend/app/services/agent_context_service.py backend/app/services/market backend/tests/test_market_data_quality_fields.py
git commit -m "feat: expose market data quality fields"
```

Expected: tests pass and commit succeeds.

---

## Task 11: Full Verification Matrix

**Files:**
- Modify: none unless verification exposes a defect

- [ ] **Step 1: Backend compile**

Run:

```bash
python3 -m compileall backend/app backend/tests scripts
```

Expected: exits `0`.

- [ ] **Step 2: Focused backend tests**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_legacy_routes.py \
  backend/tests/test_schema_index_audit.py \
  backend/tests/test_market_provider_contract.py \
  backend/tests/test_market_provider_flag.py \
  backend/tests/test_market_data_quality_fields.py \
  -q
```

Expected: all pass.

- [ ] **Step 3: Existing critical tests**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_auth_routes.py \
  backend/tests/test_paper_routes.py \
  backend/tests/test_strategy_metadata_service.py \
  backend/tests/test_feature_flags_service.py \
  -q
```

Expected: all pass.

- [ ] **Step 4: Frontend build**

Run:

```bash
cd frontend && npm run build:web
```

Expected: build passes.

- [ ] **Step 5: Strategy metadata fallback check**

Run:

```bash
cd frontend && npm run check:strategy-meta
```

Expected: fallback is up to date.

- [ ] **Step 6: Smoke checks**

Run:

```bash
./scripts/qa_smoke.sh
./scripts/prod_preflight.sh
```

Expected: both pass. If external data source failures occur, classify as external-service blocked and verify local API health separately.

- [ ] **Step 7: Commit verification notes if docs changed**

Run:

```bash
git status --short
```

Expected: only intended documentation or generated fallback changes remain. Commit intended files.

---

## Task 12: Deployment and Rollback Plan

**Files:**
- Modify: `PRODUCTION_RUNBOOK.md`
- Modify: `docs/operations/schema-index-runbook.md`
- Modify: `docs/operations/market-data-provider-runbook.md`

- [ ] **Step 1: Add deployment command**

Append to `PRODUCTION_RUNBOOK.md`:

```markdown
## High-risk optimization deployment

Run local verification first:

```bash
python3 -m compileall backend/app backend/tests scripts
cd frontend && npm run build:web && cd ..
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_legacy_routes.py backend/tests/test_market_provider_contract.py -q
```

Deploy:

```bash
CLOUD_HOST=<server-ip-or-domain> \
CLOUD_USER=ubuntu \
CLOUD_SSH_KEY=/path/to/gupiao.pem \
./scripts/deploy_cloud_server.sh
```

Verify:

```bash
curl -sS https://<server-ip-or-domain>/readyz -k
curl -sS http://<server-ip-or-domain>:18090/readyz
```
```

- [ ] **Step 2: Add rollback command**

Append:

```markdown
## Rollback

Use the previous deployment backup directory on the server:

```bash
ssh ubuntu@<server-ip-or-domain>
ls -dt /home/ubuntu/gupiao-deploy-backup-*
```

To rollback code, restore the latest backup and restart compose. To rollback schema, use Alembic downgrade only when the code version also rolls back.
```

- [ ] **Step 3: Commit docs**

Run:

```bash
git add PRODUCTION_RUNBOOK.md docs/operations
git commit -m "docs: document high-risk optimization deployment"
```

Expected: commit succeeds.

---

## Final Self-Review Checklist

- [ ] Database changes are only in Alembic migrations and docs.
- [ ] Runtime compatibility code warns but does not silently create production indexes.
- [ ] Legacy routes return structured `410` by default.
- [ ] First-party callers use current `/api/backtests` paths.
- [ ] Provider router is behind a disabled-by-default feature flag.
- [ ] Data quality states are explicit.
- [ ] Frontend build passes.
- [ ] Backend compile passes.
- [ ] Focused tests pass.
- [ ] Each task is committed independently.

## Completion Criteria

The high-risk optimization is complete only when:

1. `alembic upgrade head` succeeds against local SQLite and a MySQL staging database.
2. `scripts/schema_index_audit.py` reports no missing indexes on staging.
3. `/backtests` and `/research` return explicit `410` unless compatibility flag is enabled.
4. Market provider router tests pass and the feature flag remains disabled by default.
5. `qa_smoke.sh` and `prod_preflight.sh` pass or have documented external-service blockers.
6. Deployment runbook and rollback instructions are updated.
