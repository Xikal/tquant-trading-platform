import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { buildResolvedAuthHeaders, hashPayload, shapeOf } from "./script-utils.mjs";

const apiBase = process.env.API_BASE || "http://127.0.0.1:8000";
const timeoutMs = Number(process.env.FRONTEND_NEXT_CUTOVER_API_TIMEOUT_MS || 10_000);
const strict = process.argv.includes("--strict") || process.env.FRONTEND_NEXT_API_READINESS_STRICT === "1";
const jsonReportPath = resolve("../docs/reports/frontend-next-api-cutover-readiness-2026-06-07.json");
const markdownReportPath = resolve("../docs/reports/frontend-next-api-cutover-readiness-2026-06-07.md");

const probes = [
  {
    id: "strategy-tracking-items",
    method: "GET",
    path: "/api/strategy-tracking/items?range=60&board_filter=include_all&limit=50&offset=0",
    expected: "2xx; no 422 parameter mismatch",
    blocker: "P0 historical 422",
  },
  {
    id: "settings",
    method: "GET",
    path: "/api/settings",
    expected: "2xx; no 503 environment/config failure",
    blocker: "P0 historical 503",
  },
  {
    id: "settings-factor-weights",
    method: "GET",
    path: "/api/settings/factor-weights",
    expected: "2xx; no 503 factor configuration failure",
    blocker: "P0 historical 503",
  },
  {
    id: "strategy-workspace-bff",
    method: "GET",
    path: "/api/bff/v1/workspace/strategy",
    expected: "2xx BFF strategy payload",
    blocker: "P0 strategy page data availability",
  },
  {
    id: "settings-workspace-bff",
    method: "GET",
    path: "/api/bff/v1/workspace/settings",
    expected: "2xx BFF settings payload",
    blocker: "P0 settings page data availability",
  },
  {
    id: "monitor-workspace-bff",
    method: "GET",
    path: "/api/bff/v1/workspace/monitor?priority_limit=12&sector_limit=8&per_sector_limit=8&hedge_limit=4&view=action",
    expected: "2xx; priority_board returned in service order",
    blocker: "production priority board read path",
  },
];

const startedAt = new Date().toISOString();
const { authHeaders, authStatus } = await resolveAuth();

const results = [];
for (const probe of probes) {
  results.push(await runProbe(probe, authHeaders));
}

const failed = results.filter((item) => item.status !== "ok");
const report = {
  generated_at: startedAt,
  api_base: apiBase,
  auth_status: authStatus,
  strict,
  summary: {
    ok: failed.length === 0,
    probe_count: results.length,
    failed_count: failed.length,
    cutover_ready: failed.length === 0 && authStatus === "resolved",
  },
  probes: results,
  notes: [
    "This is a read-only API readiness probe; it never submits mutations.",
    "A local auto-created smoke token is acceptable for local integration evidence, but formal cutover still needs an approved validation account/token.",
    "strategy-tracking/items, settings and factor-weights are kept as explicit P0 probes because they previously returned 422/503.",
  ],
};

mkdirSync(resolve("../docs/reports"), { recursive: true });
writeFileSync(jsonReportPath, `${JSON.stringify(report, null, 2)}\n`);
writeFileSync(markdownReportPath, renderMarkdown(report));
console.log(JSON.stringify({ ok: report.summary.ok, reportPath: jsonReportPath, markdownReportPath, auth_status: authStatus, summary: report.summary }, null, 2));
if (strict && !report.summary.ok) process.exit(1);

async function runProbe(probe, headers) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const url = `${apiBase}${probe.path}`;
  const started = performance.now();
  try {
    const response = await fetch(url, {
      method: probe.method,
      headers,
      signal: controller.signal,
    });
    const elapsedMs = Math.round(performance.now() - started);
    const text = await response.text();
    const payload = parsePayload(text);
    const ok = response.status >= 200 && response.status < 300;
    return {
      ...probe,
      status: ok ? "ok" : "http_error",
      http_status: response.status,
      duration_ms: elapsedMs,
      payload_hash: ok ? await hashPayload(payload) : null,
      response_shape: ok ? shapeOf(payload) : null,
      error_detail: ok ? null : compactError(payload),
    };
  } catch (error) {
    return {
      ...probe,
      status: "network_error",
      http_status: null,
      duration_ms: Math.round(performance.now() - started),
      payload_hash: null,
      response_shape: null,
      error_detail: error instanceof Error ? error.message : String(error),
    };
  } finally {
    clearTimeout(timeout);
  }
}

function parsePayload(text) {
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return text;
  }
}

function compactError(payload) {
  const value =
    typeof payload === "string"
      ? payload
      : payload?.detail ?? payload?.message ?? payload?.error ?? JSON.stringify(payload);
  return String(value).replace(/\s+/g, " ").slice(0, 360);
}

function renderMarkdown(payload) {
  const rows = payload.probes
    .map((probe) => `| ${probe.id} | ${probe.http_status ?? "-"} | ${probe.status} | ${probe.duration_ms} | ${probe.error_detail ?? "-"} |`)
    .join("\n");
  return `# Frontend Next API Cutover Readiness - 2026-06-07

状态：${payload.summary.cutover_ready ? "ready" : "blocked-or-not-formal"}
生成时间：${payload.generated_at}
API Base：${payload.api_base}
Auth：${payload.auth_status}

## Probe Results

| Probe | HTTP | Status | ms | Error |
|---|---:|---|---:|---|
${rows}

## Notes

- 本脚本只读探测，不提交写操作。
- 本地 smoke token 只代表本地联调证据；正式 cutover 仍需正式验收账号/token 复跑。
- 若 strategy-tracking-items 返回 422 或 settings 端点返回 503，cutover 必须阻断。
`;
}

async function resolveAuth() {
  try {
    const headers = await buildResolvedAuthHeaders(apiBase);
    return { authHeaders: headers, authStatus: headers.Authorization ? "resolved" : "missing" };
  } catch (error) {
    return { authHeaders: {}, authStatus: `unresolved: ${error instanceof Error ? error.message : String(error)}` };
  }
}
