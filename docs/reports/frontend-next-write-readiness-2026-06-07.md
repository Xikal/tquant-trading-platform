# Frontend Next Write Readiness - 2026-06-07

状态：ready
生成时间：2026-06-08T06:40:08.786Z

## Summary

| 项 | 值 |
|---|---:|
| safe write contracts | 13 |
| production-ready contracts | 12 |
| blocked contracts | 0 |
| cutover-excluded contracts | 1 |
| covered write operations | 30 |
| uncovered write operations | 7 |

## Contract Status

| Contract | State | Required mode | Cutover status | Blocker |
|---|---|---|---|---|
| FNX-SW-AUTH-MFA | defined_production_ready | live | ready | - |
| FNX-SW-WATCHLIST | defined_production_ready | live | ready | - |
| FNX-SW-PLAYBOOK-LIFECYCLE | defined_production_ready | live | ready | - |
| FNX-SW-PAPER-ORDER | defined_production_ready | live | ready | - |
| FNX-SW-PAPER-ACCOUNT | defined_production_ready | live | ready | - |
| FNX-SW-STRATEGY-REVIEW | defined_production_ready | live | ready | - |
| FNX-SW-TRADE-JOURNAL | defined_production_ready | live | ready | - |
| FNX-SW-BACKTEST-TASK | defined_production_ready | live | ready | - |
| FNX-SW-DATA-TASK | defined_production_ready | live | ready | - |
| FNX-SW-DATA-REPAIR | defined_production_ready | live | ready | - |
| FNX-SW-SETTINGS-SECTION | defined_production_ready | live | ready | - |
| FNX-SW-FEATURE-FLAG | defined_production_ready | live | ready | - |
| FNX-SW-DATABASE-MAINTENANCE | cutover_excluded | excluded | excluded | contract is excluded from cutover scope; contract state is cutover_excluded; requiredMode is excluded; 1 operations are not ready; 1 operations lack verified static evidence; 1 operations lack rollback smoke evidence |

## Critical Blockers

| Contract | Operations | Reasons |
|---|---|---|
| - | - | - |

## Notes

- 本报告只读 frontend-next registry，不会发送写请求。
- 不得只改状态字符串来关闭阻断项；需要 OpenAPI/generated types、idempotency、audit、403、rollback 和读回一致证据。
- databaseMigrate 默认不纳入 cutover，除非用户另行授权运维变更。
