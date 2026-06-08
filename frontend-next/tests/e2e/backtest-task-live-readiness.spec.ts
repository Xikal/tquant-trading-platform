import { expect, test, type Page } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { captureApiWrites, installBacktestFixture } from "./cutover-fixtures";

test("backtest readiness covers create/cancel/validation/optimization intents without real task writes", async ({ page }) => {
  await installE2eAuthState(page);
  await installBacktestFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/backtest");
  await expect(page.getByRole("heading", { name: "回测页" }).first()).toBeVisible();
  await submitShadowPanel(page, "回测提交", "提交回测", "提交回测已记录");
  await page.getByRole("radio", { name: "研究闭环" }).click();
  await submitShadowPanel(page, "回测任务控制", "取消任务", "取消任务已记录");
  await submitShadowPanel(page, "验证与优化", "记录验证/优化", "验证/优化已记录");
  await page.getByRole("radio", { name: "ETF T0" }).click();
  await expect(page.getByText("只读研究")).toBeVisible();
  await expect(page.getByText("¥18.42")).toHaveCount(0);
  await expect(page.getByText("+¥1,600.00")).toHaveCount(0);
  await expect(page.getByText("+¥2,840")).toHaveCount(0);
  expect(writes()).toEqual([]);
});

async function submitShadowPanel(page: Page, title: string, actionLabel: string, doneText: string) {
  const panel = page.getByRole("heading", { name: title }).locator(
    "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' tq-shadow-action-card ') or contains(concat(' ', normalize-space(@class), ' '), ' tq-panel ')][1]",
  );
  await panel.getByRole("button", { name: "确认" }).click();
  await panel.getByRole("button", { name: actionLabel }).click();
  await expect(panel.getByText(doneText, { exact: false }).last()).toBeVisible();
}
