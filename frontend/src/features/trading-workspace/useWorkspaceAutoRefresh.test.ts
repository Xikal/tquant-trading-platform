import { describe, expect, it } from "vitest";
import { MONITOR_NON_REALTIME_REFRESH_INTERVAL_MS } from "../workspace-shared/workspaceConstants";
import { isMonitorDataPage } from "./workspaceRoutes";

describe("workspace monitor refresh cadence", () => {
  it("keeps monitor non-realtime polling low frequency because live quotes use SSE signals", () => {
    expect(MONITOR_NON_REALTIME_REFRESH_INTERVAL_MS).toBeGreaterThanOrEqual(5 * 60 * 1000);
  });

  it("activates monitor data for the action and market monitor pages only", () => {
    expect(isMonitorDataPage("monitor")).toBe(true);
    expect(isMonitorDataPage("monitor-market")).toBe(true);
    expect(isMonitorDataPage("playbook")).toBe(false);
    expect(isMonitorDataPage("paper")).toBe(false);
  });
});
