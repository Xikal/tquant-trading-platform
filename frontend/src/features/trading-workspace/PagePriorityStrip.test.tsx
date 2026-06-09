import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PagePriorityStrip } from "./PagePriorityStrip";
import { shouldShowPagePriorityStrip } from "./TradingWorkspaceChrome";

describe("PagePriorityStrip", () => {
  it("can render compact hierarchy for denoised pages when explicitly mounted", () => {
    const html = renderToStaticMarkup(<PagePriorityStrip page="monitor" />);

    expect(html).toContain("workspace-priority-strip");
    expect(html).toContain("实时行动");
    expect(html).toContain("首屏：今日结论");
    expect(html).toContain("明细：策略 lane");
    expect(html).toContain("影子对照");
    expect(html).toContain("研究模式");
    expect(html).toContain("观察提醒");
  });

  it("renders compact hierarchy for the market context monitor page", () => {
    const html = renderToStaticMarkup(<PagePriorityStrip page="monitor-market" />);

    expect(html).toContain("市场环境");
    expect(html).toContain("首屏：市场总闸");
    expect(html).toContain("明细：ETF T0");
  });

  it("does not render on pages outside B5 scope", () => {
    const html = renderToStaticMarkup(<PagePriorityStrip page="analysis" />);

    expect(html).toBe("");
  });

  it("hides hierarchy copy from dense work pages in the workspace shell", () => {
    expect(shouldShowPagePriorityStrip("strategy-tracking")).toBe(false);
    expect(shouldShowPagePriorityStrip("data")).toBe(false);
  });

  it("does not render removed hierarchy copy when mounted directly for dense work pages", () => {
    expect(renderToStaticMarkup(<PagePriorityStrip page="strategy-tracking" />)).toBe("");
    expect(renderToStaticMarkup(<PagePriorityStrip page="data" />)).toBe("");
  });
});
