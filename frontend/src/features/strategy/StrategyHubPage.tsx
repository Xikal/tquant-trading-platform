import { EmptyPlaceholder, ErrorBanner, SkeletonBlock } from "../../components/shared/Feedback";
import { useToast } from "../../components/shared/ToastContainer";
import type { AuthUser } from "../../types";
import { formatMoney } from "../backtest/backtestDisplay";
import { useBacktestDashboard } from "../backtest/useBacktestDashboard";
import { StrategyDoctorPanel } from "./StrategyDoctorPanel";
import { StrategyConfirmDialog } from "./StrategyConfirmDialog";
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

  return (
    <section className="strategy-hub">
      <header className="panel strategy-hero">
        <div>
          <span className="strategy-kicker">策略医生</span>
          <h1>判断策略还能不能用</h1>
          <p>系统会把回测、复盘和验证翻译成直白结论：可继续观察、谨慎使用，或暂不建议使用。</p>
        </div>
        <div className="strategy-hero-actions">
          <button type="button" onClick={() => void hub.load()} disabled={hub.loading === "load"}>
            {hub.loading === "load" ? "刷新中" : "刷新"}
          </button>
          <button type="button" className="primary" onClick={() => hub.setConfirmOpen(true)} disabled={hub.loading === "submit"}>
            手动提交体检
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

      <nav className="strategy-tabs" aria-label="策略工作台功能">
        {visibleTabsForUser(currentUser).map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={hub.tab === tab.key ? "active" : ""}
            onClick={() => hub.setTab(tab.key)}
          >
            <strong>{tab.label}</strong>
            <span>{tab.hint}</span>
          </button>
        ))}
      </nav>

      {hub.tab === "quick" ? (
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
              <RecentRuns runs={hub.runs} />
            </section>
          </aside>
        </div>
      ) : (
        hub.tab === "history" ? (
          <StrategyHistoryPanel runs={hub.runs} onRefresh={() => void hub.load()} />
        ) : (
          <StrategyBridge tab={hub.tab} currentUser={currentUser} dashboard={dashboard} />
        )
      )}

      {hub.confirmOpen ? (
        <StrategyConfirmDialog
          loading={hub.loading === "submit"}
          title="确认提交快速回测"
          description={[
            `策略：${hub.selectedStrategyNames.join("、") || "未选择"}`,
            `区间：${hub.form.start_date} 至 ${hub.form.end_date}`,
            `资金：${formatMoney(Number(hub.form.initial_capital) || 0)}，成交模型：${executionModelText(hub.form.execution_model)}`,
            "任务异步执行，预计 2-5 分钟，可在策略历史查看进度。",
          ].join("；")}
          onCancel={() => hub.setConfirmOpen(false)}
          onConfirm={submitWithToast}
        />
      ) : null}
    </section>
  );
}
