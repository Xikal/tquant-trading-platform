import { authStatusFromEnv, buildResolvedAuthHeaders, hashPayload, shapeOf } from "./script-utils.mjs";

const apiBase = process.env.API_BASE || "http://127.0.0.1:8000";
const endpoints = [
  ["/api/bff/v1/workspace/monitor?priority_limit=12&sector_limit=8&per_sector_limit=8&hedge_limit=4&view=action", "monitor-action"],
  ["/api/bff/v1/workspace/monitor?priority_limit=12&sector_limit=8&per_sector_limit=8&hedge_limit=4&view=market", "monitor-market"],
  ["/api/bff/v1/workspace/paper", "paper"],
  ["/api/bff/v1/workspace/strategy", "strategy-tracking"],
  ["/api/backtests/runs", "backtest"],
  ["/api/bff/v1/workspace/settings", "settings"],
];

async function main() {
  const results = [];
  const headers = await buildResolvedAuthHeaders(apiBase);
  for (const [path, page] of endpoints) {
    const started = Date.now();
    try {
      const response = await fetch(`${apiBase}${path}`, { credentials: "include", headers });
      const contentType = response.headers.get("content-type") || "";
      const payload = contentType.includes("json") ? await response.json() : await response.text();
      results.push({
        page,
        path,
        status: response.status,
        ok: response.ok,
        elapsed_ms: Date.now() - started,
        hash: response.ok ? await hashPayload(payload) : null,
        shape: response.ok ? shapeOf(payload) : null,
        note: "Same API contract is consumed by legacy and frontend-next; auth/backend availability controls live parity.",
      });
    } catch (error) {
      results.push({
        page,
        path,
        status: "unreachable",
        ok: false,
        elapsed_ms: Date.now() - started,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
  console.log(JSON.stringify({ apiBase, auth_status: authStatusFromEnv(), results }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
