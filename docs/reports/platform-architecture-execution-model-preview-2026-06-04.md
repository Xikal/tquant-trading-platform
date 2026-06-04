# Platform Architecture Execution Model Preview

Status: A4 completed  
Date: 2026-06-04  
Scope: Execution Model preview/parity on backtest detail

## Change

Backtest result persistence now stores an `execution_model_preview` payload built
from the existing Execution Model parity helper. Backtest detail responses expose
the same payload, and the backtest dashboard renders it as:

```text
执行模型预览：一致性校验，不替换真实收益
```

The preview includes:

- `replacement_enabled=false`
- `final_fact_source=portfolio_backtest_metrics`
- `parity.max_5`
- `parity.max_10`
- `event_counts`
- `max_5`
- `max_10`

## Boundaries

- Backtest facts remain `portfolio_backtest_metrics`.
- No production or paper fact source is replaced.
- Preview is display-only.
- Historical runs without persisted preview return an explicit
  `preview_not_persisted` status instead of pretending parity passed.

## Verification

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_execution_model_boundary.py \
  backend/tests/test_execution_model_backtest_golden.py \
  backend/tests/test_execution_model_paper_golden.py \
  backend/tests/test_backtest_engine_regression.py \
  -q
```

Result:

```text
9 passed, 1 warning
```

```bash
cd frontend && npm run api:check
```

Result: OpenAPI export, generated types, and TypeScript check passed.

```bash
cd frontend && npm test -- --run \
  src/features/backtest/BacktestDashboard.test.tsx \
  src/features/paper/PaperTradingPerformance.test.tsx
```

Result:

```text
2 passed, 5 tests passed
```

## Production Impact

Execution Model remains Preview only. It is not used to replace backtest,
paper, portfolio, or production trading fact sources.
