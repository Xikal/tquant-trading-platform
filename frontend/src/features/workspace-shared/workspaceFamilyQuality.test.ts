import { describe, expect, it } from "vitest";

import { familyStripQualityText } from "./workspaceFamilyQuality";

describe("familyStripQualityText", () => {
  it("summarizes board gaps, stale strategies, item data quality, and shadow fallbacks", () => {
    const text = familyStripQualityText(
      {
        data_quality: "partial",
        data_quality_text: "部分快照缺失",
        missing_strategies: ["ma_channel_band"],
        stale_strategies: ["leader_pullback_band"],
      } as never,
      {
        family_key: "leader_pullback_band",
        family_text: "龙头回踩波段",
        total_candidates: 2,
        immediate_count: 0,
        focus_count: 1,
        track_count: 1,
        avg_priority_score: 62,
        top_strategy_titles: ["龙头回踩波段"],
        items: [
          { data_quality: "fresh" },
          { data_quality: "stale", main_force_advice: { fallback_reason: "missing_intraday" } },
        ],
      } as never,
    );

    expect(text).toContain("部分快照缺失");
    expect(text).toContain("待补1策");
    expect(text).toContain("待刷新1策");
    expect(text).not.toContain("旁路fallback 1");
  });

  it("keeps healthy family sections quiet", () => {
    const text = familyStripQualityText(
      { data_quality: "fresh", data_quality_text: "可用" } as never,
      {
        family_key: "trend_support_band",
        family_text: "均线通道支撑",
        total_candidates: 1,
        immediate_count: 1,
        focus_count: 0,
        track_count: 0,
        avg_priority_score: 80,
        top_strategy_titles: ["均线通道支撑"],
        items: [{ data_quality: "fresh" }],
      } as never,
    );

    expect(text).toBe("");
  });
});
