# Domain Entry TLS Reset Review - 2026-06-12

## Scope

Read-only D7 network-entry review for the resource contention remediation plan. No nginx reload, no DNS change, no certificate change, no firewall/CDN/WAF change, and no container restart were executed.

## Summary

The cloud service is reachable through the IP HTTPS entry, but `https://weisilianghua.cloud` still resets during TLS ClientHello from the local external client. Server-side curls to the same domain and IP return `200`, so this is not explained by FastAPI, MySQL, runtime-worker, or general cloud CPU/memory pressure.

## Evidence

| Check | Result | Interpretation |
|---|---|---|
| local `curl -vk https://weisilianghua.cloud/readyz` | `curl: (35) Recv failure: Connection reset by peer` after TLS ClientHello | external domain/SNI path fails |
| local `curl -vk --resolve weisilianghua.cloud:443:43.143.243.97 https://weisilianghua.cloud/readyz` | same reset | DNS resolution is not the only cause; SNI/edge/path likely involved |
| local `curl -k -v https://43.143.243.97/readyz` | `HTTP/2 200` | same server IP HTTPS works without domain SNI |
| server-side `curl -vk https://weisilianghua.cloud/readyz` | `HTTP/2 200` | service and local nginx path work from server |
| server-side `curl -vk --resolve weisilianghua.cloud:443:43.143.243.97 https://weisilianghua.cloud/readyz` | `HTTP/2 200` | nginx can serve the SNI locally |
| `sudo nginx -t` | syntax ok, test successful | config parses |
| `sudo nginx -T | sed -n '/server_name/p'` | `weisilianghua.cloud www.weisilianghua.cloud` appears twice | duplicate server block risk |

Certificate observed on IP HTTPS:

- subject: `CN=www.weisilianghua.cloud`
- issuer: Let's Encrypt `E7`
- valid: `May 1 2026` to `Jul 30 2026`

## Impact

- Users reaching the service through `weisilianghua.cloud` may fail before HTTP routing.
- IP HTTPS remains available and `/readyz` returns 200.
- This issue is independent from the D4/D6 cloud resource contention fixes.

## Root Cause Judgment

Most likely causes, in order:

1. Domain/SNI-specific network or security policy between some external clients and the server.
2. Duplicate nginx `server_name` blocks causing ambiguous SNI selection or inconsistent external behavior.
3. Certificate/server-block mismatch or stale enabled-site file.
4. Cloud vendor security/WAF/CDN behavior affecting domain SNI but not direct IP.

The current evidence does not support MySQL, Redis, runtime-worker, scheduler, frontend assets, or Docker resource pressure as the direct cause.

## Recommended Fix Plan

These are not executed in this report and require explicit authorization:

1. Back up nginx enabled-site files.
2. Identify both server blocks containing `server_name weisilianghua.cloud www.weisilianghua.cloud`.
3. Consolidate them into one canonical TLS server block with the expected certificate and proxy target.
4. Run `sudo nginx -t`.
5. Reload nginx only after config review: `sudo systemctl reload nginx`.
6. Re-test from at least two external networks:
   - `curl -vk https://weisilianghua.cloud/readyz`
   - `curl -vk --resolve weisilianghua.cloud:443:43.143.243.97 https://weisilianghua.cloud/readyz`
   - browser page load for `/next/monitor`
7. If reset remains after nginx de-duplication, check cloud security group, CDN/WAF, TCP 443 policy, and domain备案/edge configuration.

## Operations Not Executed

- No nginx reload.
- No nginx file edit.
- No DNS/CDN/WAF/security-group change.
- No Docker operation.
- No `.env` change.
- No DB write.
- No deployment or cutover.
