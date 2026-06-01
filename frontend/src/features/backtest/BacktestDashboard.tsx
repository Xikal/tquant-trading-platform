import { useEffect } from "react";
import { Collapse, Grid, Tabs, Typography } from "antd";
import type {
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestStatus,
  BacktestTrade,
  EquityPoint,
} from "../../api/backtests";
import type { BacktestFormState } from "./backtestForms";
import { loadBacktestVerdictThresholds } from "./backtestDisplay";
import { STATUS_META } from "./BacktestDashboard.helpers";
import { BacktestResearchPanel, type BacktestResearchActions, type BacktestResearchState } from "./BacktestResearchPanel";
import { useBacktestStrategyOptions } from "./useBacktestStrategyOptions";
import { useBacktestUiStore } from "../../stores/backtestUiStore";
import { BacktestSubmitPanel } from "./BacktestSubmitPanel";
import {
  BacktestResearchTabs,
  EquityPanel,
  HeaderPill,
  RunDetailPanel,
  RunListPanel,
  TradesPanel,
  resolveAttribution,
  resolveMetrics,
} from "./BacktestDashboard.panels";
import {
  BACKTEST_STATUS_BASE_STYLE,
  BACKTEST_STATUS_LABEL_STYLE,
  backtestStatusToneStyle,
  combineBacktestStyles,
} from "./backtestStyles";
import {
  BACKTEST_HEADER_ACTIONS_STYLE,
  BACKTEST_HEADER_METRICS_STYLE,
  BACKTEST_HEADER_SUMMARY_STYLE,
  BACKTEST_HEADER_TITLE_STYLE,
  BACKTEST_HEADER_TITLE_WRAP_STYLE,
  BACKTEST_STATUS_RAIL_GRID_STYLE,
  BACKTEST_STATUS_RAIL_STYLE,
  BACKTEST_STATUS_RAIL_SUMMARY_STYLE,
  BACKTEST_TAB_BODY_STYLE,
  BACKTEST_TABS_STYLE,
  backtestOverviewTabGridStyle,
  backtestSubmitTabGridStyle,
  backtestDashboardGridStyle,
  backtestHeroStyle,
} from "./backtestPageLayoutStyles";
const { useBreakpoint } = Grid;

export type { BacktestFormState } from "./backtestForms";

export interface BacktestDashboardProps {
  form: BacktestFormState;
  runs: BacktestRunSummary[];
  selectedRun: BacktestRunDetail | null;
  equity: EquityPoint[];
  trades: BacktestTrade[];
  loading: string;
  error: string;
  notice: string;
  research: BacktestResearchState;
  researchActions: BacktestResearchActions;
  onFormChange: (patch: Partial<BacktestFormState>) => void;
  onToggleStrategy: (strategy: string) => void;
  onSubmit: () => void;
  onRefresh: () => void;
  onSelectRun: (runId: number) => void;
  onCancelRun: (runId: number) => void;
}

