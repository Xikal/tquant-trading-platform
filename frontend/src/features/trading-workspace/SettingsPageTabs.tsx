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
    <div className="settings-tabs" role="tablist" aria-label="系统配置分类">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.key}
          className={activeTab === tab.key ? "active" : ""}
          onClick={() => onChange(tab.key)}
        >
          <span>
            {tab.label}
            {tab.dirty ? <i aria-label="有未保存更改" /> : null}
          </span>
          <small>{tab.description}</small>
        </button>
      ))}
    </div>
  );
}
