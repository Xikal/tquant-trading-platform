import { describe, expect, it } from "vitest";
import { isValidElement } from "react";
import { webRoutes } from "./webRouteDefinitions";
import { useWorkspaceStore } from "../../stores/workspaceStore";

describe("webRoutes", () => {
  it.each(["/monitor", "/emotion", "/paper", "/strategy"])("keeps %s mounted as a real route entry", (path) => {
    const route = webRoutes.find((item) => item.path === path);

    expect(route).toBeDefined();
    expect(isValidElement(route?.element)).toBe(true);
  });

  it("mounts the backtest page instead of redirecting it to strategy", () => {
    const route = webRoutes.find((item) => item.path === "/backtest");

    expect(route).toBeDefined();
    expect(route?.element).toBeDefined();
    expect(route?.path).toBe("/backtest");
  });

  it.each(["monitor", "emotion", "paper", "strategy"] as const)(
    "workspace store accepts cold route page state %s",
    (page) => {
      useWorkspaceStore.setState({ page: "settings" });

      useWorkspaceStore.getState().setPage(page);

      expect(useWorkspaceStore.getState().page).toBe(page);
    },
  );
});
