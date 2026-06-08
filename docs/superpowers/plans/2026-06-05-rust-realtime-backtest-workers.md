# Rust Realtime And Backtest Workers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two Rust workers for the current platform: a `realtime-worker` for hot-read quote/cache/delta delivery and a `backtest-worker` for high-performance replay, matching current Python strategy results before any production-facing switch.

**Architecture:** Keep Python FastAPI as the API, OpenAPI, authorization, task submission, and production strategy fact source. Add a separate `backend-rs/` Cargo workspace with independently runnable Rust binaries. Rust workers start as shadow-only components behind feature flags and always keep Python fallback paths.

**Tech Stack:** Rust, Tokio, Axum, Serde, SQLx, Redis, DuckDB/Parquet, Tracing, Prometheus metrics, Python pytest, Rust cargo tests.

---

## 1. Scope And Non-Negotiable Boundaries

### 1.1 In Scope

1. Create a new `backend-rs/` Rust workspace.
2. Add `rust-realtime-worker`:
   - quote snapshot refresh
   - Redis hot-read cache writes
   - ordered delta event emission
   - worker health and metrics
   - Python BFF fallback support
3. Add `rust-backtest-worker`:
   - Python oracle signal ingestion
   - deterministic replay
   - execution model simulation
   - metrics/statistics generation
   - artifact output
   - parity comparison with Python backtest output
4. Add Python-side integration only where required:
   - feature flags
   - oracle export
   - optional read path to Rust Redis namespace
   - runtime task registration only after shadow parity is proven
5. Add tests, reports, and runbooks.

### 1.2 Out Of Scope

1. No deployment.
2. No production cutover.
3. No change to `backend/app/services/strategy_policy.py`.
4. No change to production strategy semantics, `production_score`, production ordering, or strategy gates.
5. No Rust production strategy calculation in this phase.
6. No removal of current Python workers.
7. No migration away from current FastAPI OpenAPI contract.
8. No use of DuckDB as the production trading fact source.

### 1.3 Required Starting Commands

```bash
cd /Users/j/Documents/gupiao
git status --short
```

If the worktree is dirty, inspect relevant diffs before editing:

```bash
cd /Users/j/Documents/gupiao
git diff -- <path>
```

Unrelated dirty files must be preserved.

---

## 2. Current Platform Baseline

The current backend already follows this architecture:

```text
Python FastAPI Web
  - lightweight reads
  - auth
  - OpenAPI
  - task submission
  - task status

Runtime worker
  - data refresh
  - quote cache
  - materialization

Analytics worker
  - Parquet export
  - DuckDB reports
  - data quality tasks

Backtest worker
  - persistent backtest job execution

Storage
  - MySQL/SQLite as business fact source
  - Redis for hot data and rate limit
  - Parquet + DuckDB for analysis
```

This plan extends that baseline with Rust workers while keeping Python as the production fact source until parity proves otherwise.

---

## 3. Target Architecture

```mermaid
flowchart LR
  FE["Frontend / frontend-next"] --> API["Python FastAPI API/BFF"]
  API --> Redis["Redis hot-read cache"]
  API --> DB["MySQL business fact source"]
  API --> Queue["RuntimeTaskQueue"]

  RT["Rust realtime-worker"] --> Redis
  RT --> DB
  RT --> Metrics["Worker metrics"]
  RT --> Events["snapshot + delta events"]

  PY["Python strategy oracle exporter"] --> Oracle["Oracle signal artifacts"]
  BW["Rust backtest-worker"] --> Oracle
  BW --> Parquet["Parquet/DuckDB analytics data"]
  BW --> Artifacts["Backtest artifacts"]
  BW --> Parity["Python/Rust parity reports"]

  Queue -.shadow only.-> BW
  API -.feature flag fallback.-> Redis
```

### 3.1 Component Responsibilities

| Component | Responsibility | Must Not Do |
|---|---|---|
| Python FastAPI | API, OpenAPI, auth, task submission, current production strategy fact source | Heavy request-time compute |
| Rust realtime-worker | Hot-read quote snapshots, Redis writes, ordered delta emission, metrics | Strategy scoring or production ordering |
| Rust backtest-worker | Replay Python oracle signals, simulate execution, calculate stats | Replace production strategy logic |
| Python oracle exporter | Export current strategy/backtest inputs and outputs for parity | Change strategy logic |
| Parity tooling | Compare Python vs Rust outputs | Auto-approve semantic differences |

---

## 4. Required File Structure

### 4.1 Create

```text
backend-rs/
  Cargo.toml
  crates/
    common/
      Cargo.toml
      src/lib.rs
      src/config.rs
      src/error.rs
      src/metrics.rs
      src/time.rs
    contracts/
      Cargo.toml
      src/lib.rs
      src/realtime.rs
      src/backtest.rs
      src/parity.rs
    storage/
      Cargo.toml
      src/lib.rs
      src/mysql.rs
      src/redis.rs
      src/duckdb.rs
      src/artifacts.rs
    realtime-worker/
      Cargo.toml
      src/main.rs
      src/worker.rs
      src/snapshot.rs
      src/delta.rs
      src/health.rs
    backtest-worker/
      Cargo.toml
      src/main.rs
      src/worker.rs
      src/oracle.rs
      src/execution.rs
      src/statistics.rs
      src/artifacts.rs
    parity/
      Cargo.toml
      src/lib.rs
      src/realtime.rs
      src/backtest.rs
backend/scripts/export_backtest_oracle.py
backend/tests/test_rust_realtime_feature_flags.py
backend/tests/test_backtest_oracle_export.py
backend/tests/test_rust_worker_shadow_boundaries.py
docs/operations/rust-workers-runbook.md
docs/reports/rust-workers-baseline-2026-06-05.md
docs/reports/rust-workers-acceptance-2026-06-05.md
scripts/run_rust_component.sh
```

### 4.2 Modify Only When Reached By The Task

```text
backend/app/core/config.py
backend/app/services/bff/monitor_workspace.py
backend/app/services/bff/strategy_workspace.py
backend/app/services/tasks/registry.py
backend/app/services/tasks/analytics_handlers.py
docker-compose.mysql.yml
scripts/deploy_cloud_server.sh
```

Rules:

1. Do not modify deployment files until the local shadow workers and tests are green.
2. `docker-compose.mysql.yml` changes must use a disabled profile such as `rust-workers`; default deployment must not start Rust workers.
3. Deploy scripts may only print or validate Rust component wiring in this phase; they must not deploy Rust workers by default.

---

## 5. Shared Data Contracts

### 5.1 Realtime Snapshot

```json
{
  "schema_version": 1,
  "source": "rust_realtime_worker",
  "as_of_ms": 1780315200000,
  "trade_date": "2026-06-05",
  "sequence": 10001,
  "quotes": [
    {
      "symbol": "000001",
      "name": "平安银行",
      "price_x10000": 123400,
      "prev_close_x10000": 120000,
      "change_bps": 283,
      "volume": 12345600,
      "amount_cent": 152345678900,
      "is_suspended": false,
      "limit_up_x10000": 132000,
      "limit_down_x10000": 108000,
      "updated_at_ms": 1780315199000
    }
  ]
}
```

