import type { Page } from "@playwright/test";

export interface E2eAuthOptions {
  isAdmin?: boolean;
  canPaperTrade?: boolean;
}

export async function installE2eAuthState(page: Page, options: E2eAuthOptions = {}) {
  const user = {
    id: 1,
    username: "frontend_next_e2e",
    display_name: "frontend-next e2e",
    can_paper_trade: options.canPaperTrade ?? true,
    roles: options.isAdmin === false ? [] : ["admin"],
    mfa_totp_enabled: false,
    created_at: new Date(0).toISOString(),
  };
  await page.route("**/api/auth/me", (route) => route.fulfill({ status: 200, json: { user } }));
  await page.route("**/api/auth/refresh", (route) => route.fulfill({ status: 200, json: { access_token: "frontend-next-e2e-token", refresh_token: "", token_type: "bearer", expires_in: 3600, user } }));
  await page.addInitScript((isAdmin) => {
    window.localStorage.setItem("tquant:auth:access_token", "frontend-next-e2e-token");
    if (isAdmin) window.localStorage.setItem("tquant:admin_api_token", "frontend-next-e2e-admin-token");
    else window.localStorage.removeItem("tquant:admin_api_token");
  }, options.isAdmin !== false);
}
