import { Suspense, type ComponentProps, type ComponentType } from "react";
import type { StrategyMeta } from "../../api/strategies";
import type { AuthUser } from "../../types";
import { PageErrorBoundary } from "./PageErrorBoundary";
import type { MonitorPageProps } from "./MonitorPage";
import type { PaperTradingPageProps } from "./PaperTradingPage";
import type { useAnalysisData } from "./useAnalysisData";
import type { useMonitorData } from "./useMonitorData";
import type { usePlaybookData } from "./usePlaybookData";
import type { useResearchData } from "./useResearchData";
import type { useSettingsData } from "./useSettingsData";
import type { Page, StockCardView } from "./workspaceTypes";

interface WorkspacePageContentProps {
  AnalysisPage: ComponentType<ComponentProps<any>>;
  BacktestPage: ComponentType;
  MonitorPage: ComponentType<MonitorPageProps>;
  PaperTradingPage: ComponentType<PaperTradingPageProps>;
  PerformanceDashboard: ComponentType;
  PlaybookPage: ComponentType<ComponentProps<any>>;
  ResearchPage: ComponentType<ComponentProps<any>>;
  SettingsPage: ComponentType<ComponentProps<any>>;
  StrategyHubPage: ComponentType<{ currentUser: AuthUser }>;
  analysis: ReturnType<typeof useAnalysisData>;
  currentUser: AuthUser;
  loading: string;
  monitor: ReturnType<typeof useMonitorData>;
  monitorPageProps: MonitorPageProps;
  page: Page;
  paperPageProps: PaperTradingPageProps;
  playbookData: ReturnType<typeof usePlaybookData>;
  research: ReturnType<typeof useResearchData>;
  settingsData: ReturnType<typeof useSettingsData>;
  strategyMeta: StrategyMeta[];
  onSelectStock: (stock: StockCardView | null) => void;
  onPreparePaperOrder: (payload: { symbol: string; name?: string; price?: number | null }) => void;
}

export function WorkspacePageContent({
  AnalysisPage,
  BacktestPage,
  MonitorPage,
  PaperTradingPage,
  PerformanceDashboard,
  PlaybookPage,
  ResearchPage,
  SettingsPage,
  StrategyHubPage,
  analysis,
  currentUser,
  loading,
  monitor,
  monitorPageProps,
  page,
  paperPageProps,
  playbookData,
  research,
  settingsData,
  strategyMeta,
  onSelectStock,
  onPreparePaperOrder,
}: WorkspacePageContentProps) {
  const sortedStrategyMeta = strategyMeta
    .slice()
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0));
  const productionStrategyTabs = sortedStrategyMeta
    .filter((item) => isProductionStrategyTier(item))
    .map(strategyTabFromMeta);
  const allStrategyTabs = sortedStrategyMeta.map(strategyTabFromMeta);
  return (
    <PageErrorBoundary resetKey={page}>
      <Suspense fallback={<div className="panel">页面模块加载中...</div>}>
        {page === "monitor" && <MonitorPage {...monitorPageProps} />}
        {page === "analysis" && (
          <AnalysisPage
            draft={analysis.draft}
            setDraft={analysis.setDraft}
            result={analysis.result}
            loading={loading}
            onRun={() => void analysis.runAnalysis()}
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
            strategyTabs={productionStrategyTabs}
          />
        )}
        {page === "strategy" && <StrategyHubPage currentUser={currentUser} />}
        {page === "research" && (
          <ResearchPage
            replays={research.replays}
            priorityBoard={research.researchBoard}
            lifecycleItems={research.tradeLifecycles}
            draft={research.draft}
            setDraft={research.setDraft}
            result={research.backtestResult}
            runs={research.backtestRuns}
            executionBacktest={research.executionBacktest}
            strategyValidation={research.strategyValidation}
            loading={loading}
            onRun={() => void research.runBacktest()}
            onValidate={() => void research.runStrategyValidation()}
            onRefresh={() => void research.loadResearch()}
            strategyTabs={allStrategyTabs}
          />
        )}
        {page === "backtests" && <BacktestPage />}
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
        {page === "performance" && (
          currentUser.can_paper_trade ? (
            <PerformanceDashboard />
          ) : (
            <section className="panel auth-guard-panel">
              <h2>绩效看板需模拟盘权限</h2>
              <p>当前账号暂未开通模拟盘白名单，无法查看模拟交易绩效。</p>
            </section>
          )
        )}
        {page === "settings" && (
          <SettingsPage
            settings={settingsData.settings}
            runtime={monitor.runtime}
            factorWeights={settingsData.factorWeights}
            adminTasks={settingsData.adminTasks}
            strategyGovernance={settingsData.strategyGovernance}
            factorDraft={settingsData.factorDraft}
            draft={settingsData.settingsDraft}
            setDraft={settingsData.setSettingsDraft}
            setFactorDraft={settingsData.setFactorDraft}
            loading={loading}
            onSave={settingsData.saveSettings}
            onSaveFactors={settingsData.saveFactorWeights}
            onRefresh={() => void settingsData.loadSettings()}
            onUpdateStrategyGovernance={(strategyKey: string, status: "active" | "watch" | "paused") => void settingsData.updateStrategyGovernance(strategyKey, status)}
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
