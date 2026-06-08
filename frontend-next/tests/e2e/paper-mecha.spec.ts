import { expect, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";

test("/next/paper keeps mecha avatar and effects visible before API success", async ({ page }) => {
  await installE2eAuthState(page);
  await page.route("**/*", (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname.startsWith("/api/auth/")) return route.fallback();
    if (pathname.startsWith("/api/")) return route.fulfill({ status: 503, body: "{}" });
    return route.continue();
  });

  await page.goto("/next/paper");

  const hud = page.locator(".paper-mecha-action-panel");
  await expect(hud).toBeVisible();
  await expect(hud.locator(".paper-mecha-action-panel__avatar svg")).toBeVisible();
  await expect(hud.locator("canvas.paper-mecha-action-panel__particles")).toBeAttached();
  await expect(hud.locator(".paper-mecha-action-panel__unit-option")).toHaveCount(5);
  await expect(hud.getByText("实时同步监控日志")).toBeVisible();
  await expect(hud.locator(".paper-mecha-action-panel__status").getByText("暂不可用", { exact: true })).toBeVisible();
  await expect(hud.locator(".paper-mecha-action-panel__status").getByText("数据异常", { exact: true })).toBeVisible();

  await hud.getByRole("button", { name: /零式/ }).click();
  await expect(hud.locator(".paper-mecha-action-panel__status strong").first()).toHaveText("零式·蓝白");
});

test("/next/paper supports workflow tabs and guarded order confirmation without default writes", async ({ page }) => {
  await installE2eAuthState(page);
  const writeRequests: string[] = [];
  page.on("request", (request) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method()) && request.url().includes("/api/")) {
      writeRequests.push(`${request.method()} ${request.url()}`);
    }
  });
  await page.route("**/api/bff/v1/workspace/paper", (route) => route.fulfill({ status: 200, json: paperWorkspaceFixture }));

  await page.goto("/next/paper");
  await expect(page.getByRole("heading", { name: "模拟盘" })).toBeVisible();
  await expect(page.locator(".paper-mecha-action-panel")).toBeVisible();

  await expect(page.getByRole("button", { name: "展开工作流" })).toBeVisible();
  await page.getByRole("button", { name: "展开工作流" }).click();
  await page.getByRole("tab", { name: "记录" }).click();
  await expect(page.getByRole("tabpanel", { name: "记录" })).toBeVisible();
  await expect(page.getByText("策略买入")).toBeVisible();

  await page.getByRole("tab", { name: "详情信息" }).click();
  await expect(page.getByRole("tabpanel", { name: "详情信息" })).toBeVisible();
  await page.getByRole("button", { name: "暂停账户" }).click();
  await expect(page.getByText("暂停账户 已进入二次确认")).toBeVisible();
  await page.getByRole("button", { name: "暂停账户确认" }).click();
  await expect(page.getByText("暂停账户 已记录，本地使用不影响账户状态")).toBeVisible();
  await expect(page.getByTestId("paper-blocked-暂停-恢复账户").getByText("本地记录")).toBeVisible();

  await page.getByTestId("paper-open-order").click();
  await expect(page.getByRole("dialog", { name: "模拟委托" })).toBeVisible();
  await expect(page.getByRole("button", { name: "导入推荐" })).toBeVisible();
  await page.getByRole("button", { name: "导入推荐" }).click();
  await expect(page.getByText("推荐已导入草稿")).toBeVisible();
  await expect(page.getByLabel("数量")).toHaveValue("100");
  await page.getByRole("button", { name: "+500" }).click();
  await expect(page.getByLabel("数量")).toHaveValue("600");
  await expect(page.getByText(/金额/)).toBeVisible();
  await expect(page.getByText(/费用/)).toBeVisible();
  await page.getByRole("button", { name: /600000/ }).click();
  await expect(page.getByText("持仓已导入草稿")).toBeVisible();
  await expect(page.getByLabel("数量")).toHaveValue("900");
  await page.getByLabel("代码").fill("600000");
  await page.getByLabel("数量").fill("200");
  await page.getByLabel("价格").fill("8.72");
  await page.getByTestId("paper-order-form").getByRole("button", { name: "确认" }).click();
  await expect(page.getByText("模拟委托已进入二次确认")).toBeVisible();
  await page.getByTestId("paper-order-form").getByRole("button", { name: "提交委托" }).click();
  await expect(page.getByText("提交委托已记录")).toBeVisible();
  expect(writeRequests).toEqual([]);
});

test("/next/paper virtualizes long positions and workflow tables", async ({ page }) => {
  await installE2eAuthState(page);
  const largeFixture = buildLargePaperFixture(80);
  await page.route("**/api/bff/v1/workspace/paper", (route) => route.fulfill({ status: 200, json: largeFixture }));

  await page.goto("/next/paper");
  await expect(page.getByRole("heading", { name: "模拟盘" })).toBeVisible();
  await expect(page.locator(".paper-mecha-action-panel")).toBeVisible();
  await expect.poll(() => page.locator(".paper-console-position").count()).toBeLessThan(18);

  await page.getByRole("button", { name: "展开工作流" }).click();
  await page.getByRole("tab", { name: "记录" }).click();
  await expect(page.getByRole("tabpanel", { name: "记录" })).toBeVisible();
  await expect.poll(() => page.locator(".tq-virtual-table__row--body").count()).toBeLessThan(40);
});

