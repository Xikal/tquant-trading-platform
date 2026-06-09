import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";

const reportPath = new URL("../dist/bundle-report.json", import.meta.url);
const allowlistPath = new URL("../.bundle-allowlist.json", import.meta.url);

const FIRST_SCREEN_GZIP_LIMIT_KB = 350;
const SINGLE_CHUNK_GZIP_LIMIT_KB = 110;
const TOTAL_GZIP_LIMIT_KB = 820;
const MIN_FIRST_SCREEN_REDUCTION_PCT = 20;
const FORBIDDEN_FIRST_SCREEN_PREFIXES = [
  "BacktestPage-",
  "SettingsPage-",
  "DataConsolePage-",
  "StrategyTrackingPage-",
  "echarts-",
];

async function main() {
  const report = await readBundleReport();
  if (!report) {
    return;
  }
  const allowlist = await readAllowlist();
  const violations = checkBundleBudget(report, allowlist);

  if (violations.length) {
    console.error("Bundle budget check failed:");
    console.error(violations.join("\n"));
    process.exit(1);
  }

  console.log("Bundle budget check passed:", {
    first_screen_js_gzip_kb: report.first_screen_js_gzip_kb,
    total_gzip_kb: report.total_gzip_kb,
  });
}

export function checkBundleBudget(report, allowlist = { chunks: {} }) {
  const violations = [];
  const summary = summarizeBundleReport(report);

  if (summary.first_screen_js_gzip_kb > FIRST_SCREEN_GZIP_LIMIT_KB) {
    violations.push(`first_screen_js_gzip_kb ${summary.first_screen_js_gzip_kb}KB exceeds ${FIRST_SCREEN_GZIP_LIMIT_KB}KB`);
  }
  if (summary.total_gzip_kb > TOTAL_GZIP_LIMIT_KB) {
    violations.push(`total_gzip_kb ${summary.total_gzip_kb}KB exceeds ${TOTAL_GZIP_LIMIT_KB}KB`);
  }
  if (
    summary.baseline_first_screen_js_gzip_kb > 0 &&
    summary.first_screen_js_gzip_reduction_pct < MIN_FIRST_SCREEN_REDUCTION_PCT
  ) {
    violations.push(
      `first_screen_js_gzip_reduction_pct ${summary.first_screen_js_gzip_reduction_pct}% is below ${MIN_FIRST_SCREEN_REDUCTION_PCT}% from baseline ${summary.baseline_first_screen_js_gzip_kb}KB`,
    );
  }

  for (const asset of summary.assets) {
    if (isForbiddenFirstScreenAsset(asset)) {
      violations.push(`${asset.file} is a lazy/heavy route chunk but is classified as first-screen-js`);
    }
    if (!asset.file?.endsWith(".js") || asset.gzip_kb <= SINGLE_CHUNK_GZIP_LIMIT_KB) {
      continue;
    }
    const allowed = allowlist.chunks?.[asset.file] ?? allowlist.chunks?.[chunkPrefix(asset.file)];
    if (!allowed?.reason) {
      violations.push(`${asset.file} gzip ${asset.gzip_kb}KB exceeds ${SINGLE_CHUNK_GZIP_LIMIT_KB}KB without allowlist reason`);
    }
  }

  return violations;
}

function isForbiddenFirstScreenAsset(asset) {
  return asset.kind === "first-screen-js"
    && FORBIDDEN_FIRST_SCREEN_PREFIXES.some((prefix) => asset.file?.startsWith(prefix));
}

export function summarizeBundleReport(report) {
  const assets = Array.isArray(report.assets) ? report.assets : [];
  const totalGzipKb = Number.isFinite(report.total_gzip_kb)
    ? Number(report.total_gzip_kb)
    : Number((assets.reduce((sum, item) => sum + Number(item.gzip_kb || 0), 0)).toFixed(2));
  const firstScreenGzipKb = Number.isFinite(report.first_screen_js_gzip_kb)
    ? Number(report.first_screen_js_gzip_kb)
    : Number((assets
      .filter((item) => item.kind === "first-screen-js")
      .reduce((sum, item) => sum + Number(item.gzip_kb || 0), 0)).toFixed(2));
  return {
    total_gzip_kb: totalGzipKb,
    first_screen_js_gzip_kb: firstScreenGzipKb,
    baseline_first_screen_js_gzip_kb: Number(report.baseline_first_screen_js_gzip_kb || 0),
    first_screen_js_gzip_reduction_pct: firstScreenReductionPct(report, firstScreenGzipKb),
    assets,
  };
}

function firstScreenReductionPct(report, currentKb) {
  if (Number.isFinite(report.first_screen_js_gzip_reduction_pct)) {
    return Number(report.first_screen_js_gzip_reduction_pct);
  }
  const baseline = Number(report.baseline_first_screen_js_gzip_kb || 0);
  if (!Number.isFinite(baseline) || baseline <= 0) {
    return 0;
  }
  return Number(((baseline - currentKb) / baseline * 100).toFixed(2));
}

async function readBundleReport() {
  if (!existsSync(reportPath)) {
    console.log("Bundle budget check skipped: dist/bundle-report.json is not built yet.");
    return null;
  }
  return JSON.parse(await readFile(reportPath, "utf8"));
}

async function readAllowlist() {
  if (!existsSync(allowlistPath)) {
    return { chunks: {} };
  }
  return JSON.parse(await readFile(allowlistPath, "utf8"));
}

function chunkPrefix(file) {
  return file.replace(/-[^-]+\.js$/, "");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
