import { EmptyPlaceholder, ErrorBanner, SkeletonBlock } from "../../components/shared/Feedback";
import { useToast } from "../../components/shared/ToastContainer";
import type { AuthUser } from "../../types";
import { formatMoney } from "../backtest/backtestDisplay";
import { useBacktestDashboard } from "../backtest/useBacktestDashboard";
import { StrategyConfirmDialog } from "./StrategyConfirmDialog";
import {
  dashboardSectionForTab,
  executionModelText,
  PanelTitle,
  QuickBacktestForm,
  RecentRuns,
  StrategyBridge,
  StrategyHistoryPanel,
  StrategyQuickGuide,
  visibleTabsForUser,
} from "./StrategyHubPanels";
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
          <span className="strategy-kicker">Strategy Workbench · Phase 3</span>
          <h1>策略工作台</h1>
          <p>按“先体检、再复盘、再优化、最后验证”的顺序使用。普通用户先点一键快速回测，完成后只看收益、胜率、最大回撤和失败原因。</p>
        </div>
        <div className="strategy-hero-actions">
          <button type="button" onClick={() => void hub.load()} disabled={hub.loading === "load"}>
            {hub.loading === "load" ? "刷新中" : "刷新"}
          </button>
          <button type="button" className="primary" onClick={() => hub.setConfirmOpen(true)} disabled={hub.loading === "submit"}>
            提交快速回测
          </button>
        </div>
      </header>

      {hub.error ? <ErrorBanner message={`策略工作台加载失败：${hub.error}`} /> : null}
      {hub.notice ? <div className="panel strategy-notice">{hub.notice}</div> : null}

      <section className="strategy-step-flow" aria-label="策略使用流程">
        {[
          ["1", "体检", "先看策略是否健康，红灯不使用。"],
          ["2", "复盘", "查看历史任务，确认不是偶然盈利。"],
          ["3", "优化", "只在样本外通过后调整参数。"],
          ["4", "验证", "验证通过后才考虑模拟盘跟踪。"],
        ].map(([step, title, desc]) => (
          <article key={step}>
            <span>{step}</span>
            <strong>{title}</strong>
            <small>{desc}</small>
          </article>
        ))}
      </section>
      <section className="strategy-traffic-light panel" aria-label="策略健康灯号说明">
        <article className="ok"><strong>健康运行</strong><span>胜率、回撤和样本量正常，可继续观察使用。</span></article>
        <article className="warn"><strong>轻微异常</strong><span>近期表现变弱或样本不足，先小仓或只复盘。</span></article>
        <article className="bad"><strong>需要关注</strong><span>回撤、胜率或数据质量异常，暂停生产执行。</span></article>
      </section>

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
            <PanelTitle title="快速回测配置" />
            <StrategyQuickGuide />
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
