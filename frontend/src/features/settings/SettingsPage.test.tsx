import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { createAppQueryClient } from "../../state/queryClient";
import { useSettingsUiStore } from "../../stores/settingsUiStore";
import { SettingsPage } from "./SettingsPage";
import type { AuthUser, SettingsPayload } from "../../types";
import type { SettingsDraft } from "../workspace-shared/workspaceTypes";

describe("SettingsPage", () => {
  it("keeps admin tuning and diagnostics out of the normal user first screen", () => {
    useSettingsUiStore.setState({ activeTab: "account", sectorDraft: [], sectorQuery: "", savedSection: "" });

    const html = renderToStaticMarkup(
      <QueryClientProvider client={createAppQueryClient()}>
        <SettingsPage
          settings={settingsFixture()}
          runtime={null}
          factorWeights={{
            weights: { momentum: 1 },
            defaults: { momentum: 1 },
            factors: [{ name: "动量因子", weight: 1, data_dependencies: [], applicable_strategies: [], activation_condition: "", status: "active", status_text: "启用" }],
          }}
          adminTasks={[]}
          adminMetrics={{ latest_low_buy_data: { status: "ok", daily_bar_count: 3200 } }}
          strategyGovernance={{ default_strategy: "core", production_strategies: ["core"], items: [] }}
          sectorExclusions={{ available_sectors: ["半导体"], excluded_sectors: [], excluded_count: 0, updated_at: "2026-06-01" }}
          factorDraft={{ momentum: "1" }}
          draft={settingsDraftFixture()}
          setDraft={vi.fn()}
          setFactorDraft={vi.fn()}
          loading=""
          onSave={vi.fn()}
          onSaveFactors={vi.fn()}
          onRefresh={vi.fn()}
          onRefreshLatestData={vi.fn()}
          onUpdateStrategyGovernance={vi.fn()}
          onSaveSectorExclusions={vi.fn()}
          currentUser={normalUserFixture()}
          onUserUpdate={vi.fn()}
        />
      </QueryClientProvider>
    );

    expect(html).toContain("我的账户");
    expect(html).toContain("交易参数");
    expect(html).not.toContain("大模型与因子");
    expect(html).not.toContain("大模型");
    expect(html).not.toContain("数据库");
    expect(html).not.toContain("数据库与诊断");
    expect(html).not.toContain("策略治理");
    expect(html).not.toContain("因子权重");
    expect(html).not.toContain("ML");
    expect(html).not.toContain("每日最新数据");
  });
});

function normalUserFixture(): AuthUser {
  return {
    id: 1,
    username: "normal",
    display_name: "普通用户",
    can_paper_trade: true,
    roles: ["user"],
    created_at: "2026-06-01T00:00:00+08:00",
  };
}

function settingsDraftFixture(): SettingsDraft {
  return {
    adminToken: "",
    llm_provider: "deepseek",
    llm_api_key: "",
    llm_base_url: "https://api.example.test",
    llm_model: "deepseek-chat",
    data_source: "akshare",
    data_source_base_url: "https://data.example.test",
    risk_max_single_loss_pct: "2",
    risk_max_daily_loss_pct: "5",
    risk_pause_after_losses: "3",
    strategy_min_profit_pct: "1",
  };
}

function settingsFixture(): SettingsPayload {
  return {
    llm_provider: "deepseek",
    llm_api_key: "",
    llm_base_url: "https://api.example.test",
    llm_model: "deepseek-chat",
    data_source: "akshare",
    data_source_base_url: "https://data.example.test",
    database_url: "sqlite:///backend/data/t_quant.db",
    risk_max_single_loss_pct: 2,
    risk_max_daily_loss_pct: 5,
    risk_pause_after_losses: 3,
    walk_forward_window_size: 20,
    event_risk_enabled: true,
    microstructure_enabled: true,
    strategy_min_amount_stock: 30_000_000,
    strategy_min_amount_etf: 10_000_000,
    strategy_min_amplitude_pct: 0.5,
    strategy_max_amplitude_pct: 8,
    strategy_max_atr_pct: 6,
    strategy_open_phase_min_tradability: 60,
    strategy_min_profit_pct: 1,
    strategy_min_profit_stock_pct: 1.2,
    strategy_min_profit_etf_pct: 0.6,
    strategy_slippage_stock_bps: 8,
    strategy_slippage_etf_bps: 4,
    llm_api_key_configured: true,
    database_url_configured: true,
    admin_auth_required: true,
  };
}
