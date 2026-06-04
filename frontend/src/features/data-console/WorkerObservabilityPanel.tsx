import { Button } from "antd";
import type {
  RuntimeTaskArtifactResponse,
  RuntimeTaskAnalyticsReportResponse,
  RuntimeTaskFailureResponse,
  RuntimeTaskSummaryResponse,
  RuntimeTaskWorkerListResponse,
} from "../../api/runtimeTasks";
import { dataConsoleText, taskStatusLabel, taskTypeLabel } from "./dataConsoleTypes";
import styles from "./DataConsolePage.module.css";

interface WorkerObservabilityPanelProps {
  summary: RuntimeTaskSummaryResponse | null;
  workers: RuntimeTaskWorkerListResponse | null;
  failures: RuntimeTaskFailureResponse | null;
  artifacts: RuntimeTaskArtifactResponse | null;
  analyticsReports: RuntimeTaskAnalyticsReportResponse | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
}

export function WorkerObservabilityPanel({
  summary,
  workers,
  failures,
  artifacts,
  analyticsReports,
  loading,
  error,
  onRefresh,
}: WorkerObservabilityPanelProps) {
  if (loading && !summary) return <EmptyLine text="后台任务观测加载中..." />;
  if (error) return <EmptyLine text={error} />;
  return (
    <div className={styles.panelBody}>
      <div className={styles.toolbar}>
        <div className={styles.detail}>队列、Worker、失败任务和产物路径只读观测。</div>
        <Button size="small" onClick={onRefresh}>刷新</Button>
      </div>
      <div className={styles.summaryGrid}>
        <Metric label="排队" value={summary?.queued ?? 0} />
        <Metric label="运行中" value={summary?.running ?? 0} />
        <Metric label="失败" value={summary?.failed ?? 0} />
        <Metric label="重试等待" value={summary?.retrying ?? 0} />
        <Metric label="近24h完成" value={summary?.succeeded_recent ?? 0} />
        <Metric label="最长等待" value={formatSeconds(summary?.longest_wait_seconds)} />
      </div>
      <div className={styles.checkList}>
        {(workers?.items ?? []).length ? workers?.items.map((worker) => (
          <div className={styles.checkRow} key={worker.worker_id}>
            <span>
              <strong>{worker.component || worker.worker_id}</strong>
              <div className={styles.detail}>
                {worker.worker_id} · {dataConsoleText(worker.status)} · 运行任务 {worker.running_task_count} · heartbeat {formatSeconds(worker.heartbeat_age_seconds)}
              </div>
            </span>
            <span className={styles.numbers}>{(worker.current_task_ids ?? []).join(", ") || "--"}</span>
          </div>
        )) : <EmptyLine text="暂无 Worker 心跳或运行任务。" />}
      </div>
      <div className={styles.grid}>
        <section className={styles.layerSection}>
          <h3>分析报告版本</h3>
          <div className={styles.checkList}>
            {(analyticsReports?.items ?? []).length ? analyticsReports?.items.slice(0, 6).map((report, index) => (
              <div className={styles.checkRow} key={`${report.output_json}-${report.generated_at}-${index}`}>
                <span>
                  <strong>{index === 0 ? "最新报告" : "历史报告"} {dataConsoleText(report.status || "--")}</strong>
                  <div className={styles.detail}>
                    {report.report_type || "--"} · manifest {report.manifest_id || report.dataset_version || "--"} · 耗时 {formatDuration(report.duration_seconds)}
                  </div>
                  <div className={styles.detail}>{report.output_md || report.output_json || "--"}</div>
                </span>
                <span className={styles.numbers}>{report.generated_at || "--"}</span>
              </div>
            )) : <EmptyLine text="暂无分析报告索引。" />}
          </div>
        </section>
        <section className={styles.layerSection}>
          <h3>最近失败</h3>
          <div className={styles.checkList}>
            {(failures?.items ?? []).length ? failures?.items.map((task) => (
              <div className={styles.checkRow} key={task.id}>
                <span>
                  <strong>#{task.id} {taskTypeLabel(task.task_type)}</strong>
                  <div className={styles.detail}>{dataConsoleText(task.error_message || "无失败原因")}</div>
                </span>
                <span className={styles.numbers}>{taskStatusLabel(task.status)}</span>
              </div>
            )) : <EmptyLine text="暂无失败任务。" />}
          </div>
        </section>
        <section className={styles.layerSection}>
          <h3>任务产物</h3>
          <div className={styles.checkList}>
            {(artifacts?.items ?? []).length ? artifacts?.items.slice(0, 6).map((artifact) => (
              <div className={styles.checkRow} key={`${artifact.task_id}-${artifact.artifact_key}-${artifact.artifact_path}`}>
                <span>
                  <strong>#{artifact.task_id} {artifact.artifact_key}</strong>
                  <div className={styles.detail}>{artifact.artifact_path}</div>
                </span>
                <span className={styles.numbers}>{taskTypeLabel(artifact.task_type)}</span>
              </div>
            )) : <EmptyLine text="暂无任务产物。" />}
          </div>
        </section>
      </div>
    </div>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <div className={styles.empty}>{text}</div>;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.kvRow}>
      <span>{label}</span>
      <strong className={styles.numbers}>{value}</strong>
    </div>
  );
}

function formatSeconds(value: number | null | undefined): string {
  if (value == null) return "--";
  if (value < 60) return `${value}s`;
  const minutes = Math.floor(value / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function formatDuration(value: number | null | undefined): string {
  if (value == null) return "--";
  if (value < 60) return `${value.toFixed(value < 10 ? 1 : 0)}s`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return `${minutes}m ${seconds}s`;
}
