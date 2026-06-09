import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createCoreWorkflowApiMock } from "./smoke-core-workflow-fixtures.mjs";

const baseUrl = (process.env.FRONTEND_SMOKE_URL || "http://127.0.0.1:4173").replace(/\/$/, "");
const scenario = process.env.CORE_WORKFLOW_SMOKE_SCENARIO || "ok";
const staleScenario = scenario === "stale";
const corePaths = ["/monitor", "/playbook", "/settings"];
const reportPath = resolve("dist", `core-workflow-smoke-report${staleScenario ? "-stale" : ""}.json`);

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, serviceWorkers: "block" });
const page = await context.newPage();
const requests = [];
const results = [];
const pageErrors = [];

page.on("request", (request) => {
  const url = new URL(request.url());
  if (url.pathname.startsWith("/api/")) {
    requests.push(url.pathname);
  }
});
page.on("pageerror", (error) => pageErrors.push(String(error.message || error)));
page.on("console", (message) => {
  if (message.type() === "error") {
    pageErrors.push(message.text());
  }
});

await page.addInitScript(() => {
  localStorage.setItem("tquant:auth:persistence_mode", "session");
  sessionStorage.setItem("tquant:auth:access_token", "smoke-token");
  window.EventSource = class SmokeEventSource {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSED = 2;
    readyState = 1;
    url;
    withCredentials = false;

    constructor(url) {
      this.url = String(url);
    }

    addEventListener() {}
    removeEventListener() {}
    dispatchEvent() {
      return true;
    }
    close() {
      this.readyState = 2;
    }
  };
});
await page.route("**/api/**", createCoreWorkflowApiMock({ staleScenario }));

let failed = false;
for (const path of corePaths) {
  const result = await smokePath(path);
  results.push(result);
  if (!result.ok) {
    failed = true;
  }
}

await context.close();
await browser.close();

const bffMonitorCount = requests.filter((item) => item === "/api/bff/v1/workspace/monitor").length;
const report = {
  ok: !failed && bffMonitorCount >= 1,
  scenario,
  base_url: baseUrl,
  generated_at: new Date().toISOString(),
  core_paths: corePaths,
  bff_monitor_count: bffMonitorCount,
  requests,
  results,
  errors: pageErrors.slice(0, 20),
};

await mkdir(resolve("dist"), { recursive: true });
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(reportPath);
if (!report.ok) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}

async function smokePath(path) {
  const started = Date.now();
  const errorsBefore = pageErrors.length;
  let status = 0;
  let visibleText = "";
  let loginGate = false;
  let routeOk = false;
  try {
    const response = await page.goto(`${baseUrl}${path}`, { waitUntil: "networkidle", timeout: 25_000 });
    status = response?.status() || 0;
    await waitForCorePage(path);
    visibleText = await page.locator("body").innerText({ timeout: 5_000 }).catch(() => "");
    loginGate = await page
      .locator('button:has-text("登录进入工作台"), input[autocomplete="username"], input[autocomplete="current-password"]')
      .first()
      .isVisible()
      .catch(() => false);
    routeOk = corePathSignal(path, visibleText);
  } catch (error) {
    pageErrors.push(String(error?.message || error));
  }
  const newErrors = pageErrors.slice(errorsBefore);
  const staleCopyOk = path !== "/monitor" || !staleScenario || /仅供复盘|数据已过期/.test(visibleText);
  return {
    path,
    ok: status > 0
      && status < 500
      && !loginGate
      && routeOk
      && staleCopyOk
      && newErrors.length === 0
      && visibleText.trim().length >= 40,
    status,
    elapsed_ms: Date.now() - started,
    login_gate: loginGate,
    route_signal_ok: routeOk,
    stale_copy_ok: staleCopyOk,
    visible_text_length: visibleText.trim().length,
    errors: newErrors.slice(0, 5),
  };
}

async function waitForCorePage(path) {
  await page.waitForFunction((currentPath) => {
    const text = document.body?.innerText || "";
    if (currentPath === "/monitor") return text.includes("实时监控") || text.includes("实时行动台");
    if (currentPath === "/playbook") return text.includes("选股宝典");
    if (currentPath === "/settings") return text.includes("系统配置");
    return text.length > 40;
  }, path, { timeout: 8_000 }).catch(() => undefined);
}

function corePathSignal(path, text) {
  if (path === "/monitor") return text.includes("实时监控") || text.includes("实时行动台");
  if (path === "/playbook") return text.includes("选股宝典");
  if (path === "/settings") return text.includes("系统配置");
  return true;
}
