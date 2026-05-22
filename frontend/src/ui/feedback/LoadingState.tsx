import { TqPageLoading } from "./StateViews";

export function LoadingState({ label = "加载中", rows = 4 }: { label?: string; rows?: number }) {
  return <TqPageLoading label={label} rows={rows} />;
}
