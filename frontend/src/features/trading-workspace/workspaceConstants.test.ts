import { describe, expect, it } from "vitest";
import { PRODUCTION_PLAYBOOK_TABS, WEB_PLAYBOOK_TABS } from "../workspace-shared/workspaceConstants";

describe("workspaceConstants", () => {
  it("shows only active playbook strategies in production tabs", () => {
    const keys = PRODUCTION_PLAYBOOK_TABS.map((tab) => tab.key);

    expect(keys).toEqual([
      "first_board",
      "volume_shrink",
      "late_session_strong_support",
    ]);
    expect(keys).not.toContain("n_pattern_long_wash");
    expect(keys).not.toContain("n_pattern_short_wash");
    expect(keys).not.toContain("core_midcap_vwap_ma5_retrace");
    expect(keys).not.toContain("sector_mainline_first_divergence_low_buy");
    expect(keys).not.toContain("mainline_limitup_shrink_retrace_reclaim");
    expect(keys).not.toContain("classic_retrace");
    expect(keys).not.toContain("ma_support");
    expect(keys).not.toContain("breakout_support");
    expect(keys).not.toContain("divergence_consensus");
  });

  it("keeps N-pattern strategies in research tabs only", () => {
    const keys = WEB_PLAYBOOK_TABS.map((tab) => tab.key);

    expect(keys).not.toContain("n_pattern_long_wash");
    expect(keys).not.toContain("n_pattern_short_wash");
    expect(PRODUCTION_PLAYBOOK_TABS.map((tab) => tab.key)).not.toContain("n_pattern_long_wash");
    expect(PRODUCTION_PLAYBOOK_TABS.map((tab) => tab.key)).not.toContain("n_pattern_short_wash");
  });
});
