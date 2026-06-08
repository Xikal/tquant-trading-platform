import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { chromium } from "playwright";
import { authStatusFromEnv, detectAuthGate, ensureAccessToken, installAuthState, startServer, stopServer } from "./script-utils.mjs";

const pages = [
  ["monitor", "/next/monitor"],
  ["monitor-market", "/next/monitor/market"],
  ["paper", "/next/paper"],
  ["strategy-tracking", "/next/strategy-tracking"],
  ["analysis", "/next/analysis"],
  ["playbook", "/next/playbook"],
  ["backtest", "/next/backtest"],
  ["data", "/next/data"],
  ["settings", "/next/settings"],
];
const viewports = [
  ["1440x900", { width: 1440, height: 900 }],
  ["1280x800", { width: 1280, height: 800 }],
  ["768x1024", { width: 768, height: 1024 }],
  ["390x844", { width: 390, height: 844 }],
];
const ownsServer = !process.env.FRONTEND_NEXT_URL;
const baseURL = process.env.FRONTEND_NEXT_URL || "http://127.0.0.1:5178";
const outputDir = resolve("../docs/reports/frontend-next-visual-consistency-2026-06-07");
const jsonReportPath = resolve(outputDir, "visual-consistency-report.json");
const markdownReportPath = resolve(outputDir, "visual-consistency-report.md");

async function main() {
  const server = ownsServer ? await startServer(5178) : null;
  await ensureAccessToken(process.env.API_BASE || "http://127.0.0.1:8000");
  mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch();
  const results = [];
  try {
    for (const [pageId, route] of pages) {
      for (const [viewportId, viewport] of viewports) {
        const screenshotPath = resolve(outputDir, `${pageId}-${viewportId}.png`);
        mkdirSync(dirname(screenshotPath), { recursive: true });
        results.push(await capture(browser, pageId, route, viewportId, viewport, screenshotPath));
      }
    }
  } finally {
    await browser.close();
    stopServer(server);
  }
  const failed = results.filter((item) => item.status !== "ok");
  const report = {
    generated_at: new Date().toISOString(),
    base_url: baseURL,
    auth_status: authStatusFromEnv(),
    summary: {
      ok: failed.length === 0,
      page_count: pages.length,
      viewport_count: viewports.length,
      capture_count: results.length,
      failed_count: failed.length,
    },
    results,
  };
  writeFileSync(jsonReportPath, `${JSON.stringify(report, null, 2)}\n`);
  writeFileSync(markdownReportPath, renderMarkdown(report));
  console.log(JSON.stringify({ ok: report.summary.ok, reportPath: jsonReportPath, markdownReportPath, outputDir, summary: report.summary }, null, 2));
  if (!report.summary.ok) process.exit(1);
}

async function capture(browser, pageId, route, viewportId, viewport, screenshotPath) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const pageErrors = [];
  const failedApiResponses = [];
  page.on("pageerror", (error) => {
    pageErrors.push(compact(error instanceof Error ? error.message : String(error)));
  });
  page.on("response", (response) => {
    const status = response.status();
    if (status >= 400 && isApiRequest(response.url())) {
      failedApiResponses.push({ status, url: compactApiUrl(response.url()) });
    }
  });
  await installAuthState(page);
  let navigationError = null;
  let appError;
  let horizontalOverflow;
  try {
    await page.goto(`${baseURL}${route}`, { waitUntil: "domcontentloaded", timeout: 12_000 }).catch((error) => {
      navigationError = compact(error instanceof Error ? error.message : String(error));
    });
    await page.waitForLoadState("networkidle", { timeout: 2_500 }).catch(() => undefined);
    await dismissTransientOverlays(page);
    appError = await detectAppError(page);
    horizontalOverflow = await detectHorizontalOverflow(page);
    navigationError = navigationError || (await detectAuthGate(page));
    await page.screenshot({ path: screenshotPath, fullPage: false });
  } finally {
    await context.close();
  }
  const status = navigationError || appError || pageErrors.length || failedApiResponses.length || horizontalOverflow.body_overflow_px > 8 ? "failed" : "ok";
  return {
    page: pageId,
    route,
    viewport: viewportId,
    screenshot: screenshotPath,
    status,
    navigation_error: navigationError,
    app_error: appError,
    page_errors: pageErrors.slice(0, 5),
    failed_api_responses: failedApiResponses.slice(0, 10),
    horizontal_overflow: horizontalOverflow,
  };
}

async function dismissTransientOverlays(page) {
  for (const label of ["今日不再提示", "关闭", "Close"]) {
    const target = page.getByText(label, { exact: true }).first();
    if (await target.isVisible().catch(() => false)) {
      await target.click({ timeout: 1_000 }).catch(() => undefined);
      await page.waitForTimeout(200);
      return;
    }
  }
}

async function detectAppError(page) {
  const bodyText = await page.locator("body").innerText({ timeout: 1_000 }).catch(() => "");
  const patterns = [/页面渲染异常/, /页面渲染时遇到异常/, /API request failed with status\s+\d{3}/i, /Unhandled Runtime Error/i, /Internal Server Error/i];
  if (!patterns.some((pattern) => pattern.test(bodyText))) return null;
  return compact(bodyText, 360);
}

async function detectHorizontalOverflow(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    const bodyOverflowPx = Math.max(0, root.scrollWidth - root.clientWidth);
    const offenders = Array.from(document.querySelectorAll("body *"))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const overflowRight = Math.max(0, Math.ceil(rect.right - root.clientWidth));
        const overflowLeft = Math.max(0, Math.ceil(-rect.left));
        return {
          tag: element.tagName.toLowerCase(),
          className: typeof element.className === "string" ? element.className.slice(0, 120) : "",
          overflowPx: Math.max(overflowLeft, overflowRight),
        };
      })
      .filter((item) => item.overflowPx > 8)
      .sort((a, b) => b.overflowPx - a.overflowPx)
      .slice(0, 8);
    return { body_overflow_px: bodyOverflowPx, offenders };
  });
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
    return compact(value);
  }
}

function compact(value, maxLength = 240) {
  return String(value).replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function renderMarkdown(payload) {
  const rows = payload.results
    .map((item) => `| ${item.page} | ${item.viewport} | ${item.status} | ${item.failed_api_responses.length} | ${item.page_errors.length} | ${item.horizontal_overflow?.body_overflow_px ?? "-"} | ${item.screenshot} |`)
    .join("\n");
  return `# Frontend Next Visual Consistency - 2026-06-07

状态：${payload.summary.ok ? "PASS" : "FAIL"}
生成时间：${payload.generated_at}
Base URL：${payload.base_url}

## Results

| Page | Viewport | Status | Failed API | JS errors | Body overflow px | Screenshot |
|---|---|---|---:|---:|---:|---|
${rows}

## Gate

- 以当前 frontend-next 样式为准，不再和旧前端做像素相似度阻断。
- 阻断项：导航失败、登录门未通过、错误边界、未捕获 JS、失败 API、明显水平溢出。
- 截图目录：${outputDir}
`;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
