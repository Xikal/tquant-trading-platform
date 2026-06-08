import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { URL } from "node:url";
import { chromium } from "playwright";
import { PNG } from "pngjs";
import { authStatusFromEnv, detectAuthGate, ensureAccessToken, installAuthState, startServer, stopServer } from "./script-utils.mjs";

const pages = [
  ["monitor-action-web.png", "/next/monitor", "/monitor"],
  ["monitor-market-web.png", "/next/monitor/market", "/monitor/market"],
  ["paper-web.png", "/next/paper", "/paper"],
  ["strategy-tracking-web.png", "/next/strategy-tracking", "/strategy-tracking"],
  ["analysis-web.png", "/next/analysis", "/analysis"],
  ["playbook-web.png", "/next/playbook", "/playbook"],
  ["backtest-web.png", "/next/backtest", "/backtest"],
  ["data-console-web.png", "/next/data", "/data"],
  ["settings-web.png", "/next/settings", "/settings"],
];

const ownsServer = !process.env.FRONTEND_NEXT_URL;
const baseURL = process.env.FRONTEND_NEXT_URL || "http://127.0.0.1:5176";
const shouldStartLegacy = process.env.START_LEGACY_FRONTEND === "1";
const legacyBaseURL = process.env.LEGACY_FRONTEND_URL || null;
const referenceDir = resolve("../docs/frontend-next/style-specs/images");
const outputDir = resolve("../docs/reports/frontend-next-screenshots-2026-06-05");
const responsiveViewports = [
  ["1280x800", { width: 1280, height: 800 }],
  ["768x1024", { width: 768, height: 1024 }],
  ["390x844", { width: 390, height: 844 }],
];

async function main() {
  const missing = pages.map(([image]) => resolve(referenceDir, image)).filter((file) => !existsSync(file));
  if (missing.length) {
    throw new Error(`Missing style images: ${missing.join(", ")}`);
  }
  const server = ownsServer ? await startServer(5176) : null;
  const legacyServer = legacyBaseURL || !shouldStartLegacy ? null : await startServer(5179, { cwd: resolve("../frontend") });
  const resolvedLegacyBaseURL = legacyBaseURL || legacyServer?.baseURL || null;
  await ensureAccessToken(process.env.API_BASE || "http://127.0.0.1:8000");
  mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch();
  try {
    const results = [];
    for (const [image, route, legacyRoute] of pages) {
      const output = resolve(outputDir, image);
      mkdirSync(dirname(output), { recursive: true });
      const nextCapture = await captureScreenshot(browser, `${baseURL}${route}`, output, { width: 1440, height: 900 });
      const reference = resolve(referenceDir, image);
      const styleComparison = comparePng(reference, output);
      const responsive = [];
      for (const [label, viewport] of responsiveViewports) {
        const responsiveOutput = resolve(outputDir, `${label}-${image}`);
        const capture = await captureScreenshot(browser, `${baseURL}${route}`, responsiveOutput, viewport);
        responsive.push({
          viewport: label,
          actual: responsiveOutput,
          navigation_error: capture.navigationError,
          app_error: capture.appError,
          page_errors: capture.pageErrors,
          failed_api_responses: capture.failedApiResponses,
          status: capture.navigationError ? "navigation-error" : "captured",
        });
      }
      let legacyComparison = { status: "legacy-not-run" };
      if (resolvedLegacyBaseURL) {
        const legacyOutput = resolve(outputDir, `legacy-${image}`);
        const legacyCapture = await captureScreenshot(browser, `${resolvedLegacyBaseURL}${legacyRoute}`, legacyOutput, { width: 1440, height: 900 }, { failOnPageError: false });
        legacyComparison = {
          legacy_route: legacyRoute,
          legacy_actual: legacyOutput,
          navigation_error: legacyCapture.navigationError,
          app_error: legacyCapture.appError,
          page_errors: legacyCapture.pageErrors,
          failed_api_responses: legacyCapture.failedApiResponses,
          ...comparePng(legacyOutput, output),
        };
      }
      results.push({
        route,
        reference,
        actual: output,
        navigation_error: nextCapture.navigationError,
        app_error: nextCapture.appError,
        page_errors: nextCapture.pageErrors,
        failed_api_responses: nextCapture.failedApiResponses,
        ...styleComparison,
        responsive,
        legacy_comparison: legacyComparison,
      });
    }
    console.log(JSON.stringify({ baseURL, legacyBaseURL: resolvedLegacyBaseURL, auth_status: authStatusFromEnv(), viewport: "1440x900", results }, null, 2));
    const hasFailure = results.some(
      (item) =>
        item.navigation_error ||
        item.status !== "compared" ||
        item.responsive.some((capture) => capture.status !== "captured") ||
        (item.legacy_comparison.status !== "legacy-not-run" && item.legacy_comparison.navigation_error),
    );
    if (hasFailure) process.exitCode = 1;
  } finally {
    await browser.close();
    stopServer(legacyServer);
    stopServer(server);
  }
}

