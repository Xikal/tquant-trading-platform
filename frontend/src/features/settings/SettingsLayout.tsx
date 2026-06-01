import type { ReactNode } from "react";
import { Badge, Button } from "antd";
import type { SettingsTabItem, SettingsTabKey } from "./SettingsPageTabs";
import styles from "./SettingsLayout.module.css";

interface SettingsLayoutProps {
  activeTab: SettingsTabKey;
  children: ReactNode;
  loading: boolean;
  onRefresh: () => void;
  onSaveAll: () => void;
  onTabChange: (tab: SettingsTabKey) => void;
  tabs: SettingsTabItem[];
  unsavedCount: number;
}

export function SettingsLayout({
  activeTab,
  children,
  loading,
  onRefresh,
  onSaveAll,
  onTabChange,
  tabs,
  unsavedCount,
}: SettingsLayoutProps) {
  return (
    <section className={`settings-layout ${styles.layout}`}>
      <div className={styles.topBar}>
        <div className={styles.topBarText}>
          <div className={styles.topBarTitle}>系统设置</div>
          <div className={styles.topBarSummary}>配置保存采用一致性语义；敏感字段只显示配置状态，不回显真实值。</div>
        </div>
        <div className={styles.topBarActions}>
          {unsavedCount > 0 ? <span className={styles.unsavedPill}>未保存 {unsavedCount} 项</span> : null}
          <Button htmlType="button" onClick={onRefresh} loading={loading}>
            刷新配置
          </Button>
          <Button type="primary" htmlType="button" onClick={onSaveAll} disabled={loading || unsavedCount === 0}>
            全部保存
          </Button>
        </div>
      </div>
      <div className={styles.body}>
        <nav className={`settings-side-nav ${styles.sideNav}`} aria-label="系统设置分区">
          {tabs.map((tab, index) => (
            <SettingsNavItem
              key={tab.key}
              active={activeTab === tab.key}
              firstAdmin={tab.admin && !tabs[index - 1]?.admin}
              item={tab}
              onClick={() => onTabChange(tab.key)}
            />
          ))}
        </nav>
        <div className={styles.content}>{children}</div>
      </div>
    </section>
  );
}

function SettingsNavItem({
  active,
  firstAdmin,
  item,
  onClick,
}: {
  active: boolean;
  firstAdmin?: boolean;
  item: SettingsTabItem;
  onClick: () => void;
}) {
  return (
    <>
      {firstAdmin ? <div className={styles.navGroupLabel}>管理员</div> : null}
      <Button
        className={`${styles.navButton} ${active ? styles.navButtonActive : ""}`.trim()}
        htmlType="button"
        onClick={onClick}
        type={active ? "default" : "text"}
      >
        <span>
          <span className={styles.navLabel}>
            {item.label}
            {item.dirty ? <Badge status="warning" aria-label="有未保存更改" /> : null}
          </span>
          <span className={styles.navDescription}>{item.description}</span>
        </span>
      </Button>
    </>
  );
}
