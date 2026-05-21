import { useEffect } from "react";
import { Button } from "antd";
import { ErrorBanner } from "../../components/shared/Feedback";
import { useToast } from "../../components/shared/ToastContainer";
import type { AuthUser } from "../../types";
import type { BacktestRunSummary } from "../../api/backtests";
import { formatDateTime, formatMoney, formatPct } from "../backtest/backtestDisplay";
import { StrategyConfirmDialog } from "./StrategyConfirmDialog";
import { StrategyHubDetailTabs } from "./StrategyHubDetailTabs";
import {
  executionModelText,
  visibleTabsForUser,
} from "./StrategyHubPanels";
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
  const latestRun = hub.runs[0];
  const completedRuns = hub.runs.filter((run) => run.status === "completed" || run.status === "succeeded");
  const avgWinRate = average(completedRuns.map((run) => run.summary?.win_rate_pct));
  const heroSummary = `市场今日：以实时监控为准 · 生产策略 ${hub.strategies.filter((item) => item.visibility === "full" && item.enabled !== false).length} 个 · 最近回测胜率 ${formatPct(avgWinRate)}`;

  return (
    <section className="strategy-hub">
      <StrategyHubSummaryBar
        runs={hub.runs}
        strategies={hub.strategies}
        loading={hub.loading === "submit" || hub.loading === "quick-submit"}
        onStartCheck={() => hub.setConfirmOpen(true)}
      />

      {hub.error ? <ErrorBanner message={`策略工作台加载失败：${hub.error}`} /> : null}
      {hub.notice ? <div className="panel strategy-notice">{hub.notice}</div> : null}
      <section className="panel strategy-hero-mini">
        <div>
          <strong>今日状态摘要</strong>
          <span>{heroSummary}</span>
        </div>
        {latestRun ? <LatestRunCard run={latestRun} /> : <small>还没有最近一次回测</small>}
        <Button type="default" onClick={() => void hub.load()} loading={hub.loading === "load"}>
          {hub.loading === "load" ? "刷新中" : "刷新"}
        </Button>
      </section>
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
          title="🚀 确认提交回测"
          description="提交前请核对策略、日期和资金。任务异步执行，可在策略历史查看进度。"
          summaryItems={confirmSummaryItems}
          onCancel={() => hub.setConfirmOpen(false)}
          onConfirm={submitWithToast}
        />
      ) : null}
    </section>
  );
}

function LatestRunCard({ run }: { run: BacktestRunSummary }) {
  const winRate = typeof run.summary?.win_rate_pct === "number" ? formatPct(run.summary.win_rate_pct) : "完成后显示";
  const conclusion = run.status === "completed" || run.status === "succeeded"
    ? `胜率 ${winRate}`
    : run.status === "failed"
      ? "任务失败"
      : "正在计算";
  return (
    <aside className="strategy-latest-run" aria-label="最近一次回测">
      <span>我的最近一次回测</span>
      <strong>{conclusion}</strong>
      <small>{formatDateTime(run.created_at)}</small>
    </aside>
  );
}

function average(values: Array<number | null | undefined>): number | undefined {
  const filtered = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!filtered.length) return undefined;
  return filtered.reduce((sum, value) => sum + value, 0) / filtered.length;
}

function estimateSubmitTime(strategyCount: number): string {
  if (strategyCount <= 2) return "< 1 分钟（轻量回测）";
  if (strategyCount <= 5) return "约 1-3 分钟";
  return "约 3-10 分钟";
}

function isExpertHubTab(tab: string): boolean {
  return tab === "optimize" || tab === "validate" || tab === "compare" || tab === "capacity" || tab === "factor";
}
