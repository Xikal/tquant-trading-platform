import { describe, expect, it } from "vitest";
import { isValidElement, type ReactElement } from "react";
import { Navigate } from "react-router";
import { webRoutes } from "./webRouteDefinitions";
import { useWorkspaceStore } from "../../stores/workspaceStore";
import { pageFromPath } from "../../features/trading-workspace/workspaceRoutes";

describe("webRoutes", () => {
  it.each(["/monitor", "/monitor/market", "/paper", "/strategy-tracking", "/data"])("keeps %s mounted as a real route entry", (path) => {
    const route = webRoutes.find((item) => item.path === path);

    expect(route).toBeDefined();
    expect(isValidElement(route?.element)).toBe(true);
  });

  it.each([
    ["/strategy", "/backtest"],
    ["/emotion", "/monitor"],
  ])("redirects %s to %s", (path, target) => {
    const route = webRoutes.find((item) => item.path === path);
    const element = route?.element;

    expect(route).toBeDefined();
    expect(isValidElement(element)).toBe(true);
    const redirect = element as ReactElement<{ to: string }>;
    expect(redirect.type).toBe(Navigate);
    expect(redirect.props.to).toBe(target);
  });

  it.each(["monitor", "monitor-market", "strategy-tracking", "paper", "data"] as const)(
    "workspace store accepts cold route page state %s",
    (page) => {
      useWorkspaceStore.setState({ page: "settings" });

      useWorkspaceStore.getState().setPage(page);

      expect(useWorkspaceStore.getState().page).toBe(page);
    },
  );

  it("maps only live workspace pages from cold paths", () => {
    expect(pageFromPath("/strategy-tracking")).toBe("strategy-tracking");
    expect(pageFromPath("/monitor/market")).toBe("monitor-market");
    expect(pageFromPath("/data")).toBe("data");
    expect(pageFromPath("/strategy")).toBe("monitor");
    expect(pageFromPath("/emotion")).toBe("monitor");
  });

  it("wraps workspace routes with an error element for cold navigation failures", () => {
    for (const route of webRoutes.filter((item) => item.path && item.path !== "*")) {
      expect(route.errorElement).toBeDefined();
    }
  });
});
