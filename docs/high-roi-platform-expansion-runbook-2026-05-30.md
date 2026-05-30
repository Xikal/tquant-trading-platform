# High ROI Platform Expansion Runbook - Batch A+B+C

Scope: Batch A, Batch B, and Batch C. Decision Context minimal storage, hard risk filter, market state master gate, sector/leader confirmation, real portfolio execution preview, advisory-only promotion review, signal attribution, intraday entry research gate, and event risk summary.

## Worker Ownership

| Task Type | Owner | Gate | Notes |
| --- | --- | --- | --- |
| `market_state_gate_refresh` | `runtime-worker` | production traceability, not research/ml/factor gated | Returns the current market gate snapshot. Missing market data must return `reduce` with explicit degraded evidence. |
| `sector_leader_snapshot_refresh` | `runtime-worker` | production traceability, not research/ml/factor gated | Refreshes sector/leader gate evidence for Monitor. Missing sector data must be explicit `research_only` or `no_data`, never fake scores. |
| `hard_risk_context_refresh` | `runtime-worker` | production traceability, not research/ml/factor gated | Batch A hard risk context is written synchronously from signal snapshots and paper order creation. |
| `paper_portfolio_execution_preview` | `runtime-worker` | production traceability, not research/ml/factor gated | Builds Paper max5/max10 preview through the single `portfolio_backtest_metrics` adapter. Requires `account_id`; missing account blocks with reason. |
| `strategy_promotion_review` | `runtime-worker` | advisory-only, not research/ml/factor gated | Writes `strategy_promotion_reviews` from explicit evidence payload. It never creates or applies `StrategyTierOverride`. |
| `signal_attribution_refresh` | `runtime-worker` | production traceability, not research/ml/factor gated | Refreshes signal outcome attribution from existing snapshots and market bars. Missing future bars must return explicit `no_data` evidence. |
| `intraday_entry_snapshot_refresh` | `runtime-worker` | production traceability, not research/ml/factor gated | Computes intraday entry decision snapshots. C0 currently keeps production boost disabled, so missing minute data returns `no_data` and never boosts production score. |
| `event_risk_refresh` | `runtime-worker` | production traceability, not research/ml/factor gated | Refreshes cached event-risk summaries. C0 currently keeps production blocking disabled; missing event sources return `data_quality=missing`. |
| `strategy_24m_duckdb_report` | `analytics-worker` | analytics dependency check | Existing 24M report task. Data-quality failures must be `blocked_by_data`, not silent success. |
| `decision_context_24m_report` | `analytics-worker` | analytics dependency check | Alias of the DuckDB 24M report with decision-context sections. |
| `portfolio_execution_24m_report` | `analytics-worker` | analytics dependency check | Alias of the DuckDB 24M report used to verify portfolio max5/max10 evidence. |

Web containers must keep `WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false`. Do not add polling or recompute loops to Web/API.

## Feature Flags

Batch A flags are declared in `backend/app/core/config.py`:

| Flag | Default | Rollback Behavior |
| --- | --- | --- |
| `DECISION_CONTEXT_ENABLED` | `true` | Disables Batch A production gates and preserves the prior scoring path. |
| `MARKET_GATE_PRODUCTION_ENABLED` | `true` | Market gate returns `allow` with `feature_flag_disabled=true`; priority board production scores are not multiplied. |
| `SECTOR_LEADER_GATE_PRODUCTION_ENABLED` | `true` | Sector/leader gate returns `allow` without extra boost; CORE/AUX production scores use the pre-Batch-B path. |
| `HARD_RISK_FILTER_PRODUCTION_ENABLED` | `true` | Paper order hard-risk snapshot blocks are ignored by the Batch A filter. |
| `INTRADAY_ENTRY_PRODUCTION_BOOST_ENABLED` | `false` | Batch C C0 coverage is insufficient; intraday entry stays research/no_data and never boosts production scores. |
| `EVENT_RISK_PRODUCTION_BLOCK_ENABLED` | `false` | Batch C C0 event-source coverage is insufficient; event risk stays summary/missing and does not block production. |
| `PROMOTION_ENGINE_AUTO_APPLY_ENABLED` | `false` | Permanently false. Promotion review remains advisory-only with `can_apply_override=false`. |

Rollback example:

```bash
DECISION_CONTEXT_ENABLED=false docker compose -f docker-compose.mysql.yml up -d app runtime-worker
```

## Data Dependencies And Blocking

- Market-level missing data: return `reduce`, keep the previous or effective regime in evidence, and keep the production board available with reduced firepower.
- Symbol-level missing data: mark that symbol `research_only`; do not clear the full board.
- ST, delisting risk, inactive status, suspended trading, invalid OHLC, zero liquidity, high event risk, too-new listings, and impossible limit-up/limit-down assumptions block production use.
- Missing limit metadata, stale metadata, or excessive gap risk reduce production confidence with explicit reasons.
- Batch C intraday-entry input gaps: minute/Tick data gaps return `no_data` with explicit coverage evidence. With the current C0 decision, they do not add production score.
- Batch C event-risk input gaps: missing or stale event data returns `data_quality=missing`. With the current C0 decision, it does not block production candidates.

