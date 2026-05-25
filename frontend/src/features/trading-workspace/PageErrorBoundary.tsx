import { Component, type CSSProperties, type ErrorInfo, type ReactNode } from "react";
import { Button } from "antd";

const PAGE_ERROR_BOUNDARY_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
  borderColor: "#efb7ad",
  background: "#fffafa",
};

const PAGE_ERROR_TITLE_STYLE: CSSProperties = {
  margin: 0,
  color: "var(--negative)",
  fontSize: 16,
};

const PAGE_ERROR_TEXT_STYLE: CSSProperties = {
  margin: 0,
  color: "var(--muted)",
  fontSize: 12,
};

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
      <section className="panel" style={PAGE_ERROR_BOUNDARY_STYLE}>
        <h2 style={PAGE_ERROR_TITLE_STYLE}>页面加载失败</h2>
        <p style={PAGE_ERROR_TEXT_STYLE}>{this.state.message}</p>
        <Button onClick={() => this.setState({ message: "" })}>重试</Button>
      </section>
    );
  }
}
