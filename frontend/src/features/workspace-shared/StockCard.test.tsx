import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StockCard, StockIdentity } from "./StockCard";
import type { StockCardView } from "./workspaceTypes";

const sampleStock: StockCardView = {
  name: "测试股份",
  symbol: "600000",
  identityNote: "沪市主板",
  identityTags: ["核心池"],
  priceText: "12.34",
  changeText: "+1.20%",
  scoreText: "82",
  riskText: "中风险",
  expectedText: "+2.5%",
  actionText: "观察确认",
  details: "等待盘中确认",
  entryText: "12.10-12.30",
  stopText: "11.80",
  operationAmountText: "2 成",
  executionHint: "观察信号，不构成买入建议。",
  tone: "warn",
  badges: ["强势回踩"],
  subBadges: ["数据完整"],
  highlight: true,
};

describe("StockCard", () => {
  it("uses shared stock card classes for tone, risk, badges, and execution hints", () => {
    const html = renderToStaticMarkup(
      <StockCard stock={sampleStock} actions={["详情", "分析"]} compact />,
    );

    expect(html).toContain("tq-stock-card");
    expect(html).toContain("tq-stock-card--compact");
    expect(html).toContain("tq-stock-card--tone-warn");
    expect(html).toContain("tq-stock-card--highlight");
    expect(html).toContain("tq-stock-card__meta--warn");
    expect(html).toContain("tq-stock-card__risk--warn");
    expect(html).toContain("tq-stock-card__operation");
    expect(html).toContain("tq-stock-card__badge--sub");
    expect(html).toContain("tq-stock-card__execution-hint");
    expect(html).toContain("观察信号，不构成买入建议。");
  });

  it("renders stock identity through semantic classes", () => {
    const html = renderToStaticMarkup(
      <StockIdentity name="测试股份" symbol="600000" note="沪市主板" tags={["核心池"]} />,
    );

    expect(html).toContain("tq-stock-identity");
    expect(html).toContain("tq-stock-identity__name");
    expect(html).toContain("tq-stock-identity__meta");
    expect(html).toContain("tq-stock-identity__tag");
  });
});
