import type { CSSProperties } from "react";
import { Button, Collapse, Space, Tag } from "antd";
import { dataQualityApi } from "../../api/dataQuality";
import type { DataQualitySnapshotItem, DataRepairAuditItem } from "../../api/dataQuality";
import { useSettingsUiStore } from "../../stores/settingsUiStore";
import { DataTable } from "../../ui/table/DataTable";
import { InfoPill, SettingCard } from "../workspace-shared/WorkspaceComponents";

const SUMMARY_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
};

export function DataQualityPanel() {
  const dataQuality = useSettingsUiStore((state) => state.dataQuality);
  const error = useSettingsUiStore((state) => state.dataQualityError);
  const loading = useSettingsUiStore((state) => state.dataQualityLoading);
  const repairLoading = useSettingsUiStore((state) => state.dataQualityRepairLoading);
  const setDataQuality = useSettingsUiStore((state) => state.setDataQuality);
  const setError = useSettingsUiStore((state) => state.setDataQualityError);
  const setLoading = useSettingsUiStore((state) => state.setDataQualityLoading);
  const setRepairLoading = useSettingsUiStore((state) => state.setDataQualityRepairLoading);

  async function refresh() {
    setLoading(true);
    try {
      const payload = await dataQualityApi.sla();
      setDataQuality(payload);
      setError("");
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "数据质量 SLA 加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function enqueueDryRun() {
    setRepairLoading(true);
    try {
      await dataQualityApi.repairDryRun();
      await refresh();
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "修复 dry-run 提交失败");
    } finally {
      setRepairLoading(false);
    }
  }

  const items = dataQuality?.items ?? [];
  const audits = dataQuality?.latest_repair_audits ?? [];
  const failCount = items.filter((item) => item.status === "fail" || item.status === "unavailable").length;

  return (
    <SettingCard
      title="数据质量 SLA"
      button="刷新 SLA"
      onSave={() => void refresh()}
      loading={loading}
      className="data-quality-sla-card"
    >
      {error ? <p className="form-error">{error}</p> : null}
      <div style={SUMMARY_STYLE}>
        <InfoPill label="数据集" value={`${items.length} 个`} />
        <InfoPill label="阻断" value={`${failCount} 个`} tone={failCount ? "down" : "neutral"} />
        <InfoPill label="最近审计" value={`${audits.length} 条`} />
        <Button size="small" htmlType="button" onClick={() => void enqueueDryRun()} loading={repairLoading}>
          提交 dry-run
        </Button>
      </div>
      <Collapse
        size="small"
        defaultActiveKey={[]}
        items={[
          {
            key: "snapshots",
            label: "SLA 快照",
            children: (
              <DataTable<DataQualitySnapshotItem>
                rowKey={(row) => `${row.dataset_key}:${row.scope}:${row.as_of_date}`}
                dataSource={items}
                defaultScrollY={260}
                columns={[
                  {
                    title: "数据集",
                    dataIndex: "dataset_key",
                    render: (value, item) => (
                      <span>
                        <strong>{value}</strong>
                        <small className="hint">{item.scope} / {item.as_of_date}</small>
                      </span>
                    ),
                  },
                  { title: "覆盖率", dataIndex: "coverage_pct", width: 90, render: (value) => `${Number(value || 0).toFixed(2)}%` },
                  { title: "缺失", dataIndex: "missing_days", width: 72 },
                  { title: "invalid", dataIndex: "invalid_rows", width: 72 },
                  { title: "重复", dataIndex: "duplicate_rows", width: 72 },
                  { title: "状态", dataIndex: "status", width: 110, render: (value) => <Tag color={statusColor(String(value))}>{String(value)}</Tag> },
                  { title: "原因", dataIndex: "blockers", render: (value) => (Array.isArray(value) && value.length ? value.join("、") : "--") },
                ]}
              />
            ),
          },
          {
            key: "audits",
            label: "最近修复审计",
            children: (
              <DataTable<DataRepairAuditItem>
                rowKey="repair_id"
                dataSource={audits}
                defaultScrollY={220}
                columns={[
                  {
                    title: "修复",
                    dataIndex: "repair_id",
                    render: (value, item) => (
                      <span>
                        <strong>{value}</strong>
                        <small className="hint">{item.dataset_key} / {item.reason}</small>
                      </span>
                    ),
                  },
                  { title: "删除", dataIndex: "deleted_rows_count", width: 72 },
                  { title: "重抓", dataIndex: "refetch_result", width: 120 },
                  { title: "fabricated", dataIndex: "fabricated", width: 110, render: (value) => <Tag color={value ? "red" : "green"}>{value ? "true" : "false"}</Tag> },
                  { title: "备份", dataIndex: "backup_path", render: (value) => String(value || "--") },
                ]}
              />
            ),
          },
        ]}
      />
      <Space size={6} wrap>
        <Tag>Web 不执行修复</Tag>
        <Tag>analytics-worker 消费</Tag>
        <Tag>apply 需管理员显式提交</Tag>
      </Space>
    </SettingCard>
  );
}

function statusColor(status: string): string {
  if (status === "ok") return "green";
  if (status === "fail" || status === "blocked_by_data") return "red";
  if (status === "unavailable") return "orange";
  return "default";
}
