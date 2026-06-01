import { Alert, Button } from "antd";
import type { DataQualitySlaResponse } from "../../api/dataQuality";
import { InfoPill } from "../workspace-shared/WorkspaceComponents";
import { Callout } from "../workspace-shared/Callout";
import { buildDataConsoleSummary } from "./dataConsoleTypes";
import styles from "./DataConsolePage.module.css";

export function DataHealthOverview({
  data,
  loading,
  error,
  onRefresh,
  onShowBlocked,
}: {
  data: DataQualitySlaResponse | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onShowBlocked: () => void;
}) {
  const summary = buildDataConsoleSummary(data?.items ?? []);
  return (
    <div className={styles.panelBody}>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <Callout
        primary
        tone={summary.status === "blocked" ? "down" : summary.status === "warn" ? "warn" : "up"}
        label="总体状态"
        title={summary.conclusion}
        detail={`最近检查：${summary.checkedAt}`}
        action={<Button size="small" onClick={onRefresh} loading={loading}>刷新</Button>}
      />
      <div className={styles.summaryGrid}>
        <InfoPill label="数据集" value={`${summary.total} 个`} />
        <InfoPill label="不可用" value={`${summary.blocked} 个`} tone={summary.blocked ? "down" : "neutral"} />
        <InfoPill label="待更新" value={`${summary.stale} 个`} tone={summary.stale ? "warn" : "neutral"} />
        <InfoPill label="待补" value={`${summary.missing} 天`} tone={summary.missing ? "warn" : "neutral"} />
      </div>
      {summary.blocked ? <Button size="small" onClick={onShowBlocked}>查看不可用的数据</Button> : null}
      {!loading && !error && !data?.items.length ? <div className={styles.empty}>暂无数据质量快照</div> : null}
    </div>
  );
}
