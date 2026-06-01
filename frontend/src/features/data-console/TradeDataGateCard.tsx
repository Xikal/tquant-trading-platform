import { Alert, Button, Tag } from "antd";
import type { TradeDataGateResponse } from "../../api/dataQuality";
import { Callout } from "../workspace-shared/Callout";
import { conclusionText, gateTone } from "./dataConsoleTypes";
import styles from "./DataConsolePage.module.css";

export function TradeDataGateCard({
  gate,
  loading,
  error,
  onRefresh,
}: {
  gate: TradeDataGateResponse | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
}) {
  const tone = gateTone(gate);
  return (
    <div className={styles.panelBody}>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <Callout
        primary
        tone={tone === "blocked" ? "down" : tone === "warn" ? "warn" : "up"}
        label="实盘前数据门"
        title={conclusionText(tone)}
        detail="仅检查数据可信度，不触发交易。"
        action={<Button size="small" onClick={onRefresh} loading={loading}>刷新</Button>}
      />
      <div className={styles.checkList}>
        {(gate?.checks ?? []).map((item) => (
          <div className={styles.checkRow} key={item.key}>
            <div>
              <strong>{item.label}</strong>
              <div className={styles.detail}>{item.detail || (item.ok ? "通过" : "未通过")}</div>
            </div>
            <Tag color={item.severity === "red" ? "red" : item.severity === "yellow" ? "orange" : "green"}>{item.severity}</Tag>
          </div>
        ))}
      </div>
      {!gate?.checks.length && !loading && !error ? <div className={styles.empty}>暂无数据门检查结果</div> : null}
    </div>
  );
}
