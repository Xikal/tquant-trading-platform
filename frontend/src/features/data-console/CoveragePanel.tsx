import { Alert, Button, Collapse, Select, Tag } from "antd";
import type { DataQualityCoverageResponse, DataQualitySnapshotItem } from "../../api/dataQuality";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { criticalStatus } from "./dataConsoleTypes";
import styles from "./DataConsolePage.module.css";

export function CoveragePanel({
  items,
  detail,
  loading,
  error,
  statusFilter,
  scopeFilter,
  onStatusFilterChange,
  onScopeFilterChange,
  onSelectDetail,
  onRefresh,
}: {
  items: DataQualitySnapshotItem[];
  detail: DataQualityCoverageResponse | null;
  loading: boolean;
  error: string;
  statusFilter: string;
  scopeFilter: string;
  onStatusFilterChange: (value: string) => void;
  onScopeFilterChange: (value: string) => void;
  onSelectDetail: (item: DataQualitySnapshotItem) => void;
  onRefresh: () => void;
}) {
  const filteredItems = items.filter((item) => {
    const statusMatched =
      statusFilter === "all" ||
      (statusFilter === "blocked" && criticalStatus(item.status)) ||
      (statusFilter === "stale" && (item.stale || item.status === "stale"));
    const scopeMatched = scopeFilter === "all" || item.scope === scopeFilter;
    return statusMatched && scopeMatched;
  });
  return (
    <div className={styles.panelBody}>
      <div className={styles.toolbar}>
        <div className={styles.formGrid}>
          <Select
            aria-label="覆盖率状态筛选"
            value={statusFilter}
            onChange={onStatusFilterChange}
            options={[
              { value: "all", label: "全部状态" },
              { value: "blocked", label: "仅阻断" },
              { value: "stale", label: "仅过期" },
            ]}
          />
          <Select
            aria-label="覆盖率范围筛选"
            value={scopeFilter}
            onChange={onScopeFilterChange}
            options={[
              { value: "all", label: "全部范围" },
              { value: "production_universe", label: "生产池" },
              { value: "watchlist", label: "自选池" },
            ]}
          />
        </div>
        <Button size="small" onClick={onRefresh} loading={loading}>刷新</Button>
      </div>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <VirtualGrid<DataQualitySnapshotItem>
        rowKey={(row) => `${row.dataset_key}:${row.scope}:${row.as_of_date}`}
        dataSource={filteredItems}
        defaultScrollY={360}
        locale={{ emptyText: "所有数据集覆盖正常" }}
        columns={[
          {
            title: "数据集",
            dataIndex: "dataset_key",
            width: 180,
            render: (value, item) => <span><strong>{String(value)}</strong><small className="hint">{item.scope} / {item.as_of_date}</small></span>,
          },
          { title: "覆盖率", dataIndex: "coverage_pct", width: 92, align: "right", render: (value) => <span className="tnum">{Number(value || 0).toFixed(2)}%</span> },
          { title: "期望", dataIndex: "expected_days", width: 76, align: "right" },
          { title: "实际", dataIndex: "actual_days", width: 76, align: "right" },
          { title: "缺失", dataIndex: "missing_days", width: 76, align: "right" },
          { title: "invalid", dataIndex: "invalid_rows", width: 86, align: "right" },
          { title: "重复", dataIndex: "duplicate_rows", width: 76, align: "right" },
          { title: "状态", dataIndex: "status", width: 124, render: (value) => <StatusTag status={String(value)} /> },
          { title: "原因", dataIndex: "blockers", render: (value) => Array.isArray(value) && value.length ? value.join("、") : "--" },
          { title: "明细", width: 88, render: (_, item) => <Button size="small" onClick={() => onSelectDetail(item)}>展开</Button> },
        ]}
      />
      <Collapse
        size="small"
        items={[
          {
            key: "coverage-detail",
            label: `缺失明细 ${detail ? `${detail.dataset_key}/${detail.scope}` : ""}`,
            children: detail ? (
              <div className={styles.panelBody}>
                <div className={styles.detail}>缺失日期：{detail.missing_dates.length ? detail.missing_dates.join("、") : "无"}</div>
                <VirtualGrid
                  rowKey="symbol"
                  dataSource={detail.missing_symbols}
                  defaultScrollY={220}
                  columns={[
                    { title: "代码", dataIndex: "symbol", width: 100 },
                    { title: "名称", dataIndex: "name", width: 140 },
                    { title: "缺失天数", dataIndex: "missing_days", width: 100, align: "right" },
                  ]}
                />
              </div>
            ) : (
              <div className={styles.empty}>点击表格行的「展开」查看缺失标的和日期。</div>
            ),
          },
        ]}
      />
    </div>
  );
}

function StatusTag({ status }: { status: string }) {
  if (criticalStatus(status)) return <Tag color="red">{status}</Tag>;
  if (status === "stale" || status === "warn") return <Tag color="orange">{status}</Tag>;
  if (status === "ok") return <Tag color="green">{status}</Tag>;
  return <Tag>{status}</Tag>;
}
