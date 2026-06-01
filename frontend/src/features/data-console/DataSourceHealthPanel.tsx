import { Alert, Button, Tag } from "antd";
import type { DataSourceProbeResponse } from "../../types";
import { dataConsoleText, qualityLabel } from "./dataConsoleTypes";
import styles from "./DataConsolePage.module.css";

const SOURCE_UNAVAILABLE_TEXT = "该数据源暂时不可用，已自动切换，部分数据可能延迟";

export function DataSourceHealthPanel({
  data,
  loading,
  error,
  onRefresh,
}: {
  data: DataSourceProbeResponse | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
}) {
  const items = data?.items ?? [];
  return (
    <div className={styles.panelBody}>
      <div className={styles.toolbar}>
        <span className={styles.muted}>最近检查：{data?.updated_at ?? "--"}</span>
        <Button size="small" onClick={onRefresh} loading={loading}>重新检查</Button>
      </div>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      {!items.length && !loading && !error ? <div className={styles.empty}>数据来源检查暂无返回</div> : null}
      <div className={styles.sourceList}>
        {items.map((item) => {
          const unhealthy = !item.ok || item.quality === "failed" || item.is_stale;
          return (
            <div className={styles.sourceRow} key={item.source}>
              <div>
                <strong>{item.source}</strong>
                <div className={styles.detail}>{dataConsoleText(unhealthy ? item.warning || SOURCE_UNAVAILABLE_TEXT : item.warning || "数据源在线")}</div>
              </div>
              <div className={styles.numbers}>
                <Tag color={unhealthy ? "red" : item.quality === "degraded" || item.quality === "stale" ? "orange" : "green"}>{qualityLabel(item.quality)}</Tag>
                <div className={styles.muted}>{Math.round(Number(item.latency_ms || 0))} ms</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
