import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { createAppQueryClient } from "../../state/queryClient";
import { MonitorMarketPage } from "./MonitorMarketPage";
import { baseMonitorPageProps } from "./monitorTestFixtures";

function renderPage(element: ReactElement) {
  return renderToStaticMarkup(
    <QueryClientProvider client={createAppQueryClient()}>
      {element}
    </QueryClientProvider>,
  );
}

describe("MonitorMarketPage", () => {
  it("renders market context sections without holding-entry actions", () => {
    const html = renderPage(
      <MonitorMarketPage
        {...baseMonitorPageProps({
          marketBreadth: {
            state_text: "震荡",
            breadth_ready: true,
            data_quality: "fresh",
            data_quality_text: "可用",
            stock_up_ratio: 0.5,
            stock_median_change: 0.1,
            limit_up_count: 20,
            limit_down_count: 2,
            broken_board_ratio: 0.1,
            promotion_ratio: 0.2,
            board_height: 3,
          } as any,
          marketPulse: {
            data_quality: "fresh",
            data_quality_text: "可用",
            pulse_level: "balanced",
            pulse_text: "盘中结构可观察",
          } as any,
          sectorEtfT0: { opportunities: [] } as any,
        })}
      />,
    );

    expect(html).toContain("市场总闸 / 数据质量");
    expect(html).toContain("市场宽度与日内脉冲");
    expect(html).toContain("板块轮动与龙头确认");
    expect(html).toContain("ETF T0 与对冲研究");
    expect(html).toContain("今日全市场午盘 / 收盘复盘");
    expect(html).toContain("运行时 / 同步状态");
    expect(html).not.toContain("+ 录入持仓");
    expect(html).not.toContain("生产优先榜");
  });
});
