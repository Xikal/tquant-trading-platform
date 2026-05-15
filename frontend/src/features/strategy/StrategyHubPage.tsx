import { EmptyPlaceholder, ErrorBanner, SkeletonBlock } from "../../components/shared/Feedback";
import { useToast } from "../../components/shared/ToastContainer";
import type { AuthUser } from "../../types";
import type { BacktestRunSummary } from "../../api/backtests";
import { formatDateTime, formatMoney, formatPct } from "../backtest/backtestDisplay";
import { useBacktestDashboard } from "../backtest/useBacktestDashboard";
import { StrategyDoctorPanel } from "./StrategyDoctorPanel";
import { StrategyConfirmDialog } from "./StrategyConfirmDialog";
import { StrategyTrafficLights } from "./StrategyTrafficLights";
import { StrategyWorkflowSteps } from "./StrategyWorkflowSteps";
import {
  dashboardSectionForTab,
  executionModelText,
  PanelTitle,
  RecentRuns,
  StrategyBridge,
  StrategyHistoryPanel,
  visibleTabsForUser,
} from "./StrategyHubPanels";
import { QuickBacktestForm } from "./StrategyQuickCheckPanel";
import { useStrategyHub } from "./useStrategyHub";

export function StrategyHubPage({ currentUser }: { currentUser: AuthUser }) {
  const hub = useStrategyHub();
  const dashboard = useBacktestDashboard(dashboardSectionForTab(hub.tab));
  const toast = useToast();

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

  const content = hub.loading === "tab-switch" ? (
    <section className="panel strategy-tab-skeleton" aria-live="polite">
      <SkeletonBlock rows={5} title />
    </section>
  ) : hub.tab === "quick" ? (
    <div className="strategy-layout">
      <section className="panel strategy-form-panel">
        <PanelTitle title="一键体检" />
        <QuickBacktestForm hub={hub} onQuickSubmit={quickSubmitWithToast} />
      </section>
      <aside className="strategy-side">
        <section className="panel strategy-presets">
          <PanelTitle title="预设方案" />
          <div className="strategy-preset-list">
            {hub.presets.map((preset) => (
              <button type="button" key={preset.key ?? preset.id ?? preset.name} onClick={() => hub.applyPreset(preset)}>
                <strong>{preset.name}</strong>
                <span>{preset.description}</span>
              </button>
            ))}
            {!hub.presets.length && hub.loading === "load" ? <SkeletonBlock rows={3} title /> : null}
            {!hub.presets.length && hub.loading !== "load" ? <EmptyPlaceholder title="暂无预设" description="后端未返回预设配置。" /> : null}
          </div>
        </section>
        <section className="panel strategy-run-panel">
          <PanelTitle title="最近任务" />
          <RecentRuns runs={hub.runs} onRerun={rerunBacktest} />
        </section>
      </aside>
    </div>
  ) : hub.tab === "history" ? (
    <StrategyHistoryPanel runs={hub.runs} onRefresh={() => void hub.load()} onRerun={rerunBacktest} />
  ) : (
    <StrategyBridge tab={hub.tab} currentUser={currentUser} dashboard={dashboard} />
  );

  return (
    <section className="strategy-hub">
      <header className="panel strategy-hero">
        <div>
          <span className="strategy-kicker">策略健康中心</span>
          <h1>判断策略还能不能用</h1>
          <p>{heroSummary}</p>
          <small>系统会把回测、复盘和验证翻译成直白结论：可继续观察、谨慎使用，或暂不建议使用。</small>
        </div>
        {latestRun ? <LatestRunCard run={latestRun} /> : null}
        <div className="strategy-hero-actions">
          <button type="button" onClick={() => void hub.load()} disabled={hub.loading === "load"}>
            {hub.loading === "load" ? "刷新中" : "刷新"}
          </button>
          <button type="button" className="primary" onClick={() => hub.setConfirmOpen(true)} disabled={hub.loading === "submit"}>
            🚀 手动提交体检
          </button>
        </div>
      </header>

      {hub.error ? <ErrorBanner message={`策略工作台加载失败：${hub.error}`} /> : null}
      {hub.notice ? <div className="panel strategy-notice">{hub.notice}</div> : null}

      <StrategyDoctorPanel
        runs={hub.runs}
        loading={hub.loading === "quick-submit"}
        onQuickCheck={quickSubmitWithToast}
        onOpenSignals={() => hub.setTab("signals")}
        onOpenCompare={() => hub.setTab("compare")}
      />

      <StrategyWorkflowSteps activeTab={hub.tab} runs={hub.runs} onSelect={hub.setTab} />
      <StrategyTrafficLights strategies={hub.strategies} />

      <nav className="strategy-tabs" aria-label="策略工作台功能">
        {visibleTabsForUser(currentUser).map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`${hub.tab === tab.key ? "active" : ""} ${tab.key === "quick" ? "primary-tab" : ""}`.trim()}
            onClick={() => hub.setTab(tab.key)}
            title={tab.key === "quick" ? "新用户从这里开始" : tab.hint}
          >
            <strong>{tab.label}</strong>
            <span>{tab.key === "quick" ? `新用户从这里开始 · ${tab.hint}` : tab.hint}</span>
          </button>
        ))}
      </nav>

      {content}

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