async function captureScreenshot(browser, url, output, viewport, options = {}) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const pageErrors = [];
  const failedApiResponses = [];
  page.on("pageerror", (error) => {
    pageErrors.push(compactErrorText(error instanceof Error ? error.message : String(error)));
  });
  page.on("response", (response) => {
    const status = response.status();
    if (status >= 400 && isApiRequest(response.url())) {
      failedApiResponses.push({
        status,
        url: compactApiUrl(response.url()),
      });
    }
  });
  await installAuthState(page);
  let navigationError = null;
  let appError;
  try {
    await page
      .goto(url, { waitUntil: "domcontentloaded", timeout: 12_000 })
      .catch((error) => {
        navigationError = error instanceof Error ? error.message : String(error);
      });
    await page.waitForLoadState("networkidle", { timeout: 2_500 }).catch(() => undefined);
    await dismissTransientOverlays(page);
    appError = await detectAppError(page);
    const runtimeError = pageErrors.length ? `page-error: ${pageErrors[0]}` : null;
    navigationError = navigationError || (await detectAuthGate(page)) || appError || (options.failOnPageError === false ? null : runtimeError);
    await page.screenshot({ path: output, fullPage: false });
  } finally {
    await context.close();
  }
  return {
    navigationError,
    appError: appError ?? null,
    pageErrors,
    failedApiResponses: failedApiResponses.slice(0, 8),
  };
}

async function dismissTransientOverlays(page) {
  const labels = ["今日不再提示", "关闭", "Close"];
  for (const label of labels) {
    const target = page.getByText(label, { exact: true }).first();
    if (await target.isVisible().catch(() => false)) {
      await target.click({ timeout: 1_000 }).catch(() => undefined);
      await page.waitForTimeout(250);
      break;
    }
  }
}

async function detectAppError(page) {
  const bodyText = await page.locator("body").innerText({ timeout: 1_000 }).catch(() => "");
  const patterns = [
    /页面渲染异常/,
    /页面渲染时遇到异常/,
    /Something went wrong!/i,
    /API request failed with status\s+\d{3}/i,
    /Unhandled Runtime Error/i,
    /Internal Server Error/i,
  ];
  if (!patterns.some((pattern) => pattern.test(bodyText))) return null;
  return `app-error-boundary: ${compactErrorText(bodyText)}`;
}

function isApiRequest(value) {
  try {
    return new URL(value).pathname.startsWith("/api/");
  } catch {
    return false;
  }
}

function compactApiUrl(value) {
  try {
    const parsed = new URL(value);
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return compactErrorText(value, 220);
  }
}

function compactErrorText(value, maxLength = 320) {
  return String(value)
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 4)
    .join(" | ")
    .slice(0, maxLength);
}

function comparePng(referencePath, actualPath) {
  const reference = PNG.sync.read(readFileSync(referencePath));
  const actual = PNG.sync.read(readFileSync(actualPath));
  const sameSize = reference.width === actual.width && reference.height === actual.height;
  const sampleWidth = Math.min(reference.width, actual.width);
  const sampleHeight = Math.min(reference.height, actual.height);
  const step = 12;
  let samples = 0;
  let totalDelta = 0;
  for (let y = 0; y < sampleHeight; y += step) {
    for (let x = 0; x < sampleWidth; x += step) {
      const refIndex = (reference.width * y + x) << 2;
      const actualIndex = (actual.width * y + x) << 2;
      totalDelta +=
        Math.abs(reference.data[refIndex] - actual.data[actualIndex]) +
        Math.abs(reference.data[refIndex + 1] - actual.data[actualIndex + 1]) +
        Math.abs(reference.data[refIndex + 2] - actual.data[actualIndex + 2]);
      samples += 1;
    }
  }
  const maxDelta = samples * 255 * 3;
  const similarity = maxDelta ? 1 - totalDelta / maxDelta : 1;
  return {
    status: sameSize ? "compared" : "size-mismatch",
    reference_size: `${reference.width}x${reference.height}`,
    actual_size: `${actual.width}x${actual.height}`,
    sample_similarity: Number(similarity.toFixed(4)),
  };
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
