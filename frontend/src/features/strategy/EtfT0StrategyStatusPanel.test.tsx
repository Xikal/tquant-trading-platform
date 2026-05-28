import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EtfT0StrategyStatusPanel } from "./EtfT0StrategyStatusPanel";

describe("EtfT0StrategyStatusPanel", () => {
  it("renders ETF T0 strategy status boundaries and Go diagnostic entry", () => {
    const html = renderToStaticMarkup(<EtfT0StrategyStatusPanel />);

    expect(html).toContain("ETF T0 策略状态");
    expect(html).toContain("Go 分钟快照诊断");
    expect(html).toContain("Python 继续生成 ETF 做T信号");
    expect(html).toContain("刷新分钟质量");
    expect(html).toContain("上线门槛");
    expect(html).toContain("OOS阶段");
    expect(html).toContain("真实 OOS 验证");
  });
});
