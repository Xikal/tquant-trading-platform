import { Button, Empty, Result, Skeleton, Spin } from "antd";
import type { ReactNode } from "react";

type EmptyProps = {
  title?: string;
  description?: string;
  action?: ReactNode;
};

export function TqEmpty({ title = "暂无数据", description, action }: EmptyProps) {
  return (
    <Empty
      description={(
        <span>
          <strong>{title}</strong>
          {description ? <small className="tq-empty__desc">{description}</small> : null}
        </span>
      )}
    >
      {action}
    </Empty>
  );
}

export function TqPageLoading({ label = "加载中", rows = 4 }: { label?: string; rows?: number }) {
  return (
    <div aria-label={label} role="status" className="tq-loading">
      <Spin size="small" /> <span>{label}</span>
      <Skeleton active paragraph={{ rows }} title />
    </div>
  );
}

export function TqErrorResult({
  status = "warning",
  title = "数据暂时不可用",
  description = "请稍后重试。",
  onRetry,
  actionHref,
  actionText = "重试",
}: {
  status?: "403" | "404" | "500" | "error" | "info" | "success" | "warning";
  title?: string;
  description?: string;
  onRetry?: () => void;
  actionHref?: string;
  actionText?: string;
}) {
  const action = onRetry ? (
    <Button type="primary" onClick={onRetry}>{actionText}</Button>
  ) : actionHref ? (
    <Button type="primary" href={actionHref}>{actionText}</Button>
  ) : null;
  return <Result status={status} title={title} subTitle={description} extra={action} />;
}

export function TqForbidden({ description = "请联系管理员开启此功能权限。" }: { description?: string }) {
  return <Result status="403" title="权限不足" subTitle={description} />;
}
