import { Input } from "antd";
import styles from "./SettingsLayout.module.css";

interface AdminTokenGateProps {
  error: string;
  onChange: (value: string) => void;
  value: string;
}

export function AdminTokenGate({ error, onChange, value }: AdminTokenGateProps) {
  const ready = Boolean(value.trim());
  return (
    <div className={styles.adminGate}>
      <div className={styles.adminGateHeader}>
        <div>
          <div className={styles.adminGateTitle}>管理员操作门</div>
          <div className={styles.adminGateHint}>
            {ready ? "已填写管理令牌，可以保存管理员配置。" : "先填写管理令牌，才能保存管理员配置。"}
          </div>
        </div>
        <span className={`${styles.adminGateStatus} ${ready ? styles.adminGateReady : ""}`.trim()}>
          {ready ? "已填写" : "未填写"}
        </span>
      </div>
      <Input.Password
        aria-label="管理令牌"
        value={value}
        status={error ? "error" : undefined}
        placeholder="输入管理令牌"
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
