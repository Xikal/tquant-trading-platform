import { expect, type Page, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import { installMonitorActionFixture } from "./cutover-fixtures";

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

  await page.getByRole("button", { name: "检测可用池范围" }).click();
  await expect(page.getByText("令牌验证未通过")).toBeVisible();
  await page.getByRole("button", { name: "确定" }).click();
  await page.getByPlaceholder("输入系统管理授权令牌").fill("ADMIN_TOKEN");
  await page.getByRole("button", { name: "检测可用池范围" }).click();
  await expect(page.getByText("已记录 [检测可用池范围] 本地维护意图。")).toBeVisible();

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
  await expect(page.getByText("[全局配置] 需要先校验管理令牌。")).toBeVisible();
  await page.getByPlaceholder("管理令牌(测试用: ADMIN_TOKEN)").fill("ADMIN_TOKEN");
  await page.getByRole("button", { name: "解锁" }).click();
  await expect(page.getByText("管理员权限校验通过，本页本地编辑已解锁。")).toBeVisible();
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
  await page.route("**/api/data-quality/coverage", (route) =>
    route.fulfill({ status: 200, json: { dataset_key: "daily_bars", scope: "all", missing_dates: ["2026-06-05"], missing_symbols: [{ symbol: "000001", name: "平安银行", missing_days: 1 }] } }),
  );
  await page.route("**/api/data-quality/sla", (route) =>
    route.fulfill({
      status: 200,
      json: {
        total: 1,
        items: [{ dataset_key: "daily_bars", scope: "all", as_of_date: "2026-06-05", coverage_pct: 0.98, missing_days: 1, invalid_rows: 0, duplicate_rows: 0, expected_days: 240, actual_days: 239, stale: false, status: "ok" }],
        latest_repair_audits: [{ id: 1, repair_id: "repair-1", dataset_key: "daily_bars", deleted_rows_count: 0, fabricated: false, operator: "e2e", created_at: "2026-06-05T09:00:00Z", reason: "dry-run", refetch_result: "ok" }],
      },
    }),
  );
  await page.route("**/api/runtime-tasks**", (route) =>
    route.fulfill({ status: 200, json: { total: 1, limit: 40, offset: 0, items: [{ id: 501, task_type: "data_backfill", status: "queued", progress_pct: 0, priority: 100, updated_at: "2026-06-05T09:10:00Z" }] } }),
  );
  await page.route("**/api/runtime-tasks/summary", (route) =>
    route.fulfill({
      status: 200,
      json: {
        queued: 3,
        running: 1,
        failed: 0,
        retrying: 0,
        succeeded_recent: 12,
        longest_wait_seconds: 22,
        running_count: 1,
        low_priority_tasks_paused: true,
        paused_task_types: ["analytics_export_strategy_tracking_snapshots", "strategy_24m_duckdb_report"],
        paused_queued: 2,
        claimable_queued: 1,
        status_counts: [{ status: "queued", count: 3 }, { status: "running", count: 1 }],
        task_type_counts: [{ task_type: "data_backfill", count: 1 }],
        paused_task_type_counts: [
          { task_type: "analytics_export_strategy_tracking_snapshots", count: 1 },
          { task_type: "strategy_24m_duckdb_report", count: 1 },
        ],
      },
    }),
  );
  await page.route("**/api/admin/metrics", (route) =>
    route.fulfill({ status: 200, json: { status: "ok", data_source: "akshare_eastmoney", task_count: 1, worker_count: 1, failed_count: 0, p95_ms: 32 } }),
  );
  await page.route("**/api/admin/tasks", (route) =>
    route.fulfill({ status: 200, json: { workers: [{ worker_id: "runtime-worker-1", component: "runtime-worker", status: "running", running_task_count: 1, heartbeat_age_seconds: 2, heartbeat_updated_at: "2026-06-05T09:11:00Z" }], tasks: [{ id: 502, task_type: "data_inspector", status: "running", progress_pct: 45, priority: 90, updated_at: "2026-06-05T09:12:00Z" }] } }),
  );

  await page.route("**/api/settings/runtime", (route) =>
    route.fulfill({ status: 200, json: { settings_consistency_status: "ok", data_source: "akshare_eastmoney", database_backend: "sqlite", frontend_dist_ready: true, llm_configured: true, ready_checks: { db: true, worker: true } } }),
  );
  await page.route("**/api/settings/sector-exclusions", (route) =>
    route.fulfill({ status: 200, json: { available_sectors: ["银行", "房地产"], excluded_sectors: ["房地产"], excluded_count: 1, updated_at: "2026-06-05T09:20:00Z" } }),
  );
  await page.route("**/api/settings/factor-weights", (route) =>
    route.fulfill({ status: 200, json: { weights: { volume_price: 0.4 }, defaults: { volume_price: 0.3 }, factors: [{ factor_key: "volume_price", name: "量价确认", status: "enabled", activation_condition: "always", weight: 0.4 }] } }),
  );
  await page.route("**/api/settings/feature-flags/audit**", (route) =>
    route.fulfill({ status: 200, json: { items: [{ key: "frontend_solid_island_enabled", action: "toggle", operator: "e2e", created_at: "2026-06-05T09:30:00Z", after: true }] } }),
  );
  await page.route("**/api/settings/feature-flags", (route) =>
    route.fulfill({ status: 200, json: { frontend_solid_island_enabled: true, data_console_next_enabled: false } }),
  );
  await page.route("**/api/settings", (route) =>
    route.fulfill({
      status: 200,
      json: {
        data_source: "akshare_eastmoney",
        data_source_base_url: "",
        database_url_configured: true,
        admin_auth_required: true,
        event_risk_enabled: true,
        microstructure_enabled: true,
        risk_max_single_loss_pct: 1,
        risk_max_daily_loss_pct: 2.5,
        risk_pause_after_losses: 3,
        strategy_min_amount_stock: 30000000,
        strategy_min_amount_etf: 15000000,
        strategy_slippage_stock_bps: 7,
        strategy_slippage_etf_bps: 4,
        llm_provider: "dashscope",
        llm_model: "qwen-plus",
        llm_base_url: "https://dashscope.aliyuncs.com",
        llm_api_key_configured: true,
      },
    }),
  );
  await page.route("**/api/quant/parameters**", (route) =>
    route.fulfill({ status: 200, json: { current_version: "v1", items: [{ id: 1, version: "v1", name: "低吸默认参数", scope: "low_buy", market_state_scope: "global", status: "active", created_at: "2026-06-05T09:40:00Z", params: { risk: 1 } }] } }),
  );
  await page.route("**/api/bff/v1/workspace/settings**", (route) =>
    route.fulfill({
      status: 200,
      json: {
        strategy_governance: {
          default_strategy: "n_pattern_long_wash",
          production_strategies: ["n_pattern_long_wash"],
          items: [{ strategy_key: "n_pattern_long_wash", strategy_title: "N形洗盘低吸", layer: "production", status: "active", status_text: "运行", participates_priority_board: true, validation_phase_text: "生产验证", strategy_health_score: 82 }],
        },
      },
    }),
  );
}
