import type { BacktestRunSummary } from "../../api/backtests";
import type { AuthUser } from "../../types";
import { SkeletonBlock } from "../../components/shared/Feedback";
import type { StrategyHubTab } from "./useStrategyHub";
import { PanelTitle, RecentRuns, StrategyBridge, StrategyHistoryPanel, visibleTabsForUser } from "./StrategyHubPanels";
import { QuickBacktestForm } from "./StrategyQuickCheckPanel";
import type { useStrategyHub } from "./useStrategyHub";
import type { useBacktestDashboard } from "../backtest/useBacktestDashboard";

type HubState = ReturnType<typeof useStrategyHub>;
type DashboardState = ReturnType<typeof useBacktestDashboard>;
type DetailTabKey = "quick" | "history" | "signals" | "factor" | "expert";
type ExpertTabKey = Extract<StrategyHubTab, "optimize" | "validate" | "compare" | "capacity">;

export function StrategyHubDetailTabs({
  currentUser,
  hub,
  dashboard,
  onQuickSubmit,
  onRerun,
}: {
  currentUser: AuthUser;
  hub: HubState;
  dashboard: DashboardState;
  onQuickSubmit: () => void;
  onRerun: (run: BacktestRunSummary) => void;
}) {
  const visibleTabs = visibleTabsForUser(currentUser);
  const expertTabs = visibleTabs.filter((tab): tab is typeof tab & { key: ExpertTabKey } =>
    ["optimize", "validate", "compare", "capacity"].includes(tab.key)
  );
  const hasFactorLab = visibleTabs.some((tab) => tab.key === "factor");
  const detailTab = currentDetailTab(hub.tab, expertTabs.length > 0, hasFactorLab);
  const detailTabs: Array<{ key: DetailTabKey; label: string; hint: string }> = [
    { key: "quick", label: "快速体检", hint: "新用户从这里开始" },
    { key: "history", label: "最近结果", hint: "看最近任务和历史变化" },
    { key: "signals", label: "信号复盘", hint: "看有效和失效案例" },
  ];
  if (hasFactorLab) {
    detailTabs.push({ key: "factor", label: "因子实验室", hint: "DeepSeek 挖掘新因子" });
  }
  if (expertTabs.length) {
    detailTabs.push({ key: "expert", label: "专家工具", hint: "调参、验证、对比、容量" });
  }

  return (
    <section className="panel strategy-detail-tabs">
      <div className="panel-title">
        <h2>详细信息</h2>
        <span className="hint">复杂信息统一收纳，首屏只保留结论和下一步。</span>
      </div>
      <div className="strategy-detail-strip" role="tablist" aria-label="策略工作台详情">
        {detailTabs.map((item) => (
          <button
            key={item.key}
            type="button"
            className={detailTab === item.key ? "active" : ""}
            onClick={() => switchDetailTab(item.key, hub)}
            role="tab"
            aria-selected={detailTab === item.key}
          >
            <strong>{item.label}</strong>
            <span>{item.hint}</span>
          </button>
        ))}
      </div>
      {hub.loading === "tab-switch" ? (
        <div className="strategy-detail-panel">
          <SkeletonBlock rows={5} title />
        </div>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "quick" ? (
        <div className="strategy-detail-panel strategy-quick-layout">
          <section className="strategy-quick-main">
            <PanelTitle title="一键体检" />
            <QuickBacktestForm hub={hub} onQuickSubmit={onQuickSubmit} />
          </section>
          <aside className="strategy-quick-side">
            <section className="strategy-side-card">
              <PanelTitle title="预设方案" />
              <div className="strategy-preset-list compact">
                {hub.presets.map((preset) => (
                  <button type="button" key={preset.key ?? preset.id ?? preset.name} onClick={() => hub.applyPreset(preset)}>
                    <strong>{preset.name}</strong>
                    <span>{preset.description}</span>
                  </button>
                ))}
              </div>
            </section>
            <section className="strategy-side-card">
              <PanelTitle title="最近任务" />
              <RecentRuns runs={hub.runs.slice(0, 3)} onRerun={onRerun} />
            </section>
          </aside>
        </div>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "history" ? (
        <div className="strategy-detail-panel">
          <StrategyHistoryPanel runs={hub.runs} onRefresh={() => void hub.load()} onRerun={onRerun} />
        </div>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "signals" ? (
        <div className="strategy-detail-panel">
          <StrategyBridge tab="signals" currentUser={currentUser} dashboard={dashboard} />
        </div>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "factor" ? (
        <div className="strategy-detail-panel">
          <StrategyBridge tab="factor" currentUser={currentUser} dashboard={dashboard} />
        </div>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "expert" ? (
        <div className="strategy-detail-panel strategy-expert-panel">
          <div className="strategy-expert-strip" role="tablist" aria-label="专家工具">
            {expertTabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={hub.tab === tab.key ? "active" : ""}
                onClick={() => hub.setTab(tab.key as StrategyHubTab)}
              >
                <strong>{tab.label}</strong>
                <span>{tab.hint}</span>
              </button>
            ))}
          </div>
          <StrategyBridge tab={expertTab(hub.tab, hub)} currentUser={currentUser} dashboard={dashboard} />
        </div>
      ) : null}
    </section>
  );
}

function currentDetailTab(tab: StrategyHubTab, hasExpertTabs: boolean, hasFactorLab: boolean): DetailTabKey {
  if (tab === "quick") return "quick";
  if (tab === "history") return "history";
  if (tab === "signals") return "signals";
  if (tab === "factor" && hasFactorLab) return "factor";
  if (!hasExpertTabs) return "quick";
  return "expert";
}

function switchDetailTab(key: DetailTabKey, hub: HubState) {
  if (key === "expert") {
    hub.setTab(expertTab(hub.tab, hub, false));
    return;
  }
  if (key === "factor") {
    hub.setTab("factor");
    return;
  }
  hub.setTab(key);
}

function expertTab(tab: StrategyHubTab, hub: HubState, fallbackToCurrent = true): ExpertTabKey {
  if (isExpertTab(tab)) return tab;
  if (fallbackToCurrent && isExpertTab(hub.tab)) return hub.tab;
  return "optimize";
}

function isExpertTab(tab: StrategyHubTab): tab is ExpertTabKey {
  return tab === "optimize" || tab === "validate" || tab === "compare" || tab === "capacity";
}
