import { Badge, Space, Tabs, Typography } from "antd";

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
    <div style={{ gridColumn: "1 / -1", padding: 0 }}>
      <Tabs
        type="card"
        size="small"
        activeKey={activeTab}
        onChange={(key) => onChange(key as SettingsTabKey)}
        tabBarStyle={{ margin: 0 }}
        items={tabs.map((tab) => ({
          key: tab.key,
          label: (
            <Space size={6} title={tab.description}>
              <Typography.Text strong style={{ fontSize: 13 }}>{tab.label}</Typography.Text>
              {tab.dirty ? <Badge status="warning" aria-label="有未保存更改" /> : null}
            </Space>
          ),
        }))}
      />
    </div>
  );
}
