import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { createAppQueryClient } from "../../state/queryClient";
import { EtfT0BacktestPanel } from "./EtfT0BacktestPanel";

describe("EtfT0BacktestPanel", () => {
  it("renders the ETF minute backtest controls and baseline placeholders", () => {
    const html = renderToStaticMarkup(
      <QueryClientProvider client={createAppQueryClient()}>
        <EtfT0BacktestPanel />
      </QueryClientProvider>,
    );

    expect(html).toContain("ETF T0 分钟回测");
    expect(html).toContain("ETF代码");
    expect(html).toContain("日内次数");
    expect(html).toContain("运行 ETF T0 回测");
    expect(html).toContain("运行参数热力图");
    expect(html).toContain("分钟回测结果");
    expect(html).toContain("参数热力图");
    expect(html).toContain("五类市场验证");
    expect(html).toContain("真实 OOS 验证");
    expect(html).toContain("OOS 使用 manifest");
    expect(html).toContain("牛市");
    expect(html).toContain("强反弹");
    expect(html).toContain("必须验收");
  });
});
