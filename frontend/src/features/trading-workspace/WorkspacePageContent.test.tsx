import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { WorkspacePageContent } from "./WorkspacePageContent";
import { baseMonitorPageProps } from "../monitor/monitorTestFixtures";

const NullPage = () => <div>other-page</div>;

describe("WorkspacePageContent", () => {
  it("routes monitor pages to separate action and market components", () => {
    const actionHtml = renderToStaticMarkup(
      <WorkspacePageContent
        {...workspaceProps()}
        page="monitor"
        MonitorPage={() => <div>action-desk</div>}
        MonitorMarketPage={() => <div>market-desk</div>}
      />,
    );
    const marketHtml = renderToStaticMarkup(
      <WorkspacePageContent
        {...workspaceProps()}
        page="monitor-market"
        MonitorPage={() => <div>action-desk</div>}
        MonitorMarketPage={() => <div>market-desk</div>}
      />,
    );

    expect(actionHtml).toContain("action-desk");
    expect(actionHtml).not.toContain("market-desk");
    expect(marketHtml).toContain("market-desk");
    expect(marketHtml).not.toContain("action-desk");
  });
});

function workspaceProps() {
  return {
    AnalysisPage: NullPage,
    DataConsolePage: NullPage as any,
    MonitorPage: NullPage as any,
    MonitorMarketPage: NullPage as any,
    PaperTradingPage: NullPage as any,
    PlaybookPage: NullPage,
    SettingsPage: NullPage,
    StrategyTrackingPage: NullPage as any,
    analysis: {
      draft: {},
      setDraft: vi.fn(),
      result: null,
      anomaly: null,
      batchSymbols: "",
      setBatchSymbols: vi.fn(),
      batchResults: [],
      runAnalysis: vi.fn(),
      runBatchAnalysis: vi.fn(),
      analyzeFromCard: vi.fn(),
    } as any,
    currentUser: { id: 1, username: "tester", display_name: "tester", roles: [], can_paper_trade: true, created_at: "2026-06-05T00:00:00+08:00" },
    loading: "",
    monitor: { runtime: null } as any,
    monitorPageProps: baseMonitorPageProps(),
    page: "monitor" as const,
    paperPageProps: {} as any,
    playbookData: {
      strategy: "first_board",
      setStrategy: vi.fn(),
      playbook: null,
      loadPlaybook: vi.fn(),
    } as any,
    settingsData: {
      settings: null,
      runtime: null,
      factorWeights: null,
      adminTasks: null,
      adminMetrics: null,
      strategyGovernance: null,
      sectorExclusions: null,
      factorDraft: {},
      settingsDraft: {},
      setSettingsDraft: vi.fn(),
      setFactorDraft: vi.fn(),
      saveSettings: vi.fn(),
      saveFactorWeights: vi.fn(),
      loadSettings: vi.fn(),
      refreshLatestData: vi.fn(),
      updateStrategyGovernance: vi.fn(),
      saveSectorExclusions: vi.fn(),
    } as any,
    strategyMeta: [],
    onSelectStock: vi.fn(),
    onPreparePaperOrder: vi.fn(),
    onUserUpdate: vi.fn(),
  };
}