const paperWorkspaceFixture = {
  api_version: "v1",
  schema_version: "v15",
  generated_at: "2026-06-06 09:45:00",
  account: {
    id: 1,
    name: "默认模拟账户",
    cash_available: 88000,
    frozen_cash: 0,
    initial_cash: 100000,
    market_value: 12000,
    max_drawdown_pct: 3.2,
    realized_pnl: 220,
    status: "active",
    today_pnl: 80,
    today_return_pct: 0.08,
    total_assets: 100220,
    total_return_pct: 0.22,
    unrealized_pnl: 120,
  },
  positions: [
    {
      id: 1,
      symbol: "600000",
      name: "浦发银行",
      quantity: 1000,
      available_quantity: 900,
      frozen_quantity: 100,
      cost_basis: 8.6,
      latest_price: 8.72,
      market_value: 8720,
      unrealized_pnl: 120,
      unrealized_pnl_pct: 1.4,
      opened_at: "2026-06-06T01:30:00Z",
      smart_exit_text: "继续观察",
    },
  ],
  orders: [
    {
      id: 10,
      account_id: 1,
      symbol: "600000",
      name: "浦发银行",
      side: "buy",
      order_type: "limit",
      quantity: 100,
      filled_quantity: 100,
      price: 8.66,
      avg_fill_price: 8.66,
      status: "filled",
      strategy_key: "n_pattern_long_wash",
      reason: "策略买入",
      source: "manual",
      created_at: "2026-06-06T01:31:00Z",
    },
  ],
  trades: [
    {
      id: 3,
      account_id: 1,
      order_id: 10,
      symbol: "600000",
      side: "buy",
      quantity: 100,
      price: 8.66,
      gross_amount: 866,
      net_amount: 866,
      commission: 0,
      stamp_tax: 0,
      transfer_fee: 0,
      commission_warning: "",
      strategy_key: "n_pattern_long_wash",
      entry_reason: "策略买入",
      entry_reason_code: "manual",
      exit_reason: "",
      exit_reason_code: "",
      trade_time: "2026-06-06T01:31:02Z",
    },
  ],
  stock_pnl: {
    summary: {
      account_total_pnl: 220,
      stock_total_pnl: 220,
      realized_pnl: 100,
      unrealized_pnl: 120,
      reconciliation_gap: 0,
      item_count: 1,
    },
    items: [
      {
        symbol: "600000",
        name: "浦发银行",
        buy_quantity: 100,
        sell_quantity: 0,
        current_quantity: 100,
        avg_cost: 8.66,
        realized_pnl: 100,
        unrealized_pnl: 120,
        total_pnl: 220,
        total_fees: 0,
        replay_complete: true,
      },
    ],
  },
  performance: {
    total_return_pct: 0.22,
    win_rate_pct: 55,
    max_drawdown_pct: 3.2,
    total_trades: 3,
    avg_hold_days: 2,
    avg_loss_pct: -1,
    avg_trade_return_pct: 0.7,
    avg_win_pct: 1.5,
    calmar_ratio: 1,
    long_win_rate_pct: 55,
    net_win_rate_pct: 55,
    risk_free_rate_annual_pct: 0,
    sharpe_ratio: 1.2,
    short_win_rate_pct: 0,
    sortino_ratio: 1.4,
    stop_loss_rate_pct: 0,
  },
  strategy_performance: [{ key: "n_pattern_long_wash", total_return_pct: 0.3, avg_return_pct: 0.1, trades: 3 }],
  market_performance: [{ key: "震荡", total_return_pct: 0.2, avg_return_pct: 0.08, trades: 2 }],
  tag_performance: [{ tag: "低吸", total_return_pct: 0.2, avg_return_pct: 0.08, trades: 2, win_rate_pct: 60, net_win_rate_pct: 60 }],
  risk_events: [],
  auto_trading_status: { running: false, engine_running: false, trading_time: true, last_cycle_at: "2026-06-06T01:35:00Z" },
  auto_trading_runs: [{ id: 1, account_id: 1, run_type: "cycle", status: "succeeded", provider: "paper", response: { summary: "复盘完成" }, error_message: "", created_at: "2026-06-06T01:35:00Z" }],
  partial_errors: [],
};

function buildLargePaperFixture(count: number) {
  const positions = Array.from({ length: count }, (_, index) => ({
    ...paperWorkspaceFixture.positions[0],
    id: index + 1,
    symbol: `${600000 + index}`,
    name: `样本持仓${index + 1}`,
    quantity: 100 + index,
    available_quantity: 80 + index,
    unrealized_pnl_pct: index % 2 === 0 ? 1.2 : -0.8,
  }));
  const orders = Array.from({ length: count }, (_, index) => ({
    ...paperWorkspaceFixture.orders[0],
    id: index + 10,
    symbol: `${600000 + index}`,
    quantity: 100 + index,
    reason: `策略买入 ${index + 1}`,
  }));
  const trades = Array.from({ length: count }, (_, index) => ({
    ...paperWorkspaceFixture.trades[0],
    id: index + 3,
    symbol: `${600000 + index}`,
    quantity: 100 + index,
  }));
  const pnlItems = Array.from({ length: count }, (_, index) => ({
    ...paperWorkspaceFixture.stock_pnl.items[0],
    symbol: `${600000 + index}`,
    name: `样本持仓${index + 1}`,
    current_quantity: 100 + index,
  }));
  return {
    ...paperWorkspaceFixture,
    positions,
    orders,
    trades,
    stock_pnl: {
      ...paperWorkspaceFixture.stock_pnl,
      items: pnlItems,
      summary: { ...paperWorkspaceFixture.stock_pnl.summary, item_count: count },
    },
  };
}
