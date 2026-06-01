import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Callout } from "./Callout";

describe("Callout", () => {
  it("renders structured tone classes for the compact primary layout", () => {
    const html = renderToStaticMarkup(
      <Callout
        title="执行提示"
        label="注意"
        detail="当前信号只作观察，不构成买入建议。"
        tone="warn"
        primary
        compact
        action={<button type="button">查看</button>}
      />,
    );

    expect(html).toContain("tq-callout");
    expect(html).toContain("tq-callout--tone-warn");
    expect(html).toContain("tq-callout--primary");
    expect(html).toContain("tq-callout--compact");
    expect(html).toContain("tq-callout__label");
    expect(html).toContain("tq-callout__title");
    expect(html).toContain("tq-callout__detail");
    expect(html).toContain("tq-callout__action");
  });
});
