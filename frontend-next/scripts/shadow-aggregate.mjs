import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const samplesDir = resolve("../docs/reports/frontend-next-shadow-samples");
const reportPath = resolve("../docs/reports/frontend-next-two-day-shadow-run-2026-06-05.json");

const samples = existsSync(samplesDir)
  ? readdirSync(samplesDir)
      .filter((name) => name.endsWith(".json"))
      .map((name) => JSON.parse(readFileSync(resolve(samplesDir, name), "utf8")))
      .sort((a, b) => String(a.generated_at).localeCompare(String(b.generated_at)))
  : [];

const tradingDaySamples = samples.filter((sample) => sample.ok && sample.trading_day);
const days = [...new Set(tradingDaySamples.map((sample) => sample.trading_day))].sort();
const latestByDay = Object.fromEntries(
  days.map((day) => [day, tradingDaySamples.filter((sample) => sample.trading_day === day).at(-1)]),
);
const requestOk = Object.values(latestByDay).every((sample) =>
  sample.request_summary.every((item) => item.next_event_source_count === 0 && item.next_api_request_count <= item.legacy_api_request_count),
);
const apiOk = Object.values(latestByDay).every((sample) => sample.api_summary.every((item) => item.ok && item.status === 200));
const screenshotOk = Object.values(latestByDay).every((sample) => sample.screenshot_summary.every((item) => item.status === "compared"));

const report = {
  generated_at: new Date().toISOString(),
  ok: days.length >= 2 && requestOk && apiOk && screenshotOk,
  trading_days: days,
  sample_count: tradingDaySamples.length,
  latest_by_day: latestByDay,
  gates: {
    at_least_two_trading_days: days.length >= 2,
    api_ok: apiOk,
    request_sse_ok: requestOk,
    screenshot_capture_ok: screenshotOk,
  },
};

mkdirSync(resolve("../docs/reports"), { recursive: true });
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({ ok: report.ok, reportPath, trading_days: days, gates: report.gates }, null, 2));
if (!report.ok) process.exit(1);
