import { Table, Typography } from "antd";
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
      className={className || undefined}
      style={{ width: "100%" }}
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
  if (typeof value !== "number" || !Number.isFinite(value)) return <Typography.Text type="secondary">--</Typography.Text>;
  return <span>{value.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}</span>;
}

export function PercentCell({ value, digits = 2 }: { value?: number | null; digits?: number }) {
  if (typeof value !== "number" || !Number.isFinite(value)) return <Typography.Text type="secondary">--</Typography.Text>;
  const color = value > 0 ? "#B42318" : value < 0 ? "#08875D" : "#64748B";
  return <Typography.Text style={{ color }}>{value.toFixed(digits)}%</Typography.Text>;
}
