import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RelativeStrengthBoard } from "./RelativeStrengthBoard";

describe("RelativeStrengthBoard", () => {
  it("renders disabled state without facts table", () => {
    const html = renderToStaticMarkup(
      <RelativeStrengthBoard
        loading={false}
        data={{
          enabled: false,
          total: 0,
          items: [],
          data_quality: "blocked",
          as_of: "2026-05-24T15:10:00",
          engine_version: "trading-experience-v1",
          source: "feature_flag",
          research_only: true,
        }}
      />,
    );

    expect(html).toContain("抗跌榜未开启");
  });

  it("renders main-board quick filter for relative strength facts", () => {
    const html = renderToStaticMarkup(
      <RelativeStrengthBoard
        loading={false}
        boardFilter="main_only"
        onBoardFilterChange={() => undefined}
        data={{
          enabled: true,
          total: 2,
          items: [
            {
              trade_date: "2026-05-24",
              symbol: "600000",
              index_code: "000001",
              sector_code: "BANK",
              stock_pct: 1.2,
              index_pct: -0.8,
              sector_pct: -0.3,
              rs_vs_index: 2,
              rs_vs_sector: 1.5,
              sector_rank: 1,
              resilience_flag: "resilient",
              data_quality: "ok",
              as_of: "2026-05-24T15:10:00",
            },
            {
              trade_date: "2026-05-24",
              symbol: "300001",
              index_code: "000001",
              sector_code: "TECH",
              stock_pct: 2.1,
              index_pct: -0.8,
              sector_pct: 0.1,
              rs_vs_index: 2.9,
              rs_vs_sector: 2,
              sector_rank: 2,
              resilience_flag: "resilient",
              data_quality: "ok",
              as_of: "2026-05-24T15:10:00",
            },
          ],
          data_quality: "ok",
          as_of: "2026-05-24T15:10:00",
          engine_version: "trading-experience-v1",
          source: "daily_bar_snapshots",
          research_only: true,
        }}
      />,
    );

    expect(html).toContain("相对强度只展示信号日事实");
    expect(html).toContain("只看主板");
    expect(html).toContain("600000");
    expect(html).not.toContain("300001");
  });
});
