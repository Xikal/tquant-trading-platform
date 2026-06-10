import { RouterProvider } from "react-router";
import { WorkspaceRouteErrorBoundary } from "./router/WorkspaceRouteErrorBoundary";
import { webRouter } from "./router/webRoutes";

export function WebApp() {
  // Top-level boundary: any uncaught render error shows a recoverable result
  // instead of a blank white screen.
  return (
    <WorkspaceRouteErrorBoundary>
      <RouterProvider router={webRouter} />
    </WorkspaceRouteErrorBoundary>
  );
}
