import { TqErrorResult } from "./StateViews";

export function ErrorState({
  title = "数据暂时不可用",
  description = "请稍后重试。",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return <TqErrorResult title={title} description={description} onRetry={onRetry} />;
}
