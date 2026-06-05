import { describe, expect, it } from "vitest";
import { buildMonitorActionModel, buildMonitorMarketModel } from "./monitorPageModel";

describe("monitorPageModel", () => {
  it("builds action page counts without changing card semantics", () => {
    const priorityCards = [{ symbol: "600000" }, { symbol: "000001" }] as any[];
    const watchCards = [{ symbol: "510300" }] as any[];

    const model = buildMonitorActionModel({
      priorityBoard: { immediate_count: 1, focus_count: 2, track_count: 3 } as any,
      priorityCards,
      watchCards,
    });

    expect(model.priorityCount).toBe(priorityCards.length);
    expect(model.watchCount).toBe(watchCards.length);
    expect(model.immediateCount).toBe(1);
    expect(model.observeCount).toBe(5);
    expect(model.hasActionContext).toBe(true);
  });

  it("builds market context availability from existing monitor payload fields", () => {
    const model = buildMonitorMarketModel({
      marketBreadth: { breadth_ready: true } as any,
      marketPulse: { data_quality: "fresh" } as any,
      sectorEtfT0: { opportunities: [{ etf_symbol: "510300" }] } as any,
    });

    expect(model.hasMarketContext).toBe(true);
    expect(model.etfOpportunityCount).toBe(1);
    expect(model.breadthReady).toBe(true);
    expect(model.pulseQuality).toBe("fresh");
  });
});
