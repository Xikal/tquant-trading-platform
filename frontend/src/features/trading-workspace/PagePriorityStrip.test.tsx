import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PagePriorityStrip } from "./PagePriorityStrip";

describe("PagePriorityStrip", () => {
  it("renders compact hierarchy for denoised pages", () => {
    const html = renderToStaticMarkup(<PagePriorityStrip page="monitor" />);

    expect(html).toContain("workspace-priority-strip");
    expect(html).toContain("实时监控");
    expect(html).toContain("首屏：市场状态");
    expect(html).toContain("明细：ETF 做T替代");
    expect(html).toContain("影子对照");
    expect(html).toContain("研究模式");
    expect(html).toContain("观察提醒");
  });

  it("does not render on pages outside B5 scope", () => {
    const html = renderToStaticMarkup(<PagePriorityStrip page="analysis" />);

    expect(html).toBe("");
  });
});
