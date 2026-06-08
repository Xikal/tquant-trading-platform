import { expect, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { captureApiWrites, installPlaybookFixture } from "./cutover-fixtures";

test("playbook governance readiness keeps lifecycle actions protected and research-only by default", async ({ page }) => {
  await installE2eAuthState(page);
  await installPlaybookFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/playbook");
  await expect(page.getByRole("heading", { name: /注目核心标的/ })).toBeVisible();
  await expect(page.getByText("平安银行").first()).toBeVisible();
  await page.getByText("浦发银行").first().click();
  await expect(page.getByTestId("playbook-detail")).toContainText("600000");
  await page.getByTestId("playbook-detail").locator("..").getByRole("button", { name: "记录状态" }).click();
  await expect(page.getByText("状态更新已记录")).toBeVisible();
  await page.getByTestId("playbook-open-analysis").click();
  await expect(page).toHaveURL(/\/next\/analysis\?symbol=600000$/);
  expect(writes()).toEqual([]);
});
