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
    <div style={{ gridColumn: "1 / -1", marginTop: -4, padding: "8px 10px 0" }}>
      <Tabs
        type="card"
        activeKey={activeTab}
        onChange={(key) => onChange(key as SettingsTabKey)}
        tabBarStyle={{ margin: 0 }}
        items={tabs.map((tab) => ({
          key: tab.key,
          label: (
            <Space direction="vertical" size={2} style={{ minWidth: 124, textAlign: "left" }}>
              <Space size={6}>
                <Typography.Text strong>{tab.label}</Typography.Text>
                {tab.dirty ? <Badge status="warning" aria-label="有未保存更改" /> : null}
              </Space>
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>{tab.description}</Typography.Text>
            </Space>
          ),
        }))}
      />
    </div>
  );
}
