import { describe, expect, it } from "vitest";
import {
  monitorWorkspaceProjection,
  monitorWorkspaceView,
  nextMonitorDataPageRef,
} from "./useMonitorData";

describe("monitor workspace view projection", () => {
  it("clears market-only state when the BFF action view returns null fields", () => {
    const projected = monitorWorkspaceProjection({
      hourly_snapshot_history: [],
      market_breadth: null,
      market_pulse: { pulse_text: "行动台总闸" } as any,
      paired_hedge: null,
      review_reports: [],
      review_status: null,
      sector_relative_strength: null,
    });

    expect(projected.marketBreadth).toBeNull();
    expect(projected.marketPulse?.pulse_text).toBe("行动台总闸");
    expect(projected.pairedHedge).toBeNull();
    expect(projected.reviewReports).toEqual([]);
    expect(projected.reviewStatus).toBeNull();
    expect(projected.sectorRelativeStrength).toBeNull();
    expect(projected.hourlySnapshotHistory).toEqual([]);
  });

  it("maps monitor routes to explicit BFF views", () => {
    expect(monitorWorkspaceView("monitor")).toBe("action");
    expect(monitorWorkspaceView("monitor-market")).toBe("market");
    expect(monitorWorkspaceView("paper")).toBe("full");
  });
});

describe("monitor page switch refresh gate", () => {
  it("accepts a new monitor page when refresh was queued behind an in-flight request", () => {
    expect(nextMonitorDataPageRef("monitor", "monitor-market", "queued")).toBe("monitor-market");
  });

  it("accepts a new monitor page after its refresh starts", () => {
    expect(nextMonitorDataPageRef("monitor", "monitor-market", "started")).toBe("monitor-market");
  });

  it("clears the remembered monitor page outside monitor surfaces", () => {
    expect(nextMonitorDataPageRef("monitor", "paper", "started")).toBeNull();
  });
});
