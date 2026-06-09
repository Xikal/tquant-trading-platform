import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MODE_SAFETY_BADGES, ModeSafetyBadges } from "./ModeSafetyBadges";

describe("ModeSafetyBadges", () => {
  it("renders denoised labels without action-copy leakage", () => {
    const html = renderToStaticMarkup(<ModeSafetyBadges kinds={["shadow", "preview", "research", "paper", "watch"]} />);

    expect(html).toContain("影子对照");
    expect(html).toContain("预览验证");
    expect(html).toContain("研究模式");
    expect(html).toContain("观察验证");
    expect(html).toContain("观察提醒");
    expect(html).not.toContain("建议买入");
    expect(html).not.toContain("必涨");
    expect(html).not.toContain("突破即买");
  });

  it("keeps every label linked to a boundary document", () => {
    for (const badge of Object.values(MODE_SAFETY_BADGES)) {
      expect(badge.docHref).toMatch(/^\/docs\//);
      expect(badge.tooltip.length).toBeGreaterThan(0);
    }
  });
});
