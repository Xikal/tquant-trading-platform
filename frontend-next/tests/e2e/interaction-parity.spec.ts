import { expect, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { installDataSettingsFixtures } from "./cutover-fixtures";

const shadowFlows = [
  {
    kind: "local-intent",
    route: "/next/data",
    heading: "管理操作解锁",
    field: "粘贴管理员授权令牌",
    value: "ADMIN_TOKEN",
    submitButton: "数据重新拉取",
    doneText: "已基于当前管理员账号记录 [数据重新拉取] 本地维护意图",
  },
  {
    kind: "local-intent",
    route: "/next/settings",
    heading: "QUANT COMMAND 极致量化综合面板",
    field: "粘贴管理员授权令牌",
    value: "ADMIN_TOKEN",
    submitButton: "记录全部意图",
    unlockButton: "解锁管理操作",
    doneText: "[全局配置] 已记录本地配置意图",
  },
] as const;

for (const flow of shadowFlows) {
  test(`${flow.route} supports no-write shadow interaction`, async ({ page }) => {
    await installE2eAuthState(page);
    await installDataSettingsFixtures(page);
    const writeRequests: string[] = [];
    page.on("request", (request) => {
      if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method()) && request.url().includes("/api/")) {
        writeRequests.push(`${request.method()} ${request.url()}`);
      }
    });

    await page.goto(flow.route);
    await expect(page.getByRole("heading", { name: flow.heading })).toBeVisible();

    if (flow.kind === "shadow-panel") {
      const panel = page.getByTestId(flow.testId);
      await panel.getByLabel(flow.field).fill(flow.value);
      await panel.getByRole("button", { name: "确认" }).click();
      await expect(page.getByText(flow.confirmText)).toBeVisible();
      await panel.getByRole("button", { name: flow.submitButton }).click();
    } else if (flow.route === "/next/settings") {
      await page.getByPlaceholder(flow.field).fill(flow.value);
      await page.getByRole("button", { name: flow.unlockButton }).click();
      await page.getByRole("button", { name: flow.submitButton }).click();
    } else {
      const panel = page.getByRole("heading", { name: flow.heading }).locator("xpath=ancestor::article[1]");
      await panel.getByPlaceholder(flow.field).fill(flow.value);
      await panel.getByRole("button", { name: flow.submitButton }).click();
    }

    await expect(page.getByText(flow.doneText)).toBeVisible();
    expect(writeRequests).toEqual([]);
  });
}
