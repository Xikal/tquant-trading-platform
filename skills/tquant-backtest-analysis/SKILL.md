---
name: tquant-backtest-analysis
description: Interpret TQuant backtest reports with A-share execution realism and anti-overfitting checks.
---

# TQuant Backtest Analysis

## Required Metrics

- Filled signals, unfilled rate, net win rate, average net return, profit factor.
- 1/2/3/4/5 day win rate and return.
- Stop-loss rate, max adverse excursion, drawdown, consecutive losses.
- Market-state, sector-tier, and signal-state buckets.

## Rules

- Do not treat hypothetical high-price hits as the primary win rate.
- Discount strategies with insufficient filled samples.
- Compare recent 3/6/12/24 month windows.
- Separate production, observation, and research strategies.

## Output

- Strategy ranking by stability, not only return.
- Recommended layer changes.
- Thresholds to tighten or loosen.
