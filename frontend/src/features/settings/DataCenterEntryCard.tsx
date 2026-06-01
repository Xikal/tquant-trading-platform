import { SettingCard } from "../workspace-shared/WorkspaceComponents";
import styles from "./SettingsLayout.module.css";

interface DataCenterEntryCardProps {
  description: string;
  title: string;
}

export function DataCenterEntryCard({ description, title }: DataCenterEntryCardProps) {
  return (
    <SettingCard
      title={title}
      button="打开数据中心"
      loading={false}
      onSave={() => {
        window.location.assign("/data");
      }}
    >
      <div className={styles.dataCenterCard}>
        <div className={styles.dataCenterText}>
          <strong>{description}</strong>
          <span>数据质量、更新任务、修复和交易标的范围统一在数据中心维护；设置页只保留入口，避免重复操作。</span>
        </div>
      </div>
    </SettingCard>
  );
}
