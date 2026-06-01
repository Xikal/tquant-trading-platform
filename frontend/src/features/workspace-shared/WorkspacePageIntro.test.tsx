import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { WorkspacePageIntro } from "./WorkspacePageIntro";

describe("WorkspacePageIntro", () => {
  it("renders semantic classes for the intro header and pills", () => {
    const html = renderToStaticMarkup(
      <WorkspacePageIntro
        title="监控"
        summary="查看今日行情与重点候选。"
        detail="页面首屏应保持轻量，不引入营销式视觉。"
        note="更新频率以页面数据刷新为准。"
        more="更多说明"
        pills={[{ label: "状态", value: "正常" }]}
        actions={<button type="button">刷新</button>}
      />,
    );

    expect(html).toContain("tq-workspace-intro");
    expect(html).toContain("tq-workspace-intro__head");
    expect(html).toContain("tq-workspace-intro__title");
    expect(html).toContain("tq-workspace-intro__summary");
    expect(html).toContain("tq-workspace-intro__detail");
    expect(html).toContain("tq-workspace-intro__note");
    expect(html).toContain("tq-workspace-intro__more");
    expect(html).toContain("tq-info-pill");
  });
});
