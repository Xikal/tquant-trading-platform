import { describe, expect, it } from "vitest";
import {
  WORKSPACE_DENOISED_PAGES,
  WORKSPACE_PAGE_RESPONSIBILITIES,
  pageResponsibility,
  pageResponsibilityHint,
} from "./pageResponsibilities";

describe("workspace page responsibilities", () => {
  it("documents the Phase 6 page split for the five decision surfaces", () => {
    expect(WORKSPACE_DENOISED_PAGES).toEqual([
      "monitor",
      "monitor-market",
      "strategy-tracking",
      "paper",
      "data",
    ]);

    for (const page of WORKSPACE_DENOISED_PAGES) {
      const responsibility = WORKSPACE_PAGE_RESPONSIBILITIES[page];
      expect(responsibility.page).toBe(page);
      expect(responsibility.coreQuestion.length).toBeGreaterThan(0);
      expect(responsibility.firstScreenConclusion.length).toBeGreaterThan(0);
      expect(responsibility.primarySections.length).toBeGreaterThanOrEqual(4);
      expect(responsibility.detailSections.length).toBeGreaterThanOrEqual(3);
      expect(responsibility.emptyFallback).toMatch(/空态|stale|partial|no_data|blocked|补数|持仓|快照/);
      expect(responsibility.featureFlagFallback).toMatch(/关闭|flag/);
      expect(responsibility.heavyListSurface.length).toBeGreaterThan(0);
      expect(responsibility.modeBadges.length).toBeGreaterThan(0);
    }
  });

  it("keeps non-denoised pages outside the Phase 6 responsibility map", () => {
    expect(pageResponsibility("analysis")).toBeNull();
    expect(pageResponsibility("playbook")).toBeNull();
    expect(pageResponsibility("settings")).toBeNull();
    expect(pageResponsibilityHint("analysis", "fallback")).toBe("fallback");
  });

  it("keeps command hints aligned with the page core question", () => {
    expect(pageResponsibilityHint("monitor", "fallback")).toContain("优先榜");
    expect(pageResponsibilityHint("monitor-market", "fallback")).toContain("宽度");
    expect(pageResponsibilityHint("strategy-tracking", "fallback")).toContain("复盘");
    expect(pageResponsibilityHint("paper", "fallback")).toContain("持仓");
    expect(pageResponsibilityHint("data", "fallback")).toContain("覆盖率");
  });

  it("keeps Shadow and Preview labels explicitly scoped to non-production modes", () => {
    expect(WORKSPACE_PAGE_RESPONSIBILITIES.monitor.modeBadges).toContain("shadow");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES["monitor-market"].modeBadges).toContain("research");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES.paper.modeBadges).toContain("paper");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES["strategy-tracking"].modeBadges).toContain("watch");
  });

  it("documents the monitor action and market split responsibilities", () => {
    expect(WORKSPACE_PAGE_RESPONSIBILITIES.monitor.primaryQuestion).toContain("今天");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES.monitor.primarySections).toContain("生产优先榜");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES["monitor-market"].primaryQuestion).toContain("市场");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES["monitor-market"].primarySections).toContain("市场宽度");
    expect(WORKSPACE_PAGE_RESPONSIBILITIES["monitor-market"].heavyListSurface).toContain("VirtualCardList");
  });
});
