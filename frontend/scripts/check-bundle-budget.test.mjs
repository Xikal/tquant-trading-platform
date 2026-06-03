import { describe, expect, it } from "vitest";
import { checkBundleBudget } from "./check-bundle-budget.mjs";

describe("checkBundleBudget", () => {
  it("fails first-screen and unallowlisted single-chunk regressions", () => {
    const violations = checkBundleBudget({
      first_screen_js_gzip_kb: 351,
      total_gzip_kb: 700,
      assets: [{ file: "antd-core-demo.js", gzip_kb: 151 }],
    });

    expect(violations).toEqual([
      "first_screen_js_gzip_kb 351KB exceeds 350KB",
      "antd-core-demo.js gzip 151KB exceeds 150KB without allowlist reason",
    ]);
  });

  it("allows a large chunk only with an explicit reason", () => {
    const violations = checkBundleBudget(
      {
        first_screen_js_gzip_kb: 100,
        total_gzip_kb: 700,
        assets: [{ file: "echarts-charts-AbC123.js", gzip_kb: 151 }],
      },
      { chunks: { "echarts-charts": { reason: "ECharts chart registry is lazy-loaded." } } },
    );

    expect(violations).toEqual([]);
  });
});
