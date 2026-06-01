import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { ConclusionBar } from "./ConclusionBar";

describe("ConclusionBar", () => {
  it("renders a shared conclusion strip with clickable cards", () => {
    const html = renderToStaticMarkup(
      <ConclusionBar
        title="结论区"
        summary="今天该做什么"
        items={[
          { key: "alpha", label: "机会", value: "可买 2 / 观察 4", tone: "warn", onClick: vi.fn(), active: true, helper: "优先处理可买项" },
          { key: "beta", label: "风险", value: "高风险 1", tone: "down", helper: "高风险要先处理" },
          { key: "gamma", label: "状态", value: "震荡修复", tone: "neutral" },
        ]}
      />
    );

    expect(html).toContain("结论区");
    expect(html).toContain("今天该做什么");
    expect(html).toContain("可买 2 / 观察 4");
    expect(html).toContain("高风险 1");
    expect(html).toContain("震荡修复");
    expect(html).toContain("tq-conclusion-bar");
    expect(html).toContain("tq-conclusion-bar__item");
  });
});
