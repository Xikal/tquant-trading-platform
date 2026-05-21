import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router";
import { ErrorState } from "../../ui/feedback/ErrorState";
import { LoadingState } from "../../ui/feedback/LoadingState";

const TradingWorkspace = lazy(async () => ({
  default: (await import("../../features/trading-workspace/TradingWorkspace")).TradingWorkspace,
}));

export const webRouter = createBrowserRouter([
  {
    path: "*",
    element: (
      <Suspense fallback={<LoadingState label="工作台加载中" />}>
        <TradingWorkspace />
      </Suspense>
    ),
    errorElement: <ErrorState title="页面加载失败" description="请刷新页面，或返回工作台首页。" />,
  },
]);
