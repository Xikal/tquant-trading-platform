import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { TradeJournalPanel } from "./TradeJournalPanel";
import { TradeReviewPanel } from "./TradeReviewPanel";

describe("TradeReviewPanel", () => {
  it("renders review pool with board labels without production wording", () => {
    const html = renderToStaticMarkup(
      <TradeReviewPanel
        loading={false}
        boardFilter="main_only"
        onBoardFilterChange={() => undefined}
        data={{
          enabled: true,
          pool_date: "2026-05-24",
          board_filter: "main_only",
          total: 1,
          data_quality: "ok",
          as_of: "2026-05-24T15:10:00",
          engine_version: "trading-experience-v1",
          source: "daily_bar_snapshots",
          research_only: true,
          items: [
            {
              pool_date: "2026-05-24",
              symbol: "600000",
              name: "浦发银行",
              board_type: "main",
              board_name: "主板",
              status: "dropped",
              entry_pct: 9.2,
              volume_ratio: 2.1,
              mainline_state: "sector_known",
              sector_role: "银行",
              drop_reason: "跟踪期最大单日回撤 -3.50%",
              tracked_days: 3,
              evidence: ["信号日涨幅 9.20%"],
              data_quality: "ok",
              as_of: "2026-05-24T15:10:00",
              engine_version: "trading-experience-v1",
            },
            {
              pool_date: "2026-05-24",
              symbol: "600001",
              name: "主板样本",
              board_type: "main",
              board_name: "主板",
              status: "retained",
              entry_pct: 3.1,
              volume_ratio: 1.2,
              mainline_state: "unknown",
              sector_role: "测试",
              drop_reason: "",
              tracked_days: 1,
              evidence: ["信号日涨幅 3.10%"],
              data_quality: "ok",
              as_of: "2026-05-24T15:10:00",
              engine_version: "trading-experience-v1",
            },
          ],
        }}
      />,
    );

    expect(html).toContain("观察池只用于收盘复盘");
    expect(html).toContain("只看主板");
    expect(html).toContain("市场板");
    expect(html).toContain("主板");
    expect(html).toContain("浦发银行");
    expect(html).not.toContain("production_score");
    expect(html).not.toContain("稳赚");
  });

  it("renders journal disabled state", () => {
    const html = renderToStaticMarkup(
      <TradeJournalPanel
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

    expect(html).toContain("纪律日志未开启");
  });
});
