# Observability Alerting And Warning Budget Runbook

## Scope

This runbook governs two release gates:

- Go service observability noise: BFF partial source failures and market-read cache fallback behavior.
- Backend test warning budget: pytest warnings must either be fixed or explicitly allowed with a narrow reason and maximum count.

## Warning Budget

Run:

```bash
python scripts/warning_budget.py backend/tests
make warning-budget
```

Budget policy:

- Unexpected warnings fail the gate.
- The only current allowance is one local `NotOpenSSLWarning` from urllib3 when this macOS workspace Python is linked against LibreSSL.
- sklearn `RuntimeWarning` from ML training is not allowed. Logistic ML training must stay numerically quiet.

Why the LibreSSL allowance exists:

- It is emitted at import time by the local Python/OpenSSL build.
- It is not emitted by project business logic.
- It must remain capped at one. More copies usually mean repeated import warnings or an unreviewed warning source.

## Go BFF Partial Source Failures

Metrics:

- `tquant_bff_gateway_partial_source_failures_total`
- `tquant_bff_gateway_partial_source_failures_total{reason="timeout"}`
- `tquant_bff_gateway_partial_source_failures_total{reason="status"}`
- `tquant_bff_gateway_partial_source_failures_total{reason="decode"}`
- `tquant_bff_gateway_partial_source_failures_total{reason="other"}`

Response payloads include `partial_errors[].source`, `partial_errors[].reason`, `partial_errors[].detail`, and `partial_errors[].elapsed_ms`.

Severity:

- `timeout`: warning when repeated. Check slow Python source endpoints, DB latency, and `BFF_SOURCE_TIMEOUT_SECONDS`.
- `status`: warning immediately. A source endpoint returned non-2xx.
- `decode`: warning immediately. A source endpoint returned invalid JSON or incompatible content.
- `other`: warning immediately. Treat as unclassified until root-caused.

## Go Market-Read Cache Fallbacks

Metrics:

- `tquant_market_read_cache_miss_total`: Redis quote cache miss count.
- `tquant_market_read_mysql_fallbacks_total`: Redis miss satisfied by MySQL daily snapshot fallback.
- `tquant_market_read_unresolved_misses_total`: Miss not satisfied by Redis or MySQL fallback.

Severity:

- Redis miss plus MySQL fallback: info normally, warning if volume spikes. It means the service stayed available with stale fallback data.
- Unresolved misses: critical. It means requested symbols could not be served by either cache layer.
- Partial responses: warning if they persist during trading hours.

## Cloud Performance Report

Run:

```bash
python scripts/measure_cloud_go_rust_performance.py
make full-regression-cloud
```

The report contains an `observability` object:

- `max_severity`
- `alerts`
- `bff_partial`
- `market_read`

The script fails only on critical observability alerts. Warning and info alerts are preserved in the report so they can be triaged without blocking every deploy.

## Prometheus Alerts

Alert rules live in `deploy/prometheus/tquant-alerts.yml`.

Required rules:

- `TQuantBffPartialSourceTimeouts`
- `TQuantBffPartialSourceErrors`
- `TQuantMarketReadUnresolvedMisses`
- `TQuantMarketReadMysqlFallbackSpike`

Do not replace reason-specific alerts with only the legacy total counter. The total counter is useful for dashboard trend lines, but it is too coarse for action.

## Regression Commands

Fast focused checks:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_phase4_phase5_foundation.py backend/tests/test_full_regression_runner.py -q -ra
python scripts/warning_budget.py backend/tests/test_phase4_phase5_foundation.py
cd go-services/bff-gateway && go test ./...
cd go-services/market-read-service && go test ./...
```

Full gate:

```bash
python scripts/full_regression_runner.py --profile core --fail-fast
```
