# Platform Modular Architecture Phase 5 Acceptance

Date: 2026-06-04.

Scope: Phase 5 only. This pass creates a shared execution-model boundary for
backtest and paper trading semantics. It does not switch existing backtest or
paper routes to new code paths.

## Added Boundary Module

New module:

```text
backend/app/services/execution_model/
```

Files:

- `events.py`
  - `ExecutionSignal`
  - `ExecutionOrder`
  - `ExecutionFill`
  - `ExecutionPosition`
  - `ExitEvent`
- `rules.py`
  - weighted cost basis
  - lot-sized quantity
  - available quantity by date
  - position return percentage
- `portfolio_preview.py`
  - thin adapter over `decision_context.portfolio_executor`
  - keeps max5/max10 delegated to the audited
    `portfolio_backtest_metrics` path
- `recommendations.py`
  - strategy action classifier:
    `retain`, `downgrade`, `default_off`, `delete_candidate`

## Existing Unified Semantics Confirmed

Current code already shares important execution semantics:

- Backtest broker uses `PaperMatchingEngine` and paper fee semantics.
- Backtest portfolio and paper positions both use weighted cost basis and
  quantity lots.
- Portfolio max5/max10 preview delegates to `portfolio_backtest_metrics`.

The new module documents and guards these shared semantics without changing
production behavior.

## Non-Changes

This phase intentionally does not:

- change `BacktestBroker`
- change `BacktestPortfolio`
- change `PaperOrderService`
- change `PaperPositionService`
- change `portfolio_backtest_metrics`
- alter max5/max10 portfolio constraints
- connect any real order or paper scheduler path to new code

## Validation Commands

Command:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_execution_model_boundary.py \
  backend/tests/test_quant_enhancement_completion.py \
  backend/tests/test_low_buy_backtest_isolation.py \
  backend/tests/test_decision_context_portfolio_executor.py \
  -q
```

Expected result:

```text
all tests pass
```

## Phase 5 Verdict

Phase 5 is accepted as an execution-model baseline:

- Shared event objects exist for signal/order/fill/position/exit.
- Shared lot/cost/availability rules are covered by tests.
- max5/max10 remains delegated to the existing audited portfolio function.
- Strategy recommendation actions are standardized.
- Existing backtest and paper behavior is unchanged.

No deployment was performed.
