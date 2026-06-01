import { Alert, Button, Select, Space, Tag } from "antd";
import type { DataRepairAuditItem } from "../../api/dataQuality";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import styles from "./DataConsolePage.module.css";

export function DataRepairPanel({
  audits,
  adminReady,
  disabledReason,
  loading,
  error,
  datasetKey,
  confirmOpen,
  onDatasetChange,
  onDryRun,
  onOpenConfirm,
  onConfirmApply,
  onCancelConfirm,
}: {
  audits: DataRepairAuditItem[];
  adminReady: boolean;
  disabledReason: string;
  loading: boolean;
  error: string;
  datasetKey: string;
  confirmOpen: boolean;
  onDatasetChange: (value: string) => void;
  onDryRun: () => void;
  onOpenConfirm: () => void;
  onConfirmApply: () => void;
  onCancelConfirm: () => void;
}) {
  const disabled = !adminReady || loading;
  return (
    <div className={styles.panelBody}>
      {!adminReady ? <Alert type="warning" showIcon message={disabledReason} /> : null}
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <div className={styles.formGrid}>
        <Select
          aria-label="修复数据集"
          value={datasetKey}
          onChange={onDatasetChange}
          options={[
            { value: "daily_bars", label: "daily_bars" },
            { value: "minute_bars", label: "minute_bars" },
            { value: "tick_trades", label: "tick_trades" },
          ]}
        />
      </div>
      <Space wrap>
        <Button htmlType="button" disabled={disabled} loading={loading} onClick={onDryRun}>dry-run 预览</Button>
        <Button type="primary" htmlType="button" disabled={disabled} onClick={onOpenConfirm}>执行修复</Button>
      </Space>
      {confirmOpen ? (
        <div className={styles.confirmation}>
          <strong>将删除并重抓 {datasetKey} 数据集的异常数据（自动备份），由后台任务执行，确认继续？</strong>
          <Space wrap>
            <Button type="primary" danger htmlType="button" onClick={onConfirmApply} loading={loading}>确认继续</Button>
            <Button htmlType="button" onClick={onCancelConfirm}>取消</Button>
          </Space>
        </div>
      ) : null}
      <VirtualGrid<DataRepairAuditItem>
        rowKey="repair_id"
        dataSource={audits}
        defaultScrollY={260}
        locale={{ emptyText: "暂无修复审计" }}
        columns={[
          { title: "修复", dataIndex: "repair_id", width: 180, render: (value, item) => <span><strong>{String(value)}</strong><small className="hint">{item.dataset_key} / {item.reason}</small></span> },
          { title: "删除", dataIndex: "deleted_rows_count", width: 74, align: "right" },
          { title: "重抓", dataIndex: "refetch_result", width: 120 },
          { title: "fabricated", dataIndex: "fabricated", width: 116, render: (value) => <Tag color={value ? "red" : "green"}>{value ? "true" : "false"}</Tag> },
          { title: "备份", dataIndex: "backup_path", render: (value) => String(value || "--") },
        ]}
      />
      <div className={styles.muted}>Web 只提交任务，修复由 worker 消费并写审计。</div>
    </div>
  );
}
