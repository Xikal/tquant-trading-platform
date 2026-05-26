import { useEffect } from "react";
import { Alert, Button, Space } from "antd";
import { ErrorBanner } from "../../components/shared/Feedback";
import { useToast } from "../../components/shared/ToastContainer";
import type { AuthUser } from "../../types";
import type { BacktestRunSummary } from "../../api/backtests";
import { formatMoney } from "../backtest/backtestDisplay";
import { WorkspacePageIntro } from "../workspace-shared/WorkspacePageIntro";
import { StrategyConfirmDialog } from "./StrategyConfirmDialog";
import { StrategyHubDetailTabs } from "./StrategyHubDetailTabs";
import { executionModelText, visibleTabsForUser } from "./StrategyHubPanels";
import { StrategyHubSummaryBar } from "./StrategyHubSummaryBar";
import { StrategyWorkflow } from "./StrategyWorkflow";
import { useStrategyHub } from "./useStrategyHub";

export function StrategyHubPage({ currentUser }: { currentUser: AuthUser }) {
  const hub = useStrategyHub();
  const expertEnabled = visibleTabsForUser(currentUser).some((tab) => isExpertHubTab(tab.key));
  const effectiveTab = !expertEnabled && isExpertHubTab(hub.tab) ? "quick" : hub.tab;
  const toast = useToast();

  useEffect(() => {
    if (!expertEnabled && isExpertHubTab(hub.tab)) {
      hub.setTab("quick");
    }
  }, [expertEnabled, hub.tab, hub.setTab]);

  function submitWithToast() {
    void hub.submit().then((ok) => {
      if (ok) {
        toast.pushToast({ tone: "success", title: "回测任务已提交", description: "可在右侧任务列表查看进度。" });
      }
    });
  }

  function quickSubmitWithToast() {
    void hub.submitQuickBacktest().then((ok) => {
      if (ok) {
        toast.pushToast({
          tone: "success",
          title: "一键回测已提交",
          description: "已进入策略历史，可在任务列表查看进度。",
        });
      }
    });
  }

  function rerunBacktest(run: BacktestRunSummary) {
    hub.updateForm({
      name: `${run.name || "策略体检"} - 重新运行`,
      strategies: run.strategies?.length ? run.strategies : hub.form.strategies,
      start_date: run.start_date || hub.form.start_date,
      end_date: run.end_date || hub.form.end_date,
      initial_capital: String(run.initial_capital ?? run.initial_cash ?? hub.form.initial_capital),
      execution_model: (run.execution_model || hub.form.execution_model) as typeof hub.form.execution_model,
      benchmark: run.benchmark || run.benchmark_symbol || hub.form.benchmark,
      max_position_pct: String(run.risk_limits?.max_position_pct ?? hub.form.max_position_pct),
      max_positions: String(run.risk_limits?.max_positions ?? hub.form.max_positions),
    });
    hub.setConfirmOpen(true);
  }

  const confirmSummaryItems = [
    {
      label: "选中策略",
      value: `${hub.selectedStrategyNames.join("、") || "未选择"}（共 ${hub.form.strategies.length} 个）`,
    },
    { label: "回测日期", value: `${hub.form.start_date} → ${hub.form.end_date}` },
    { label: "初始资金", value: formatMoney(Number(hub.form.initial_capital) || 0) },
    { label: "成交模型", value: executionModelText(hub.form.execution_model) },
    { label: "预计耗时", value: estimateSubmitTime(hub.form.strategies.length) },
  ];
  const runningCount = hub.runs.filter((run) => run.status === "queued" || run.status === "running").length;
  const completedCount = hub.runs.filter((run) => run.status === "completed" || run.status === "succeeded").length;
  return (
    <Space direction="vertical" size={8} style={{ display: "flex" }}>
      <div className="panel">
        <WorkspacePageIntro
          title="策略工作台"
          summary={expertEnabled ? "生产策略、研究验证、容量评估。" : "一键体检、策略历史、可执行入口。"}
          more="回测页保持独立入口；策略工作台负责策略选择、提交和运行状态。"
          moreLabel="工作台边界"
          tone={runningCount ? "warn" : hub.error ? "down" : "neutral"}
          actions={<Button type="primary" onClick={() => hub.setConfirmOpen(true)} loading={hub.loading === "submit"}>提交回测</Button>}
          pills={[
            { label: "策略数", value: String(hub.strategies.length) },
            { label: "任务数", value: String(hub.runs.length) },
            { label: "运行中", value: String(runningCount), tone: runningCount ? "warn" : "neutral" },
            { label: "已完成", value: String(completedCount), tone: completedCount ? "up" : "neutral" },
          ]}
        />
      </div>
      <StrategyHubSummaryBar
        runs={hub.runs}
        strategies={hub.strategies}
        loading={hub.loading === "submit" || hub.loading === "quick-submit"}
        onStartCheck={() => hub.setConfirmOpen(true)}
      />

      {hub.error ? <ErrorBanner message={`策略工作台加载失败：${hub.error}`} /> : null}
      {hub.notice ? <Alert type="info" showIcon message={hub.notice} /> : null}
      <StrategyWorkflow
        activeTab={effectiveTab}
        runs={hub.runs}
        mode={expertEnabled ? "expert" : "simple"}
        showExpert={expertEnabled}
        onSelect={hub.setTab}
      />
      <StrategyHubDetailTabs
        currentUser={currentUser}
        hub={hub}
        onQuickSubmit={quickSubmitWithToast}
        onRerun={rerunBacktest}
      />

      {hub.confirmOpen ? (
        <StrategyConfirmDialog
          loading={hub.loading === "submit"}
          title="确认提交回测"
          description="提交前请核对策略、日期和资金。任务异步执行，可在策略历史查看进度。"
          summaryItems={confirmSummaryItems}
          onCancel={() => hub.setConfirmOpen(false)}
          onConfirm={submitWithToast}
        />
      ) : null}
    </Space>
  );
}

function estimateSubmitTime(strategyCount: number): string {
  if (strategyCount <= 2) return "< 1 分钟（轻量回测）";
  if (strategyCount <= 5) return "约 1-3 分钟";
  return "约 3-10 分钟";
}

function isExpertHubTab(tab: string): boolean {
  return tab === "optimize" || tab === "validate" || tab === "compare" || tab === "capacity" || tab === "factor";
}
