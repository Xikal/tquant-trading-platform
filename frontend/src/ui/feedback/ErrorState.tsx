import { Button, Result } from "antd";

export function ErrorState({
  title = "数据暂时不可用",
  description = "请稍后重试。",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <Result
      status="warning"
      title={title}
      subTitle={description}
      extra={onRetry ? <Button onClick={onRetry}>重试</Button> : null}
    />
  );
}
