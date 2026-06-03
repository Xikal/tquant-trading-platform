import { Alert, Button } from "antd";
import type { DataQualitySlaResponse, RuntimeFallbackStatus } from "../../api/dataQuality";
import { InfoPill } from "../workspace-shared/WorkspaceComponents";
import { Callout } from "../workspace-shared/Callout";
import { buildDataConsoleSummary } from "./dataConsoleTypes";
import styles from "./DataConsolePage.module.css";

export function DataHealthOverview({
  data,
  runtimeFallback,
  loading,
  error,
  onRefresh,
  onShowBlocked,
}: {
  data: DataQualitySlaResponse | null;
  runtimeFallback?: RuntimeFallbackStatus | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onShowBlocked: () => void;
}) {
  const summary = buildDataConsoleSummary(data?.items ?? []);
  const runtimeFallbackDescription = runtimeFallback ? describeRuntimeFallbackBlock(runtimeFallback) : "";
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
      {runtimeFallback?.blocking ? (
        <Alert
          type="warning"
          showIcon
          message="后台兜底正在阻断"
          description={runtimeFallbackDescription}
        />
      ) : null}
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

function describeRuntimeFallbackBlock(status: RuntimeFallbackStatus): string {
  if (status.worker_status === "missing") {
    return "后台未运行，请先启动 runtime-worker。";
  }
  if (status.worker_status === "stale") {
    return "后台心跳长时间未更新，请检查 runtime-worker 是否仍在执行或已卡住。";
  }
  return "关键刷新排队过久，请先处理后台任务积压。";
}
