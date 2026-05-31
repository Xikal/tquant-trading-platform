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
      items: [{
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
      }],
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

    expect(html).toContain("ETF Universe 管理");
    expect(html).toContain("修复草稿");
    expect(html).toContain("校验草稿");
    expect(html).toContain("保存 Universe");
    expect(html).toContain("回滚");
    expect(html).toContain("不生成策略信号");
    expect(html).toContain("quant parameter audit");
  });
});
