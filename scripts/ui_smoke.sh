#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${1:-http://127.0.0.1:18080}"
OUT_SUFFIX="$(
  python3 - <<'PY' "$BASE_URL"
import re
import sys

value = sys.argv[1].strip().lower()
value = re.sub(r"^https?://", "", value)
value = re.sub(r"[^a-z0-9._-]+", "_", value).strip("_")
print(value or "default")
PY
)"
OUT_DIR="$ROOT_DIR/.runtime/ui-smoke/$OUT_SUFFIX"
mkdir -p "$OUT_DIR"

export TQUANT_UI_SMOKE_BASE_URL="$BASE_URL"
export TQUANT_UI_SMOKE_OUT_DIR="$OUT_DIR"

NODE_PATH="$ROOT_DIR/frontend-next/node_modules" node <<'NODE'
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const baseUrl = process.env.TQUANT_UI_SMOKE_BASE_URL;
const outDir = process.env.TQUANT_UI_SMOKE_OUT_DIR;
const username = "ui_smoke";
const password = "UiSmoke12345!";

async function requestJson(page, path, options = {}) {
  const response = await page.request.fetch(`${baseUrl}${path}`, options);
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { raw: text };
  }
  return { response, payload };
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: "chrome" });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  const health = await page.request.get(`${baseUrl}/healthz`);
  if (!health.ok()) {
    throw new Error(`healthz failed: ${health.status()}`);
  }

  let auth = await requestJson(page, "/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    data: { username, password, display_name: "UI Smoke" },
  });
  if (!auth.payload.access_token) {
    auth = await requestJson(page, "/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      data: { username, password },
    });
  }
  if (!auth.payload.access_token) {
    throw new Error(`auth failed: ${JSON.stringify(auth.payload)}`);
  }

  await page.goto(baseUrl, { waitUntil: "networkidle" });
  if (await page.getByPlaceholder("请输入手机号或账号").count()) {
    await page.getByPlaceholder("请输入手机号或账号").fill(username);
    await page.getByPlaceholder("请输入登录密码").fill(password);
    await page.getByRole("button", { name: /登录进入工作台/ }).click();
  }
  await page.getByText("实时监控").waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outDir, "monitor.png"), fullPage: true });

  const tabs = ["量化分析", "选股宝典", "策略工作台"];
  for (const tab of tabs) {
    await page.getByText(tab).first().click();
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(outDir, `${tab}.png`), fullPage: true });
  }

  const blockedByBackdrop = await page.locator(".modal-backdrop, .strategy-dialog-backdrop, .order-modal-backdrop").count();
  if (blockedByBackdrop > 0) {
    throw new Error(`unexpected modal backdrop after navigation: ${blockedByBackdrop}`);
  }

  const ignored = consoleErrors.filter((item) => !/favicon|ResizeObserver/i.test(item));
  if (ignored.length) {
    throw new Error(`console errors: ${ignored.slice(0, 5).join(" | ")}`);
  }
  await browser.close();
  console.log(`ui-smoke:ok screenshots=${outDir}`);
})().catch(async (error) => {
  console.error(error);
  process.exit(1);
});
NODE
