import { expect, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";

const routes = [
  "/monitor",
  "/next/monitor",
  "/next/monitor/market",
  "/next/strategy-tracking",
  "/next/analysis",
  "/next/playbook",
  "/next/data",
  "/next/settings",
] as const;

for (const route of routes) {
  test(`${route} renders shell`, async ({ page }) => {
    await installE2eAuthState(page);
    await page.goto(route);
    await expect(page.locator(".legacy-main")).toBeVisible();
    await expect(page.locator(".tq-sidebar")).toBeVisible();
  });
}
