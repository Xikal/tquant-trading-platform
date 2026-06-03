import { Alert, Button, Tag } from "antd";
import type { RuntimeFallbackStatus } from "../../api/dataQuality";
import { Callout } from "../workspace-shared/Callout";
import { InfoPill } from "../workspace-shared/WorkspaceComponents";
import styles from "./DataConsolePage.module.css";

export function RuntimeFallbackPanel({
  status,
  loading,
  error,
  onRefresh,
}: {
  status: RuntimeFallbackStatus | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
}) {
  const state = resolveRuntimeFallbackState(status);
  return (
    <div className={styles.panelBody}>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <Callout
        primary
        tone={state.tone}
        label="后台兜底"
        title={state.title}
        detail={state.detail}
        action={<Button size="small" onClick={onRefresh} loading={loading}>刷新</Button>}
      />
      <div className={styles.summaryGrid}>
        <InfoPill label="后台状态" value={state.workerLabel} tone={state.tone === "down" ? "down" : state.tone === "warn" ? "warn" : "neutral"} />
        <InfoPill label="关键刷新" value={state.queueLabel} tone={status?.blocking ? "down" : "neutral"} />
        <InfoPill label="最后心跳" value={state.heartbeatLabel} />
      </div>
      {status?.blocking ? (
        <div className={styles.checkList}>
          {(status.recovery_actions.length ? status.recovery_actions : ["检查后台刷新任务"]).map((action) => {
            const label = actionText(action);
            return (
            <div className={styles.checkRow} key={label}>
              <div>
                <strong>{label}</strong>
                <div className={styles.detail}>先恢复后台刷新，再看低吸榜和数据面板。</div>
              </div>
              <Tag color="orange">待处理</Tag>
            </div>
            );
          })}
        </div>
      ) : null}
      {!status && !loading && !error ? <div className={styles.empty}>暂无后台兜底状态</div> : null}
    </div>
  );
}

export function resolveRuntimeFallbackState(status: RuntimeFallbackStatus | null): {
  tone: "up" | "warn" | "down";
  title: string;
  detail: string;
  workerLabel: string;
  queueLabel: string;
  heartbeatLabel: string;
} {
  if (!status) {
    return {
      tone: "warn",
      title: "后台状态待确认",
      detail: "还没有拿到后台兜底检查结果。",
      workerLabel: "--",
      queueLabel: "--",
      heartbeatLabel: "--",
    };
  }
  const workerLabel = workerStatusLabel(status.worker_status);
  const queueLabel = status.oldest_critical_queued_age_seconds && status.oldest_critical_queued_age_seconds >= 600
    ? "关键刷新排队过久"
    : status.critical_queued_count > 0
      ? `${status.critical_queued_count} 个待处理`
      : "无积压";
  const heartbeatLabel = status.heartbeat_age_seconds == null ? "--" : `${status.heartbeat_age_seconds} 秒前`;
  if (status.worker_status === "missing") {
    return {
      tone: "down",
      title: "后台未运行",
      detail: "收盘刷新、补数和物化不会在页面里直接重算。",
      workerLabel,
      queueLabel,
      heartbeatLabel,
    };
  }
  if (status.worker_status === "stale") {
    return {
      tone: "warn",
      title: "后台未响应",
      detail: "最近心跳偏旧，先确认后台进程是否还在。",
      workerLabel,
      queueLabel,
      heartbeatLabel,
    };
  }
  if (status.blocking) {
    return {
      tone: "down",
      title: "关键刷新排队过久",
      detail: "数据刷新链路正在安全阻断，不会用旧数据冒充新数据。",
      workerLabel,
      queueLabel,
      heartbeatLabel,
    };
  }
  return {
    tone: "up",
    title: "后台正常",
    detail: "后台刷新链路可用，关键任务没有长时间积压。",
    workerLabel,
    queueLabel,
    heartbeatLabel,
  };
}

function workerStatusLabel(value: string): string {
  if (value === "running") return "正常";
  if (value === "stale") return "未响应";
  if (value === "missing") return "未运行";
  return "未知";
}

function actionText(value: string): string {
  return String(value || "")
    .replace(/runtime-worker/g, "后台刷新进程")
    .replace(/runtime-scheduler/g, "后台调度进程")
    .replace(/runtime_tasks/g, "后台任务表")
    .replace(/\bqueued\b/g, "排队中")
    .replace(/\bstale\b/g, "长时间未响应");
}
