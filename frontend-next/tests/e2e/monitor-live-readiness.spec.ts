import { expect, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { captureApiWrites, installMonitorActionFixture } from "./cutover-fixtures";

test("monitor readiness keeps production board order and local watchlist edits no-write", async ({ page }) => {
  await installE2eAuthState(page);
  await installMonitorActionFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/monitor");
  const rows = page.getByTestId("monitor-priority-order-table").locator(".monitor-rank-row");
  await expect(page.getByText("市场修复但仍需确认").first()).toBeVisible();
  await expect(page.getByText("小仓试错").first()).toBeVisible();
  await expect(rows.nth(0)).toContainText("000001");
  await expect(rows.nth(1)).toContainText("600000");
  await expect(rows.nth(0)).toContainText("建议买入区间");
  await expect(rows.nth(0)).toContainText("11.8-12.1");
  await expect(rows.nth(0)).toContainText("买入信号");
  await expect(rows.nth(0)).toContainText("接近买点，等待承接确认");
  await expect(rows.nth(0).getByRole("button", { name: /详情/ })).toBeVisible();

  await page.getByRole("button", { name: "前排加权" }).click();
  await expect(page.getByText("浦发银行").first()).toBeVisible();
  await page.getByRole("button", { name: "解读榜单" }).click();
  await expect(page.getByRole("status")).toContainText("榜单研判解析载入中");

  await page.getByRole("button", { name: "录入" }).click();
  await expect(page.getByRole("dialog", { name: "录入持仓" })).toBeVisible();
  await page.getByLabel("股票名称").fill("测试持仓");
  await page.getByLabel("代码").fill("300001");
  await page.getByRole("button", { name: "记录意图" }).click();
  await expect(page.getByRole("status")).toContainText("已保存更新");
  await expect(page.getByText("测试持仓").first()).toBeVisible();

  await page.getByRole("button", { name: "选股宝典" }).click();
  await expect(page).toHaveURL(/\/next\/playbook$/);
  expect(writes()).toEqual([]);
});
