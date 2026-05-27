import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";
import { TqErrorResult } from "../../ui/feedback/StateViews";

type WorkspaceRouteErrorBoundaryProps = {
  children: ReactNode;
};

type WorkspaceRouteErrorBoundaryState = {
  hasError: boolean;
};

export class WorkspaceRouteErrorBoundary extends Component<WorkspaceRouteErrorBoundaryProps, WorkspaceRouteErrorBoundaryState> {
  state: WorkspaceRouteErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): WorkspaceRouteErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error("WorkspaceRoute render failed", error, info.componentStack);
    }
  }

  render() {
    if (this.state.hasError) {
      return <TqErrorResult title="页面加载失败" description="请刷新页面，或返回实时监控。" actionHref="/monitor" actionText="返回实时监控" />;
    }
    return this.props.children;
  }
}
