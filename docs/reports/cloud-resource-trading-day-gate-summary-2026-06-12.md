# Cloud Resource Trading Day Gate Summary

- D5 ready: `false`
- Full trading day complete: `false`
- D5 blockers: full_trading_day_observation_incomplete
- Warnings: mysql_slow_queries=55, scheduler_provider_warning_lines_observed=5

## Coverage

| Checkpoint | Required | Observed |
| --- | --- | --- |
| `09:15` | pre-open baseline | no |
| `09:35` | after open pressure | no |
| `10:30` | sustained morning load | no |
| `11:30` | midday close | no |
| `13:05` | afternoon reopen | no |
| `14:55` | close pressure | no |
| `15:10` | post-close tasks | no |
| `15:30` | close-refresh cooldown | no |

## Resource Envelope

| Metric | Value |
| --- | ---: |
| Min memory available MB | 1346.0 |
| Max swap used percent | 32.46 |
| Max root used percent | 63.0 |
| Max runtime-worker memory percent | 38.56 |
| Max runtime-scheduler memory percent | 39.85 |
| Max MySQL memory percent | 56.57 |

## Snapshots

| Checkpoint | Generated at | Status | D5 blockers | Warnings |
| --- | --- | --- | --- | --- |
| `premarket-0448` | `2026-06-11T20:48:36.513153+00:00` | `warning` | full_trading_day_observation_incomplete | scheduler_provider_warning_lines_observed=5, mysql_slow_queries=55 |

## Operations Not Executed

- This summary reads local JSON snapshots only.
- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
