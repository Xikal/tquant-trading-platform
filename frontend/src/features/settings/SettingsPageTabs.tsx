import { Tabs } from "antd";

export type SettingsTabKey = "account" | "trading" | "llm" | "data" | "governance";

export interface SettingsTabItem {
  key: SettingsTabKey;
  label: string;
  description: string;
  dirty?: boolean;
}

export function SettingsPageTabs({
  tabs,
  activeTab,
  onChange,
}: {
  tabs: SettingsTabItem[];
  activeTab: SettingsTabKey;
  onChange: (tab: SettingsTabKey) => void;
}) {
  return (
    <Tabs
      className="settings-tabs settings-antd-tabs"
      activeKey={activeTab}
      onChange={(key) => onChange(key as SettingsTabKey)}
      items={tabs.map((tab) => ({
        key: tab.key,
        label: (
          <span className="settings-tab-label">
            <span>
              {tab.label}
              {tab.dirty ? <i aria-label="有未保存更改" /> : null}
            </span>
            <small>{tab.description}</small>
          </span>
        ),
      }))}
    />
  );
}
