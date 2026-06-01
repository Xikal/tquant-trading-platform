import type { ReactNode } from "react";
import styles from "./SettingsLayout.module.css";

export function SettingsSection({
  title,
  description,
  admin = false,
  children,
}: {
  title: string;
  description: string;
  admin?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <div>
          <div className={styles.sectionTitle}>{title}</div>
          <div className={styles.sectionDescription}>{description}</div>
        </div>
        {admin ? <span className={styles.adminBadge}>管理员</span> : null}
      </div>
      <div className={styles.sectionCards}>{children}</div>
    </section>
  );
}
