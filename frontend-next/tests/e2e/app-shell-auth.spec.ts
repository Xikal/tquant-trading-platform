import { expect, type Page, test } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";

test("anonymous users are sent to the login page before /next business pages", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({ status: 401, json: { detail: "not authenticated" } }));
  await page.goto("/next/analysis");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "WISE QUANT" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Connect & Synch Neural Link" })).toBeVisible();
});

test("login restores the original guarded /next route after redirect", async ({ page }) => {
  const user = {
    id: 1,
    username: "redirect_e2e",
    display_name: "redirect e2e",
    can_paper_trade: true,
    roles: ["admin"],
    mfa_totp_enabled: false,
    created_at: new Date(0).toISOString(),
  };
  let authenticated = false;
  await page.route("**/api/auth/me", (route) => {
    if (authenticated) return route.fulfill({ status: 200, json: { user } });
    return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
  });
  await page.route("**/api/auth/login", (route) => {
    authenticated = true;
    return route.fulfill({
      status: 200,
      json: {
        access_token: "frontend-next-redirect-token",
        refresh_token: "frontend-next-redirect-refresh-token",
        token_type: "bearer",
        expires_in: 3600,
        user,
      },
    });
  });

  await page.goto("/next/analysis?symbol=000001");
  await expect(page).toHaveURL(/\/login\?redirect=/);
  await page.locator("input[autocomplete='username']").fill("redirect_e2e");
  await page.locator("input[autocomplete='current-password']").fill("secret");
  await page.getByRole("button", { name: "Connect & Synch Neural Link" }).click();

  await expect(page).toHaveURL(/\/next\/analysis\?symbol=000001$/);
  await expect(page.getByRole("heading", { name: "量化分析" }).first()).toBeVisible();
});

test("expired startup access token refreshes once and stays on the guarded route", async ({ page }) => {
  const user = {
    id: 1,
    username: "refresh_e2e",
    display_name: "refresh e2e",
    can_paper_trade: true,
    roles: ["admin"],
    mfa_totp_enabled: false,
    created_at: new Date(0).toISOString(),
  };
  let refreshed = false;
  await page.route("**/api/auth/me", (route) => {
    if (refreshed) return route.fulfill({ status: 200, json: { user } });
    return route.fulfill({ status: 401, json: { detail: "expired" } });
  });
  await page.route("**/api/auth/refresh", (route) => {
    refreshed = true;
    return route.fulfill({
      status: 200,
      json: {
        access_token: "frontend-next-refresh-access",
        refresh_token: "frontend-next-refresh-token-2",
        token_type: "bearer",
        expires_in: 3600,
        user,
      },
    });
  });
  await page.addInitScript(() => {
    window.localStorage.setItem("tquant:auth:access_token", "expired-access");
    window.localStorage.setItem("tquant:auth:refresh_token", "refresh-token-1");
  });

  await page.goto("/next/monitor?symbol=000001");
  await expect(page).toHaveURL(/\/next\/monitor\?symbol=000001$/);
  await expect(page.getByText("实时流 未连接").first()).toBeVisible();
  await expect(page.evaluate(() => window.localStorage.getItem("tquant:auth:access_token"))).resolves.toBe("frontend-next-refresh-access");
});

test("failed startup refresh clears tokens and redirects to login with original path", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({ status: 401, json: { detail: "expired" } }));
  await page.route("**/api/auth/refresh", (route) => route.fulfill({ status: 401, json: { detail: "refresh expired" } }));
  await page.addInitScript(() => {
    window.localStorage.setItem("tquant:auth:access_token", "expired-access");
    window.localStorage.setItem("tquant:auth:refresh_token", "expired-refresh");
  });

  await page.goto("/next/settings?tab=security");
  await expect(page).toHaveURL(/\/login\?redirect=.*next%2Fsettings/);
  await expect(page.getByRole("heading", { name: "WISE QUANT" })).toBeVisible();
  await expect(page.evaluate(() => window.localStorage.getItem("tquant:auth:access_token"))).resolves.toBeNull();
  await expect(page.evaluate(() => window.localStorage.getItem("tquant:auth:refresh_token"))).resolves.toBeNull();
});

test("command palette opens by shortcut and routes a symbol to analysis", async ({ page }) => {
  await installE2eAuthState(page);
  await page.goto("/next/monitor");
  await openCommandPalette(page);
  await expect(page.getByRole("dialog", { name: "全局搜索" })).toBeVisible();
  await page.getByPlaceholder("搜索页面、策略或输入 6 位股票代码").fill("000001");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/next\/analysis/);
  await expect(page.getByRole("heading", { name: "量化分析" }).first()).toBeVisible();
  await expect(page.getByLabel("分析代码")).toHaveValue("000001");
});

test("command palette traps focus and restores the trigger focus on close", async ({ page }) => {
  await installE2eAuthState(page);
  await page.goto("/next/monitor");

  await page.getByRole("button", { name: "打开全局搜索" }).click();
  await expect(page.getByRole("dialog", { name: "全局搜索" })).toBeVisible();
  await expect(page.getByPlaceholder("搜索页面、策略或输入 6 位股票代码")).toBeFocused();

  await page.keyboard.press("Shift+Tab");
  await expect(page.getByRole("button", { name: "关闭" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByPlaceholder("搜索页面、策略或输入 6 位股票代码")).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "全局搜索" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "打开全局搜索" })).toBeFocused();
});

test("command palette routes named pages without losing app shell", async ({ page }) => {
  await installE2eAuthState(page);
  await page.goto("/next/monitor");
  await openCommandPalette(page);
  await page.getByPlaceholder("搜索页面、策略或输入 6 位股票代码").fill("回测");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/next\/backtest$/);
  await expect(page.getByRole("heading", { name: "回测页" }).first()).toBeVisible();
});

