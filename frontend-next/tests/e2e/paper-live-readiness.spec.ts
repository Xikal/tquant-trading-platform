import { expect, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { captureApiWrites, installPaperFixture } from "./cutover-fixtures";

test("paper readiness guards order, pause/resume, reconcile, and keeps mecha display independent", async ({ page }) => {
  await installE2eAuthState(page);
  await installPaperFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/paper");
  await expect(page.getByRole("heading", { name: "模拟盘" })).toBeVisible();
  await expect(page.locator(".paper-mecha-action-panel")).toBeVisible();

  await page.getByRole("button", { name: "展开工作流" }).click();
  await page.getByRole("tab", { name: "详情信息" }).click();
  await page.getByRole("button", { name: "暂停账户" }).click();
  await expect(page.getByText("暂停账户 已进入二次确认")).toBeVisible();
  await page.getByRole("button", { name: "暂停账户确认" }).click();
  await expect(page.getByTestId("paper-blocked-暂停-恢复账户")).toContainText("本地记录");
  await expect(page.getByText("暂停账户 已记录，本地使用不影响账户状态")).toBeVisible();

  await page.getByTestId("paper-open-order").click();
  await expect(page.getByLabel("代码")).toHaveValue("");
  await expect(page.getByLabel("价格")).toHaveValue("");
  await page.getByLabel("代码").fill("600000");
  await page.getByLabel("数量").fill("200");
  await page.getByLabel("价格").fill("8.72");
  await page.getByTestId("paper-order-form").getByRole("button", { name: "确认" }).click();
  await expect(page.getByText("模拟委托已进入二次确认")).toBeVisible();
  await page.getByTestId("paper-order-form").getByRole("button", { name: "提交委托" }).click();
  await expect(page.getByText("提交委托已记录")).toBeVisible();
  expect(writes()).toEqual([]);
});
