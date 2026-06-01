import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { useEtfUniverseAdminStore } from "../../stores/etfUniverseAdminStore";
import { createAppQueryClient } from "../../state/queryClient";
import { EtfUniverseAdminCard } from "./EtfUniverseAdminCard";
import { ETF_UNIVERSE_ADMIN_SERVER_KEYS } from "./EtfUniverseAdminCard";

describe("EtfUniverseAdminCard", () => {
  it("renders universe admin summary, repair guide and audit actions", () => {
    const queryClient = createAppQueryClient();
    queryClient.setQueryData(ETF_UNIVERSE_ADMIN_SERVER_KEYS.payload, {
      version: "etf-universe-v1",
      updated_at: "2026-05-27T00:00:00Z",
      audit_scope: "market.sector_etf_t0.universe_overrides",
      baseline_count: 1,
      current_count: 1,
      override_count: 1,
      t0_enabled_count: 1,
      items: [
        {
          symbol: "518880",
          name: "黄金ETF",
          category: "gold",
          t0_eligible: true,
          settlement_rule: "t0",
          tracking_index: "黄金现货",
          min_amount: 30000000,
          max_spread_bps: 10,
          slippage_bps: 4,
          premium_discount_available: true,
          enabled_for_t0: true,
          same_day_sell_allowed: true,
          notes: "黄金 ETF",
          source: "override",
          validation_severity: "ok",
        },
        {
          symbol: "510300",
          name: "沪深300ETF",
          category: "broad_base",
          t0_eligible: true,
          settlement_rule: "t0",
          tracking_index: "沪深300",
          min_amount: 100000000,
          max_spread_bps: 8,
          slippage_bps: 4,
          premium_discount_available: false,
          enabled_for_t0: true,
          same_day_sell_allowed: true,
          notes: "宽基 ETF",
          source: "baseline",
          validation_severity: "warning",
        },
        {
          symbol: "511010",
          name: "国债ETF",
          category: "bond",
          t0_eligible: true,
          settlement_rule: "t0",
          tracking_index: "国债",
          min_amount: 30000000,
          max_spread_bps: 6,
          slippage_bps: 3,
          premium_discount_available: true,
          enabled_for_t0: true,
          same_day_sell_allowed: true,
          notes: "债券 ETF",
          source: "baseline",
          validation_severity: "info",
        },
        {
          symbol: "159985",
          name: "豆粕ETF",
          category: "commodity",
          t0_eligible: true,
          settlement_rule: "t0",
          tracking_index: "商品",
          min_amount: 30000000,
          max_spread_bps: 10,
          slippage_bps: 5,
          premium_discount_available: true,
          enabled_for_t0: true,
          same_day_sell_allowed: true,
          notes: "商品 ETF",
          source: "baseline",
          validation_severity: "error",
        },
        {
          symbol: "511880",
          name: "货币ETF",
          category: "money",
          t0_eligible: true,
          settlement_rule: "t0",
          tracking_index: "货币",
          min_amount: 30000000,
          max_spread_bps: 4,
          slippage_bps: 2,
          premium_discount_available: true,
          enabled_for_t0: true,
          same_day_sell_allowed: true,
          notes: "货币 ETF",
          source: "baseline",
          validation_severity: "ok",
        },
        {
          symbol: "000000",
          name: "未知ETF",
          category: "unknown",
          t0_eligible: false,
          settlement_rule: "t1",
          tracking_index: "",
          min_amount: 0,
          max_spread_bps: 0,
          slippage_bps: 0,
          premium_discount_available: false,
          enabled_for_t0: false,
          same_day_sell_allowed: false,
          notes: "待确认",
          source: "override",
          validation_severity: "ok",
        },
      ],
      overrides: {},
      normalized_overrides: {},
      validation: { error_count: 0, warning_count: 0, info_count: 0, issues: [] },
      diff: [],
      recent_versions: [],
      notes: ["策略决策仍由 Python 服务执行。"],
    });
    useEtfUniverseAdminStore.setState({
      draftOverrides: {},
      loading: false,
      error: "",
      message: "",
    });

    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <EtfUniverseAdminCard />
      </QueryClientProvider>
    );

    expect(html).toContain("交易标的范围");
    expect(html).toContain("修复草稿");
    expect(html).toContain("校验草稿");
    expect(html).toContain("保存标的范围");
    expect(html).toContain("回滚");
    expect(html).toContain("不生成策略信号");
    expect(html).toContain("参数审计");
    expect(html).toContain("正常");
    expect(html).toContain("宽基");
    expect(html).toContain("债券");
    expect(html).toContain("商品");
    expect(html).toContain("货币");
    expect(html).toContain("未知");
    expect(html).toContain("0 异常 / 0 注意");
    expect(html).not.toContain(">ok<");
    expect(html).not.toContain(">broad_base<");
    expect(html).not.toContain(">bond<");
    expect(html).not.toContain(">commodity<");
    expect(html).not.toContain(">money<");
    expect(html).not.toContain(">unknown<");
    expect(html).not.toContain("error /");
    expect(html).not.toContain("warning");
  });
});
