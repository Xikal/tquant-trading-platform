import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { QueryErrorBoundary, QueryErrorFallback } from "./QueryErrorBoundary";

describe("QueryErrorBoundary", () => {
  it("renders retry copy for transient query failures without business advice wording", () => {
    const html = renderToStaticMarkup(
      <QueryErrorFallback status={500} />,
    );

    expect(html).toContain("加载失败，正在重试");
    expect(html).toContain("已保留上次可用数据");
    expect(html).not.toContain("建议买入");
    expect(html).not.toContain("必涨");
    expect(html).not.toContain("突破即买");
  });

  it("renders login copy for auth failures instead of retry-loop copy", () => {
    const html = renderToStaticMarkup(
      <QueryErrorFallback status={401} />,
    );

    expect(html).toContain("登录已失效");
    expect(html).not.toContain("正在重试");
  });

  it("exports a boundary component for workspace pages", () => {
    const html = renderToStaticMarkup(
      <QueryErrorBoundary>
        <section>ok</section>
      </QueryErrorBoundary>,
    );
    expect(html).toContain("ok");
  });
});
