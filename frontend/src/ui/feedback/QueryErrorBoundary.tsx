import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "antd";

interface QueryErrorBoundaryProps {
  children: ReactNode;
  resetKey?: string;
  onReset?: () => void;
}

interface QueryErrorBoundaryState {
  message: string;
  status?: number;
}

export class QueryErrorBoundary extends Component<QueryErrorBoundaryProps, QueryErrorBoundaryState> {
  state: QueryErrorBoundaryState = { message: "" };

  static getDerivedStateFromError(error: Error): QueryErrorBoundaryState {
    const status = (error as Error & { status?: number }).status;
    return {
      message: error.message || "接口暂时不可用",
      ...(typeof status === "number" ? { status } : {}),
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("query boundary captured error", error, errorInfo);
  }

  componentDidUpdate(prevProps: QueryErrorBoundaryProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.message) {
      this.setState({ message: "" });
    }
  }

  render() {
    if (!this.state.message) {
      return this.props.children;
    }
    return <QueryErrorFallback status={this.state.status} onRetry={this.reset} />;
  }

  private reset = () => {
    this.setState({ message: "" });
    this.props.onReset?.();
  };
}

export function QueryErrorFallback({
  status,
  onRetry,
}: {
  status?: number;
  onRetry?: () => void;
}) {
  if (status === 401) {
    return (
      <section className="panel" role="alert">
        <h2>登录已失效</h2>
        <p>请重新登录后继续查看。</p>
      </section>
    );
  }
  return (
    <section className="panel" role="alert">
      <h2>加载失败，正在重试…</h2>
      <p>已保留上次可用数据，接口恢复后会自动更新。</p>
      <Button onClick={onRetry}>重试</Button>
    </section>
  );
}