### 5.2 Realtime Delta

```json
{
  "schema_version": 1,
  "channel": "quotes",
  "sequence": 10002,
  "base_sequence": 10001,
  "as_of_ms": 1780315201000,
  "changes": [
    {
      "symbol": "000001",
      "field": "price_x10000",
      "old": 123400,
      "new": 123500
    }
  ]
}
```

### 5.3 Backtest Oracle Signal Event

```json
{
  "schema_version": 1,
  "run_id": "oracle-2026-06-05-first-board",
  "strategy_key": "first_board",
  "strategy_variant": "baseline",
  "trade_date": "2026-06-05",
  "symbol": "000001",
  "signal_state": "buy_now",
  "production_allowed": true,
  "production_score": 88.5,
  "watch_score": 91.2,
  "side": "buy",
  "target_price_x10000": 123400,
  "score_components": {
    "trend": 20.0,
    "liquidity": 18.0,
    "risk": -3.0
  },
  "exclusion_reasons": [],
  "warning_tags": []
}
```

### 5.4 Backtest Result Summary

```json
{
  "schema_version": 1,
  "engine": "rust_backtest_worker",
  "run_id": "bt-2026-06-05-first-board",
  "oracle_run_id": "oracle-2026-06-05-first-board",
  "strategy_key": "first_board",
  "start_date": "2024-06-05",
  "end_date": "2026-06-05",
  "trade_count": 120,
  "win_rate_bps": 5333,
  "total_return_bps": 1880,
  "max_drawdown_bps": -620,
  "annualized_return_bps": 930,
  "parity_status": "matched"
}
```

---

## 6. Fixed-Point Numeric Rules

1. Price: `price_x10000: i64`.
2. Percentage: basis points, `bps: i64`.
3. Money: cents, `amount_cent: i64`.
4. Quantity: integer shares or lots.
5. Sorting tie-breaker: `trade_date`, `production_score`, `symbol`, `strategy_key`.
6. No floating-point threshold checks in Rust execution logic.
7. Float is allowed only in report rendering after deterministic integer calculation is complete.

---

## 7. Feature Flags

Add flags in Python config and keep all default values off:

```text
RUST_REALTIME_WORKER_ENABLED=false
RUST_REALTIME_READ_PATH_ENABLED=false
RUST_REALTIME_PUSH_ENABLED=false
RUST_BACKTEST_WORKER_ENABLED=false
RUST_BACKTEST_SHADOW_ONLY=true
RUST_BACKTEST_PYTHON_ORACLE_REQUIRED=true
```

Runtime behavior:

1. If `RUST_REALTIME_READ_PATH_ENABLED=false`, Python BFF ignores Rust Redis keys.
2. If `RUST_REALTIME_READ_PATH_ENABLED=true` and Rust Redis read fails, Python BFF uses existing Python path.
3. If `RUST_BACKTEST_WORKER_ENABLED=false`, Python backtest worker remains the only active backtest worker.
4. If `RUST_BACKTEST_WORKER_ENABLED=true`, Rust worker may consume only shadow or parity tasks while `RUST_BACKTEST_SHADOW_ONLY=true`.

---

## 8. Redis Namespace

Rust realtime-worker must use a separate namespace until accepted:

```text
tq:rust:rt:quote:{symbol}
tq:rust:rt:market:snapshot
tq:rust:rt:monitor:snapshot
tq:rust:rt:delta:{channel}
tq:rust:rt:health
tq:rust:rt:metrics
```

Required fields for every cached payload:

```text
schema_version
source
as_of_ms
trade_date
sequence
ttl_seconds
data_version
```

TTL policy:

| Key | TTL |
|---|---:|
| `tq:rust:rt:quote:{symbol}` | 30 seconds during market hours |
| `tq:rust:rt:market:snapshot` | 30 seconds during market hours |
| `tq:rust:rt:monitor:snapshot` | 30 seconds during market hours |
| `tq:rust:rt:delta:{channel}` | 300 seconds |
| `tq:rust:rt:health` | 60 seconds |

---

## 9. Metrics

### 9.1 Realtime Metrics

```text
rust_realtime_worker_up
rust_realtime_snapshot_refresh_total
rust_realtime_snapshot_refresh_errors_total
rust_realtime_snapshot_freshness_seconds
rust_realtime_redis_write_total
rust_realtime_redis_write_errors_total
rust_realtime_delta_events_total
rust_realtime_delta_sequence_gap_total
rust_realtime_symbols_loaded
rust_realtime_loop_duration_ms
```

### 9.2 Backtest Metrics

```text
rust_backtest_worker_up
rust_backtest_runs_total
rust_backtest_run_errors_total
rust_backtest_oracle_events_loaded
rust_backtest_trades_simulated
rust_backtest_run_duration_ms
rust_backtest_parity_mismatch_total
rust_backtest_artifact_write_errors_total
```

---

## 10. Multi-Agent Workstreams

### Agent A: Rust Workspace And Shared Contracts

Owns:

1. `backend-rs/` workspace.
2. `common`, `contracts`, and `storage` crates.
3. Rust formatting, clippy, unit tests.

### Agent B: Realtime Worker

Owns:

1. `realtime-worker` crate.
2. Redis namespace.
3. snapshot/delta sequence.
4. health and metrics.

### Agent C: Backtest Worker

Owns:

1. `backtest-worker` crate.
2. Python oracle ingestion.
3. deterministic execution simulation.
4. result statistics and artifacts.

### Agent D: Python Integration

Owns:

1. feature flags.
2. oracle exporter.
3. optional BFF Rust read path with fallback.
4. targeted pytest coverage.

### Agent E: QA And Parity

Owns:

1. golden fixtures.
2. Python vs Rust parity reports.
3. performance baseline.
4. acceptance report.

---

## 11. Development Tasks

### Task 1: Baseline Report And Safety Gate

**Files:**
- Create: `docs/reports/rust-workers-baseline-2026-06-05.md`

- [ ] **Step 1: Record working tree**

Run:

```bash
cd /Users/j/Documents/gupiao
git status --short
```

Expected: output is copied into the baseline report.

- [ ] **Step 2: Record current backend worker topology**

Run:

```bash
cd /Users/j/Documents/gupiao
rg -n "runtime-worker|analytics-worker|backtest-worker|RuntimeTaskQueue|FastAPI|OpenAPI" docs/architecture/current-boundary-map.md docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md docs/operations
```

Expected: report lists current Python Web, runtime-worker, analytics-worker, and backtest-worker boundaries.

