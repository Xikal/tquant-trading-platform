import { expect, type Page, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { installDataSettingsFixtures, installMonitorActionFixture } from "./cutover-fixtures";

test.beforeEach(async ({ page }) => {
  await installE2eAuthState(page);
  await installSliceMocks(page);
});

test("/next/backtest redirects to action desk and does not call backtest APIs", async ({ page }) => {
  const writeRequests = captureWriteRequests(page);
  const backtestRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/backtests")) {
      backtestRequests.push(`${request.method()} ${request.url()}`);
    }
  });
  await installMonitorActionFixture(page);

  await page.goto("/next/backtest");

  await expect(page).toHaveURL(/\/next\/monitor$/);
  await expect(page.getByRole("heading", { name: "我的持仓监测" })).toBeVisible();
  expect(writeRequests).toEqual([]);
  expect(backtestRequests).toEqual([]);
});

test("/next/data shows operations tabs and keeps repair/backfill/task in default protected mode", async ({ page }) => {
  const writeRequests = captureWriteRequests(page);
  await page.goto("/next/data");

  await expect(page.getByRole("heading", { name: "QuantData 实时监控" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "数据完整度检查 (全市场数据集)" })).toBeVisible();
  await expect(page.getByText("低优先级降载")).toBeVisible();
  await expect(page.getByText("暂停积压 2 · 可领取 1")).toBeVisible();

  await page.evaluate(() => window.localStorage.removeItem("tquant:admin_api_token"));
  await page.getByRole("button", { name: "检测可用池范围" }).click();
  await expect(page.getByRole("dialog", { name: "管理授权缺失" })).toBeVisible();
  await expect(page.getByText("当前管理员账号未加载管理授权令牌，仅可查看，不记录维护意图。")).toBeVisible();
  await page.getByRole("button", { name: "确定" }).click();
  await page.getByPlaceholder("粘贴管理员授权令牌").fill("ADMIN_TOKEN");
  await page.getByRole("button", { name: "检测可用池范围" }).click();
  await expect(page.getByText("已基于当前管理员账号记录 [检测可用池范围] 本地维护意图。")).toBeVisible();

  await expect(page.getByRole("heading", { name: "运行时计算集群状况 (Running Workers)" })).toBeVisible();
  await expect(page.getByText("runtime-worker-1")).toBeVisible();
  await expect(page.getByText("calc-engine-0")).toHaveCount(0);
  await expect(page.getByText("sandbox-env")).toHaveCount(0);
  await expect(page.getByText("system-core")).toHaveCount(0);

  await expect(page.getByRole("heading", { name: "高危排错控制台 (24H 故障流)" })).toBeVisible();
  await expect(page.getByText("key_level_snapshots")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "数据重新拉取" })).toBeVisible();
  expect(writeRequests).toEqual([]);
});

test("/next/data keeps QuantData header separated from the dashboard cards", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/next/data");

  await expect(page.getByRole("heading", { name: "QuantData 实时监控" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "今日数据能用吗？" })).toBeVisible();

  const layout = await page.evaluate(() => {
    const header = document.querySelector(".data-terminal-header")?.getBoundingClientRect();
    const firstCard = document.querySelector(".data-terminal-grid--top .data-terminal-card")?.getBoundingClientRect();
    return {
      headerBottom: header?.bottom ?? 0,
      firstCardTop: firstCard?.top ?? 0,
      scrollWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
    };
  });

  expect(layout.headerBottom).toBeLessThanOrEqual(layout.firstCardTop);
  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.viewportWidth + 1);
});

test("/next/settings shows security/governance tabs and keeps config writes in default protected mode", async ({ page }) => {
  const writeRequests = captureWriteRequests(page);
  await page.goto("/next/settings");

  await expect(page.getByRole("heading", { name: "账户安全与 2FA 动态认证" })).toBeVisible();
  await expect(page.getByText("frontend-next e2e").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "大模型底层底座" })).toBeVisible();
  await expect(page.getByText("qwen-plus")).toBeVisible();
  await expect(page.getByText("量价确认")).toBeVisible();
  await expect(page.getByRole("button", { name: "房地产", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ML 机器学习模型深度参数" })).toBeVisible();

  await page.getByRole("button", { name: "记录全部意图" }).click();
  await expect(page.getByText("[全局配置] 当前只读，请先解锁管理操作；页面不会直接写入生产。")).toBeVisible();
  await page.getByPlaceholder("粘贴管理员授权令牌").fill("ADMIN_TOKEN");
  await page.getByRole("button", { name: "解锁管理操作" }).click();
  await expect(page.getByText("已使用当前管理员账号解锁本地编辑。")).toBeVisible();
  await page.getByRole("button", { name: "记录全部意图" }).click();
  await expect(page.getByText("[全局配置] 已记录本地配置意图，正式保存待复验后开启。")).toBeVisible();
  expect(writeRequests).toEqual([]);
});

function captureWriteRequests(page: Page): string[] {
  const writeRequests: string[] = [];
  page.on("request", (request) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method()) && request.url().includes("/api/")) {
      writeRequests.push(`${request.method()} ${request.url()}`);
    }
  });
  return writeRequests;
}

async function installSliceMocks(page: Page) {
  await page.route("**/api/strategies/meta", (route) =>
    route.fulfill({
      status: 200,
      json: {
        strategies: [
          { key: "first_board", name: "首板回调", display_name: "首板回调", enabled: true, visibility: "full", sort_order: 1, tier: "core" },
          { key: "n_pattern_long_wash", name: "N形洗盘研究", display_name: "N形洗盘研究", enabled: true, visibility: "full", sort_order: 2, tier: "research" },
        ],
      },
    }),
  );
  await installDataSettingsFixtures(page);
}