## Batch C C0 Data Availability Gate

Measured locally on 2026-05-31 against `sqlite:///backend/data/t_quant.db`.

Command:

```bash
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend backend/.venv/bin/python - <<'PY'
from sqlalchemy import func, select, distinct
from app.core.database import SessionLocal
from app.models.entities import LowBuyResultSnapshot, MinuteBarSnapshot, TickTradeSnapshot, MarketEventCache
from app.services.low_buy.strategy_policy import participates_in_priority_board

with SessionLocal() as db:
    dates = [row[0] for row in db.execute(select(distinct(LowBuyResultSnapshot.latest_trade_date)).order_by(LowBuyResultSnapshot.latest_trade_date.desc()).limit(10)).all() if row[0]]
    strategies = [row[0] for row in db.execute(select(LowBuyResultSnapshot.strategy_key).distinct()).all() if participates_in_priority_board(str(row[0]))]
    rows = db.execute(
        select(LowBuyResultSnapshot.symbol, LowBuyResultSnapshot.latest_trade_date)
        .where(LowBuyResultSnapshot.latest_trade_date.in_(dates))
        .where(LowBuyResultSnapshot.strategy_key.in_(strategies))
    ).all()
    pairs = {(str(symbol), str(trade_date)) for symbol, trade_date in rows}
    symbols = sorted({symbol for symbol, _ in pairs})
    minute_pairs = db.execute(
        select(MinuteBarSnapshot.symbol, MinuteBarSnapshot.trade_date)
        .where(MinuteBarSnapshot.symbol.in_(symbols))
        .where(MinuteBarSnapshot.trade_date.in_(dates))
        .where(MinuteBarSnapshot.bar_period == "1m")
        .group_by(MinuteBarSnapshot.symbol, MinuteBarSnapshot.trade_date)
    ).all() if pairs else []
    tick_pairs = db.execute(
        select(TickTradeSnapshot.symbol, TickTradeSnapshot.trade_date)
        .where(TickTradeSnapshot.symbol.in_(symbols))
        .where(TickTradeSnapshot.trade_date.in_(dates))
        .group_by(TickTradeSnapshot.symbol, TickTradeSnapshot.trade_date)
    ).all() if pairs else []
    print({
        "window_trade_dates": dates,
        "production_candidate_pairs": len(pairs),
        "minute_pairs_with_1m_bars": len(minute_pairs),
        "tick_pairs_with_trades": len(tick_pairs),
        "minute_latest_trade_date": str(db.execute(select(func.max(MinuteBarSnapshot.trade_date))).scalar() or ""),
        "tick_latest_trade_date": str(db.execute(select(func.max(TickTradeSnapshot.trade_date))).scalar() or ""),
        "event_cache_total_rows": int(db.execute(select(func.count(MarketEventCache.id))).scalar() or 0),
        "event_cache_symbols": int(db.execute(select(func.count(distinct(MarketEventCache.symbol)))).scalar() or 0),
        "event_cache_latest_created_at": str(db.execute(select(func.max(MarketEventCache.created_at))).scalar() or ""),
    })
PY
```

Result:

| Input | Observed |
| --- | ---: |
| Production strategy keys found | `first_board`, `volume_shrink` |
| Latest production candidate dates in window | `2026-05-28`, `2026-04-27` |
| Production candidate symbol/date pairs | 28 |
| 1m minute pairs with bars | 0 |
| 1m minute pair coverage | 0.00% |
| Tick pairs with trades | 0 |
| Tick pair coverage | 0.00% |
| Latest minute trade date in table | `2026-05-27` |
| Latest tick trade date in table | empty |
| Event cache rows / symbols | 2 / 1 |
| Event cache latest created_at | `2026-04-08 11:09:55` |

Decision:

- `INTRADAY_ENTRY_PRODUCTION_BOOST_ENABLED=false` remains the required production default. Batch C C2 must output `no_data`/research evidence when minute or Tick data is missing and must not add production score.
- `EVENT_RISK_PRODUCTION_BLOCK_ENABLED=false` remains the required production default. Batch C C3 may summarize cached events, but the current event cache is too sparse/stale to block production candidates.
- To enable either flag later, rerun C0 on the target production database and require materially complete recent coverage before changing defaults.

## Enqueue And Verify Runtime Tasks

