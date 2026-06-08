import type { JSX } from "solid-js";
import { render } from "solid-js/web";
import { afterEach, describe, expect, it } from "vitest";
import { AppErrorBoundary, RouteErrorBoundary } from "./ErrorBoundary";

function ThrowSensitiveError(): JSX.Element {
  throw new Error("Authorization: Bearer access-token-123 access_token=token-456 password=unsafe");
}

describe("frontend-next app error boundary", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("redacts sensitive values before rendering error messages", () => {
    render(
      () => (
        <AppErrorBoundary>
          <ThrowSensitiveError />
        </AppErrorBoundary>
      ),
      document.body,
    );

    const text = document.body.textContent ?? "";
    expect(text).toContain("页面渲染异常");
    expect(text).toContain("[redacted]");
    expect(text).not.toContain("access-token-123");
    expect(text).not.toContain("token-456");
    expect(text).not.toContain("unsafe");
  });

  it("keeps the app shell around a failed route-level page", () => {
    render(
      () => (
        <div data-testid="shell">
          <header>维斯量化</header>
          <RouteErrorBoundary routeLabel="策略跟踪">
            <ThrowSensitiveError />
          </RouteErrorBoundary>
        </div>
      ),
      document.body,
    );

    const text = document.body.textContent ?? "";
    expect(document.querySelector("[data-testid='shell']")).not.toBeNull();
    expect(document.querySelector("[data-testid='route-error-boundary']")).not.toBeNull();
    expect(text).toContain("维斯量化");
    expect(text).toContain("策略跟踪渲染异常");
    expect(text).toContain("工作台导航和账户菜单仍可使用");
    expect(text).not.toContain("access-token-123");
    expect(text).not.toContain("token-456");
    expect(text).not.toContain("unsafe");
  });
});
