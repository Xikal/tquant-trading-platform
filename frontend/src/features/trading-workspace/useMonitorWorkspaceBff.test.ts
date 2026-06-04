import { describe, expect, it, vi } from "vitest";
import {
  isMonitorBffDisabled,
  monitorBffAggregateEnabled,
  monitorPriorityBoardParityProjection,
  stableMonitorPriorityParityPayload,
} from "./useMonitorWorkspaceBff";

describe("monitor BFF aggregate switch", () => {
  it("enables the monitor BFF aggregate by default and can be disabled by flag", () => {
    vi.stubEnv("VITE_MONITOR_BFF_AGGREGATE_ENABLED", undefined);
    expect(monitorBffAggregateEnabled()).toBe(true);

    vi.stubEnv("VITE_MONITOR_BFF_AGGREGATE_ENABLED", "false");
    expect(monitorBffAggregateEnabled()).toBe(false);
  });

  it("recognizes the explicit backend disabled response for legacy fallback", () => {
    const disabled = new Error("monitor BFF aggregate disabled") as Error & { status: number };
    disabled.status = 404;
    expect(isMonitorBffDisabled(disabled)).toBe(true);

    const missing = new Error("not found") as Error & { status: number };
    missing.status = 404;
    expect(isMonitorBffDisabled(missing)).toBe(false);
  });
});

describe("monitor BFF priority-board parity projection", () => {
  it("keeps the production ranking guard fields stable across aggregate and legacy payloads", async () => {
    const legacyBoard = priorityBoardFixture();
    const aggregateBoard = priorityBoardFixture();

    expect(monitorPriorityBoardParityProjection(aggregateBoard)).toEqual([
      {
        symbol: "600000",
        priority_score: 88.5,
        production_score: 71.2,
        buy_signal_state: "near_entry",
        elite_watch_score: 63.1,
      },
      {
        symbol: "601288",
        priority_score: 77,
        production_score: null,
        buy_signal_state: "watch",
        elite_watch_score: null,
      },
    ]);
    await expect(sha256(stableMonitorPriorityParityPayload(aggregateBoard))).resolves.toBe(
      await sha256(stableMonitorPriorityParityPayload(legacyBoard)),
    );
  });
});

function priorityBoardFixture() {
  return {
    items: [
      {
        symbol: "600000",
        priority_score: 88.5,
        production_score: 71.2,
        buy_signal_state: "near_entry",
        elite_watch_score: 63.1,
        latest_price: 10.1,
        name: "浦发银行",
      },
      {
        symbol: "601288",
        priority_score: 77,
        production_score: null,
        buy_signal_state: "watch",
        elite_watch_score: null,
        latest_price: 4.32,
        name: "农业银行",
      },
    ],
  };
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest))
    .map((item) => item.toString(16).padStart(2, "0"))
    .join("");
}
