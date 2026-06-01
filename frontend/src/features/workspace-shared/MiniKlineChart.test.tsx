import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { buildMiniKlineOption, MiniKline } from "./MiniKlineChart";
import { color } from "../../ui/theme/tokens";

const bars: Parameters<typeof buildMiniKlineOption>[0] = [
  { timestamp: "2026-06-01T09:31:00", open: 10, close: 10.2, low: 9.9, high: 10.3, volume: 12000, amount: 0 },
  { timestamp: "2026-06-01T09:32:00", open: 10.2, close: 10.1, low: 10, high: 10.25, volume: 18000, amount: 0 },
];

describe("MiniKline", () => {
  it("uses semantic shell classes instead of local inline shell styles", () => {
    const html = renderToStaticMarkup(<MiniKline bars={[]} />);

    expect(html).toContain("tq-mini-kline");
    expect(html).toContain("tq-mini-kline__empty");
    expect(html).toContain("等待分析后显示K线");
  });

  it("builds kline colors from the token source", () => {
    const option = buildMiniKlineOption(bars);
    const candle = option.series[0] as { itemStyle: { color: string; color0: string } };
    const volume = option.series.find((item) => item.name === "成交量") as { data: Array<{ itemStyle: { color: string } }> } | undefined;

    expect(candle.itemStyle.color).toBe(color.mktUp);
    expect(candle.itemStyle.color0).toBe(color.mktDown);
    expect(volume?.data[0].itemStyle.color).toBe(color.mktUp);
    expect(volume?.data[1].itemStyle.color).toBe(color.mktDown);
  });
});
