---
name: tquant-strategy-review
description: Review TQuant A-share strategy changes for production readiness, risk boundaries, and sample validity.
---

# TQuant Strategy Review

Use this skill before promoting a strategy from research or observation into production.

## Checklist

1. Confirm the strategy has a declared layer: `production`, `observation`, `research`, or `auxiliary_factor`.
2. Verify sample coverage by trade date, market state, sector heat, and signal state.
3. Require real execution metrics, not only future high-price hit rate.
4. Check hard risk gates: ST, suspended, limit-up/limit-down, stale data, zero price, event risk.
5. Confirm market-state action matrix does not allow new buys in `risk_release` or `high_flyer_retreat`.
6. Verify entry, exit, invalidation, and holding-day hints are explicit.
7. Ensure Agent/AI only explains system results and does not loosen buy rules.

## Output

- Verdict: `pass`, `needs_fix`, or `research_only`.
- Blocking issues.
- Suggested tests and backtest slices.
