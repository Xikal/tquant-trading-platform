# Frontend Bundle Budget Local Readiness - 2026-06-04

Status: local code and tests only. Not deployed, not committed, not pushed.

## Scope

- `npm run analyze` now builds, writes `dist/bundle-report.json`, and runs the same bundle budget gate.
- Bundle budget checks still enforce:
  - first-screen JS gzip <= 350 KB
  - single JS chunk gzip <= 110 KB unless allowlisted with a reason
  - total gzip <= 820 KB
- Heavy ECharts chunks are allowlisted with explicit reasons.
- AntD icons continue to be imported through `frontend/src/ui/icons/index.ts` rather than broad package imports.

## Boundaries

- React, AntD, Vite, and ECharts are unchanged.
- No framework-level npm dependency was added.
- This is a local CI/build guard only and does not deploy anything.

## Local Verification

Planned commands:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `cd frontend && npm run analyze`

Online validation is pending explicit user authorization.
