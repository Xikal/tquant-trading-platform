# Platform Architecture Strategy Engine Shadow

Status: A3 completed  
Date: 2026-06-04  
Scope: Strategy Engine Shadow read path for priority board and strategy tracking

## Change

Strategy Engine output is now attached as optional read-only diagnostics on:

- low-buy priority board items
- strategy tracking items

New fields:

- `strategy_engine_shadow`
- `strategy_engine_decision`
- `strategy_engine_warning_tags`
- `strategy_engine_exclusion_reasons`
- `strategy_engine_score_delta`
- `strategy_engine_parity_status`

The adapter remains a parity/read path. `strategy_engine_adapter_enabled` still
defaults to `false`, and `production_sort_replaced=false` is preserved.

## Boundaries

- Production sorting is not replaced.
- `strategy_policy.py` was not changed.
- `near_entry` remains watch-only.
- `front_row_only` does not emit a production score.
- Research-only strategies do not enter production.
- Frontend labels the output as "影子校验，不影响真实排序".

## Verification

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_strategy_engine_adapter_golden.py \
  backend/tests/test_strategy_engine_boundary.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_strategy_tracking.py \
  -q
```

Result:

```text
36 passed, 1 warning
```

```bash
cd frontend && npm run api:check
```

Result: OpenAPI export, generated types, and TypeScript check passed.

```bash
cd frontend && npm test -- --run \
  src/features/strategy-tracking/StrategyTrackingPage.test.tsx \
  src/features/trading-workspace/MonitorPage.test.tsx \
  src/features/trading-workspace/workspaceViewModels.test.ts
```

Result:

```text
3 passed, 33 tests passed
```

## Production Impact

No production ranking field or production admission rule was replaced. The new
payload is diagnostic only and can be hidden by clients without changing old
behavior.
