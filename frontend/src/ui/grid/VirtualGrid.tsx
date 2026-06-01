import { Table, Typography } from "antd";
import type { TableProps } from "antd";
import { PriceText } from "../data/PriceText";

export type VirtualGridProps<RecordType extends object> = TableProps<RecordType> & {
  defaultScrollY?: number;
  paginated?: boolean;
  virtualized?: boolean;
};

export function resolveVirtualGridTableProps<RecordType extends object>({
  className = "",
  size = "small",
  pagination = false,
  defaultScrollY = 420,
  locale,
  paginated = false,
  scroll,
  virtualized = true,
  ...props
}: VirtualGridProps<RecordType>): TableProps<RecordType> {
  const { style, ...tableProps } = props;
  const mustUseNonVirtualBranch = Boolean(tableProps.expandable);
  const useVirtualBranch = virtualized && !mustUseNonVirtualBranch;
  const resolvedPagination = paginated ? pagination || {} : pagination;
  const resolvedScroll = useVirtualBranch
    ? {
        ...scroll,
        x: scroll?.x ?? 960,
        y: scroll?.y ?? defaultScrollY,
      }
    : scroll;

  return {
    ...tableProps,
    className: className || undefined,
    locale: {
      emptyText: "暂无数据",
      ...locale,
    },
    pagination: resolvedPagination,
    scroll: resolvedScroll,
    size,
    style: { width: "100%", ...style },
    virtual: useVirtualBranch || undefined,
  };
}

export function VirtualGrid<RecordType extends object>(props: VirtualGridProps<RecordType>) {
  return <Table<RecordType> {...resolveVirtualGridTableProps(props)} />;
}

export function MoneyCell({ value, digits = 2 }: { value?: number | null; digits?: number }) {
  if (typeof value !== "number" || !Number.isFinite(value)) return <Typography.Text type="secondary">--</Typography.Text>;
  return <span className="tnum">{value.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}</span>;
}

export function PercentCell({ value, digits = 2 }: { value?: number | null; digits?: number }) {
  if (typeof value !== "number" || !Number.isFinite(value)) return <Typography.Text type="secondary">--</Typography.Text>;
  return <PriceText value={value} digits={digits} suffix="%" />;
}