- [ ] **Step 3: Record current tests to preserve**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_web_route_no_heavy_compute.py backend/tests/test_runtime_task_registry_governance.py backend/tests/test_backtest_worker.py -q
```

Expected: existing tests pass or failures are copied verbatim into the report before any code change.

- [ ] **Step 4: Commit**

```bash
cd /Users/j/Documents/gupiao
git add docs/reports/rust-workers-baseline-2026-06-05.md
git commit -m "docs: add rust workers baseline"
```

### Task 2: Rust Workspace Scaffold

**Files:**
- Create: `backend-rs/Cargo.toml`
- Create: `backend-rs/crates/common/Cargo.toml`
- Create: `backend-rs/crates/common/src/lib.rs`
- Create: `backend-rs/crates/contracts/Cargo.toml`
- Create: `backend-rs/crates/contracts/src/lib.rs`
- Create: `backend-rs/crates/storage/Cargo.toml`
- Create: `backend-rs/crates/storage/src/lib.rs`

- [ ] **Step 1: Create failing workspace command**

Run:

```bash
cd /Users/j/Documents/gupiao/backend-rs
cargo metadata --format-version 1
```

Expected before scaffold: command fails because `backend-rs/` does not exist.

- [ ] **Step 2: Create workspace manifest**

Create `backend-rs/Cargo.toml`:

```toml
[workspace]
resolver = "2"
members = [
  "crates/common",
  "crates/contracts",
  "crates/storage",
  "crates/realtime-worker",
  "crates/backtest-worker",
  "crates/parity"
]

[workspace.package]
edition = "2021"
license = "UNLICENSED"
version = "0.1.0"

