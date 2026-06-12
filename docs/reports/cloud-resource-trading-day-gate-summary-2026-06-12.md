# Cloud Resource Trading Day Gate Summary

- D5 ready: `false`
- Full trading day complete: `false`
- D5 blockers: full_trading_day_observation_incomplete, kernel_oom_logs_present, runtime_nonterminal_task_count=1, runtime_nonterminal_task_count=2, runtime_nonterminal_task_count=4, runtime_worker_memory_pct=99.96, runtime_worker_signal_logs_present, scheduler_provider_warning_lines=160
- Warnings: mysql_slow_queries=117, mysql_slow_queries=133, mysql_slow_queries=55, mysql_slow_queries=71, mysql_slow_queries=72, mysql_slow_queries=89, runtime_nonterminal_task_count=1, runtime_nonterminal_task_count=2, runtime_nonterminal_task_count=4, runtime_worker_signal_logs_present, scheduler_provider_warning_lines=160, scheduler_provider_warning_lines_observed=10, scheduler_provider_warning_lines_observed=5, scheduler_provider_warning_lines_observed=8, swap_used_pct=35.03, swap_used_pct=35.28, swap_used_pct=36.64

## Coverage

| Checkpoint | Required | Observed |
| --- | --- | --- |
| `09:15` | pre-open baseline | yes |
| `09:35` | after open pressure | yes |
| `10:30` | sustained morning load | no |
| `11:30` | midday close | no |
| `13:05` | afternoon reopen | no |
| `14:55` | close pressure | yes |
| `15:10` | post-close tasks | no |
| `15:30` | close-refresh cooldown | no |

## Resource Envelope

| Metric | Value |
| --- | ---: |
| Min memory available MB | 489.0 |
| Max swap used percent | 36.64 |
| Max root used percent | 63.0 |
| Max runtime-worker memory percent | 99.96 |
| Max runtime-scheduler memory percent | 55.54 |
| Max MySQL memory percent | 58.76 |

## Snapshots

| Checkpoint | Generated at | Status | D5 blockers | Warnings |
| --- | --- | --- | --- | --- |
| `premarket-0448` | `2026-06-11T20:48:36.513153+00:00` | `warning` | full_trading_day_observation_incomplete | scheduler_provider_warning_lines_observed=5, mysql_slow_queries=55 |
| `09:15` | `2026-06-12T01:17:20.734698+00:00` | `warning` | full_trading_day_observation_incomplete | scheduler_provider_warning_lines_observed=5, mysql_slow_queries=71 |
| `09:35` | `2026-06-12T01:40:58.015233+00:00` | `warning` | full_trading_day_observation_incomplete, runtime_nonterminal_task_count=1 | runtime_nonterminal_task_count=1, mysql_slow_queries=72 |
| `14:55` | `2026-06-12T07:08:09.940654+00:00` | `blocking` | runtime_worker_memory_pct=99.96, kernel_oom_logs_present, full_trading_day_observation_incomplete, runtime_worker_signal_logs_present, runtime_nonterminal_task_count=4 | swap_used_pct=35.28, runtime_worker_signal_logs_present, scheduler_provider_warning_lines_observed=8, runtime_nonterminal_task_count=4, mysql_slow_queries=89 |
| `postclose-current-2155` | `2026-06-12T13:53:57.912794+00:00` | `warning` | full_trading_day_observation_incomplete, runtime_nonterminal_task_count=1 | scheduler_provider_warning_lines_observed=10, runtime_nonterminal_task_count=1, mysql_slow_queries=133 |
| `postclose-late-2035` | `2026-06-12T12:34:39.424002+00:00` | `blocking` | kernel_oom_logs_present, full_trading_day_observation_incomplete, runtime_worker_signal_logs_present, runtime_nonterminal_task_count=2 | swap_used_pct=36.64, runtime_worker_signal_logs_present, scheduler_provider_warning_lines_observed=10, runtime_nonterminal_task_count=2, mysql_slow_queries=117 |
| `postclose-late-2135` | `2026-06-12T13:31:26.213607+00:00` | `blocking` | kernel_oom_logs_present, full_trading_day_observation_incomplete, scheduler_provider_warning_lines=160, runtime_nonterminal_task_count=1 | swap_used_pct=35.03, scheduler_provider_warning_lines=160, runtime_nonterminal_task_count=1, mysql_slow_queries=133 |

## Operations Not Executed

- This summary reads local JSON snapshots only.
- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
