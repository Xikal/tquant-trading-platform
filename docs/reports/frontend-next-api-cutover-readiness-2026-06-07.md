# Frontend Next API Cutover Readiness - 2026-06-07

状态：ready
生成时间：2026-06-08T06:40:16.470Z
API Base：http://43.143.243.97:18090
Auth：resolved

## Probe Results

| Probe | HTTP | Status | ms | Error |
|---|---:|---|---:|---|
| strategy-tracking-items | 200 | ok | 3032 | - |
| settings | 200 | ok | 62 | - |
| settings-factor-weights | 200 | ok | 70 | - |
| strategy-workspace-bff | 200 | ok | 92 | - |
| settings-workspace-bff | 200 | ok | 349 | - |
| monitor-workspace-bff | 200 | ok | 108 | - |

## Notes

- 本脚本只读探测，不提交写操作。
- 本地 smoke token 只代表本地联调证据；正式 cutover 仍需正式验收账号/token 复跑。
- 若 strategy-tracking-items 返回 422 或 settings 端点返回 503，cutover 必须阻断。