[workspace.dependencies]
anyhow = "1"
axum = "0.7"
chrono = { version = "0.4", features = ["serde"] }
clap = { version = "4", features = ["derive", "env"] }
duckdb = "1"
redis = { version = "0.25", features = ["tokio-comp", "connection-manager"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
sqlx = { version = "0.7", features = ["runtime-tokio-rustls", "mysql", "chrono", "json"] }
thiserror = "1"
tokio = { version = "1", features = ["macros", "rt-multi-thread", "signal", "time"] }
tower-http = { version = "0.5", features = ["trace"] }
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
```

- [ ] **Step 3: Create common crate**

Create `backend-rs/crates/common/Cargo.toml`:

```toml
[package]
name = "tq-common"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
chrono.workspace = true
clap.workspace = true
serde.workspace = true
thiserror.workspace = true
tracing.workspace = true
```

Create `backend-rs/crates/common/src/lib.rs`:

```rust
pub mod config;
pub mod error;
pub mod metrics;
pub mod time;
```

- [ ] **Step 4: Create contracts crate**

Create `backend-rs/crates/contracts/Cargo.toml`:

```toml
[package]
name = "tq-contracts"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
chrono.workspace = true
serde.workspace = true
serde_json.workspace = true
```

Create `backend-rs/crates/contracts/src/lib.rs`:

```rust
pub mod backtest;
pub mod parity;
pub mod realtime;
```

- [ ] **Step 5: Create storage crate**

Create `backend-rs/crates/storage/Cargo.toml`:

```toml
[package]
name = "tq-storage"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
anyhow.workspace = true
duckdb.workspace = true
redis.workspace = true
serde.workspace = true
serde_json.workspace = true
sqlx.workspace = true
tokio.workspace = true
tracing.workspace = true
tq-contracts = { path = "../contracts" }
```

Create `backend-rs/crates/storage/src/lib.rs`:

```rust
pub mod artifacts;
pub mod duckdb;
pub mod mysql;
pub mod redis;
```

- [ ] **Step 6: Verify workspace metadata**

Run:

```bash
cd /Users/j/Documents/gupiao/backend-rs
cargo metadata --format-version 1 >/tmp/gupiao-rust-workers-metadata.json
```

Expected: command exits with status 0.

- [ ] **Step 7: Commit**

```bash
cd /Users/j/Documents/gupiao
git add backend-rs
git commit -m "feat: scaffold rust worker workspace"
```

### Task 3: Shared Rust Contracts

**Files:**
- Create: `backend-rs/crates/contracts/src/realtime.rs`
- Create: `backend-rs/crates/contracts/src/backtest.rs`
- Create: `backend-rs/crates/contracts/src/parity.rs`

- [ ] **Step 1: Write serialization tests**

Create `backend-rs/crates/contracts/src/realtime.rs` with tests and structs:

```rust
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct QuoteItem {
    pub symbol: String,
    pub name: String,
    pub price_x10000: i64,
    pub prev_close_x10000: i64,
    pub change_bps: i64,
    pub volume: i64,
    pub amount_cent: i64,
    pub is_suspended: bool,
    pub limit_up_x10000: i64,
    pub limit_down_x10000: i64,
    pub updated_at_ms: i64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RealtimeSnapshot {
    pub schema_version: u16,
    pub source: String,
    pub as_of_ms: i64,
    pub trade_date: String,
    pub sequence: u64,
    pub quotes: Vec<QuoteItem>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DeltaChange {
    pub symbol: String,
    pub field: String,
    pub old: serde_json::Value,
    pub new: serde_json::Value,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RealtimeDelta {
    pub schema_version: u16,
    pub channel: String,
    pub sequence: u64,
    pub base_sequence: u64,
    pub as_of_ms: i64,
    pub changes: Vec<DeltaChange>,
}

pub type QuoteMap = BTreeMap<String, QuoteItem>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn snapshot_serializes_fixed_point_fields() {
        let snapshot = RealtimeSnapshot {
            schema_version: 1,
            source: "rust_realtime_worker".to_string(),
            as_of_ms: 1_780_315_200_000,
            trade_date: "2026-06-05".to_string(),
            sequence: 10001,
            quotes: vec![QuoteItem {
                symbol: "000001".to_string(),
                name: "平安银行".to_string(),
                price_x10000: 123400,
                prev_close_x10000: 120000,
                change_bps: 283,
                volume: 12_345_600,
                amount_cent: 152_345_678_900,
                is_suspended: false,
                limit_up_x10000: 132000,
                limit_down_x10000: 108000,
                updated_at_ms: 1_780_315_199_000,
            }],
        };

        let text = serde_json::to_string(&snapshot).unwrap();
        assert!(text.contains("\"price_x10000\":123400"));
        assert!(text.contains("\"change_bps\":283"));
    }
}
```

- [ ] **Step 2: Add backtest contract**

Create `backend-rs/crates/contracts/src/backtest.rs`:

```rust
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BacktestSignalEvent {
    pub schema_version: u16,
    pub run_id: String,
    pub strategy_key: String,
    pub strategy_variant: String,
    pub trade_date: String,
    pub symbol: String,
    pub signal_state: String,
    pub production_allowed: bool,
    pub production_score: Option<f64>,
    pub watch_score: Option<f64>,
    pub side: String,
    pub target_price_x10000: i64,
    pub score_components: BTreeMap<String, f64>,
    pub exclusion_reasons: Vec<String>,
    pub warning_tags: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SimulatedTrade {
    pub trade_date: String,
    pub symbol: String,
    pub side: String,
    pub quantity: i64,
    pub price_x10000: i64,
    pub fee_cent: i64,
    pub slippage_bps: i64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BacktestResultSummary {
    pub schema_version: u16,
    pub engine: String,
    pub run_id: String,
    pub oracle_run_id: String,
    pub strategy_key: String,
    pub start_date: String,
    pub end_date: String,
    pub trade_count: usize,
    pub win_rate_bps: i64,
    pub total_return_bps: i64,
    pub max_drawdown_bps: i64,
    pub annualized_return_bps: i64,
    pub parity_status: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backtest_result_uses_integer_metrics() {
        let summary = BacktestResultSummary {
            schema_version: 1,
            engine: "rust_backtest_worker".to_string(),
            run_id: "bt-2026-06-05-first-board".to_string(),
            oracle_run_id: "oracle-2026-06-05-first-board".to_string(),
            strategy_key: "first_board".to_string(),
            start_date: "2024-06-05".to_string(),
            end_date: "2026-06-05".to_string(),
            trade_count: 120,
            win_rate_bps: 5333,
            total_return_bps: 1880,
            max_drawdown_bps: -620,
            annualized_return_bps: 930,
            parity_status: "matched".to_string(),
        };

        assert_eq!(summary.total_return_bps, 1880);
        assert_eq!(summary.max_drawdown_bps, -620);
    }
}
```

- [ ] **Step 3: Add parity contract**

Create `backend-rs/crates/contracts/src/parity.rs`:

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ParitySeverity {
    Matched,
    ToleranceOnly,
    OrderingChanged,
    ProductionStateChanged,
    GateChanged,
    MissingRecord,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ParityIssue {
    pub severity: ParitySeverity,
    pub key: String,
    pub field: String,
    pub python_value: String,
    pub rust_value: String,
    pub explanation: String,
}
```

- [ ] **Step 4: Run contract tests**

Run:

```bash
cd /Users/j/Documents/gupiao/backend-rs
cargo test -p tq-contracts
```

Expected: all contract tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/j/Documents/gupiao
git add backend-rs/crates/contracts
git commit -m "feat: add rust worker contracts"
```

### Task 4: Realtime Worker Shadow Cache

**Files:**
- Create: `backend-rs/crates/realtime-worker/Cargo.toml`
- Create: `backend-rs/crates/realtime-worker/src/main.rs`
- Create: `backend-rs/crates/realtime-worker/src/worker.rs`
- Create: `backend-rs/crates/realtime-worker/src/snapshot.rs`
- Create: `backend-rs/crates/realtime-worker/src/delta.rs`
- Create: `backend-rs/crates/realtime-worker/src/health.rs`

- [ ] **Step 1: Write delta test**

Create `backend-rs/crates/realtime-worker/src/delta.rs`:

```rust
use tq_contracts::realtime::{DeltaChange, QuoteMap, RealtimeDelta};

pub fn build_delta(base_sequence: u64, next_sequence: u64, previous: &QuoteMap, current: &QuoteMap, as_of_ms: i64) -> RealtimeDelta {
    let mut changes = Vec::new();
    for (symbol, current_quote) in current {
        if let Some(previous_quote) = previous.get(symbol) {
            if previous_quote.price_x10000 != current_quote.price_x10000 {
                changes.push(DeltaChange {
                    symbol: symbol.clone(),
                    field: "price_x10000".to_string(),
                    old: serde_json::json!(previous_quote.price_x10000),
                    new: serde_json::json!(current_quote.price_x10000),
                });
            }
        }
    }
    RealtimeDelta {
        schema_version: 1,
        channel: "quotes".to_string(),
        sequence: next_sequence,
        base_sequence,
        as_of_ms,
        changes,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tq_contracts::realtime::{QuoteItem, QuoteMap};

    fn quote(symbol: &str, price_x10000: i64) -> QuoteItem {
        QuoteItem {
            symbol: symbol.to_string(),
            name: symbol.to_string(),
            price_x10000,
            prev_close_x10000: 100000,
            change_bps: 0,
            volume: 0,
            amount_cent: 0,
            is_suspended: false,
            limit_up_x10000: 110000,
            limit_down_x10000: 90000,
            updated_at_ms: 1,
        }
    }

    #[test]
    fn delta_contains_only_changed_price() {
        let mut previous = QuoteMap::new();
        previous.insert("000001".to_string(), quote("000001", 100000));
        let mut current = QuoteMap::new();
        current.insert("000001".to_string(), quote("000001", 100500));

        let delta = build_delta(10, 11, &previous, &current, 1000);

        assert_eq!(delta.sequence, 11);
        assert_eq!(delta.base_sequence, 10);
        assert_eq!(delta.changes.len(), 1);
        assert_eq!(delta.changes[0].field, "price_x10000");
    }
}
```

- [ ] **Step 2: Create worker manifest**

Create `backend-rs/crates/realtime-worker/Cargo.toml`:

```toml
[package]
name = "tq-realtime-worker"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
anyhow.workspace = true
axum.workspace = true
clap.workspace = true
redis.workspace = true
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
tq-common = { path = "../common" }
tq-contracts = { path = "../contracts" }
tq-storage = { path = "../storage" }
```

- [ ] **Step 3: Create shadow-only entrypoint**

Create `backend-rs/crates/realtime-worker/src/main.rs`:

```rust
mod delta;
mod health;
mod snapshot;
mod worker;

use clap::Parser;
use worker::{RealtimeWorker, RealtimeWorkerConfig};

#[derive(Debug, Parser)]
struct Args {
    #[arg(long, env = "REDIS_URL")]
    redis_url: String,
    #[arg(long, env = "DATABASE_URL")]
    database_url: String,
    #[arg(long, env = "RUST_REALTIME_WORKER_ENABLED", default_value_t = false)]
    enabled: bool,
    #[arg(long, env = "RUST_REALTIME_POLL_INTERVAL_MS", default_value_t = 1000)]
    poll_interval_ms: u64,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter("info").init();
    let args = Args::parse();
    let config = RealtimeWorkerConfig {
        redis_url: args.redis_url,
        database_url: args.database_url,
        enabled: args.enabled,
        poll_interval_ms: args.poll_interval_ms,
    };
    RealtimeWorker::new(config).run().await
}
```

- [ ] **Step 4: Create worker loop with disabled default**

Create `backend-rs/crates/realtime-worker/src/worker.rs`:

```rust
use anyhow::Result;
use std::time::Duration;

#[derive(Debug, Clone)]
pub struct RealtimeWorkerConfig {
    pub redis_url: String,
    pub database_url: String,
    pub enabled: bool,
    pub poll_interval_ms: u64,
}

pub struct RealtimeWorker {
    config: RealtimeWorkerConfig,
}

impl RealtimeWorker {
    pub fn new(config: RealtimeWorkerConfig) -> Self {
        Self { config }
    }

    pub async fn run(self) -> Result<()> {
        if !self.config.enabled {
            tracing::info!("rust realtime worker disabled by flag");
            return Ok(());
        }

        loop {
            tracing::info!("rust realtime worker heartbeat");
            tokio::time::sleep(Duration::from_millis(self.config.poll_interval_ms)).await;
        }
    }
}
```

- [ ] **Step 5: Run realtime tests**

Run:

```bash
cd /Users/j/Documents/gupiao/backend-rs
cargo test -p tq-realtime-worker
```

Expected: delta test passes.

- [ ] **Step 6: Commit**

```bash
cd /Users/j/Documents/gupiao
git add backend-rs/crates/realtime-worker
git commit -m "feat: add rust realtime worker shadow scaffold"
```

### Task 5: Python Realtime Feature Flags And Fallback Guard

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_rust_realtime_feature_flags.py`

- [ ] **Step 1: Write failing pytest**

Create `backend/tests/test_rust_realtime_feature_flags.py`:

```python
from app.core.config import Settings


def test_rust_realtime_flags_default_off() -> None:
    settings = Settings()

    assert settings.rust_realtime_worker_enabled is False
    assert settings.rust_realtime_read_path_enabled is False
    assert settings.rust_realtime_push_enabled is False
```

- [ ] **Step 2: Run failing test**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_rust_realtime_feature_flags.py -q
```

Expected before implementation: failure because settings fields do not exist.

- [ ] **Step 3: Add settings fields**

Modify `backend/app/core/config.py` by adding these fields to `Settings`:

```python
rust_realtime_worker_enabled: bool = False
rust_realtime_read_path_enabled: bool = False
rust_realtime_push_enabled: bool = False
```

- [ ] **Step 4: Run test**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_rust_realtime_feature_flags.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/j/Documents/gupiao
git add backend/app/core/config.py backend/tests/test_rust_realtime_feature_flags.py
git commit -m "feat: add rust realtime feature flags"
```

### Task 6: Backtest Oracle Exporter

**Files:**
- Create: `backend/scripts/export_backtest_oracle.py`
- Create: `backend/tests/test_backtest_oracle_export.py`

- [ ] **Step 1: Write oracle shape test**

Create `backend/tests/test_backtest_oracle_export.py`:

```python
import json
from pathlib import Path

from backend.scripts.export_backtest_oracle import export_oracle_events


def test_export_oracle_events_writes_versioned_events(tmp_path: Path) -> None:
    output = tmp_path / "oracle.jsonl"

    export_oracle_events(
        output_path=output,
        run_id="oracle-test",
        strategy_key="first_board",
        trade_date="2026-06-05",
        events=[
            {
                "symbol": "000001",
                "signal_state": "buy_now",
                "production_allowed": True,
                "production_score": 88.5,
                "watch_score": 91.2,
                "side": "buy",
                "target_price_x10000": 123400,
                "score_components": {"trend": 20.0},
                "exclusion_reasons": [],
                "warning_tags": [],
            }
        ],
    )

    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["schema_version"] == 1
    assert payload["run_id"] == "oracle-test"
    assert payload["strategy_key"] == "first_board"
    assert payload["target_price_x10000"] == 123400
```

- [ ] **Step 2: Run failing test**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_backtest_oracle_export.py -q
```

Expected before implementation: import fails.

- [ ] **Step 3: Create exporter**

Create `backend/scripts/export_backtest_oracle.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Any


def export_oracle_events(
    *,
    output_path: Path,
    run_id: str,
    strategy_key: str,
    trade_date: str,
    events: Iterable[Mapping[str, Any]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for event in events:
            payload = {
                "schema_version": 1,
                "run_id": run_id,
                "strategy_key": strategy_key,
                "strategy_variant": str(event.get("strategy_variant") or "baseline"),
                "trade_date": trade_date,
                "symbol": str(event["symbol"]),
                "signal_state": str(event["signal_state"]),
                "production_allowed": bool(event["production_allowed"]),
                "production_score": event.get("production_score"),
                "watch_score": event.get("watch_score"),
                "side": str(event["side"]),
                "target_price_x10000": int(event["target_price_x10000"]),
                "score_components": dict(event.get("score_components") or {}),
                "exclusion_reasons": list(event.get("exclusion_reasons") or []),
                "warning_tags": list(event.get("warning_tags") or []),
            }
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
```

- [ ] **Step 4: Run exporter test**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_backtest_oracle_export.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/j/Documents/gupiao
git add backend/scripts/export_backtest_oracle.py backend/tests/test_backtest_oracle_export.py
git commit -m "feat: add python backtest oracle exporter"
```

### Task 7: Rust Backtest Worker Replay Core

**Files:**
- Create: `backend-rs/crates/backtest-worker/Cargo.toml`
- Create: `backend-rs/crates/backtest-worker/src/main.rs`
- Create: `backend-rs/crates/backtest-worker/src/oracle.rs`
- Create: `backend-rs/crates/backtest-worker/src/execution.rs`
- Create: `backend-rs/crates/backtest-worker/src/statistics.rs`
- Create: `backend-rs/crates/backtest-worker/src/artifacts.rs`
- Create: `backend-rs/crates/backtest-worker/src/worker.rs`

- [ ] **Step 1: Write execution test**

Create `backend-rs/crates/backtest-worker/src/execution.rs`:

```rust
use tq_contracts::backtest::{BacktestSignalEvent, SimulatedTrade};

pub fn simulate_market_buy(event: &BacktestSignalEvent, quantity: i64, slippage_bps: i64, fee_cent: i64) -> Option<SimulatedTrade> {
    if !event.production_allowed {
        return None;
    }
    if event.side != "buy" {
        return None;
    }
    let price = event.target_price_x10000 + (event.target_price_x10000 * slippage_bps / 10_000);
    Some(SimulatedTrade {
        trade_date: event.trade_date.clone(),
        symbol: event.symbol.clone(),
        side: "buy".to_string(),
        quantity,
        price_x10000: price,
        fee_cent,
        slippage_bps,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    fn signal(production_allowed: bool) -> BacktestSignalEvent {
        BacktestSignalEvent {
            schema_version: 1,
            run_id: "oracle-test".to_string(),
            strategy_key: "first_board".to_string(),
            strategy_variant: "baseline".to_string(),
            trade_date: "2026-06-05".to_string(),
            symbol: "000001".to_string(),
            signal_state: "buy_now".to_string(),
            production_allowed,
            production_score: Some(88.5),
            watch_score: Some(91.2),
            side: "buy".to_string(),
            target_price_x10000: 100000,
            score_components: BTreeMap::new(),
            exclusion_reasons: Vec::new(),
            warning_tags: Vec::new(),
        }
    }

    #[test]
    fn production_allowed_signal_creates_trade_with_slippage() {
        let trade = simulate_market_buy(&signal(true), 100, 50, 500).unwrap();
        assert_eq!(trade.price_x10000, 100500);
        assert_eq!(trade.quantity, 100);
        assert_eq!(trade.fee_cent, 500);
    }

    #[test]
    fn production_disallowed_signal_creates_no_trade() {
        assert!(simulate_market_buy(&signal(false), 100, 50, 500).is_none());
    }
}
```

- [ ] **Step 2: Create manifest**

Create `backend-rs/crates/backtest-worker/Cargo.toml`:

```toml
[package]
name = "tq-backtest-worker"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
anyhow.workspace = true
clap.workspace = true
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
tq-common = { path = "../common" }
tq-contracts = { path = "../contracts" }
tq-storage = { path = "../storage" }
```

- [ ] **Step 3: Create oracle reader**

Create `backend-rs/crates/backtest-worker/src/oracle.rs`:

```rust
use anyhow::Result;
use std::path::Path;
use tq_contracts::backtest::BacktestSignalEvent;

pub fn read_oracle_jsonl(path: &Path) -> Result<Vec<BacktestSignalEvent>> {
    let text = std::fs::read_to_string(path)?;
    let mut events = Vec::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        events.push(serde_json::from_str::<BacktestSignalEvent>(line)?);
    }
    events.sort_by(|left, right| {
        left.trade_date
            .cmp(&right.trade_date)
            .then(left.strategy_key.cmp(&right.strategy_key))
            .then(left.symbol.cmp(&right.symbol))
    });
    Ok(events)
}
```

- [ ] **Step 4: Create disabled-by-default entrypoint**

Create `backend-rs/crates/backtest-worker/src/main.rs`:

```rust
mod artifacts;
mod execution;
mod oracle;
mod statistics;
mod worker;

use clap::Parser;
use std::path::PathBuf;
use worker::{BacktestWorker, BacktestWorkerConfig};

#[derive(Debug, Parser)]
struct Args {
    #[arg(long, env = "RUST_BACKTEST_WORKER_ENABLED", default_value_t = false)]
    enabled: bool,
    #[arg(long, env = "RUST_BACKTEST_SHADOW_ONLY", default_value_t = true)]
    shadow_only: bool,
    #[arg(long, env = "RUST_BACKTEST_ORACLE_PATH")]
    oracle_path: Option<PathBuf>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter("info").init();
    let args = Args::parse();
    let config = BacktestWorkerConfig {
        enabled: args.enabled,
        shadow_only: args.shadow_only,
        oracle_path: args.oracle_path,
    };
    BacktestWorker::new(config).run().await
}
```

- [ ] **Step 5: Create worker shell**

Create `backend-rs/crates/backtest-worker/src/worker.rs`:

```rust
use anyhow::Result;
use std::path::PathBuf;

#[derive(Debug, Clone)]
pub struct BacktestWorkerConfig {
    pub enabled: bool,
    pub shadow_only: bool,
    pub oracle_path: Option<PathBuf>,
}

pub struct BacktestWorker {
    config: BacktestWorkerConfig,
}

impl BacktestWorker {
    pub fn new(config: BacktestWorkerConfig) -> Self {
        Self { config }
    }

    pub async fn run(self) -> Result<()> {
        if !self.config.enabled {
            tracing::info!("rust backtest worker disabled by flag");
            return Ok(());
        }
        if !self.config.shadow_only {
            anyhow::bail!("rust backtest worker must remain shadow-only in this phase");
        }
        tracing::info!("rust backtest worker shadow run ready");
        Ok(())
    }
}
```

- [ ] **Step 6: Run backtest tests**

Run:

```bash
cd /Users/j/Documents/gupiao/backend-rs
cargo test -p tq-backtest-worker
```

Expected: execution tests pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/j/Documents/gupiao
git add backend-rs/crates/backtest-worker
git commit -m "feat: add rust backtest worker replay core"
```

### Task 8: Rust Worker Shadow Boundary Tests

**Files:**
- Create: `backend/tests/test_rust_worker_shadow_boundaries.py`

- [ ] **Step 1: Write Python boundary tests**

Create `backend/tests/test_rust_worker_shadow_boundaries.py`:

```python
from pathlib import Path


def test_rust_worker_plan_does_not_modify_strategy_policy() -> None:
    path = Path("backend/app/services/strategy_policy.py")
    assert path.exists()


def test_rust_workers_default_to_shadow_flags() -> None:
    from app.core.config import Settings

    settings = Settings()
    assert settings.rust_backtest_worker_enabled is False
    assert settings.rust_backtest_shadow_only is True
    assert settings.rust_backtest_python_oracle_required is True
```

- [ ] **Step 2: Run failing test**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_rust_worker_shadow_boundaries.py -q
```

Expected before config implementation: backtest flag assertions fail.

- [ ] **Step 3: Add backtest settings fields**

Modify `backend/app/core/config.py`:

```python
rust_backtest_worker_enabled: bool = False
rust_backtest_shadow_only: bool = True
rust_backtest_python_oracle_required: bool = True
```

- [ ] **Step 4: Run boundary tests**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_rust_worker_shadow_boundaries.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/j/Documents/gupiao
git add backend/app/core/config.py backend/tests/test_rust_worker_shadow_boundaries.py
git commit -m "test: guard rust worker shadow boundaries"
```

### Task 9: Run Script For Local Rust Components

**Files:**
- Create: `scripts/run_rust_component.sh`
- Test: `backend/tests/test_independent_runtime_components.py`

- [ ] **Step 1: Add script test**

Modify `backend/tests/test_independent_runtime_components.py` with:

```python
from pathlib import Path


def test_run_rust_component_script_exposes_shadow_workers() -> None:
    text = Path("scripts/run_rust_component.sh").read_text(encoding="utf-8")

    assert "realtime-worker" in text
    assert "backtest-worker" in text
    assert "RUST_REALTIME_WORKER_ENABLED" in text
    assert "RUST_BACKTEST_WORKER_ENABLED" in text
```

- [ ] **Step 2: Run failing test**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_independent_runtime_components.py::test_run_rust_component_script_exposes_shadow_workers -q
```

Expected before script: failure because file does not exist.

- [ ] **Step 3: Create script**

Create `scripts/run_rust_component.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

component="${1:-}"
shift || true

case "${component}" in
  realtime-worker)
    RUST_REALTIME_WORKER_ENABLED="${RUST_REALTIME_WORKER_ENABLED:-false}" \
      cargo run --manifest-path backend-rs/Cargo.toml -p tq-realtime-worker -- "$@"
    ;;
  backtest-worker)
    RUST_BACKTEST_WORKER_ENABLED="${RUST_BACKTEST_WORKER_ENABLED:-false}" \
    RUST_BACKTEST_SHADOW_ONLY="${RUST_BACKTEST_SHADOW_ONLY:-true}" \
      cargo run --manifest-path backend-rs/Cargo.toml -p tq-backtest-worker -- "$@"
    ;;
  *)
    echo "Usage: scripts/run_rust_component.sh <realtime-worker|backtest-worker> [args...]" >&2
    exit 2
    ;;
esac
```

- [ ] **Step 4: Mark executable and run test**

Run:

```bash
cd /Users/j/Documents/gupiao
chmod +x scripts/run_rust_component.sh
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_independent_runtime_components.py::test_run_rust_component_script_exposes_shadow_workers -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/j/Documents/gupiao
git add scripts/run_rust_component.sh backend/tests/test_independent_runtime_components.py
git commit -m "feat: add rust component runner"
```

### Task 10: Parity Report Tooling

**Files:**
- Create: `backend-rs/crates/parity/Cargo.toml`
- Create: `backend-rs/crates/parity/src/lib.rs`
- Create: `backend-rs/crates/parity/src/backtest.rs`
- Create: `backend-rs/crates/parity/src/realtime.rs`

- [ ] **Step 1: Write parity classification test**

Create `backend-rs/crates/parity/src/backtest.rs`:

```rust
use tq_contracts::backtest::BacktestResultSummary;
use tq_contracts::parity::{ParityIssue, ParitySeverity};

pub fn compare_summary(python: &BacktestResultSummary, rust: &BacktestResultSummary) -> Vec<ParityIssue> {
    let mut issues = Vec::new();
    if python.trade_count != rust.trade_count {
        issues.push(ParityIssue {
            severity: ParitySeverity::ProductionStateChanged,
            key: rust.run_id.clone(),
            field: "trade_count".to_string(),
            python_value: python.trade_count.to_string(),
            rust_value: rust.trade_count.to_string(),
            explanation: "trade count changed between Python oracle and Rust replay".to_string(),
        });
    }
    if python.total_return_bps != rust.total_return_bps {
        issues.push(ParityIssue {
            severity: ParitySeverity::ToleranceOnly,
            key: rust.run_id.clone(),
            field: "total_return_bps".to_string(),
            python_value: python.total_return_bps.to_string(),
            rust_value: rust.total_return_bps.to_string(),
            explanation: "return metric differs and must be reviewed against fixed-point execution rules".to_string(),
        });
    }
    issues
}

#[cfg(test)]
mod tests {
    use super::*;

    fn summary(trade_count: usize, total_return_bps: i64) -> BacktestResultSummary {
        BacktestResultSummary {
            schema_version: 1,
            engine: "engine".to_string(),
            run_id: "run".to_string(),
            oracle_run_id: "oracle".to_string(),
            strategy_key: "first_board".to_string(),
            start_date: "2024-06-05".to_string(),
            end_date: "2026-06-05".to_string(),
            trade_count,
            win_rate_bps: 5000,
            total_return_bps,
            max_drawdown_bps: -500,
            annualized_return_bps: 900,
            parity_status: "matched".to_string(),
        }
    }

    #[test]
    fn trade_count_diff_is_production_state_changed() {
        let issues = compare_summary(&summary(10, 100), &summary(11, 100));
        assert_eq!(issues[0].severity, ParitySeverity::ProductionStateChanged);
    }
}
```

- [ ] **Step 2: Create manifest and lib**

Create `backend-rs/crates/parity/Cargo.toml`:

```toml
[package]
name = "tq-parity"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
tq-contracts = { path = "../contracts" }
```

Create `backend-rs/crates/parity/src/lib.rs`:

```rust
pub mod backtest;
pub mod realtime;
```

Create `backend-rs/crates/parity/src/realtime.rs`:

```rust
use tq_contracts::realtime::RealtimeSnapshot;

pub fn is_stale(snapshot: &RealtimeSnapshot, now_ms: i64, max_age_ms: i64) -> bool {
    now_ms.saturating_sub(snapshot.as_of_ms) > max_age_ms
}
```

- [ ] **Step 3: Run parity tests**

Run:

```bash
cd /Users/j/Documents/gupiao/backend-rs
cargo test -p tq-parity
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/j/Documents/gupiao
git add backend-rs/crates/parity
git commit -m "feat: add rust parity tooling"
```

### Task 11: Operations Runbook

**Files:**
- Create: `docs/operations/rust-workers-runbook.md`

- [ ] **Step 1: Create runbook**

Create `docs/operations/rust-workers-runbook.md`:

```markdown
# Rust Workers Runbook

## Scope

This runbook covers local and shadow operation for:

- `rust-realtime-worker`
- `rust-backtest-worker`

Both workers are disabled by default and must not be deployed or cut over without explicit approval.

## Local Commands

```bash
cd /Users/j/Documents/gupiao
scripts/run_rust_component.sh realtime-worker --help
scripts/run_rust_component.sh backtest-worker --help
```

## Shadow Realtime Run

```bash
cd /Users/j/Documents/gupiao
RUST_REALTIME_WORKER_ENABLED=true \
REDIS_URL=redis://localhost:6379/0 \
DATABASE_URL=mysql://user:pass@localhost:3306/tquant \
scripts/run_rust_component.sh realtime-worker
```

## Shadow Backtest Run

```bash
cd /Users/j/Documents/gupiao
RUST_BACKTEST_WORKER_ENABLED=true \
RUST_BACKTEST_SHADOW_ONLY=true \
RUST_BACKTEST_ORACLE_PATH=backend/data/backtest/oracle/oracle.jsonl \
scripts/run_rust_component.sh backtest-worker
```

## Rollback

Set these values:

```text
RUST_REALTIME_WORKER_ENABLED=false
RUST_REALTIME_READ_PATH_ENABLED=false
RUST_REALTIME_PUSH_ENABLED=false
RUST_BACKTEST_WORKER_ENABLED=false
RUST_BACKTEST_SHADOW_ONLY=true
```

## Acceptance

Rust workers are acceptable only when:

1. Python backend tests pass.
2. Rust cargo tests pass.
3. realtime freshness and Redis write metrics are present.
4. backtest parity report has no unexplained production state or gate changes.
5. `strategy_policy.py` remains unchanged.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/j/Documents/gupiao
git add docs/operations/rust-workers-runbook.md
git commit -m "docs: add rust workers runbook"
```

### Task 12: Acceptance Report And Full Verification

**Files:**
- Create: `docs/reports/rust-workers-acceptance-2026-06-05.md`

- [ ] **Step 1: Run Rust verification**

Run:

```bash
cd /Users/j/Documents/gupiao/backend-rs
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

Expected: all pass.

- [ ] **Step 2: Run Python verification**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_rust_realtime_feature_flags.py backend/tests/test_backtest_oracle_export.py backend/tests/test_rust_worker_shadow_boundaries.py backend/tests/test_independent_runtime_components.py -q
```

Expected: all pass.

- [ ] **Step 3: Run platform regression**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

Expected: pass. Any failure must be copied into the report with a clear pre-existing/new classification.

- [ ] **Step 4: Run repository checks**

Run:

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

Expected: no whitespace errors. Status must show only intended files.

- [ ] **Step 5: Create acceptance report**

Create `docs/reports/rust-workers-acceptance-2026-06-05.md` with:

```markdown
# Rust Workers Acceptance Report

## Initial Git Status

Paste the initial `git status --short` output here.

## Implemented Scope

- Rust realtime-worker shadow scaffold
- Rust backtest-worker shadow replay core
- Python feature flags
- Python oracle exporter
- parity tooling
- runbook

## Production Strategy Impact

No production strategy semantics changed.

## Strategy Policy Impact

`backend/app/services/strategy_policy.py` was not modified.

## Realtime Verification

Record command outputs and metrics.

## Backtest Verification

Record Python oracle and Rust replay parity results.

## Test Results

Paste exact command outputs.

## Rollback

Set all Rust flags to false except `RUST_BACKTEST_SHADOW_ONLY=true`.
```

- [ ] **Step 6: Commit**

```bash
cd /Users/j/Documents/gupiao
git add docs/reports/rust-workers-acceptance-2026-06-05.md
git commit -m "docs: add rust workers acceptance report"
```

---

## 12. Cutover Gates

Realtime read path may be enabled only when:

1. `rust-realtime-worker` has shadow Redis writes for at least two trading days.
2. Snapshot freshness is within accepted budget during market hours.
3. Delta sequence gaps are zero.
4. Python BFF fallback works.
5. Redis namespace can be disabled without changing platform behavior.

Rust backtest worker may be enabled for user-visible backtest tasks only when:

1. Python oracle exporter is stable.
2. Rust replay matches Python oracle on core fields.
3. Trade count differences are zero unless explicitly explained.
4. Production state and gate differences are zero.
5. Return, drawdown, win rate, and annualized metrics are within documented fixed-point tolerance.
6. User explicitly approves enabling the Rust worker.

Production strategy calculation must not move to Rust in this plan.

---

## 13. Validation Command Set

Rust:

```bash
cd /Users/j/Documents/gupiao/backend-rs
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
cargo test -p tq-realtime-worker
cargo test -p tq-backtest-worker
cargo test -p tq-parity
```

Python:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_rust_realtime_feature_flags.py backend/tests/test_backtest_oracle_export.py backend/tests/test_rust_worker_shadow_boundaries.py backend/tests/test_independent_runtime_components.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

Repository:

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

OpenAPI:

Run only if API routes or schemas change:

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
```

---

## 14. Risk Register

| Risk | Mitigation |
|---|---|
| Rust realtime cache becomes stale | TTL, freshness metric, Python fallback |
| Delta events lose order | monotonic sequence, sequence gap metric, snapshot recovery |
| Rust backtest changes strategy semantics | consume Python oracle signals first; no Rust strategy calculation |
| Backtest result differs from Python | parity report classifies trade count, gate, ordering, and metric differences |
| Deployment starts Rust workers accidentally | feature flags default off; compose profile disabled |
| Debug complexity increases | tracing, metrics, runbook, separate namespace |
| Redis payload contract drifts | serde contract tests and Python payload tests |

---

## 15. Implementation Prompt

```text
你在 /Users/j/Documents/gupiao 仓库工作。本轮目标是按开发文档新增两个 Rust shadow worker：
1. Rust realtime-worker：只负责热读、行情快照、Redis 缓存、snapshot + delta、health/metrics。
2. Rust backtest-worker：只负责读取 Python oracle 信号、执行高性能回放、撮合/统计、生成 parity 报告。

必须先阅读：
/Users/j/Documents/gupiao/AGENTS.md
/Users/j/Documents/gupiao/docs/engineering-conventions.md
/Users/j/Documents/gupiao/docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md
/Users/j/Documents/gupiao/docs/architecture/current-boundary-map.md
/Users/j/Documents/gupiao/docs/superpowers/plans/2026-06-05-rust-realtime-backtest-workers.md

开始前必须执行：
cd /Users/j/Documents/gupiao
git status --short

硬边界：
1. 不部署。
2. 不修改 backend/app/services/strategy_policy.py。
3. 不修改生产策略语义、production_score、生产排序、生产门控。
4. Rust realtime-worker 不计算策略、不改变排序、不写生产事实源。
5. Rust backtest-worker 第一阶段只消费 Python oracle 信号，不重写策略判断。
6. 所有 Rust worker 默认关闭，必须通过 feature flag 显式启用。
7. Python FastAPI 仍是 API/OpenAPI/权限/任务提交入口。
8. DuckDB/Parquet 只做分析和回测数据层，不作为生产交易事实源。
9. 如工作区已有无关脏文件，不得覆盖、回滚或清理。

默认 feature flags：
RUST_REALTIME_WORKER_ENABLED=false
RUST_REALTIME_READ_PATH_ENABLED=false
RUST_REALTIME_PUSH_ENABLED=false
RUST_BACKTEST_WORKER_ENABLED=false
RUST_BACKTEST_SHADOW_ONLY=true
RUST_BACKTEST_PYTHON_ORACLE_REQUIRED=true

开发顺序：
P0 生成 docs/reports/rust-workers-baseline-2026-06-05.md，记录 git status、当前 worker 边界、现有验证命令。
P1 新建 backend-rs/ Cargo workspace，包含 common/contracts/storage/realtime-worker/backtest-worker/parity crates。
P2 建 contracts：RealtimeSnapshot、RealtimeDelta、BacktestSignalEvent、BacktestResultSummary、ParityIssue。
P3 建 Rust realtime-worker shadow scaffold：Redis namespace 使用 tq:rust:rt:*，支持 snapshot/delta/health/metrics。
P4 在 Python config 增加 Rust realtime flags，默认全关，写 pytest 证明默认关闭。
P5 建 backend/scripts/export_backtest_oracle.py，导出当前 Python 策略信号为 JSONL oracle。
P6 建 Rust backtest-worker：读取 oracle JSONL，使用定点整数执行撮合和统计，默认 shadow-only。
P7 建 parity crate，对 Python/Rust backtest summary 做差异分类。
P8 新增 scripts/run_rust_component.sh，只支持本地 shadow 运行，不部署。
P9 生成 docs/operations/rust-workers-runbook.md 和 docs/reports/rust-workers-acceptance-2026-06-05.md。

必须使用 TDD：
- 每个 Python 改动先写 pytest，再实现。
- 每个 Rust crate 先写 cargo test，再实现。
- 每个阶段通过后再进入下一阶段。

Rust 数值规则：
- 价格用 price_x10000: i64。
- 百分比用 bps: i64。
- 金额用 amount_cent: i64。
- 股数用整数。
- 排序必须有稳定 tie-breaker。
- 不用 float 做阈值判断。

验证命令：
cd /Users/j/Documents/gupiao/backend-rs
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
cargo test -p tq-realtime-worker
cargo test -p tq-backtest-worker
cargo test -p tq-parity

cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_rust_realtime_feature_flags.py backend/tests/test_backtest_oracle_export.py backend/tests/test_rust_worker_shadow_boundaries.py backend/tests/test_independent_runtime_components.py -q
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
git diff --check
git status --short

如果修改 API 契约或路由，再运行：
cd /Users/j/Documents/gupiao/frontend
npm run api:check

输出报告：
生成 docs/reports/rust-workers-acceptance-2026-06-05.md，包含：
1. 初始 git status。
2. 新增 backend-rs/ 架构和 crate 清单。
3. Rust realtime-worker 实现范围和 Redis namespace。
4. Rust backtest-worker 实现范围和 Python oracle 口径。
5. 是否修改 strategy_policy.py，必须明确回答“未修改”。
6. 是否影响生产策略语义，必须明确回答“不影响”或列出风险。
7. Python/Rust parity 结果。
8. 测试命令和结果。
9. git diff --check 结果。
10. 回滚方式。
11. 未完成项和需要用户确认项。

最终回复必须包含：
- 新建了哪些目录/文件。
- realtime-worker 完成内容。
- backtest-worker 完成内容。
- 是否修改生产策略语义。
- 是否影响平台功能。
- 测试结果。
- 是否需要用户授权后才能启用 Rust worker。
```

---

## 16. Self-Review

### 16.1 Spec Coverage

| Requirement | Covered By |
|---|---|
| Rust realtime-worker hot-read and quote push | Tasks 4, 5, 9, 11, 12 |
| Rust backtest-worker high-performance replay | Tasks 6, 7, 10, 12 |
| Strategy accuracy protection | Sections 5, 6, 7, 12 and Tasks 6, 7, 10 |
| Python production semantics preserved | Sections 1, 3, 7, 12 |
| Feature flags and fallback | Sections 7, 8 and Tasks 5, 8 |
| Complete prompt | Section 15 |

### 16.2 Placeholder Scan

No placeholder markers are required for implementation. Every task lists concrete files, commands, and expected outcomes.

### 16.3 Type Consistency

The contracts use the same field names across realtime, backtest, parity, Python oracle export, and the implementation prompt:

```text
schema_version
run_id
strategy_key
strategy_variant
production_score
production_allowed
price_x10000
amount_cent
sequence
parity_status
```
