import { describe, expect, it } from "vitest";
import { buildSettingsPageViewModel } from "./SettingsPage.viewModel";
import type { AuthUser, SettingsPayload } from "../../types";
import type { SettingsDraft } from "../workspace-shared/workspaceTypes";

describe("buildSettingsPageViewModel", () => {
  it("hides admin-only tabs from normal users", () => {
    const view = buildSettingsPageViewModel({
      currentUser: userFixture(["user"]),
      settings: settingsFixture(),
      factorWeights: null,
      draft: draftFixture(),
      factorDraft: {},
      sectorDraft: [],
      sectorQuery: "",
      sectorExclusions: { available_sectors: ["半导体"], excluded_sectors: [], excluded_count: 0, updated_at: "" },
    });

    expect(view.isAdmin).toBe(false);
    expect(view.settingsTabs.map((tab) => tab.key)).toEqual(["account", "trading"]);
  });

  it("includes admin tabs and dirty counts for administrators", () => {
    const draft = { ...draftFixture(), data_source: "eastmoney" };
    const view = buildSettingsPageViewModel({
      currentUser: userFixture(["administrator"]),
      settings: settingsFixture(),
      factorWeights: null,
      draft,
      factorDraft: {},
      sectorDraft: ["半导体"],
      sectorQuery: "",
      sectorExclusions: { available_sectors: ["半导体"], excluded_sectors: [], excluded_count: 0, updated_at: "" },
    });

    expect(view.isAdmin).toBe(true);
    expect(view.settingsTabs.map((tab) => tab.key)).toEqual(["account", "trading", "llm", "data", "governance"]);
    expect(view.sectorDirty).toBe(true);
    expect(view.unsavedCount).toBeGreaterThan(0);
  });

  it("filters sectors by query", () => {
    const view = buildSettingsPageViewModel({
      currentUser: userFixture(["admin"]),
      settings: settingsFixture(),
      factorWeights: null,
      draft: draftFixture(),
      factorDraft: {},
      sectorDraft: [],
      sectorQuery: "半",
      sectorExclusions: { available_sectors: ["半导体", "机器人"], excluded_sectors: [], excluded_count: 0, updated_at: "" },
    });

    expect(view.filteredSectors).toEqual(["半导体"]);
  });
});

function userFixture(roles: string[]): AuthUser {
  return {
    id: 1,
    username: "tester",
    display_name: "测试用户",
    can_paper_trade: true,
    roles,
    created_at: "2026-06-01T00:00:00+08:00",
  };
}

function draftFixture(): SettingsDraft {
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
