import { expect, test, type Page } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";
import {
  captureApiWrites,
  installAnalysisFixture,
  installDataSettingsFixtures,
  installMonitorActionFixture,
  installPlaybookFixture,
  installStrategyFixture,
} from "./cutover-fixtures";

test("/next/login exposes auth controls and local UI toggles", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({ status: 401, json: { detail: "not authenticated" } }));

  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "WISE QUANT" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "[ 常规登入 ]" })).toBeVisible();
  await expect(page.locator("input[autocomplete='username']")).toBeVisible();
  await expect(page.locator("input[autocomplete='current-password']")).toBeVisible();

  await page.getByRole("button", { name: "显示密码" }).click();
  await expect(page.locator("input[autocomplete='current-password']")).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "隐藏密码" }).click();
  await expect(page.locator("input[autocomplete='current-password']")).toHaveAttribute("type", "password");

  await page.getByRole("button", { name: "[ 限制器解除 ]" }).click();
  await expect(page.getByText("OVERLOAD: TYPE II (THE BEAST)")).toBeVisible();
  await expect(page.getByRole("button", { name: "[ 限制器复位 ]" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Connect & Synch Neural Link" })).toBeVisible();
});

test("/next/monitor covers priority board, filters, navigation, and local watch intent", async ({ page }) => {
  await installE2eAuthState(page);
  await installMonitorActionFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/monitor");
  await expect(page.getByRole("heading", { name: "我的持仓监测" })).toBeVisible();
  await expect(page.getByTestId("monitor-priority-order-table")).toContainText("000001");
  await expect(page.getByTestId("monitor-priority-order-table")).toContainText("600000");

  await page.getByRole("button", { name: "观察池" }).click();
  await expect(page.getByTestId("monitor-priority-order-table")).toContainText("600000");
  await page.getByRole("button", { name: "解读榜单" }).click();
  await expect(page.getByRole("status")).toContainText("榜单研判解析载入中");

  await page.getByRole("button", { name: "录入" }).click();
  await expect(page.getByRole("dialog", { name: "录入持仓" })).toBeVisible();
  await page.getByPlaceholder("例如: 顺钠股份").fill("测试观察");
  await page.getByPlaceholder("如: 000533").fill("000533");
  await page.getByRole("button", { name: "记录意图" }).click();
  await expect(page.getByRole("status")).toContainText("已保存更新");

  await page.getByRole("button", { name: "选股宝典" }).click();
  await expect(page).toHaveURL(/\/next\/playbook$/);
  expect(writes()).toEqual([]);
});

test("/next/monitor/market covers gate mode, refresh, and runtime panels", async ({ page }) => {
  await installE2eAuthState(page);
  await installMonitorActionFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/monitor/market");
  await expect(page.getByRole("heading", { name: "市场总闸 & 数据质量监控" })).toBeVisible();
  await page.getByRole("button", { name: "空态预览" }).click();
  await expect(page.getByRole("button", { name: "空态预览" })).toHaveClass(/market-sentiment-mode__item--active/);
  await page.getByRole("button", { name: "实时数据" }).click();
  await expect(page.getByRole("button", { name: "实时数据" })).toHaveClass(/market-sentiment-mode__item--active/);
  await page.getByRole("button", { name: "刷新" }).click();
  await expect(page.getByRole("heading", { name: "市场状态总闸" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "市场宽度与脉冲" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "板块与龙头确认" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ETF T0 / 对冲" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "运行时同步状态" })).toBeVisible();
  expect(writes()).toEqual([]);
});

test("/next/strategy-tracking covers filters, detail, holding, and review intents", async ({ page }) => {
  await installE2eAuthState(page);
  await installStrategyFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/strategy-tracking");
  await expect(page.getByRole("heading", { name: "策略跟踪" }).first()).toBeVisible();
  await expect(page.getByTestId("strategy-tracking-table")).toContainText("000001");
  await page.getByRole("button", { name: "筛选条件" }).click();
  await page.getByPlaceholder("代码 / 策略 / 说明").fill("600000");
  await page.getByRole("button", { name: "应用" }).click();
  await expect(page.getByTestId("strategy-tracking-table")).toContainText("600000");
  await page.getByRole("button", { name: "查看 600000 详情", exact: true }).click();
  await expect(page.getByTestId("strategy-tracking-detail-panel")).toContainText("浦发银行");
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("tab", { name: "持有" }).click();
  await expect(page.getByTestId("strategy-tracking-tabs")).toContainText("短线 1-3 天");
  await page.getByRole("tab", { name: "复盘中心" }).click();
  await page.getByLabel("复盘理由").fill("矩阵检查记录");
  await page.getByRole("button", { name: "确认" }).last().click();
  await page.getByRole("button", { name: "提交日志" }).click();
  await expect(page.getByText("交易日志已本地记录，正式保存待复验后开启")).toBeVisible();
  expect(writes()).toEqual([]);
});

test("/next/analysis covers symbol analysis, chart, and batch without trading handoff", async ({ page }) => {
  await installE2eAuthState(page);
  await installAnalysisFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/analysis");
  await expect(page.getByRole("heading", { name: "量化分析" }).first()).toBeVisible();
  await page.getByLabel("分析代码").fill("600000");
  await page.getByTestId("analysis-control-start").click();
  await expect(page.getByText("600000 分析完成")).toBeVisible();
  await expect(page.locator(".analysis-kline-frame .chart-frame canvas").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前行动建议细则点" })).toBeVisible();
  await page.getByLabel("批量代码").fill("000001,600000");
  await page.getByTestId("analysis-batch").click();
  await expect(page.getByText("2 个标的批量分析完成")).toBeVisible();
  await expect(page.getByTestId("analysis-batch-results")).toContainText("600000");
  await expect(page.getByTestId("analysis-open-paper")).toHaveCount(0);
  expect(writes()).toEqual(["POST /api/analyze", "POST /api/analyze/batch"]);
});

test("/next/playbook covers candidate selection, quote refresh, analysis route, and lifecycle guard", async ({ page }) => {
  await installE2eAuthState(page);
  await installPlaybookFixture(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/playbook");
  await expect(page.getByRole("heading", { name: /注目核心标的/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "候选分层" })).toBeVisible();
  await page.locator(".playbook-candidates-panel").getByRole("button").filter({ hasText: "浦发银行" }).click();
  await expect(page.getByTestId("playbook-detail")).toContainText("600000");
  await page.getByTestId("playbook-refresh").click();
  await expect(page.getByText("刷新全量")).toBeVisible();
  await page.getByTestId("playbook-detail").locator("..").getByRole("button", { name: "记录状态" }).click();
  await expect(page.getByText("状态更新已记录")).toBeVisible();
  await page.getByTestId("playbook-open-analysis").click();
  await expect(page).toHaveURL(/\/next\/analysis\?symbol=600000$/);
  expect(writes()).toEqual([]);
});

test("/next/backtest redirects to action desk without loading backtest APIs", async ({ page }) => {
  await installE2eAuthState(page);
  await installMonitorActionFixture(page);
  const writes = captureApiWrites(page);
  const backtestRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/backtests")) {
      backtestRequests.push(`${request.method()} ${request.url()}`);
    }
  });

  await page.goto("/next/backtest");
  await expect(page).toHaveURL(/\/next\/monitor$/);
  await expect(page.getByRole("heading", { name: "我的持仓监测" })).toBeVisible();
  expect(writes()).toEqual([]);
  expect(backtestRequests).toEqual([]);
});

test("/next/data covers admin dashboard, token gate, search, and local maintenance intent", async ({ page }) => {
  await installE2eAuthState(page);
  await installDataSettingsFixtures(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/data");
  await expect(page.getByRole("heading", { name: "QuantData 实时监控" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "数据完整度检查 (全市场数据集)" })).toBeVisible();
  await page.getByPlaceholder("快速搜索表名/异常代码...").fill("000001");
  await expect(page.getByText("000001")).toBeVisible();
  await page.getByRole("button", { name: "检测可用池范围" }).click();
  await expect(page.getByText("已基于当前管理员账号记录 [检测可用池范围] 本地维护意图。")).toBeVisible();
  await expect(page.getByRole("heading", { name: "运行时计算集群状况 (Running Workers)" })).toBeVisible();
  expect(writes()).toEqual([]);
});

test("/next/settings covers security, governance, sector filters, and protected config intent", async ({ page }) => {
  await installE2eAuthState(page);
  await installDataSettingsFixtures(page);
  const writes = captureApiWrites(page);

  await page.goto("/next/settings");
  await expect(page.getByRole("heading", { name: "账户安全与 2FA 动态认证" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "大模型底层底座" })).toBeVisible();
  await expect(page.getByRole("button", { name: "房地产", exact: true })).toBeVisible();
  await page.getByPlaceholder("搜索不想参与过滤的板块...").fill("银行");
  await expect(page.getByRole("button", { name: "银行", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "记录全部意图" }).click();
  await expect(page.getByText("[全局配置] 当前只读，请先解锁管理操作；页面不会直接写入生产。")).toBeVisible();
  await page.getByRole("button", { name: "解锁管理操作" }).click();
  await expect(page.getByText("已使用当前管理员账号解锁本地编辑。")).toBeVisible();
  await page.getByRole("button", { name: "记录全部意图" }).click();
  await expect(page.getByText("[全局配置] 已记录本地配置意图，正式保存待复验后开启。")).toBeVisible();
  expect(writes()).toEqual([]);
});
