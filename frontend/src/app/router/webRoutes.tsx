import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router";
import { TqErrorResult, TqPageLoading } from "../../ui/feedback/StateViews";

const TradingWorkspace = lazy(async () => ({
  default: (await import("../../features/trading-workspace/TradingWorkspace")).TradingWorkspace,
}));

const workspaceElement = (
  <Suspense fallback={<TqPageLoading label="工作台加载中" />}>
    <TradingWorkspace />
  </Suspense>
);

export const webRouter = createBrowserRouter([
  { path: "/", element: <Navigate to="/monitor" replace /> },
  { path: "/monitor", element: workspaceElement },
  { path: "/emotion", element: workspaceElement },
  { path: "/analysis", element: workspaceElement },
  { path: "/playbook", element: workspaceElement },
  { path: "/low-buy", element: workspaceElement },
  { path: "/strategy", element: workspaceElement },
  { path: "/paper", element: workspaceElement },
  { path: "/performance", element: workspaceElement },
  { path: "/settings", element: workspaceElement },
  {
    path: "*",
    element: (
      <TqErrorResult
        status="404"
        title="页面不存在"
        description="请检查地址，或返回实时监控。"
        actionHref="/monitor"
        actionText="返回实时监控"
      />
    ),
    errorElement: <TqErrorResult title="页面加载失败" description="请刷新页面，或返回工作台首页。" />,
  },
]);
