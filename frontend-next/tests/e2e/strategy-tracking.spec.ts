import { expect, test, type Page } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";

test("strategy tracking filters, detail tabs, and review shadow writes stay no-write", async ({ page }) => {
  await installE2eAuthState(page);
  await installStrategyTrackingRoutes(page);
  const writeRequests: string[] = [];
  const initialReadRequests: string[] = [];
  page.on("request", (request) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method()) && request.url().includes("/api/")) {
      writeRequests.push(`${request.method()} ${request.url()}`);
    }
    const requestPath = new URL(request.url()).pathname;
    if (request.method() === "GET" && requestPath.startsWith("/api/") && !requestPath.startsWith("/api/auth/")) {
      initialReadRequests.push(request.url());
    }
  });

  await page.goto("/next/strategy-tracking");
  await expect(page.getByRole("heading", { name: "策略跟踪" }).first()).toBeVisible();
  await expect(page.getByTestId("strategy-tracking-table")).toContainText("000001");
  expect(initialReadRequests.filter((url) => url.includes("/api/bff/v1/workspace/strategy"))).toHaveLength(1);
  expect(initialReadRequests.filter((url) => url.includes("/api/strategy-tracking/items"))).toHaveLength(0);
  expect(initialReadRequests.filter((url) => url.includes("/api/strategy-tracking/summary"))).toHaveLength(0);
  expect(initialReadRequests, initialReadRequests.join("\n")).toHaveLength(1);

  await page.getByRole("button", { name: "筛选条件" }).click();
  await expect(page.getByRole("dialog", { name: "筛选条件" })).toBeVisible();
  await page.getByPlaceholder("代码 / 策略 / 说明").fill("600000");
  await expect(page.getByTestId("strategy-tracking-filter-summary")).toContainText("600000");
  await page.getByRole("button", { name: "应用" }).click();
  await expect(page.getByTestId("strategy-tracking-table")).toContainText("600000");
  await expect(page.getByTestId("strategy-tracking-table")).not.toContainText("000001");

  await page.getByRole("button", { name: "查看 600000 详情", exact: true }).click();
  await expect(page.getByTestId("strategy-tracking-detail-panel")).toContainText("浦发银行");
  await page.getByRole("button", { name: "关闭", exact: true }).click();

  await page.getByRole("tab", { name: "持有" }).click();
  await expect(page.getByTestId("strategy-tracking-tabs")).toContainText("短线 1-3 天");
  await page.getByRole("tab", { name: "复盘中心" }).click();
  await expect(page.getByTestId("strategy-tracking-review-center")).toContainText("交易日志");

  await page.getByLabel("复盘理由").fill("e2e 纪律记录");
  await page.getByRole("button", { name: "确认" }).last().click();
  await expect(page.getByText("交易日志已进入二次确认")).toBeVisible();
  await page.getByRole("button", { name: "提交日志" }).click();
  await expect(page.getByText("交易日志已本地记录，正式保存待复验后开启")).toBeVisible();
  await page.getByRole("button", { name: "编辑日志" }).click();
  await expect(page.getByText("编辑日志已本地记录，正式保存待复验后开启")).toBeVisible();
  await page.getByRole("button", { name: "删除日志" }).click();
  await expect(page.getByText("删除日志已本地记录，正式保存待复验后开启")).toBeVisible();
  expect(writeRequests).toEqual([]);
});

async function installStrategyTrackingRoutes(page: Page) {
  const items = [
    {
      id: "item-000001",
      symbol: "000001",
      name: "平安银行",
      strategy_key: "n_pattern",
      strategy_name: "N形洗盘低吸",
      signal_state: "buy_ready",
      signal_text: "确定可买",
      lifecycle_status: "active",
      lifecycle_status_text: "跟踪中",
      plain_language_summary: "回踩支撑后放量",
      current_return_pct: 0.034,
      max_gain_pct: 0.061,
      max_drawdown_pct: -0.018,
      best_holding_days: 3,
      hold_extension_text: "可持有",
      needs_review: false,
      board_type: "main",
    },
    {
      id: "item-600000",
      symbol: "600000",
      name: "浦发银行",
      strategy_key: "mean_revert",
      strategy_name: "均值回归观察",
      signal_state: "watch",
      signal_text: "观察确认",
      lifecycle_status: "review",
      lifecycle_status_text: "需复盘",
      plain_language_summary: "冲高回落，等待纪律复盘",
      current_return_pct: -0.012,
      max_gain_pct: 0.028,
      max_drawdown_pct: -0.045,
      failure_reason_text: "回落过快",
      review_text: "观察池只提醒复盘",
      best_holding_days: 2,
      needs_review: true,
      abnormal_return: true,
      board_type: "main",
    },
  ];
  await page.route("**/api/bff/v1/workspace/strategy", (route) => route.fulfill({ status: 200, json: { items, summary: { total: 2, needs_review_count: 1 } } }));
  await page.route("**/api/strategy-tracking/items*", (route) => route.fulfill({ status: 200, json: { items, total: 2, limit: 50, offset: 0, summary: { total: 2, needs_review_count: 1 } } }));
  await page.route("**/api/strategy-tracking/summary*", (route) => route.fulfill({ status: 200, json: { total: 2, needs_review_count: 1, win_rate_5d: 0.62, drift_count: 1 } }));
  await page.route("**/api/strategy-tracking/performance*", (route) => route.fulfill({ status: 200, json: [{ strategy_key: "n_pattern", strategy_name: "N形洗盘低吸", recommendation_count: 12, win_rate_5d: 0.64, avg_current_return_pct: 0.021, health_grade: "ok" }] }));
  await page.route("**/api/strategy-tracking/holding-analysis*", (route) => route.fulfill({ status: 200, json: { data_quality: "ok", items: [{ strategy_key: "n_pattern", strategy_name: "N形洗盘低吸", conclusion: "短线 1-3 天", dominant_holding_bucket_text: "短线 1-3 天", short_hold_ratio: 0.7, swing_hold_ratio: 0.2, trend_hold_ratio: 0.1 }] } }));
  await page.route("**/api/strategy-tracking/review*", (route) => route.fulfill({ status: 200, json: { needs_review_items: [items[1]], abnormal_return_items: [items[1]], failure_tags: { 回落过快: 1 }, market_segments: [] } }));
  await page.route("**/api/strategy-tracking/items/item-600000", (route) => route.fulfill({ status: 200, json: { item: items[1], review_text: "观察池只提醒复盘", timeline: [{ trade_date: "2026-06-05", close: 8.6, current_return_pct: -0.012, holding_day: 1 }], markers: [{ kind: "review", label: "跌破短线支撑", trade_date: "2026-06-05" }] } }));
  await page.route("**/api/trading-experience/trade-journal*", (route) => route.fulfill({ status: 200, json: { enabled: true, total: 1, items: [{ entry_id: 1, symbol: "600000", action: "note", reason_text: "等待确认", data_quality: "ok" }] } }));
  await page.route("**/api/trading-experience/relative-strength*", (route) => route.fulfill({ status: 200, json: { enabled: true, total: 1, items: [{ symbol: "600000", stock_pct: -0.01, sector_pct: -0.02, index_pct: -0.018, rs_vs_sector: 0.01, rs_vs_index: 0.008, data_quality: "ok" }] } }));
}
