# Platform Next Stage B3 Strategy Engine Integration

Date: 2026-06-04

Scope: B3 only. This batch adds a low-buy Strategy Engine adapter in parity mode
and keeps production-facing adoption behind a disabled feature flag. It does not
change existing production sorting, `strategy_policy`, scoring formulas, or
priority board ranking.

## Worktree Gate

Initial B3 status after B2 commit:

```text
?? docs/superpowers/plans/2026-06-04-platform-modular-architecture-next-stage-development-plan.md
```

The untracked plan file remains user-provided authority input and is not staged
by B3.

## Implementation

Added feature flag:

```text
strategy_engine_adapter_enabled=false
```

Added adapter:

- `low_buy_strategy_engine_output(...)`
- source: `low_buy_adapter`
- version: `low-buy-adapter-v1`

Adapter output fields:

- `production_score`
- `watch_score`
- `score_components`
- `exclusion_reasons`
- `warning_tags`
- `metadata.production_decision`
- `metadata.front_row_tier`
- `metadata.score_cap`
- `metadata.production_scoring_config_version`
- `metadata.gate`

The adapter calls the existing `score_low_buy_candidate_for_production(...)` and
`evaluate_strategy_gate(...)`. It does not replace the priority board item
builder and does not sort any production list.

## Golden Parity

Golden fixture:

- strategy: `first_board`
- signal: `soft_buy_now`
- front-row tier: `core_leader`
- adapter hash: `b0bd63801097`

Field parity:

| Field | Result |
| --- | --- |
| `production_score` | equal to existing low-buy scoring |
| `watch_score` | equal to existing low-buy scoring |
| `score_components` | equal to existing low-buy scoring |
| `production_decision` | preserved in metadata |
| `front_row_tier` | preserved in metadata |
| `score_cap` | preserved in metadata |

Guard coverage:

- `near_entry` remains watch-only.
- `research_only` / non-production strategy remains outside production ranking.
- `front_row_only` remains watch-only and does not become a hard production
  filter rewrite.
- Shadow/Paper candidates cannot enter production ranking.
- Hard-risk blocked candidates have no production score.

## Tests

Acceptance command:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_strategy_engine_adapter_golden.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_low_buy_production_scoring.py \
  -q
```

Result before B3 commit: pass.

## Rollback

Set `STRATEGY_ENGINE_ADAPTER_ENABLED=false` or leave the default unchanged. The
adapter is not wired as a production ranking source, so rollback is limited to
hiding adapter display/explanation usage in later read paths.

## Production Sorting Verdict

B3 does not affect production sorting. Existing low-buy, priority board,
front-row weighted, strategy tracking, `production_score`, `priority_score`,
`elite_watch_score`, `buy_signal_state`, and `strategy_policy` behavior remain
unchanged. The Strategy Engine adapter is parity/read-path safe only.
