import { describe, expect, it } from "vitest";
import { PRODUCTION_PLAYBOOK_TABS, WEB_PLAYBOOK_TABS } from "./workspaceConstants";

describe("workspaceConstants", () => {
  it("shows only active playbook strategies in production tabs", () => {
    const keys = PRODUCTION_PLAYBOOK_TABS.map((tab) => tab.key);

    expect(keys).toEqual([
      "first_board",
      "volume_shrink",
      "n_pattern_long_wash",
      "n_pattern_short_wash",
      "late_session_strong_support",
      "core_midcap_vwap_ma5_retrace",
      "sector_mainline_first_divergence_low_buy",
      "mainline_limitup_shrink_retrace_reclaim",
    ]);
    expect(keys).not.toContain("classic_retrace");
    expect(keys).not.toContain("ma_support");
    expect(keys).not.toContain("breakout_support");
    expect(keys).not.toContain("divergence_consensus");
  });

  it("shows production N-pattern strategies in web playbook tabs", () => {
    const keys = WEB_PLAYBOOK_TABS.map((tab) => tab.key);

    expect(keys).toContain("n_pattern_long_wash");
    expect(keys).toContain("n_pattern_short_wash");
    expect(PRODUCTION_PLAYBOOK_TABS.map((tab) => tab.key)).toContain("n_pattern_long_wash");
    expect(PRODUCTION_PLAYBOOK_TABS.map((tab) => tab.key)).toContain("n_pattern_short_wash");
  });
});
