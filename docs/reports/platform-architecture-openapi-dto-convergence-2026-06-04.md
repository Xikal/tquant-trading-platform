# Platform Architecture OpenAPI DTO Convergence

Status: A5 completed  
Date: 2026-06-04  
Scope: frontend API wrapper DTOs

## Change

`frontend/src/api/dataQuality.ts` now derives request and response DTOs from
`frontend/src/generated/api-types.ts`:

- SLA response
- coverage response
- backfill request
- repair request
- runtime fallback status
- trade gate response
- runtime task response

The wrapper keeps stable ViewModel-facing aliases and normalizes optional arrays
from generated schemas to empty arrays, so pages do not need defensive fallback
logic in every component.

## Existing Coverage

- `frontend/src/api/runtimeTasks.ts` already uses generated schemas.
- `frontend/src/api/backtests.ts` already derives core create/list/detail/equity
  and trades DTOs from generated OpenAPI paths.

## Verification

```bash
cd frontend && npm run api:check
```

Result: OpenAPI export, generated types, and TypeScript check passed.

```bash
cd frontend && npm test -- --run \
  src/api/backtests.test.ts \
  src/api/dataQuality.test.ts \
  src/api/base.test.ts
```

Result:

```text
3 passed, 10 tests passed
```

## Production Impact

No API route behavior changed. This is a frontend typing and normalization
change only.
