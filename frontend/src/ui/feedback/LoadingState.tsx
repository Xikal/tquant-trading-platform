import { Skeleton, Spin } from "antd";

export function LoadingState({ label = "加载中", rows = 4 }: { label?: string; rows?: number }) {
  return (
    <div aria-label={label} role="status">
      <Spin size="small" /> <span>{label}</span>
      <Skeleton active paragraph={{ rows }} title />
    </div>
  );
}
