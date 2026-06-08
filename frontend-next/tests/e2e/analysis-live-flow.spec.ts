import { expect, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { captureApiWrites, installAnalysisFixture, installPaperFixture } from "./cutover-fixtures";

test("analysis readiness covers symbol flow, K line canvas, batch worker sort, and paper draft handoff", async ({ page }) => {
  await installE2eAuthState(page);
  await installAnalysisFixture(page);
  await installPaperFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/analysis");
  await expect(page.getByTestId("analysis-control-start")).toBeDisabled();
  await expect(page.getByTestId("analysis-batch")).toBeDisabled();
  await page.getByLabel("分析代码").fill("600000");
  await expect(page.getByTestId("analysis-control-start")).toBeEnabled();
  await page.getByTestId("analysis-control-start").click();
  await expect(page.getByText("600000 分析完成")).toBeVisible();
  await expect(page.locator(".analysis-kline-frame .chart-frame canvas").first()).toBeVisible();

  await page.getByLabel("批量代码").fill("000001,600000");
  await expect(page.getByTestId("analysis-batch")).toBeEnabled();
  await page.getByTestId("analysis-batch").click();
  await expect(page.getByText("2 个标的批量分析完成")).toBeVisible();
  await expect(page.getByTestId("analysis-batch-results").locator("tbody tr").first()).toContainText("600000");

  await page.getByTestId("analysis-open-paper").click();
  await expect(page).toHaveURL(/\/next\/paper.*source=analysis/);
  await expect(page.getByRole("dialog", { name: "模拟委托" })).toBeVisible();
  await expect(page.getByLabel("代码")).toHaveValue("600000");
  expect(writes()).toEqual(["POST /api/analyze", "POST /api/analyze/batch"]);
});
