import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RelativeStrengthBoard } from "./RelativeStrengthBoard";
import { VolumePositionTagStrip } from "./VolumePositionTagStrip";

describe("Trading experience observation widgets", () => {
  it("renders volume-position tags as observable labels", () => {
    const html = renderToStaticMarkup(
      <VolumePositionTagStrip
        items={[{
          symbol: "600000",
          trade_date: "2026-05-24",
          tag_code: "high_vol_distribution_risk",
          level: "warn",
          evidence: ["量比 2.20"],
          explanation: "高量但收盘位置偏弱，需警惕价量分歧。",
          data_quality: "ok",
          as_of: "2026-05-24T15:10:00",
          engine_version: "trading-experience-v1",
        }]}
      />,
    );

    expect(html).toContain("高量分歧");
    expect(html).not.toContain("主力出货");
  });

  it("renders relative strength board with fact labels", () => {
    const html = renderToStaticMarkup(
      <RelativeStrengthBoard
        loading={false}
        data={{
          enabled: true,
          total: 1,
          data_quality: "ok",
          as_of: "2026-05-24T15:10:00",
          engine_version: "trading-experience-v1",
          source: "daily_bar_snapshots",
          research_only: true,
          items: [{
            symbol: "600000",
            trade_date: "2026-05-24",
            index_code: "market_average",
            sector_code: "银行",
            stock_pct: 0.5,
            index_pct: -2,
            sector_pct: -1,
            rs_vs_index: 2.5,
            rs_vs_sector: 1.5,
            sector_rank: 1,
            resilience_flag: "resilient",
            data_quality: "ok",
            as_of: "2026-05-24T15:10:00",
          }],
        }}
      />,
    );

    expect(html).toContain("相对强度只展示信号日事实");
    expect(html).toContain("抗跌");
  });
});
