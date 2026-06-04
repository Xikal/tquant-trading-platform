# Platform Next Stage B4 Execution Model Integration

Date: 2026-06-04

Scope: B4 only. This batch adds execution-model parity previews for existing
backtest and paper outcome data. It does not replace the canonical backtest
engine, paper-trading state mutation, or `portfolio_backtest_metrics`.

## Worktree Gate

Initial B4 status after B3 commit:

```text
?? docs/superpowers/plans/2026-06-04-platform-modular-architecture-next-stage-development-plan.md
```

The untracked plan file remains user-provided authority input and is not staged
by B4.

## Implementation

Added feature flag:

```text
execution_model_shared_rules_enabled=false
```

Added parity preview helpers:

- `build_backtest_execution_model_preview(outcomes)`
- `build_paper_execution_model_preview(outcomes)`

Preview output:

- `mode=parallel_preview`
- `source=backtest|paper`
- signal/order/fill/position/exit event counts
- position summary
- exit reason counts
- max5/max10 preview
- field-level parity against `portfolio_backtest_metrics`
- `final_fact_source=portfolio_backtest_metrics`
- `replacement_enabled=false`

The preview builds shared execution events from existing `TradeOutcome` values
and delegates max5/max10 to the existing audited portfolio execution path. It is
display-only and does not mutate backtest or paper state.

## Golden Parity

Backtest fixture:

- 3 filled outcomes
- event counts: signal/order/fill/position/exit all equal 3
- max5 parity: all tracked fields equal
- max10 parity: all tracked fields equal

Paper fixture:

- 3 filled paper-style outcomes
- position count: 3
- exit reason count: `测试退出=3`
- max5 parity: all tracked fields equal

Tracked parity fields:

- `profit_factor`
- `avg_trade_return_pct`
- `portfolio_return_pct`
- `max_drawdown_pct`
- `trade_count`

## Tests

Acceptance command:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_execution_model_backtest_golden.py \
  backend/tests/test_execution_model_paper_golden.py \
  backend/tests/test_execution_model_position_exit_rules.py \
  backend/tests/test_backtest_engine_regression.py \
  -q
```

`backend/tests/test_backtest_engine_regression.py` was added as the narrow
canonical-engine guard required by the B4 plan.

Supplemental regression command:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_execution_model_boundary.py \
  backend/tests/test_decision_context_portfolio_executor.py \
  backend/tests/test_backtest_v2_engine_contract.py \
  -q
```

Result before B4 commit: pass.

## Production Sorting And Fact Source Verdict

B4 does not affect production sorting, backtest facts, or paper facts. Existing
backtest and paper services remain canonical. `portfolio_backtest_metrics`
remains the final max5/max10 fact source, and the shared execution-model preview
is parallel/read-only.
