import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { TTradeAttributionPanel } from "./TTradeAttributionPanel";

describe("TTradeAttributionPanel", () => {
  it("renders insufficient completeness issues and key-level state", () => {
    const html = renderToStaticMarkup(
      <TTradeAttributionPanel
        loading={false}
        data={{
          enabled: true,
          account_id: 1,
          total: 1,
          data_quality: "insufficient",
          as_of: "2026-05-24T15:10:00",
          engine_version: "trading-experience-v1",
          source: "paper_trades",
          research_only: true,
          items: [{
            account_id: 1,
            symbol: "600000",
            period: "30d",
            t_trade_count: 1,
            realized_cost_delta: -1.2,
            win_rate: 0,
            sell_fly_count: 0,
            vs_no_t_trade_return_delta: null,
            minute_data_coverage: 0.8,
            completeness_issues: ["trade:1:price_missing"],
            comparison_method: "paired_cashflow_vs_hold",
            key_level_state: "support_broken",
            discipline_notes: ["AKeyLevel 显示支撑破位，仅用于纪律归因"],
            data_quality: "insufficient",
            as_of: "2026-05-24T15:10:00",
          }],
        }}
      />,
    );

    expect(html).toContain("关键位破位");
    expect(html).toContain("trade:1:price_missing");
    expect(html).not.toContain("应该做 T");
  });
});
