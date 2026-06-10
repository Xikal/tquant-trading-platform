import { Navigate, Outlet, createRootRoute, createRoute } from "@tanstack/solid-router";
import { Suspense, type Component, lazy } from "solid-js";
import { AppShell } from "./AppShell";
import { RouteErrorBoundary } from "./ErrorBoundary";
import { RouteLoadingFallback } from "./RouteLoading";
import { AdminGuard, AuthGuard } from "./guards";

const LoginPage = lazy(() => import("../features/auth/LoginPage").then((module) => ({ default: module.LoginPage })));
const MonitorActionPage = lazy(() => import("../features/monitor-action/MonitorActionPage").then((module) => ({ default: module.MonitorActionPage })));
const MonitorMarketPage = lazy(() => import("../features/monitor-market/MonitorMarketPage").then((module) => ({ default: module.MonitorMarketPage })));
const StrategyTrackingPage = lazy(() => import("../features/strategy-tracking/StrategyTrackingPage").then((module) => ({ default: module.StrategyTrackingPage })));
const AnalysisPage = lazy(() => import("../features/analysis/AnalysisPage").then((module) => ({ default: module.AnalysisPage })));
const PlaybookPage = lazy(() => import("../features/playbook/PlaybookPage").then((module) => ({ default: module.PlaybookPage })));
const DataConsolePage = lazy(() => import("../features/data-console/DataConsolePage").then((module) => ({ default: module.DataConsolePage })));
const SettingsPage = lazy(() => import("../features/settings/SettingsPage").then((module) => ({ default: module.SettingsPage })));

function routeBoundaryComponent(ComponentToRender: Component, routeLabel: string): Component {
  return () => (
    <RouteErrorBoundary routeLabel={routeLabel}>
      <Suspense fallback={<RouteLoadingFallback routeLabel={routeLabel} />}>
        <ComponentToRender />
      </Suspense>
    </RouteErrorBoundary>
  );
}

function guardedRouteComponent(ComponentToRender: Component, routeLabel: string): Component {
  return () => (
    <AuthGuard>
      <RouteErrorBoundary routeLabel={routeLabel}>
        <Suspense fallback={<RouteLoadingFallback routeLabel={routeLabel} />}>
          <ComponentToRender />
        </Suspense>
      </RouteErrorBoundary>
    </AuthGuard>
  );
}

function adminRouteComponent(ComponentToRender: Component, routeLabel: string): Component {
  return () => (
    <AuthGuard>
      <AdminGuard>
        <RouteErrorBoundary routeLabel={routeLabel}>
          <Suspense fallback={<RouteLoadingFallback routeLabel={routeLabel} />}>
            <ComponentToRender />
          </Suspense>
        </RouteErrorBoundary>
      </AdminGuard>
    </AuthGuard>
  );
}

function shellGuardedRouteComponent(ComponentToRender: Component, routeLabel: string): Component {
  return () => (
    <AppShell>
      <AuthGuard>
        <RouteErrorBoundary routeLabel={routeLabel}>
          <Suspense fallback={<RouteLoadingFallback routeLabel={routeLabel} />}>
            <ComponentToRender />
          </Suspense>
        </RouteErrorBoundary>
      </AuthGuard>
    </AppShell>
  );
}

function shellAdminRouteComponent(ComponentToRender: Component, routeLabel: string): Component {
  return () => (
    <AppShell>
      <AuthGuard>
        <AdminGuard>
          <RouteErrorBoundary routeLabel={routeLabel}>
            <Suspense fallback={<RouteLoadingFallback routeLabel={routeLabel} />}>
              <ComponentToRender />
            </Suspense>
          </RouteErrorBoundary>
        </AdminGuard>
      </AuthGuard>
    </AppShell>
  );
}

const rootRoute = createRootRoute({
  component: () => (
    <Suspense fallback={<RouteLoadingFallback />}>
      <Outlet />
    </Suspense>
  ),
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <Navigate to="/next/monitor" />,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "login",
  component: routeBoundaryComponent(LoginPage, "登录页"),
});

const nextLoginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "next/login",
  component: routeBoundaryComponent(LoginPage, "登录页"),
});

const nextRootRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "next",
  component: () => (
    <AppShell>
      <Suspense fallback={<RouteLoadingFallback />}>
        <Outlet />
      </Suspense>
    </AppShell>
  ),
});

const monitorRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "monitor", component: guardedRouteComponent(MonitorActionPage, "实时行动台") });
const monitorMarketRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "monitor/market", component: guardedRouteComponent(MonitorMarketPage, "市场总闸") });
const paperRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "paper", component: () => <Navigate to="/next/monitor" search={true} /> });
const strategyRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "strategy-tracking", component: guardedRouteComponent(StrategyTrackingPage, "策略跟踪") });
const analysisRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "analysis", component: guardedRouteComponent(AnalysisPage, "量化分析") });
const playbookRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "playbook", component: guardedRouteComponent(PlaybookPage, "选股宝典") });
const backtestRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "backtest", component: () => <Navigate to="/next/monitor" search={true} /> });
const dataRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "data", component: adminRouteComponent(DataConsolePage, "数据中心") });
const settingsRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "settings", component: guardedRouteComponent(SettingsPage, "系统设置") });

const monitorLevel1CutoverRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "monitor",
  component: shellGuardedRouteComponent(MonitorActionPage, "实时行动台"),
});
const monitorMarketCutoverRoute = createRoute({ getParentRoute: () => rootRoute, path: "monitor/market", component: shellGuardedRouteComponent(MonitorMarketPage, "市场总闸") });
const paperCutoverRoute = createRoute({ getParentRoute: () => rootRoute, path: "paper", component: () => <Navigate to="/next/monitor" search={true} /> });
const strategyCutoverRoute = createRoute({ getParentRoute: () => rootRoute, path: "strategy-tracking", component: shellGuardedRouteComponent(StrategyTrackingPage, "策略跟踪") });
const analysisCutoverRoute = createRoute({ getParentRoute: () => rootRoute, path: "analysis", component: shellGuardedRouteComponent(AnalysisPage, "量化分析") });
const playbookCutoverRoute = createRoute({ getParentRoute: () => rootRoute, path: "playbook", component: shellGuardedRouteComponent(PlaybookPage, "选股宝典") });
const backtestCutoverRoute = createRoute({ getParentRoute: () => rootRoute, path: "backtest", component: () => <Navigate to="/next/monitor" search={true} /> });
const dataCutoverRoute = createRoute({ getParentRoute: () => rootRoute, path: "data", component: shellAdminRouteComponent(DataConsolePage, "数据中心") });
const settingsCutoverRoute = createRoute({ getParentRoute: () => rootRoute, path: "settings", component: shellGuardedRouteComponent(SettingsPage, "系统设置") });

const emotionCompatRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "emotion", component: () => <Navigate to="/next/monitor" search={true} /> });
const lowBuyCompatRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "low-buy", component: () => <Navigate to="/next/playbook" search={true} /> });
const strategyCompatRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "strategy", component: () => <Navigate to="/next/strategy-tracking" search={true} /> });
const performanceCompatRoute = createRoute({ getParentRoute: () => nextRootRoute, path: "performance", component: () => <Navigate to="/next/monitor" search={true} /> });

export const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  nextLoginRoute,
  monitorLevel1CutoverRoute,
  monitorMarketCutoverRoute,
  paperCutoverRoute,
  strategyCutoverRoute,
  analysisCutoverRoute,
  playbookCutoverRoute,
  backtestCutoverRoute,
  dataCutoverRoute,
  settingsCutoverRoute,
  nextRootRoute.addChildren([
    monitorRoute,
    monitorMarketRoute,
    paperRoute,
    strategyRoute,
    analysisRoute,
    playbookRoute,
    backtestRoute,
    dataRoute,
    settingsRoute,
    emotionCompatRoute,
    lowBuyCompatRoute,
    strategyCompatRoute,
    performanceCompatRoute,
  ]),
]);
