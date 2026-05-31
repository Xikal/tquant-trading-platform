import { describe, expect, it } from "vitest";
import { MONITOR_NON_REALTIME_REFRESH_INTERVAL_MS } from "../workspace-shared/workspaceConstants";

describe("workspace monitor refresh cadence", () => {
  it("keeps monitor non-realtime polling low frequency because live quotes use SSE signals", () => {
    expect(MONITOR_NON_REALTIME_REFRESH_INTERVAL_MS).toBeGreaterThanOrEqual(5 * 60 * 1000);
  });
});
