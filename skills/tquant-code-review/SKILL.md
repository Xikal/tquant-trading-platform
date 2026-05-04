---
name: tquant-code-review
description: Review TQuant code changes for strategy contamination, performance regressions, and API compatibility.
---

# TQuant Code Review

## Focus

- No request-triggered full scans on API hot paths.
- No external data calls inside per-candidate loops without TTL/cache.
- No production strategy threshold changes unless documented.
- User/account isolation for paper trading.
- Agent tools remain read-only by default; write/notify require explicit enablement.
- API responses remain compatible with Web and App clients.

## Output

Prioritize findings as P0/P1/P2/P3 with exact file references and fix guidance.
