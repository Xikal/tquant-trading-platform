# Cloud Resource Remaining Closure Audit

- Generated at: `2026-06-12T14:48:51.068792+00:00`
- Status: `blocked`

## Summary

| Status | Count |
| --- | ---: |
| `complete` | 3 |
| `blocked` | 1 |
| `observation_required` | 1 |
| `needs_authorization` | 2 |
| `needs_investigation` | 2 |
| `partial` | 0 |

## Checks

| ID | Status | Evidence | Next action |
| --- | --- | --- | --- |
| `d5.full_trading_day_observation` | `observation_required` | d5_ready=False; full_trading_day_complete=False; missing_checkpoints=10:30,11:30,13:05,15:10,15:30 | Collect the missing formal trading-day checkpoints and regenerate the D5 summary. |
| `d5.scheduler_embed_cutover` | `blocked` | d5_ready=False; blockers=full_trading_day_observation_incomplete,kernel_oom_logs_present,runtime_nonterminal_task_count=1,runtime_nonterminal_task_count=2,runtime_nonterminal_task_count=4,runtime_worker_memory_pct=99.96,runtime_worker_signal_logs_present,scheduler_provider_warning_lines=160 | If and only if D5 is ready, run the scheduler embed maintenance-window plan with rollback prepared. |
| `mysql.root_cause` | `needs_investigation` | budget_status=ok; mysql_warnings=mysql_slow_queries=117,mysql_slow_queries=133,mysql_slow_queries=145,mysql_slow_queries=55,mysql_slow_queries=71,mysql_slow_queries=72,mysql_slow_queries=89 | Run a slow-query/index/p95 review; change indexes or machine size only after evidence and authorization. |
| `domain.tls_sni_reset` | `needs_authorization` | domain_runbook_present=True | Capture nginx/DNS/CDN/WAF evidence, then authorize a domain-entry maintenance change or provider ticket. |
| `provider.scheduler_warning_residual` | `needs_investigation` | guard_report_present=True; provider_signals=scheduler_provider_warning_lines=160,scheduler_provider_warning_lines_observed=10,scheduler_provider_warning_lines_observed=5,scheduler_provider_warning_lines_observed=8,scheduler_provider_warning_lines=160 | Recheck scheduler logs during the next trading window and tune provider cooldown/cache only with fresh evidence. |
| `runtime_tasks.historical_failed_noise` | `needs_authorization` | historical_failed_noise_recorded=True | Prepare an archive/marking migration and execute only after DB-write authorization and backup confirmation. |
| `legacy_frontend.retirement_guard` | `complete` | frontend_hot_blocked=True; frontend_legacy_blocked=True; legacy_route_findings=0; retired_assets=True; runbook_current=True; legacy_doc_mentions_scope=True | If partial, update runbooks/tests before any frontend deploy. |
| `optional_workers.on_demand_runbook` | `complete` | missing_terms=none | Fill missing runbook terms and keep analytics/backtest/ML/factor outside the always-on profile. |
| `data_quality_sla.non_core_requeue` | `complete` | sla_rollout_recorded=True | Keep DATA_QUALITY_SLA_ENABLED=false in the small-host profile unless analytics-worker is made resident. |

## Operations Not Executed

- This audit reads local reports, runbooks, and source guards only.
- No remote shell command.
- No deployment or cutover.
- No Docker restart/recreate/remove.
- No `.env` change.
- No DB write.
- No nginx/systemd/DNS/CDN change.
