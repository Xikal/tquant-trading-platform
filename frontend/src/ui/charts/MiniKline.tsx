import { Suspense, lazy } from "react";

const LazyKlineChart = lazy(() => import("./LazyKlineChart"));

export function MiniKline(props: { option: unknown; className?: string }) {
  return (
    <Suspense fallback={<div className="tq-chart-loading">K线加载中</div>}>
      <LazyKlineChart {...props} />
    </Suspense>
  );
}
