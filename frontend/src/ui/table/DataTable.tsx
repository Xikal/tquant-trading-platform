import { Table } from "antd";
import type { TableProps } from "antd";

export function DataTable<RecordType extends object>({
  className = "",
  size = "small",
  pagination = false,
  locale,
  ...props
}: TableProps<RecordType>) {
  return (
    <Table<RecordType>
      className={`data-table${className ? ` ${className}` : ""}`}
      size={size}
      pagination={pagination}
      locale={{
        emptyText: "暂无数据",
        ...locale,
      }}
      {...props}
    />
  );
}

export function MoneyCell({ value, digits = 2 }: { value?: number | null; digits?: number }) {
  if (typeof value !== "number" || !Number.isFinite(value)) return <span className="muted">--</span>;
  return <span>{value.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}</span>;
}

export function PercentCell({ value, digits = 2 }: { value?: number | null; digits?: number }) {
  if (typeof value !== "number" || !Number.isFinite(value)) return <span className="muted">--</span>;
  const tone = value > 0 ? "up" : value < 0 ? "down" : "flat";
  return <span className={`data-table-percent ${tone}`}>{value.toFixed(digits)}%</span>;
}
