import { lazy } from "react";
import type { AiDecisionSupportResponse, AuthUser } from "../../types";
import type { StrategyMeta } from "../../api/strategies";
import { CommandPalette } from "./CommandPalette";
import { Topbar } from "./Topbar";
import { AiInsightDialog, ErrorDialog, StatusStrip, StockDetailDialog } from "../workspace-shared/WorkspaceComponents";
import type { Page, StockCardView } from "../workspace-shared/workspaceTypes";
import { WorkspacePageContent } from "./WorkspacePageContent";

const AnalysisPage = lazy(async () => ({ default: (await import("../analysis/AnalysisPage")).AnalysisPage }));
const MarketEmotionPage = lazy(async () => ({ default: (await import("../market-emotion/MarketEmotionPage")).MarketEmotionPage }));
const MonitorPage = lazy(async () => ({ default: (await import("../monitor/MonitorPage")).MonitorPage }));
const PaperTradingPage = lazy(async () => ({ default: (await import("../paper/PaperTradingPage")).PaperTradingPage }));
const PlaybookPage = lazy(async () => ({ default: (await import("../playbook/PlaybookPage")).PlaybookPage }));
const SettingsPage = lazy(async () => ({ default: (await import("../settings/SettingsPage")).SettingsPage }));
const StrategyHubPage = lazy(async () => ({ default: (await import("../strategy/StrategyHubPage")).StrategyHubPage }));

type TradingWorkspaceChromeProps = {
  aiDialogOpen: boolean;
  aiLoading: boolean;
  aiResult: AiDecisionSupportResponse | null;
  analysis: any;
  commandOpen: boolean;
  commandStrategies: StrategyMeta[];
  currentUser: AuthUser;
  error: string;
  loading: string;
  monitor: any;
  monitorPageProps: any;
  notice: string;
  page: Page;
  paperPageProps: any;
  paperRefreshLoading: boolean;
  playbookData: any;
  selectedStock: StockCardView | null;
  settingsData: any;
  strategyMeta: StrategyMeta[];
  onAnalyzeSymbol: (symbol: string) => void;
  onCloseAi: () => void;
  onCloseCommand: () => void;
  onCloseError: () => void;
  onCloseStock: () => void;
  onLogout: () => void;
  onNavigate: (page: Page) => void;
  onOpenStrategy: (strategyKey: string) => void;
  onPaperRefresh?: () => void;
  onPreparePaperOrder: (payload: { symbol: string; name?: string; price?: number | null }) => void;
  onSelectStock: (stock: StockCardView | null) => void;
  onUserUpdate: (user: AuthUser) => void;
};

export function TradingWorkspaceChrome(props: TradingWorkspaceChromeProps) {
  return (
    <div className={`app page-${props.page}`}>
      <Topbar
        page={props.page}
        setPage={props.onNavigate}
        priorityBoard={props.monitor.priorityBoard}
        watchCards={props.monitor.watchCards}
        currentUser={props.currentUser}
        onLogout={props.onLogout}
        onPaperRefresh={props.onPaperRefresh}
        paperRefreshLoading={props.paperRefreshLoading}
      />
      <main className="workspace">
        <StatusStrip loading={props.loading} notice={props.notice} />
        <ErrorDialog message={props.error} onClose={props.onCloseError} />
        <StockDetailDialog
          stock={props.selectedStock}
          onClose={props.onCloseStock}
          onAnalyze={props.analysis.analyzeFromCard}
        />
        {props.aiDialogOpen ? (
          <AiInsightDialog
            response={props.aiResult}
            loading={props.aiLoading}
            onClose={props.onCloseAi}
          />
        ) : null}
        <CommandPalette
          open={props.commandOpen}
          strategies={props.commandStrategies}
          onClose={props.onCloseCommand}
          onNavigate={props.onNavigate}
          onAnalyzeSymbol={props.onAnalyzeSymbol}
          onOpenStrategy={props.onOpenStrategy}
        />
        <WorkspacePageContent
          AnalysisPage={AnalysisPage}
          MarketEmotionPage={MarketEmotionPage}
          MonitorPage={MonitorPage}
          PaperTradingPage={PaperTradingPage}
          PlaybookPage={PlaybookPage}
          SettingsPage={SettingsPage}
          StrategyHubPage={StrategyHubPage}
          analysis={props.analysis}
          currentUser={props.currentUser}
          loading={props.loading}
          monitor={props.monitor}
          monitorPageProps={props.monitorPageProps}
          page={props.page}
          paperPageProps={props.paperPageProps}
          playbookData={props.playbookData}
          settingsData={props.settingsData}
          strategyMeta={props.strategyMeta}
          onSelectStock={props.onSelectStock}
          onPreparePaperOrder={props.onPreparePaperOrder}
          onUserUpdate={props.onUserUpdate}
        />
      </main>
    </div>
  );
}
