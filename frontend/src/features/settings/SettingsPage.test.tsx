import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { createAppQueryClient } from "../../state/queryClient";
import { useSettingsUiStore } from "../../stores/settingsUiStore";
import { SettingsPage } from "./SettingsPage";
import { AdminTokenGate } from "./AdminTokenGate";
import { DataCenterEntryCard } from "./DataCenterEntryCard";
import { SettingsLayout } from "./SettingsLayout";
import { SettingsSection } from "./SettingsSection";
import type { AuthUser, SettingsPayload } from "../../types";
import type { SettingsDraft } from "../workspace-shared/workspaceTypes";
import type { SettingsTabItem } from "./SettingsPageTabs";

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

    expect(html).toContain("账户与安全");
    expect(html).toContain("交易偏好");
    expect(html).not.toContain("模型与因子");
    expect(html).not.toContain("大模型");
    expect(html).not.toContain("数据库");
    expect(html).not.toContain("数据库与诊断");
    expect(html).not.toContain("策略治理");
    expect(html).not.toContain("因子权重");
    expect(html).not.toContain("ML");
    expect(html).not.toContain("每日最新数据");
  });

  it("renders the redesigned settings shell with side navigation and admin token gate", () => {
    const html = renderToStaticMarkup(
      <SettingsLayout
        activeTab="data"
        loading={false}
        onRefresh={vi.fn()}
        onSaveAll={vi.fn()}
        onTabChange={vi.fn()}
        tabs={adminTabsFixture()}
        unsavedCount={1}
      >
        <SettingsSection title="数据与运行" description="数据源配置、最新数据状态和运行快照。" admin>
          <AdminTokenGate error="保存配置前需要填写管理令牌" value="" onChange={vi.fn()} />
          <DataCenterEntryCard title="数据质量与修复" description="数据质量、更新任务和修复操作在数据中心统一处理。" />
        </SettingsSection>
      </SettingsLayout>
    );

    expect(html).toContain("settings-layout");
    expect(html).toContain("settings-side-nav");
    expect(html).toContain("数据与运行");
    expect(html).toContain("诊断与审计");
    expect(html).toContain("管理员操作门");
    expect(html).toContain("先填写管理令牌，才能保存管理员配置。");
    expect(html).toContain("打开数据中心");
    expect(html).not.toContain("当前页签");
    expect(html).not.toContain("数据质量 SLA");
  });

  it("keeps ETF universe management as a data center entry instead of duplicating the full card", () => {
    const html = renderToStaticMarkup(
      <SettingsSection title="交易偏好" description="风控、行业过滤和 ETF 参数。">
        <DataCenterEntryCard title="交易标的范围" description="ETF / 股票池在数据中心统一维护。" />
      </SettingsSection>
    );

    expect(html).toContain("交易标的范围");
    expect(html).toContain("ETF / 股票池在数据中心统一维护");
    expect(html).toContain("打开数据中心");
    expect(html).not.toContain("股票池修复");
  });
});

function adminTabsFixture(): SettingsTabItem[] {
  return [
    { key: "account", label: "账户与安全", description: "安全与权限" },
    { key: "trading", label: "交易偏好", description: "风控、行业、退出", dirty: true },
    { key: "llm", label: "模型与因子", description: "DeepSeek、权重、ML", admin: true },
    { key: "data", label: "数据与运行", description: "数据源、运行状态", admin: true },
    { key: "governance", label: "诊断与审计", description: "治理、开关、审计", admin: true },
  ];
}

function adminUserFixture(): AuthUser {
  return {
    ...normalUserFixture(),
    id: 99,
    username: "admin",
    display_name: "管理员",
    roles: ["admin"],
  };
}

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
