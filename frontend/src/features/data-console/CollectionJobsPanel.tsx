import { Alert, Button, Input, Select, Space, Tag } from "antd";
import type { RuntimeTaskOut } from "../../api/runtimeTasks";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { dataConsoleText, datasetLabel, scopeLabel, taskStatusLabel, taskTypeLabel } from "./dataConsoleTypes";
import styles from "./DataConsolePage.module.css";

export function CollectionJobsPanel({
  adminReady,
  disabledReason,
  tasks,
  loading,
  error,
  datasetKey,
  scope,
  startDate,
  endDate,
  onFieldChange,
  onSyncInstruments,
  onRefreshCloseData,
  onBackfill,
  onRefresh,
}: {
  adminReady: boolean;
  disabledReason: string;
  tasks: RuntimeTaskOut[];
  loading: boolean;
  error: string;
  datasetKey: string;
  scope: string;
  startDate: string;
  endDate: string;
  onFieldChange: (field: "datasetKey" | "scope" | "startDate" | "endDate", value: string) => void;
  onSyncInstruments: () => void;
  onRefreshCloseData: () => void;
  onBackfill: () => void;
  onRefresh: () => void;
}) {
  const disabled = !adminReady || loading;
  return (
    <div className={styles.panelBody}>
      {!adminReady ? <Alert type="warning" showIcon message={disabledReason} /> : null}
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <div className={styles.formGrid}>
        <Select
          aria-label="回补数据集"
          value={datasetKey}
          onChange={(value) => onFieldChange("datasetKey", value)}
          options={[
            { value: "daily_bars", label: datasetLabel("daily_bars") },
            { value: "minute_bars", label: datasetLabel("minute_bars") },
            { value: "tick_trades", label: datasetLabel("tick_trades") },
          ]}
        />
        <Select
          aria-label="回补范围"
          value={scope}
          onChange={(value) => onFieldChange("scope", value)}
          options={[
            { value: "all", label: scopeLabel("all") },
            { value: "production_universe", label: scopeLabel("production_universe") },
            { value: "watchlist", label: scopeLabel("watchlist") },
          ]}
        />
        <Input aria-label="回补开始日期" value={startDate} onChange={(event) => onFieldChange("startDate", event.target.value)} placeholder="YYYY-MM-DD" />
        <Input aria-label="回补结束日期" value={endDate} onChange={(event) => onFieldChange("endDate", event.target.value)} placeholder="YYYY-MM-DD" />
      </div>
      <Space wrap>
        <Button htmlType="button" disabled={disabled} onClick={onSyncInstruments}>更新标的库</Button>
        <Button htmlType="button" disabled={disabled} onClick={onRefreshCloseData}>拉取今日收盘数据</Button>
        <Button type="primary" htmlType="button" disabled={disabled} onClick={onBackfill}>补历史数据</Button>
        <Button htmlType="button" onClick={onRefresh} loading={loading}>刷新</Button>
      </Space>
      <VirtualGrid<RuntimeTaskOut>
        rowKey="id"
        dataSource={tasks}
        defaultScrollY={300}
        locale={{ emptyText: "暂无采集任务" }}
        columns={[
          { title: "任务", dataIndex: "task_type", width: 190, render: (value, item) => <span><strong>{taskTypeLabel(String(value))}</strong><small className="hint">#{item.id}</small></span> },
          { title: "状态", dataIndex: "status", width: 110, render: (value) => <TaskStatusTag status={String(value)} /> },
          { title: "进度", dataIndex: "progress_pct", width: 86, align: "right", render: (value) => <span className="tnum">{Math.round(Number(value || 0))}%</span> },
          { title: "触发时间", dataIndex: "created_at", width: 180, render: (value) => String(value || "--") },
          { title: "失败原因", dataIndex: "error_message", render: (value) => dataConsoleText(String(value || "--")) },
        ]}
      />
    </div>
  );
}

function TaskStatusTag({ status }: { status: string }) {
  if (status === "succeeded") return <Tag color="green">{taskStatusLabel(status)}</Tag>;
  if (status === "failed") return <Tag color="red">{taskStatusLabel(status)}</Tag>;
  if (status === "running" || status === "queued") return <Tag color="blue">{taskStatusLabel(status)}</Tag>;
  return <Tag>{taskStatusLabel(status)}</Tag>;
}
