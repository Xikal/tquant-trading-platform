import { describe, expect, it } from "vitest";
import { createRouter } from "@tanstack/solid-router";
import { render } from "solid-js/web";
import { compatibilityRoutes, nextRoutes } from "../shared/config/routes";
import { routeHasParityTarget } from "../shared/testing/legacyParity";
import { AUTH_LOGIN_ROUTE } from "./authRoutes";
import { RouteLoadingFallback } from "./RouteLoading";
import { routeTree } from "./routeTree";

describe("frontend-next route inventory", () => {
  it("maps every target page under /next/* to a legacy parity route", () => {
    expect(nextRoutes).toHaveLength(7);
    expect(nextRoutes.map((route) => route.path)).toEqual([
      "/next/monitor",
      "/next/monitor/market",
      "/next/analysis",
      "/next/playbook",
      "/next/strategy-tracking",
      "/next/data",
      "/next/settings",
    ]);
    expect(nextRoutes.every((route) => routeHasParityTarget(route.path))).toBe(true);
  });

  it("keeps shortcut and compatibility route inventory explicit", () => {
    expect(nextRoutes.filter((route) => route.commandIndex).map((route) => route.commandIndex)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(compatibilityRoutes).toEqual([
      { from: "/next/emotion", to: "/next/monitor" },
      { from: "/next/low-buy", to: "/next/playbook" },
      { from: "/next/strategy", to: "/next/strategy-tracking" },
      { from: "/next/performance", to: "/next/monitor" },
    ]);
  });

  it("keeps compatibility route query strings for workflow handoff context", () => {
    const sampleSearch = "?symbol=000001&source=compat";
    expect(compatibilityRoutes.map((route) => `${route.to}${sampleSearch}`)).toEqual([
      "/next/monitor?symbol=000001&source=compat",
      "/next/playbook?symbol=000001&source=compat",
      "/next/strategy-tracking?symbol=000001&source=compat",
      "/next/monitor?symbol=000001&source=compat",
    ]);
  });

  it("keeps every cutover route paired with a legacy root path", () => {
    expect(nextRoutes.map((route) => route.legacyPath)).toEqual([
      "/monitor",
      "/monitor/market",
      "/analysis",
      "/playbook",
      "/strategy-tracking",
      "/data",
      "/settings",
    ]);
  });

  it("keeps the production login entry under /next to avoid the legacy frontend shell", () => {
    const router = createRouter({ routeTree });
    expect(AUTH_LOGIN_ROUTE).toBe("/next/login");
    expect(router.routesByPath[AUTH_LOGIN_ROUTE]).toBeDefined();
    expect(router.routesByPath["/login"]).toBeDefined();
  });

  it("renders a visible route fallback instead of a blank content area", () => {
    const container = document.createElement("div");
    const dispose = render(() => <RouteLoadingFallback routeLabel="选股宝典" />, container);

    expect(container.textContent).toContain("选股宝典加载中");
    expect(container.querySelector("[data-testid='route-loading-fallback']")).toBeTruthy();

    dispose();
  });
});
