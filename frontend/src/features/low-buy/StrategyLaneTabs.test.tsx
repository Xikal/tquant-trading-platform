import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { StrategyLaneStatusCard } from "./StrategyLaneStatusCard";
import { StrategyLaneTabs } from "./StrategyLaneTabs";

describe("StrategyLaneTabs", () => {
  it("shows all strategy lanes with plain names", () => {
    const html = renderToStaticMarkup(<StrategyLaneTabs value="baseline" onChange={() => undefined} />);

    expect(html).toContain("原低吸策略");
    expect(html).toContain("前排加权");
    expect(html).toContain("前排极精选");
  });

  it("renders user-friendly front row weighted status", () => {
    const html = renderToStaticMarkup(<StrategyLaneStatusCard board={null} activeLane="front_row_weighted" />);

    expect(html).toContain("只做验证，暂不影响真实排序");
    expect(html).toContain("样本外验证不足、滚动验证不稳定、成交数据不足");
  });

  it("renders watch-only front row only status", () => {
    const html = renderToStaticMarkup(<StrategyLaneStatusCard board={null} activeLane="front_row_only" />);

    expect(html).toContain("只做提醒，不参与生产排序");
    expect(html).toContain("信号很少，可能连续多天没有票");
  });
});
