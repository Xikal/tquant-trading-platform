import { expect, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { captureApiWrites, installDataSettingsFixtures } from "./cutover-fixtures";

test("data and settings readiness show 503/403 states and keep admin writes permission-guarded", async ({ page }) => {
  await installE2eAuthState(page, { isAdmin: false });
  await page.goto("/next/data");
  await expect(page.getByRole("heading", { name: "管理员权限不足" })).toBeVisible();

  await installE2eAuthState(page, { isAdmin: true });
  await installDataSettingsFixtures(page, 503);
  const writes = captureApiWrites(page);
  await page.goto("/next/settings");
  await expect(page.getByRole("heading", { name: "账户安全与 2FA 动态认证" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("API request failed with status 503");

  await page.getByPlaceholder("管理令牌(测试用: ADMIN_TOKEN)").fill("ADMIN_TOKEN");
  await page.getByRole("button", { name: "解锁" }).click();
  await page.getByRole("button", { name: "记录全部意图" }).click();
  await expect(page.getByText("[全局配置] 已记录本地配置意图，正式保存待复验后开启。")).toBeVisible();
  expect(writes()).toEqual([]);
});
