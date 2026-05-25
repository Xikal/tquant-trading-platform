import { lazy, Suspense } from "react";
import { Button, Card, Col, Row, Space, Tabs, Typography } from "antd";
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
    <Card variant="borderless" styles={{ body: { display: "grid", gap: 8, padding: 10 } }}>
      <Space direction="vertical" size={2}>
        <Typography.Text strong>详细信息</Typography.Text>
        <Typography.Text type="secondary">复杂信息统一收纳，首屏只保留结论和下一步。</Typography.Text>
      </Space>
      <Tabs
        type="card"
        activeKey={detailTab}
        onChange={(key) => switchDetailTab(key as DetailTabKey, hub)}
        tabBarStyle={{ marginBottom: 0 }}
        items={detailTabs.map((item) => ({
          key: item.key,
          label: (
            <Space direction="vertical" size={2} style={{ minWidth: 72, textAlign: "left" }}>
              <Typography.Text strong style={{ fontSize: 12 }}>{item.label}</Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>{item.hint}</Typography.Text>
            </Space>
          ),
        }))}
      />
      {hub.loading === "tab-switch" ? (
        <div style={{ minHeight: 280 }}>
          <SkeletonBlock rows={5} title />
        </div>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "quick" ? (
        <Row gutter={[10, 10]} style={{ minHeight: 280 }}>
          <Col xs={24} xl={15}>
            <Space direction="vertical" size={10} style={{ display: "flex" }}>
              <PanelTitle title="一键体检" />
              <QuickBacktestForm hub={hub} onQuickSubmit={onQuickSubmit} />
            </Space>
          </Col>
          <Col xs={24} xl={9}>
            <Space direction="vertical" size={10} style={{ display: "flex" }}>
              <Card size="small">
                <Space direction="vertical" size={8} style={{ display: "flex" }}>
                  <PanelTitle title="预设方案" />
                  {hub.presets.map((preset) => (
                    <Button block type="text" key={preset.key ?? preset.id ?? preset.name} onClick={() => hub.applyPreset(preset)} style={{ height: "auto", textAlign: "left" }}>
                      <Space direction="vertical" size={2} style={{ display: "flex" }}>
                        <Typography.Text strong>{preset.name}</Typography.Text>
                        <Typography.Text type="secondary">{preset.description}</Typography.Text>
                      </Space>
                    </Button>
                  ))}
                </Space>
              </Card>
              <Card size="small">
                <PanelTitle title="最近任务" />
                <RecentRuns runs={hub.runs.slice(0, 3)} onRerun={onRerun} />
              </Card>
            </Space>
          </Col>
        </Row>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "history" ? (
        <div style={{ minHeight: 280 }}>
          <StrategyHistoryPanel runs={hub.runs} onRefresh={() => void hub.load()} onRerun={onRerun} />
        </div>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "signals" ? (
        <div style={{ minHeight: 280 }}>
          <StrategyBridge tab="signals" />
        </div>
      ) : null}
      {hub.loading !== "tab-switch" && detailTab === "expert" ? (
        <Space direction="vertical" size={10} style={{ display: "flex", minHeight: 280 }}>
          <Tabs
            type="card"
            activeKey={hub.tab}
            onChange={(key) => hub.setTab(key as StrategyHubTab)}
            tabBarStyle={{ marginBottom: 0 }}
            items={expertTabs.map((tab) => ({
              key: tab.key,
              label: (
                <Space direction="vertical" size={2} style={{ textAlign: "left" }}>
                  <Typography.Text strong style={{ fontSize: 12 }}>{tab.label}</Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>{tab.hint}</Typography.Text>
                </Space>
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
        </Space>
      ) : null}
    </Card>
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
