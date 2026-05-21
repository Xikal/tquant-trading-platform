import { lazy, Suspense } from "react";
import { Button, Tabs } from "antd";
import type { BacktestRunSummary } from "../../api/backtests";
import type { AuthUser } from "../../types";
import { SkeletonBlock } from "../../components/shared/Feedback";
import type { StrategyHubTab } from "./useStrategyHub";
import { PanelTitle, RecentRuns, StrategyBridge, StrategyHistoryPanel, visibleTabsForUser } from "./StrategyHubPanels";
import { QuickBacktestForm } from "./StrategyQuickCheckPanel";
import type { useStrategyHub } from "./useStrategyHub";

type HubState = ReturnType<typeof useStrategyHub>;
type DetailTabKey = "quick" | "history" | "signals" | "expert";
type ExpertTabKey = Extract<StrategyHubTab, "optimize" | "validate" | "compare" | "capacity" | "factor">;
type ResearchExpertTabKey = Exclude<ExpertTabKey, "factor">;

const StrategyHubExpertPanel = lazy(async () => ({
  default: (await import("./StrategyHubExpertPanel")).StrategyHubExpertPanel,
}));
const FactorMiningTab = lazy(async () => ({
  default: (await import("../factor-mining/FactorMiningTab")).FactorMiningTab,
}));

export function StrategyHubDetailTabs({
  currentUser,
  hub,
  onQuickSubmit,
  onRerun,
}: {
  currentUser: AuthUser;
  hub: HubState;
  onQuickSubmit: () => void;
  onRerun: (run: BacktestRunSummary) => void;
}) {
  const visibleTabs = visibleTabsForUser(currentUser);
  const expertTabs = visibleTabs.filter((tab): tab is typeof tab & { key: ExpertTabKey } =>
    ["optimize", "validate", "compare", "capacity", "factor"].includes(tab.key)
  );
  const detailTab = currentDetailTab(hub.tab, expertTabs.length > 0);
  const detailTabs: Array<{ key: DetailTabKey; label: string; hint: string }> = [
    { key: "quick", label: "快速体检", hint: "新用户从这里开始" },
    { key: "history", label: "最近结果", hint: "看最近任务和历史变化" },
    { key: "signals", label: "信号复盘", hint: "看有效和失效案例" },
  ];
  if (expertTabs.length) {
    detailTabs.push({ key: "expert", label: "专家工具", hint: "调参、验证、对比、因子" });
  }

  return (
    <section className="panel strategy-detail-tabs">
      <div className="panel-title">
        <h2>详细信息</h2>
        <span className="hint">复杂信息统一收纳，首屏只保留结论和下一步。</span>
      </div>
      <Tabs
        className="strategy-detail-tabs-antd"
        activeKey={detailTab}
        onChange={(key) => switchDetailTab(key as DetailTabKey, hub)}
        items={detailTabs.map((item) => ({
          key: item.key,
          label: (
            <span className="strategy-tab-label">
              <strong>{item.label}</strong>
              <small>{item.hint}</small>
            </span>
          ),
        }))}
      />
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
                  <Button type="text" key={preset.key ?? preset.id ?? preset.name} onClick={() => hub.applyPreset(preset)}>
                    <strong>{preset.name}</strong>
                    <span>{preset.description}</span>
                  </Button>
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
          <StrategyBridge tab="signals" />
        </div>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "expert" ? (
        <div className="strategy-detail-panel strategy-expert-panel">
          <Tabs
            className="strategy-expert-tabs-antd"
            activeKey={hub.tab}
            onChange={(key) => hub.setTab(key as StrategyHubTab)}
            items={expertTabs.map((tab) => ({
              key: tab.key,
              label: (
                <span className="strategy-tab-label">
                  <strong>{tab.label}</strong>
                  <small>{tab.hint}</small>
                </span>
              ),
            }))}
          />
          <Suspense fallback={<SkeletonBlock rows={5} title />}>
            {hub.tab === "factor" ? (
              <FactorMiningTab currentUser={currentUser} />
            ) : (
              <StrategyHubExpertPanel tab={researchExpertTab(hub.tab, hub)} currentUser={currentUser} />
            )}
          </Suspense>
        </div>
      ) : null}
    </section>
  );
}

function currentDetailTab(tab: StrategyHubTab, hasExpertTabs: boolean): DetailTabKey {
  if (tab === "quick") return "quick";
  if (tab === "history") return "history";
  if (tab === "signals") return "signals";
  if (!hasExpertTabs) return "quick";
  return "expert";
}

function switchDetailTab(key: DetailTabKey, hub: HubState) {
  if (key === "expert") {
    hub.setTab(expertTab(hub.tab, hub, false));
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
  return tab === "optimize" || tab === "validate" || tab === "compare" || tab === "capacity" || tab === "factor";
}

function researchExpertTab(tab: StrategyHubTab, hub: HubState): ResearchExpertTabKey {
  const current = expertTab(tab, hub);
  return current === "factor" ? "optimize" : current;
}
