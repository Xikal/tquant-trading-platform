import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { HoldingDisciplinePanel } from "./HoldingDisciplinePanel";
import { TTradeAttributionPanel } from "./TTradeAttributionPanel";

describe("Paper trading experience panels", () => {
  it("renders holding discipline as readonly facts", () => {
    const html = renderToStaticMarkup(
      <HoldingDisciplinePanel
        loading={false}
        data={{
          enabled: true,
          account_id: 1,
          total: 1,
          data_quality: "ok",
          as_of: "2026-05-24T15:10:00",
          engine_version: "trading-experience-v1",
          source: "paper_positions",
          research_only: true,
          items: [{
            account_id: 1,
            symbol: "600000",
            hint_code: "break_down",
            level: "warn",
            evidence: ["现价 9.00", "近五日低点 9.50"],
            data_quality: "ok",
            as_of: "2026-05-24T15:10:00",
          }],
        }}
      />,
    );

    expect(html).toContain("破位事实");
    expect(html).not.toContain("加仓");
  });

  it("renders t attribution no_data explicitly", () => {
    const html = renderToStaticMarkup(
      <TTradeAttributionPanel
        loading={false}
        data={{
          enabled: true,
          account_id: 1,
          total: 1,
          data_quality: "no_data",
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
            minute_data_coverage: 0,
            completeness_issues: [],
            comparison_method: "paired_cashflow_vs_hold",
            key_level_state: "insufficient",
            discipline_notes: ["分钟数据覆盖不足，归因降级为 no_data"],
            data_quality: "no_data",
            as_of: "2026-05-24T15:10:00",
          }],
        }}
      />,
    );

    expect(html).toContain("no_data");
    expect(html).not.toContain("应该做 T");
  });
});
