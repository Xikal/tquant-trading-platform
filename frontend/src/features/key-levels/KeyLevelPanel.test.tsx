import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { KeyLevelResult } from "../../types";
import { KeyLevelPanel } from "./KeyLevelPanel";

describe("KeyLevelPanel", () => {
  it("renders support and resistance without trading advice wording", () => {
    const html = renderToStaticMarkup(<KeyLevelPanel result={fixture()} />);

    expect(html).toContain("关键位观察");
    expect(html).toContain("支撑");
    expect(html).toContain("压力");
    expect(html).not.toMatch(/建议买入|建议卖出|强烈推荐|直接低吸/);
  });

  it("renders insufficient data as observation only", () => {
    const html = renderToStaticMarkup(
      <KeyLevelPanel result={{ ...fixture(), data_quality: "insufficient", explanation: "数据不足，仅观察。", support_price: null, resistance_price: null }} />
    );

    expect(html).toContain("数据不足，仅观察。");
  });

  it("hides the panel when the backend feature flag is disabled", () => {
    const html = renderToStaticMarkup(
      <KeyLevelPanel
        result={{
          ...fixture(),
          data_quality: "blocked",
          warnings: ["AKeyLevel 功能开关关闭，关键位入口隐藏。"],
        }}
      />
    );

    expect(html).toBe("");
  });
});

function fixture(): KeyLevelResult {
  return {
    symbol: "000001",
    name: "平安银行",
    scope: "stock",
    trade_date: "2026-06-02",
    latest_price: 10,
    engine_version: "akey-level-v1",
    as_of: "2026-06-02",
    adjust_mode: "qfq",
    intraday_included: true,
    support_price: 9.8,
    support_zone_low: 9.75,
    support_zone_high: 9.86,
    support_distance_pct: -2,
    support_strength: 80,
    support_level_type: "platform_low",
    resistance_price: 10.5,
    resistance_zone_low: 10.42,
    resistance_zone_high: 10.58,
    resistance_distance_pct: 5,
    resistance_strength: 72,
    resistance_level_type: "volume_profile",
    ma5: 9.95,
    ma10: 9.9,
    ma20: 9.88,
    ma30: 9.86,
    ma60: 9.5,
    close_to_ma5: -0.5,
    close_to_ma10: -1,
    close_to_ma20: -1.2,
    close_to_ma30: -1.4,
    close_to_ma60: -5.3,
    trend_above_ma30: true,
    trend_above_ma60: true,
    key_level_candidates: [
      {
        price: 9.8,
        zone_low: 9.75,
        zone_high: 9.86,
        direction: "support",
        level_type: "platform_low",
        strength_score: 80,
        evidence: ["平台低点", "成交密集区"],
        invalid_condition: "跌破 9.75 且未收回，支撑降级",
        invalidate_below: 9.75,
        invalidate_volume_x: 1.5,
      },
    ],
    data_quality: "ok",
    explanation: "离最近支撑约 2.00%，仅用于观察。",
    warnings: [],
  };
}