export function BacktestDashboard({
  form,
  runs,
  selectedRun,
  equity,
  trades,
  loading,
  error,
  notice,
  research,
  researchActions,
  onFormChange,
  onSubmit,
  onRefresh,
  onSelectRun,
  onCancelRun,
}: BacktestDashboardProps) {
  const strategyOptions = useBacktestStrategyOptions();
  const selectedId = selectedRun?.id ?? runs[0]?.id;
  const selectedMetrics = selectedRun ? resolveMetrics(selectedRun) : null;
  const selectedAttribution = selectedRun ? resolveAttribution(selectedRun) : null;
  const mode = useBacktestUiStore((state) => state.mode);
  const activeTab = useBacktestUiStore((state) => state.activeTab);
  const activeTabTouched = useBacktestUiStore((state) => state.activeTabTouched);
  const screens = useBreakpoint();
  const wideLayout = Boolean(screens.xl);
  useBacktestUiStore((state) => state.verdictThresholdVersion);
  const setMode = useBacktestUiStore((state) => state.setMode);
  const setActiveTab = useBacktestUiStore((state) => state.setActiveTab);
  const bumpVerdictThresholdVersion = useBacktestUiStore((state) => state.bumpVerdictThresholdVersion);
  const resolvedActiveTab = selectedRun && !activeTabTouched ? "overview" : activeTab;
  const runningCount = runs.filter((run) => run.status === "queued" || run.status === "running").length;
  const completedCount = runs.filter((run) => run.status === "completed" || run.status === "succeeded").length;
  const tabItems = [
    {
      key: "submit",
      label: "提交任务",
      children: (
        <div style={backtestSubmitTabGridStyle(wideLayout)}>
          <BacktestSubmitPanel
            form={form}
            loading={loading}
            error={error}
            notice={notice}
            mode={mode}
            strategyOptions={strategyOptions}
            onModeChange={setMode}
            onFormChange={onFormChange}
            onSubmit={onSubmit}
            onRefresh={onRefresh}
          />
          <RunListPanel
            runs={runs}
            selectedId={selectedId}
            onSelectRun={onSelectRun}
          />
        </div>
      ),
    },
    {
      key: "overview",
      label: "结果概览",
      children: (
        <div style={backtestOverviewTabGridStyle(wideLayout)}>
          <RunDetailPanel
            loading={loading}
            selectedAttribution={selectedAttribution}
            selectedMetrics={selectedMetrics}
            selectedRun={selectedRun}
            onCancelRun={onCancelRun}
          />
          <EquityPanel equity={equity} />
        </div>
      ),
    },
    {
      key: "trades",
      label: "成交明细",
      children: <TradesPanel trades={trades} />,
    },
    {
      key: "etf-t0",
      label: "ETF T0",
      children: <BacktestResearchPanel state={research} actions={researchActions} sections={["etf-t0"]} equity={equity} />,
    },
    {
      key: "research",
      label: "研究闭环",
      children: <BacktestResearchTabs state={research} actions={researchActions} equity={equity} />,
    },
  ];

  useEffect(() => {
    let active = true;
    void loadBacktestVerdictThresholds().then(() => {
      if (active) bumpVerdictThresholdVersion();
    });
    return () => {
      active = false;
    };
  }, [bumpVerdictThresholdVersion]);

  return (
    <section className="backtest-page" style={backtestDashboardGridStyle(wideLayout)}>
      <div className="panel" style={backtestHeroStyle(wideLayout)}>
        <div style={BACKTEST_HEADER_TITLE_WRAP_STYLE}>
          <Typography.Text strong style={BACKTEST_HEADER_TITLE_STYLE}>回测页</Typography.Text>
          <Typography.Text style={BACKTEST_HEADER_SUMMARY_STYLE}>
            {runs.length} 任务 / {runningCount} 运行 / {trades.length} 成交
          </Typography.Text>
        </div>
        <div style={BACKTEST_HEADER_METRICS_STYLE}>
          <HeaderPill label="任务" value={String(runs.length)} />
          <HeaderPill label="运行中" value={String(runningCount)} tone={runningCount ? "warn" : "neutral"} />
          <HeaderPill label="已完成" value={String(completedCount)} tone={completedCount ? "up" : "neutral"} />
          <HeaderPill label="成交" value={String(trades.length)} />
        </div>
        <div style={BACKTEST_HEADER_ACTIONS_STYLE}>
          <Collapse
            ghost
            size="small"
            style={BACKTEST_STATUS_RAIL_STYLE}
            items={[{
              key: "status",
              label: <span style={BACKTEST_STATUS_RAIL_SUMMARY_STYLE}>状态图例</span>,
              children: (
                <div style={BACKTEST_STATUS_RAIL_GRID_STYLE}>
                  {(Object.keys(STATUS_META) as BacktestStatus[]).map((status) => (
                    <span
                      key={status}
                      style={combineBacktestStyles(BACKTEST_STATUS_BASE_STYLE, backtestStatusToneStyle(STATUS_META[status].tone))}
                    >
                      {status}<small style={BACKTEST_STATUS_LABEL_STYLE}>{STATUS_META[status].label}</small>
                    </span>
                  ))}
                </div>
              ),
            }]}
          />
        </div>
      </div>
      <Tabs
        size="small"
        style={BACKTEST_TABS_STYLE}
        tabBarGutter={8}
        activeKey={resolvedActiveTab}
        onChange={(key) => setActiveTab(key as typeof resolvedActiveTab)}
        items={tabItems.map((item) => ({
          ...item,
          children: <div style={BACKTEST_TAB_BODY_STYLE}>{item.children}</div>,
        }))}
      />
    </section>
  );
}
