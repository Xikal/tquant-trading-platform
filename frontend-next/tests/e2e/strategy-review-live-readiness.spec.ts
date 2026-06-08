import { expect, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { captureApiWrites, installStrategyFixture } from "./cutover-fixtures";

test("strategy review readiness covers filters, detail, journal CRUD intents, and protected default writes", async ({ page }) => {
  await installE2eAuthState(page);
  await installStrategyFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/strategy-tracking");
  await page.getByRole("button", { name: "筛选条件" }).click();
  await page.getByPlaceholder("代码 / 策略 / 说明").fill("600000");
  await page.getByRole("button", { name: "应用" }).click();
  await expect(page.getByTestId("strategy-tracking-table")).toContainText("600000");

  await page.getByRole("button", { name: "查看 600000 详情", exact: true }).click();
  await expect(page.getByTestId("strategy-tracking-detail-panel")).toContainText("浦发银行");
  await page.getByRole("button", { name: "关闭", exact: true }).click();

  await page.getByRole("tab", { name: "复盘中心" }).click();
  await page.getByLabel("复盘理由").fill("cutover readiness journal");
  await page.getByRole("button", { name: "确认" }).last().click();
  await page.getByRole("button", { name: "提交日志" }).click();
  await expect(page.getByText("交易日志已本地记录，正式保存待复验后开启")).toBeVisible();
  await page.getByRole("button", { name: "编辑日志" }).click();
  await page.getByRole("button", { name: "删除日志" }).click();
  await expect(page.getByText("删除日志已本地记录，正式保存待复验后开启")).toBeVisible();
  expect(writes()).toEqual([]);
});
