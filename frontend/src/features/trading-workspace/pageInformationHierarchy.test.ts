import { describe, expect, it } from "vitest";
import { WORKSPACE_DENOISED_PAGES, WORKSPACE_PAGE_RESPONSIBILITIES } from "./pageResponsibilities";

describe("workspace page information hierarchy", () => {
  it("keeps each core page split into primary, detail, and drilldown layers", () => {
    for (const page of WORKSPACE_DENOISED_PAGES) {
      const responsibility = WORKSPACE_PAGE_RESPONSIBILITIES[page];
      expect(responsibility.primaryQuestion).toMatch(/是否|哪些|当前|策略|数据|执行/);
      expect(responsibility.detailQuestion).toMatch(/哪些|哪里|哪个|信号|数据|成交/);
      expect(responsibility.drilldownPattern.length).toBeGreaterThan(8);
      expect(new Set(responsibility.primarySections).size).toBe(responsibility.primarySections.length);
      expect(new Set(responsibility.detailSections).size).toBe(responsibility.detailSections.length);
    }
  });

  it("assigns scalable list surfaces only where large lists are expected", () => {
    expect(WORKSPACE_PAGE_RESPONSIBILITIES.monitor.heavyListSurface).toContain("VirtualCardList");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES["monitor-market"].heavyListSurface).toContain("VirtualCardList");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES["strategy-tracking"].heavyListSurface).toContain("DataTable");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES.data.heavyListSurface).toEqual(["DataTable"]);
    expect(WORKSPACE_PAGE_RESPONSIBILITIES.backtest.heavyListSurface).toContain("DataTable");
  });

  it("keeps data quality fallbacks visible on all core pages", () => {
    for (const page of WORKSPACE_DENOISED_PAGES) {
      const responsibility = WORKSPACE_PAGE_RESPONSIBILITIES[page];
      expect(`${responsibility.emptyFallback} ${responsibility.featureFlagFallback}`).toMatch(
        /stale|partial|no_data|blocked|空态|补数|关闭/,
      );
    }
  });
});
