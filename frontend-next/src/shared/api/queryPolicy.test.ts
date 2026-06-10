import { describe, expect, it } from "vitest";
import { queryKeys } from "./queryKeys";
import { operationStaleTimeMs, realtimeRefetchIntervalMs, refetchOnWindowFocus } from "./queryPolicy";

describe("frontend-next query policy", () => {
  it("polls stock-price and live workspace operations on their contract cadence", () => {
    expect(realtimeRefetchIntervalMs(queryKeys.monitorWorkspace("action"))).toBe(10_000);
    expect(realtimeRefetchIntervalMs(queryKeys.quote("600000"))).toBe(8_000);
    expect(realtimeRefetchIntervalMs(queryKeys.lowBuyQuotes(["000001", "600000"]))).toBe(6_000);
    expect(refetchOnWindowFocus(queryKeys.monitorWorkspace("action"))).toBe("always");
  });

  it("keeps static admin/settings queries non-polling", () => {
    expect(operationStaleTimeMs(queryKeys.settings)).toBe(20_000);
    expect(realtimeRefetchIntervalMs(queryKeys.settings)).toBe(false);
    expect(refetchOnWindowFocus(queryKeys.settings)).toBe(false);
  });

  it("keeps priority-board cache keys aligned with request parameters", () => {
    expect(queryKeys.lowBuyPriorityBoard(30, "baseline", "cache")).toEqual([
      "frontend-next",
      "operation",
      "lowBuyPriorityBoard",
      { query: { limit: 30, strategy_variant: "baseline", refresh: "cache" } },
    ]);
  });
});
