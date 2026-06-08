import { describe, expect, it } from "vitest";
import {
  normalizedStrategyKey,
  strategyCommandRegistry,
  strategyCommandSearchText,
} from "./strategyCommands";

describe("strategy command registry", () => {
  it("keeps strategy commands as navigation-only hints", () => {
    expect(strategyCommandRegistry).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "first_board",
          label: "首板回调",
          target: "playbook",
        }),
        expect.objectContaining({
          key: "n_pattern_long_wash",
          label: "N形洗盘研究",
          target: "strategy-tracking",
        }),
      ]),
    );
  });

  it("indexes labels, scope labels and aliases for command palette search", () => {
    const firstBoard = strategyCommandRegistry.find((command) => command.key === "first_board");

    expect(firstBoard).toBeDefined();
    expect(strategyCommandSearchText(firstBoard!)).toContain("首板");
    expect(strategyCommandSearchText(firstBoard!)).toContain("生产策略");
    expect(strategyCommandSearchText(firstBoard!)).toContain("first_board");
  });

  it("accepts only bounded route strategy keys", () => {
    expect(normalizedStrategyKey(" first_board ")).toBe("first_board");
    expect(normalizedStrategyKey("n_pattern_long_wash")).toBe("n_pattern_long_wash");
    expect(normalizedStrategyKey("bad key")).toBeNull();
    expect(normalizedStrategyKey("首板")).toBeNull();
    expect(normalizedStrategyKey("x".repeat(81))).toBeNull();
    expect(normalizedStrategyKey(null)).toBeNull();
  });
});
