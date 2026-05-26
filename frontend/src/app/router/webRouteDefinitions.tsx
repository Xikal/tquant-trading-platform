import { lazy, Suspense } from "react";
import { Navigate } from "react-router";
import type { RouteObject } from "react-router";
import { TqErrorResult, TqPageLoading } from "../../ui/feedback/StateViews";
import type { Page } from "../../features/workspace-shared/workspaceTypes";

const WorkspaceRoute = lazy(async () => ({
  default: (await import("./WorkspaceRoute")).WorkspaceRoute,
}));
const EmotionRoute = lazy(async () => ({
  default: (await import("./EmotionRoute")).EmotionRoute,
}));
const AnalysisRoute = lazy(async () => ({
  default: (await import("./AnalysisRoute")).AnalysisRoute,
}));
const PlaybookRoute = lazy(async () => ({
  default: (await import("./PlaybookRoute")).PlaybookRoute,
}));
const MonitorRoute = lazy(async () => ({
  default: (await import("./MonitorRoute")).MonitorRoute,
}));
const PaperRoute = lazy(async () => ({
  default: (await import("./PaperRoute")).PaperRoute,
}));
const SettingsRoute = lazy(async () => ({
  default: (await import("./SettingsRoute")).SettingsRoute,
}));
const StrategyRoute = lazy(async () => ({
  default: (await import("./StrategyRoute")).StrategyRoute,
}));

const workspaceElement = (page: Page) => (
  <Suspense fallback={<TqPageLoading label="工作台加载中" />}>
    <WorkspaceRoute page={page} />
  </Suspense>
);

const routeElement = (Route: typeof MonitorRoute) => (
  <Suspense fallback={<TqPageLoading label="工作台加载中" />}>
    <Route />
  </Suspense>
);

export const webRoutes: RouteObject[] = [
  { path: "/", element: <Navigate to="/monitor" replace /> },
  { path: "/monitor", element: routeElement(MonitorRoute) },
  { path: "/emotion", element: routeElement(EmotionRoute) },
  { path: "/analysis", element: routeElement(AnalysisRoute) },
  { path: "/playbook", element: routeElement(PlaybookRoute) },
  { path: "/low-buy", element: <Navigate to="/playbook" replace /> },
  { path: "/strategy", element: routeElement(StrategyRoute) },
  { path: "/backtest", element: workspaceElement("backtest") },
  { path: "/paper", element: routeElement(PaperRoute) },
  { path: "/performance", element: <Navigate to="/paper" replace /> },
  { path: "/settings", element: routeElement(SettingsRoute) },
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
];
