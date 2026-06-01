import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { createAppQueryClient } from "../../state/queryClient";
import { GroupedPerformanceTable, SectorEtfT0PerformancePanel } from "./PaperTradingPerformance";

describe("SectorEtfT0PerformancePanel", () => {
  it("renders ETF T0 performance with separated return semantics and plain-language status", () => {
    const html = renderToStaticMarkup(
      <QueryClientProvider client={createAppQueryClient()}>
        <SectorEtfT0PerformancePanel
          item={{
            simulated_trades: 2,
            simulated_closed_trades: 1,
            simulated_win_rate_pct: 100,
            simulated_net_win_rate_pct: 100,
            simulated_avg_return_pct: 0.38,
            simulated_profit_factor: null,
            shadow_sample_count: 12,
            shadow_settled_count: 8,
            shadow_pending_count: 4,
            shadow_success_rate_pct: 62.5,
            shadow_avg_return_1d_pct: 0.25,
            shadow_avg_return_3d_pct: 0.42,
            notes: ["ETF T0 模拟绩效"],
            execution_gate_notes: ["自动执行门禁：T+0 eligibility + positive_t_buy + no risk flags"],
            review_trades: [{
              id: 1,
              order_id: 1,
              symbol: "510300",
              side: "buy",
              price: 3.456,
              quantity: 10000,
              trade_time: "2026-05-27T10:30:00",
              entry_reason: "positive_t_buy",
              exit_reason: "",
              market_state: "震荡",
              attribution: "分钟信号 positive_t_buy 触发，执行门禁通过。",
              execution_summary: "buy 10000 @ 3.4560",
              risk_notes: [],
            }],
          }}
        />
      </QueryClientProvider>,
    );

    expect(html).toContain("自动委托");
    expect(html).toContain("真实模拟组合收益");
    expect(html).toContain("影子跟踪收益（非真实成交）");
    expect(html).toContain("每日信号等权收益（非真实组合收益）");
    expect(html).toContain("执行门禁说明");
    expect(html).toContain("分钟级正向买点");
    expect(html).not.toContain("positive_t_buy");
    expect(html).not.toContain("T+0 eligibility");
    expect(html).not.toContain("no risk flags");
    expect(html).toContain("逐笔复盘归因");
    expect(html).toContain("样本外状态");
    expect(html).toContain("真实样本外尚未验证");
    expect(html).not.toContain("OOS阶段");
    expect(html).not.toContain("真实 OOS");
    expect(html).not.toContain("needs_validation");
    expect(html).toContain("跟踪胜率（非真实成交）");
    expect(html).toContain("510300");
    expect(html).toContain("paper-etf-t0-kv-grid");
    expect(html).toContain("paper-etf-t0-review-list");
    expect(html).not.toContain("ant-table");
  });
});

describe("GroupedPerformanceTable", () => {
  it("renders paper grouped performance as responsive cards instead of a wide table", () => {
    const html = renderToStaticMarkup(
      <GroupedPerformanceTable
        emptyText="暂无策略绩效"
        items={[{
          key: "首板低吸",
          trades: 8,
          win_rate_pct: 62.5,
          net_win_rate_pct: 50,
          avg_return_pct: 1.2,
          profit_factor: 1.8,
        }]}
      />,
    );

    expect(html).toContain("paper-grouped-performance-list");
    expect(html).toContain("首板低吸");
    expect(html).toContain("PF");
    expect(html).not.toContain("ant-table");
  });
});
