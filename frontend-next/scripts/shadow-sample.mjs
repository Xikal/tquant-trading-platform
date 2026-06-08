import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

const reportPath = resolve("../docs/reports/frontend-next-shadow-sample-2026-06-05.json");
const samplesDir = resolve("../docs/reports/frontend-next-shadow-samples");
const steps = [
  { key: "apiParity", script: "api-parity.mjs" },
  { key: "requestTrace", script: "request-trace.mjs", env: { START_LEGACY_FRONTEND: "1" } },
  { key: "screenshotParity", script: "screenshot-parity.mjs", env: { START_LEGACY_FRONTEND: "1" } },
];

const startedAt = new Date().toISOString();
const results = {};
let ok = true;

for (const step of steps) {
  const child = spawnSync(process.execPath, [resolve("scripts", step.script)], {
    cwd: resolve("."),
    env: { ...process.env, ...(step.env ?? {}) },
    encoding: "utf8",
    maxBuffer: 1024 * 1024 * 32,
  });

  const payload = parseJsonOutput(child.stdout);
  const stepOk = child.status === 0 && payloadPasses(step.key, payload);
  if (!stepOk) ok = false;
  results[step.key] = {
    ok: stepOk,
    exit_code: child.status,
    payload,
    stderr: child.stderr.trim(),
  };
}

const report = {
  generated_at: new Date().toISOString(),
  started_at: startedAt,
  trading_day: process.env.SHADOW_TRADING_DAY || beijingDate(),
  ok,
  note:
    "One local shadow sample across API payload parity, request/SSE trace, and screenshot parity. Repeat during two real trading-day windows before any cutover.",
  results,
};
report.api_summary = summarizeApi(report.results.apiParity?.payload);
report.request_summary = summarizeRequests(report.results.requestTrace?.payload);
report.screenshot_summary = summarizeScreenshots(report.results.screenshotParity?.payload);

mkdirSync(resolve("../docs/reports"), { recursive: true });
mkdirSync(samplesDir, { recursive: true });
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
writeFileSync(resolve(samplesDir, `${report.trading_day}-${timestampForFile(report.generated_at)}.json`), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({ ok, reportPath, generated_at: report.generated_at }, null, 2));
if (!ok) process.exit(1);

function parseJsonOutput(stdout) {
  const trimmed = stdout.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return { raw: trimmed.slice(0, 20_000) };
  }
}

function payloadPasses(key, payload) {
  if (!payload) return false;
  if (key === "apiParity") return Array.isArray(payload.results) && payload.results.every((item) => item.ok);
  if (key === "requestTrace") {
    return (
      Array.isArray(payload.results) &&
      payload.results.every((item) => !item.nextTrace?.navigation_error && !item.legacyTrace?.navigation_error)
    );
  }
  if (key === "screenshotParity") {
    return (
      Array.isArray(payload.results) &&
      payload.results.every(
        (item) =>
          item.status === "compared" &&
          !item.navigation_error &&
          !item.app_error &&
          !item.page_errors?.length &&
          !item.failed_api_responses?.length,
      )
    );
  }
  return true;
}

function summarizeApi(payload) {
  return Array.isArray(payload?.results)
    ? payload.results.map((item) => ({
        page: item.page,
        status: item.status,
        ok: Boolean(item.ok),
        elapsed_ms: item.elapsed_ms,
        hash: item.hash,
      }))
    : [];
}

function summarizeRequests(payload) {
  return Array.isArray(payload?.results)
    ? payload.results.map((item) => ({
        legacy_route: item.legacyRoute,
        next_route: item.nextRoute,
        legacy_api_request_count: item.legacyTrace?.api_request_count ?? null,
        next_api_request_count: item.nextTrace?.api_request_count ?? null,
        legacy_unique_api_request_count: item.legacyTrace?.unique_api_request_count ?? null,
        next_unique_api_request_count: item.nextTrace?.unique_api_request_count ?? null,
        legacy_event_source_count: item.legacyTrace?.event_source_count ?? null,
        next_event_source_count: item.nextTrace?.event_source_count ?? null,
      }))
    : [];
}

function summarizeScreenshots(payload) {
  return Array.isArray(payload?.results)
    ? payload.results.map((item) => ({
        route: item.route,
        status: item.status,
        navigation_error: item.navigation_error ?? null,
        app_error: item.app_error ?? null,
        page_errors: item.page_errors ?? [],
        failed_api_responses: item.failed_api_responses ?? [],
        style_similarity: item.sample_similarity,
        legacy_similarity: item.legacy_comparison?.sample_similarity ?? null,
        legacy_page_errors: item.legacy_comparison?.page_errors ?? [],
        legacy_failed_api_responses: item.legacy_comparison?.failed_api_responses ?? [],
      }))
    : [];
}

function beijingDate() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function timestampForFile(value) {
  return value.replace(/[:.]/g, "-");
}
