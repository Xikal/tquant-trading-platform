import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { createAppQueryClient } from "../../state/queryClient";
import { MonitorActionPage } from "./MonitorActionPage";
import { baseMonitorPageProps } from "./monitorTestFixtures";

function renderPage(element: ReactElement) {
  return renderToStaticMarkup(
    <QueryClientProvider client={createAppQueryClient()}>
      {element}
    </QueryClientProvider>,
  );
}

describe("MonitorActionPage", () => {
  it("renders action desk sections without the full market review surface", () => {
    const html = renderPage(<MonitorActionPage {...baseMonitorPageProps()} />);

    expect(html).toContain("tq-conclusion-bar");
    expect(html).toContain("生产优先榜");
    expect(html).toContain("我的持仓");
    expect(html).toContain("+ 录入持仓");
    expect(html).not.toContain("今日全市场午盘 / 收盘复盘");
    expect(html).not.toContain("ETF 做T替代");
    expect(html).not.toContain("小时全市场快照");
  });
});
