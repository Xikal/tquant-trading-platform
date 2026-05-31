import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { createAppQueryClient } from "../../state/queryClient";
import { EtfT0OosPanel } from "./EtfT0OosPanel";

describe("EtfT0OosPanel", () => {
  it("renders dataset quality, real regime labels and stage gate copy", () => {
    const html = renderToStaticMarkup(
      <QueryClientProvider client={createAppQueryClient()}>
        <EtfT0OosPanel
          symbol="510300"
          name="沪深300ETF"
          quantity={10000}
          maxTradesPerDay={2}
          minSignalBars={20}
          bars={[{ timestamp: "2026-05-27 09:30", open: 10, high: 10.1, low: 9.9, close: 10, volume: 1000, amount: 10000 }]}
        />
      </QueryClientProvider>,
    );

    expect(html).toContain("真实 OOS 验证");
    expect(html).toContain("manifest 中真实标注");
    expect(html).toContain("OOS 数据集");
    expect(html).toContain("运行真实 OOS");
    expect(html).toContain("质量");
    expect(html).toContain("覆盖状态");
    expect(html).toContain("暂无 OOS 数据集");
  });
});
