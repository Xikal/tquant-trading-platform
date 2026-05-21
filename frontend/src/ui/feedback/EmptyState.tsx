import { Empty } from "antd";
import type { ReactNode } from "react";

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <Empty description={<span>{description ?? title}</span>}>{action}</Empty>;
}