test("command palette routes strategy commands to playbook and strategy tracking", async ({ page }) => {
  await installE2eAuthState(page);
  await page.goto("/next/monitor");

  await openCommandPalette(page);
  await page.getByPlaceholder("搜索页面、策略或输入 6 位股票代码").fill("首板");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/next\/playbook\?strategy=first_board$/);
  await expect(page.getByRole("heading", { name: "选股宝典" }).first()).toBeVisible();

  await openCommandPalette(page);
  await page.getByPlaceholder("搜索页面、策略或输入 6 位股票代码").fill("N形");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/next\/strategy-tracking\?strategy_key=n_pattern_long_wash$/);
  await expect(page.getByRole("heading", { name: "策略跟踪" }).first()).toBeVisible();
});

test("user menu opens settings and logs out through the app shell", async ({ page }) => {
  await installE2eAuthState(page);
  await page.route("**/api/auth/logout", (route) => route.fulfill({ status: 200, json: { ok: true } }));

  await page.goto("/next/monitor");
  await page.getByRole("button", { name: "账户菜单" }).click();
  await page.getByRole("menuitem", { name: "系统设置" }).click();
  await expect(page).toHaveURL(/\/next\/settings$/);
  await expect(page.getByRole("heading", { name: "账户安全与 2FA 动态认证" })).toBeVisible();

  await page.getByRole("button", { name: "账户菜单" }).click();
  await page.getByRole("menuitem", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "WISE QUANT" })).toBeVisible();
});

test("compatibility routes redirect to their /next targets under auth guard and preserve query", async ({ page }) => {
  await installE2eAuthState(page);
  const cases = [
    ["/next/emotion", "/next/monitor", "实时流 未连接", "text"],
    ["/next/low-buy", "/next/playbook", "选股宝典", "heading"],
    ["/next/strategy", "/next/backtest", "回测页", "heading"],
    ["/next/performance", "/next/paper", "模拟盘", "heading"],
  ] as const;

  for (const [from, to, title, role] of cases) {
    await page.goto(`${from}?symbol=000001&source=compat&tab=x`);
    await expect(page).toHaveURL(new RegExp(`${to.replace(/\//g, "\\/")}\\?symbol=000001&source=compat&tab=x`));
    const locator = role === "text" ? page.getByText(title).first() : page.getByRole(role, { name: title }).first();
    await expect(locator).toBeVisible();
  }
});

test("mobile navigation opens, routes, and closes without desktop sidebar dependency", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installE2eAuthState(page);
  await page.goto("/next/monitor");

  const sidebar = page.locator(".tq-sidebar");
  await expect(sidebar).not.toHaveClass(/tq-sidebar--mobile-open/);

  await page.getByRole("button", { name: "打开导航" }).click();
  await expect(sidebar).toHaveClass(/tq-sidebar--mobile-open/);

  await page.getByRole("link", { name: "选股宝典" }).click();
  await expect(page).toHaveURL(/\/next\/playbook$/);
  await expect(page.getByRole("heading", { name: "选股宝典" }).first()).toBeVisible();
  await expect(sidebar).not.toHaveClass(/tq-sidebar--mobile-open/);

  await page.getByRole("button", { name: "打开导航" }).click();
  await expect(sidebar).toHaveClass(/tq-sidebar--mobile-open/);
  await page.getByRole("button", { name: "关闭导航" }).click();
  await expect(sidebar).not.toHaveClass(/tq-sidebar--mobile-open/);
});

test("non-admin users cannot enter data console or admin-only settings controls", async ({ page }) => {
  await installE2eAuthState(page, { isAdmin: false });

  await page.goto("/next/data");
  await expect(page.getByRole("heading", { name: "管理员权限不足" })).toBeVisible();

  await page.goto("/next/settings");
  await expect(page.getByRole("heading", { name: "账户安全与 2FA 动态认证" })).toBeVisible();
  await expect(page.getByRole("radio", { name: "开关" })).toHaveCount(0);
  await expect(page.getByRole("radio", { name: "治理" })).toHaveCount(0);
  await expect(page.getByRole("radio", { name: "Audit" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "功能开关写入" })).toHaveCount(0);
});

test("users without paper trading permission cannot enter paper workspace", async ({ page }) => {
  await installE2eAuthState(page, { canPaperTrade: false });

  await page.goto("/next/paper");
  await expect(page.getByRole("heading", { name: "模拟盘权限不足" })).toBeVisible();
});

test("route-level errors keep the app shell available and redact sensitive details", async ({ page }) => {
  await installE2eAuthState(page);
  await page.route("**/src/features/analysis/AnalysisPage.tsx*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/javascript",
      body: `export function AnalysisPage() { throw new Error("Authorization: Bearer access-token-123 access_token=token-456 password=unsafe"); }`,
    }),
  );

  await page.goto("/next/analysis");
  await expect(page.locator(".tq-sidebar")).toBeVisible();
  await expect(page.getByText("维斯量化")).toBeVisible();
  await expect(page.getByTestId("route-error-boundary")).toBeVisible();
  await expect(page.getByRole("heading", { name: "量化分析渲染异常" })).toBeVisible();
  await expect(page.locator("body")).toContainText("[redacted]");
  await expect(page.locator("body")).not.toContainText("access-token-123");
  await expect(page.locator("body")).not.toContainText("token-456");
  await expect(page.locator("body")).not.toContainText("unsafe");

  await page.getByRole("link", { name: "选股宝典" }).click();
  await expect(page).toHaveURL(/\/next\/playbook$/);
  await expect(page.getByRole("heading", { name: "选股宝典" }).first()).toBeVisible();
});

async function openCommandPalette(page: Page) {
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
}
