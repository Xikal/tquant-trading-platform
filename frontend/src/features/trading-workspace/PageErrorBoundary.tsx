import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "antd";

interface PageErrorBoundaryProps {
  children: ReactNode;
  resetKey: string;
}

interface PageErrorBoundaryState {
  message: string;
}

export class PageErrorBoundary extends Component<PageErrorBoundaryProps, PageErrorBoundaryState> {
  state: PageErrorBoundaryState = { message: "" };

  static getDerivedStateFromError(error: Error): PageErrorBoundaryState {
    return { message: error.message || "页面模块加载失败" };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error("workspace page crashed", error, errorInfo);
    }
  }

  componentDidUpdate(prevProps: PageErrorBoundaryProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.message) {
      this.setState({ message: "" });
    }
  }

  render() {
    if (!this.state.message) {
      return this.props.children;
    }
    return (
      <section className="panel page-error-boundary">
        <h2>页面加载失败</h2>
        <p>{this.state.message}</p>
        <Button onClick={() => this.setState({ message: "" })}>重试</Button>
      </section>
    );
  }
}
