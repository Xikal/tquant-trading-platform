import { Suspense, type ComponentProps, type ComponentType } from "react";
import type { StrategyMeta } from "../../api/strategies";
import type { AuthUser } from "../../types";
import { PageErrorBoundary } from "./PageErrorBoundary";
import type { MonitorPageProps } from "../monitor/MonitorPage";
import type { PaperTradingPageProps } from "../paper/PaperTradingPage";
import type { useAnalysisData } from "./useAnalysisData";
import type { useMonitorData } from "./useMonitorData";
import type { usePlaybookData } from "./usePlaybookData";
import type { useSettingsData } from "./useSettingsData";
import { OBSERVATION_PLAYBOOK_KEYS } from "../workspace-shared/workspaceConstants";
import type { Page, StockCardView } from "../workspace-shared/workspaceTypes";

interface WorkspacePageContentProps {
  AnalysisPage: ComponentType<ComponentProps<any>>;
  BacktestPage: ComponentType<ComponentProps<any>>;
  DataConsolePage: ComponentType<{ currentUser: AuthUser }>;
  MonitorPage: ComponentType<MonitorPageProps>;
  PaperTradingPage: ComponentType<PaperTradingPageProps>;
  PlaybookPage: ComponentType<ComponentProps<any>>;
  SettingsPage: ComponentType<ComponentProps<any>>;
  StrategyTrackingPage: ComponentType<{ strategyMeta: StrategyMeta[] }>;
  analysis: ReturnType<typeof useAnalysisData>;
  currentUser: AuthUser;
  loading: string;
  monitor: ReturnType<typeof useMonitorData>;
  monitorPageProps: MonitorPageProps;
  page: Page;
  paperPageProps: PaperTradingPageProps;
  playbookData: ReturnType<typeof usePlaybookData>;
  settingsData: ReturnType<typeof useSettingsData>;
  strategyMeta: StrategyMeta[];
  onSelectStock: (stock: StockCardView | null) => void;
  onPreparePaperOrder: (payload: { symbol: string; name?: string; price?: number | null }) => void;
  onUserUpdate: (user: AuthUser) => void;
}

export function WorkspacePageContent({
  AnalysisPage,
  BacktestPage,
  DataConsolePage,
  MonitorPage,
  PaperTradingPage,
  PlaybookPage,
  SettingsPage,
  StrategyTrackingPage,
  analysis,
  currentUser,
  loading,
  monitor,
  monitorPageProps,
  page,
  paperPageProps,
  playbookData,
  settingsData,
  strategyMeta,
  onSelectStock,
  onPreparePaperOrder,
  onUserUpdate,
}: WorkspacePageContentProps) {
  const sortedStrategyMeta = strategyMeta
    .slice()
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0));
  const playbookStrategyTabs = sortedStrategyMeta
    .filter((item) => isWebPlaybookStrategy(item))
    .map(strategyTabFromMeta);
  return (
    <PageErrorBoundary resetKey={page}>
      <Suspense fallback={<div className="panel">页面模块加载中...</div>}>
        {page === "monitor" && <MonitorPage {...monitorPageProps} />}
        {page === "analysis" && (
          <AnalysisPage
            draft={analysis.draft}
            setDraft={analysis.setDraft}
            result={analysis.result}
            anomaly={analysis.anomaly}
            batchSymbols={analysis.batchSymbols}
            setBatchSymbols={analysis.setBatchSymbols}
            batchResults={analysis.batchResults}
            loading={loading}
            onRun={() => void analysis.runAnalysis()}
            onBatchRun={() => void analysis.runBatchAnalysis()}
            onOpenPaperOrder={onPreparePaperOrder}
          />
        )}
        {page === "playbook" && (
          <PlaybookPage
            strategy={playbookData.strategy}
            setStrategy={playbookData.setStrategy}
            playbook={playbookData.playbook}
            loading={loading}
            onRefresh={() => void playbookData.loadPlaybook(playbookData.strategy, true)}
            onAnalyze={analysis.analyzeFromCard}
            onSelect={onSelectStock}
            strategyTabs={playbookStrategyTabs}
          />
        )}
        {page === "strategy-tracking" && <StrategyTrackingPage strategyMeta={strategyMeta} />}
        {page === "backtest" && <BacktestPage />}
        {page === "data" && <DataConsolePage currentUser={currentUser} />}
        {page === "paper" && (
          currentUser.can_paper_trade ? (
            <PaperTradingPage {...paperPageProps} />
          ) : (
            <section className="panel auth-guard-panel">
              <h2>模拟盘需申请白名单权限</h2>
              <p>当前账号可以查看行情和策略，但暂未开通模拟交易。请联系管理员加入模拟盘白名单。</p>
            </section>
          )
        )}
        {page === "settings" && (
          <SettingsPage
            settings={settingsData.settings}
            runtime={monitor.runtime}
            factorWeights={settingsData.factorWeights}
            adminTasks={settingsData.adminTasks}
            adminMetrics={settingsData.adminMetrics}
            strategyGovernance={settingsData.strategyGovernance}
            sectorExclusions={settingsData.sectorExclusions}
            factorDraft={settingsData.factorDraft}
            draft={settingsData.settingsDraft}
            setDraft={settingsData.setSettingsDraft}
            setFactorDraft={settingsData.setFactorDraft}
            loading={loading}
            onSave={settingsData.saveSettings}
            onSaveFactors={settingsData.saveFactorWeights}
            onRefresh={() => void settingsData.loadSettings()}
            onRefreshLatestData={() => void settingsData.refreshLatestData()}
            onUpdateStrategyGovernance={(strategyKey: string, status: "active" | "watch" | "paused") => void settingsData.updateStrategyGovernance(strategyKey, status)}
            onSaveSectorExclusions={(excludedSectors: string[]) => void settingsData.saveSectorExclusions(excludedSectors)}
            currentUser={currentUser}
            onUserUpdate={onUserUpdate}
          />
        )}
      </Suspense>
    </PageErrorBoundary>
  );
}

function strategyTabFromMeta(item: StrategyMeta) {
  return { key: item.key, label: item.display_name || item.name || item.key };
}

function isProductionStrategyTier(item: StrategyMeta) {
  const tier = item.tier || item.category_key;
  return tier === "core" || tier === "auxiliary";
}

function isWebPlaybookStrategy(item: StrategyMeta) {
  if (item.enabled === false || item.visibility !== "full") {
    return false;
  }
  return isProductionStrategyTier(item) || OBSERVATION_PLAYBOOK_KEYS.has(item.key);
}
