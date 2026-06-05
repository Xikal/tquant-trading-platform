import { lazy } from "react";
import { Drawer, Grid } from "antd";
import type { AiDecisionSupportResponse, AuthUser } from "../../types";
import type { StrategyMeta } from "../../api/strategies";
import { useWorkspaceStore } from "../../stores/workspaceStore";
import { AppSidebar } from "./AppSidebar";
import { CommandPalette } from "./CommandPalette";
import { Topbar } from "./Topbar";
import { AiInsightDialog, ErrorDialog, StatusStrip, StockDetailDialog } from "../workspace-shared/WorkspaceComponents";
import { RitualBlessingModal } from "../ritual-ui";
import type { Page, StockCardView } from "../workspace-shared/workspaceTypes";
import { WorkspacePageContent } from "./WorkspacePageContent";
import { PagePriorityStrip } from "./PagePriorityStrip";
import {
  CONTENT_INNER_STYLE,
  CONTENT_MAIN_STYLE,
  DRAWER_BODY_STYLE,
  SIDEBAR_COLLAPSED_WIDTH,
  SIDEBAR_WIDTH,
  WORKSPACE_SHELL_STYLE,
  contentColStyle,
  sidebarStyle,
} from "./workspaceShellStyles";

const { useBreakpoint } = Grid;

const AnalysisPage = lazy(async () => ({ default: (await import("../analysis/AnalysisPage")).AnalysisPage }));
const BacktestPage = lazy(async () => ({ default: (await import("../backtest/BacktestPage")).BacktestPage }));
const MonitorPage = lazy(async () => ({ default: (await import("../monitor/MonitorPage")).MonitorPage }));
const MonitorMarketPage = lazy(async () => ({ default: (await import("../monitor/MonitorMarketPage")).MonitorMarketPage }));
const PaperTradingPage = lazy(async () => ({ default: (await import("../paper/PaperTradingPage")).PaperTradingPage }));
const PlaybookPage = lazy(async () => ({ default: (await import("../playbook/PlaybookPage")).PlaybookPage }));
const SettingsPage = lazy(async () => ({ default: (await import("../settings/SettingsPage")).SettingsPage }));
const StrategyTrackingPage = lazy(async () => ({ default: (await import("../strategy-tracking/StrategyTrackingPage")).StrategyTrackingPage }));
const DataConsolePage = lazy(async () => ({ default: (await import("../data-console/DataConsolePage")).DataConsolePage }));

const PAGES_WITHOUT_PRIORITY_STRIP: ReadonlySet<Page> = new Set([
  "monitor",
  "monitor-market",
  "strategy-tracking",
  "backtest",
  "paper",
  "data",
]);

export function shouldShowPagePriorityStrip(page: Page): boolean {
  return !PAGES_WITHOUT_PRIORITY_STRIP.has(page);
}

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
  const screens = useBreakpoint();
  const isDesktop = screens.lg ?? true;
  const collapsed = useWorkspaceStore((state) => state.sidebarCollapsed);
  const toggleCollapsed = useWorkspaceStore((state) => state.toggleSidebarCollapsed);
  const mobileNavOpen = useWorkspaceStore((state) => state.mobileNavOpen);
  const setMobileNavOpen = useWorkspaceStore((state) => state.setMobileNavOpen);
  const marginLeft = isDesktop ? (collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH) : 0;

  return (
    <div style={WORKSPACE_SHELL_STYLE}>
      {isDesktop ? (
        <aside style={sidebarStyle(collapsed)}>
          <AppSidebar
            page={props.page}
            currentUser={props.currentUser}
            collapsed={collapsed}
            onNavigate={props.onNavigate}
            onToggleCollapse={toggleCollapsed}
          />
        </aside>
      ) : (
        <Drawer
          placement="left"
          width={SIDEBAR_WIDTH}
          open={mobileNavOpen}
          closable={false}
          styles={{ body: DRAWER_BODY_STYLE }}
          onClose={() => setMobileNavOpen(false)}
        >
          <AppSidebar
            page={props.page}
            currentUser={props.currentUser}
            collapsed={false}
            onNavigate={props.onNavigate}
            onItemClick={() => setMobileNavOpen(false)}
          />
        </Drawer>
      )}
      <div style={contentColStyle(marginLeft)}>
        <Topbar
          page={props.page}
          currentUser={props.currentUser}
          priorityBoard={props.monitor.priorityBoard}
          watchCards={props.monitor.watchCards}
          onLogout={props.onLogout}
          onNavigate={props.onNavigate}
          onOpenNav={() => setMobileNavOpen(true)}
          onPaperRefresh={props.onPaperRefresh}
          paperRefreshLoading={props.paperRefreshLoading}
        />
        <main style={CONTENT_MAIN_STYLE}>
          <div style={CONTENT_INNER_STYLE}>
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
            <RitualBlessingModal userId={props.currentUser.id} />
            {shouldShowPagePriorityStrip(props.page) ? <PagePriorityStrip page={props.page} /> : null}
            <WorkspacePageContent
              AnalysisPage={AnalysisPage}
              BacktestPage={BacktestPage}
              DataConsolePage={DataConsolePage}
              MonitorPage={MonitorPage}
              MonitorMarketPage={MonitorMarketPage}
              PaperTradingPage={PaperTradingPage}
              PlaybookPage={PlaybookPage}
              SettingsPage={SettingsPage}
              StrategyTrackingPage={StrategyTrackingPage}
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
          </div>
        </main>
      </div>
    </div>
  );
}
