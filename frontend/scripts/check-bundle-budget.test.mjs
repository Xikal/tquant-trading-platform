import { describe, expect, it } from "vitest";
import { checkBundleBudget, summarizeBundleReport } from "./check-bundle-budget.mjs";

describe("checkBundleBudget", () => {
  it("fails first-screen and unallowlisted single-chunk regressions", () => {
    const violations = checkBundleBudget({
      first_screen_js_gzip_kb: 351,
      total_gzip_kb: 700,
      assets: [{ file: "antd-core-demo.js", gzip_kb: 111 }],
    });

    expect(violations).toEqual([
      "first_screen_js_gzip_kb 351KB exceeds 350KB",
      "antd-core-demo.js gzip 111KB exceeds 110KB without allowlist reason",
    ]);
  });

  it("fails when first-screen gzip reduction is below the documented 20 percent target", () => {
    const violations = checkBundleBudget({
      first_screen_js_gzip_kb: 325,
      baseline_first_screen_js_gzip_kb: 400,
      total_gzip_kb: 700,
      assets: [],
    });

    expect(violations).toEqual([
      "first_screen_js_gzip_reduction_pct 18.75% is below 20% from baseline 400KB",
    ]);
  });

  it("allows a large chunk only with an explicit reason", () => {
    const violations = checkBundleBudget(
      {
        first_screen_js_gzip_kb: 100,
        total_gzip_kb: 700,
        assets: [{ file: "echarts-charts-AbC123.js", gzip_kb: 111 }],
      },
      { chunks: { "echarts-charts": { reason: "ECharts chart registry is lazy-loaded." } } },
    );

    expect(violations).toEqual([]);
  });

  it("computes budget summary from assets when explicit totals are missing", () => {
    const summary = summarizeBundleReport({
      assets: [
        { file: "index-demo.js", kind: "first-screen-js", gzip_kb: 12.25 },
        { file: "lazy-demo.js", kind: "lazy-feature", gzip_kb: 4.5 },
      ],
    });

    expect(summary).toEqual({
      first_screen_js_gzip_kb: 12.25,
      baseline_first_screen_js_gzip_kb: 0,
      first_screen_js_gzip_reduction_pct: 0,
      total_gzip_kb: 16.75,
      assets: [
        { file: "index-demo.js", kind: "first-screen-js", gzip_kb: 12.25 },
        { file: "lazy-demo.js", kind: "lazy-feature", gzip_kb: 4.5 },
      ],
    });
  });
});
