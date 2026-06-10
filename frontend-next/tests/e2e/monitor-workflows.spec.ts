import { expect, test, type Page } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";

test.beforeEach(async ({ page }) => {
  await installE2eAuthState(page);
  await installMonitorRoutes(page);
});

test("/next/monitor preserves priority order and keeps monitor writes protected by default", async ({ page }) => {
  const writes = captureWriteRequests(page);
  await page.goto("/next/monitor");

  await expect(page.getByRole("heading", { name: "我的持仓监测" })).toBeVisible();
  await expect(page.getByRole("button", { name: /解读榜单/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /选股宝典/ })).toBeVisible();
  await expect(page.getByTestId("monitor-priority-order-table")).toContainText("000001");

  const rows = page.getByTestId("monitor-priority-order-table").locator(".monitor-rank-row");
  await expect(rows.nth(0)).toContainText("000001");
  await expect(rows.nth(1)).toContainText("600000");

  await page.getByRole("button", { name: "观察池" }).click();
  await expect(page.getByText("浦发银行").first()).toBeVisible();
  await page.getByRole("button", { name: "全部候选" }).click();
  await rows.filter({ hasText: "600000" }).first().click();
  await page.getByRole("button", { name: "选股宝典" }).click();
  await expect(page).toHaveURL(/\/next\/playbook$/);
  expect(writes()).toEqual([]);
});

test("/next/monitor/market renders gate, breadth, sector, ETF, review and runtime panels", async ({ page }) => {
  const writes = captureWriteRequests(page);
  await page.goto("/next/monitor/market");

  await expect(page.getByRole("heading", { name: "市场总闸 & 数据质量监控" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "市场状态总闸" })).toBeVisible();
  await expect(page.getByText("震荡可做").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "市场宽度与脉冲" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "板块与龙头确认" })).toBeVisible();
  await expect(page.getByText("半导体").first()).toBeVisible();
  await expect(page.getByText("申昊科技")).toHaveCount(0);
  await expect(page.getByText("意华股份")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "ETF T0 / 对冲" })).toBeVisible();
  await expect(page.getByText("沪深300ETF").first()).toBeVisible();
  await expect(page.getByText("半导体ETF")).toHaveCount(0);
  await expect(page.getByText("512480")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "午盘 / 收盘复盘分析与实战建议" })).toBeVisible();
  await expect(page.getByText("板块轮动较快").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "运行时同步状态" })).toBeVisible();
  await expect(page.getByText("SQLITE").first()).toBeVisible();
  expect(writes()).toEqual([]);
});

function captureWriteRequests(page: Page) {
  const writes: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/") && ["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) {
      writes.push(`${request.method()} ${url.pathname}`);
    }
  });
  return () => writes;
}

async function installMonitorRoutes(page: Page) {
  await page.route("**/api/bff/v1/workspace/monitor?**", (route) => {
    const view = new URL(route.request().url()).searchParams.get("view");
    return route.fulfill({ status: 200, json: view === "market" ? marketWorkspaceFixture : actionWorkspaceFixture });
  });
}

const priorityItems = [
  {
    symbol: "000001",
    name: "平安银行",
    latest_price: 12.3,
    change_pct: 0.012,
    production_score: 91,
    signal_state: "立即处理",
    strategy_name: "N形洗盘低吸",
    risk_text: "风控通过",
    plain_language_summary: "回踩支撑后放量确认",
    suggested_position_text: "20%",
    key_level_text: "支撑 12.1 / 压力 12.8",
    warning_tags: ["立即", "低吸"],
    lane: "buy_now",
    support_price: 12.1,
    pressure_price: 12.8,
    stop_loss_price: 11.9,
  },
  {
    symbol: "600000",
    name: "浦发银行",
    latest_price: 8.72,
    change_pct: -0.004,
    production_score: 83,
    signal_state: "观察确认",
    strategy_name: "均值回归观察",
    risk_text: "等待价格",
    plain_language_summary: "接近支撑，等待缩量",
    suggested_position_text: "10%",
    key_level_text: "支撑 8.5 / 压力 9.1",
    warning_tags: ["观察"],
    lane: "observe",
    support_price: 8.5,
    pressure_price: 9.1,
    stop_loss_price: 8.35,
  },
];

const actionWorkspaceFixture = {
  api_version: "v1",
  monitor_snapshot: {
    latest_trade_date: "2026-06-05",
    priority_board: {
      display_lane_title: "生产优先榜",
      immediate_count: 1,
      focus_count: 1,
      total_candidates: 2,
      market_firepower_multiplier: 0.82,
      market_gate_decision: "pass",
      market_state_text: "震荡可做",
      data_quality_text: "正常",
      directional_bias_text: "偏多观察",
      hot_industries: ["半导体", "银行"],
      portfolio_risk: { risk_level: "可控" },
      plain_language_summary: "生产优先榜按服务端顺序展示，先看低吸，再看观察确认。",
      items: priorityItems,
    },
    watchlist_signals: [priorityItems[1]],
  },
  stock_key_levels: {
    items: [
      { type: "支撑", price: 8.5, summary: "低吸观察位" },
      { type: "压力", price: 9.1, summary: "放量突破确认" },
    ],
  },
  positions: [{ symbol: "000001", name: "平安银行", quantity: 1000, cost_price: 12.1, pnl_pct: 0.016 }],
  instrument_sync_status: { status: "ok" },
  runtime: { database_backend: "sqlite", status: "ok" },
  data_quality: { status: "ok", coverage_ratio: "98%" },
};

const marketWorkspaceFixture = {
  api_version: "v1",
  monitor_snapshot: {
    priority_board: {
      market_state_text: "震荡可做",
      market_firepower_multiplier: 0.82,
      stock_up_ratio: 0.56,
      limit_up_count: 42,
      limit_down_count: 3,
      market_gate_decision: "pass",
      market_gate_reasons: ["指数未破位", "量能温和"],
    },
    review_reports: [
      { title: "午盘复盘", summary: "板块轮动较快，控制仓位。" },
      { title: "收盘复盘", summary: "缩量震荡，继续控制仓位。" },
    ],
  },
  market_breadth: {
    state_text: "震荡可做",
    data_quality_text: "正常",
    items: [
      { label: "上涨", count: 2800, ratio: 0.56 },
      { label: "下跌", count: 1900, ratio: 0.38 },
    ],
  },
  market_pulse: {
    data_quality_text: "正常",
    items: [
      { time: "10:00", up_count: 1800, down_count: 1400, strength: 0.53 },
      { time: "11:00", up_count: 2100, down_count: 1200, strength: 0.62 },
    ],
  },
  market_sector_relative_strength: {
    mainline: "半导体",
    leader_gate_status: "confirmed",
    items: [
      { sector_name: "半导体", leader_symbol: "688981", relative_strength: 0.036, state: "confirmed" },
      { sector_name: "银行", leader_symbol: "000001", relative_strength: 0.012, state: "watch" },
    ],
  },
  sector_etf_t0: {
    opportunities: [
      { name: "沪深300ETF", symbol: "510300", direction: "观察", spread_pct: 0.004, reason: "价差收敛" },
    ],
  },
  review_summary: {
    items: [{ title: "缩量震荡", summary: "热点轮动，控制交易频率。" }],
  },
  instrument_sync_status: { status: "ok" },
  runtime: {
    database_backend: "sqlite",
    workers: [{ name: "instrument-sync", status: "ok", updated_at: "2026-06-05T15:00:00Z" }],
  },
};
