import { describe, expect, it } from "vitest";
import { shouldShowPagePriorityStrip } from "./TradingWorkspaceChrome";

describe("TradingWorkspaceChrome", () => {
  it.each(["monitor", "monitor-market", "paper", "strategy-tracking", "data", "backtest"] as const)(
    "hides workspace responsibility copy on %s",
    (page) => {
      expect(shouldShowPagePriorityStrip(page)).toBe(false);
    },
  );

  it.each(["analysis", "playbook", "settings"] as const)("keeps responsibility copy on %s", (page) => {
    expect(shouldShowPagePriorityStrip(page)).toBe(true);
  });
});