```bash
curl -fsS -X POST "$BASE_URL/api/runtime-tasks" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"market_state_gate_refresh","payload":{},"priority":30,"idempotency_key":"batch-a-market-gate"}'

curl -fsS -X POST "$BASE_URL/api/runtime-tasks" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"hard_risk_context_refresh","payload":{},"priority":30,"idempotency_key":"batch-a-hard-risk"}'

curl -fsS -X POST "$BASE_URL/api/runtime-tasks" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"sector_leader_snapshot_refresh","payload":{"limit":8,"per_sector_limit":10},"priority":30,"idempotency_key":"batch-b-sector-leader"}'

curl -fsS -X POST "$BASE_URL/api/runtime-tasks" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"paper_portfolio_execution_preview","payload":{"account_id":1},"priority":30,"idempotency_key":"batch-b-paper-portfolio-account-1"}'

curl -fsS -X POST "$BASE_URL/api/runtime-tasks" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"strategy_promotion_review","payload":{"strategy_key":"n_pattern_long_wash","sample_count":0,"profit_factor":0,"average_trade_pct":0,"max_drawdown_pct":0,"max5_return_pct":0,"max10_return_pct":0,"quarterly_stability":0,"walk_forward_pass":false,"oos_pass":false},"priority":30,"idempotency_key":"batch-b-promotion-n-pattern-long-wash"}'

curl -fsS -X POST "$BASE_URL/api/runtime-tasks" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"signal_attribution_refresh","payload":{"as_of_date":"2026-05-31","horizons":[1,3,5,10],"limit":200},"priority":30,"idempotency_key":"batch-c-signal-attribution"}'

curl -fsS -X POST "$BASE_URL/api/runtime-tasks" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"intraday_entry_snapshot_refresh","payload":{"symbols":["600000"],"trade_date":"2026-05-31"},"priority":30,"idempotency_key":"batch-c-intraday-entry"}'

curl -fsS -X POST "$BASE_URL/api/runtime-tasks" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"event_risk_refresh","payload":{"symbols":["600000"]},"priority":30,"idempotency_key":"batch-c-event-risk"}'
```

Verify completion:

```bash
docker compose -f docker-compose.mysql.yml logs --tail=200 runtime-worker
docker compose -f docker-compose.mysql.yml exec app python - <<'PY'
from app.core.database import SessionLocal
from app.models.entities import RuntimeTask
with SessionLocal() as db:
    task_types = [
        "market_state_gate_refresh",
        "hard_risk_context_refresh",
        "sector_leader_snapshot_refresh",
        "paper_portfolio_execution_preview",
        "strategy_promotion_review",
        "signal_attribution_refresh",
        "intraday_entry_snapshot_refresh",
        "event_risk_refresh",
    ]
    for row in db.query(RuntimeTask).filter(RuntimeTask.task_type.in_(task_types)).order_by(RuntimeTask.id.desc()).limit(10):
        print(row.id, row.task_type, row.status, row.result_json)
PY
```

## Batch B Acceptance

- Sector/leader production boost is capped at CORE +12 and AUX +6. RESEARCH strategies return `research_only` and never receive a production prior.
- Portfolio execution preview must state that it reuses `portfolio_backtest_metrics`; max5/max10 values must match the 24M report when fed the same `TradeOutcome` set.
- Promotion review must return `can_apply_override=false`; `PROMOTION_ENGINE_AUTO_APPLY_ENABLED` stays false and no worker task may modify `strategy_policy.py`.
- Missing sector, paper account, or promotion evidence data must return `research_only`, `no_data`, or `blocked_by_data` with explicit reasons.

## Decision Context Snapshots

The minimal storage tables are:

- `decision_context_snapshots`
- `signal_outcome_attributions`
- `strategy_promotion_reviews`

Inspect latest blocked or degraded snapshots:

```bash
docker compose -f docker-compose.mysql.yml exec mysql \
  mysql -utquant_app -p"$MYSQL_PASSWORD" t_quant \
  -e "SELECT trade_date,strategy_key,symbol,final_decision,data_quality,gates_json FROM decision_context_snapshots WHERE final_decision IN ('blocked','research_only') OR data_quality <> 'ok' ORDER BY trade_date DESC,id DESC LIMIT 20;"
```

## 24M Report

Regenerate the tracked Markdown summary:

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py --output docs/reports/strategy_24m_duckdb_report.md
```

Online analytics task:

```bash
curl -fsS -X POST "$BASE_URL/api/runtime-tasks" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"strategy_24m_duckdb_report","payload":{"manifest":"latest"},"priority":20,"idempotency_key":"strategy-24m-duckdb-report"}'
```

Expected artifact paths:

- `backend/data/analytics/reports/strategy_24m_duckdb_report.md`
- `backend/data/analytics/reports/strategy_24m_duckdb_report.json`

If critical inputs fail quality checks, the task must record `blocked_by_data` and the report must not be treated as production evidence.

## UI Acceptance

- Monitor page shows a collapsed market gate panel.
- Monitor page shows risk badges.
- Priority board fields include `market_gate_decision`, `market_gate_score`, `market_gate_reasons`, and `market_firepower_multiplier`.
- N-pattern research strategies still have no production score and do not enter the priority board.

## Deferred Scope

Batch C remains out of this run:

- Batch C: signal attribution, intraday entry boost, event risk production blocking, decision context drawer.
