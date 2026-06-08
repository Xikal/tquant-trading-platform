import type { JSX } from "solid-js";
import { ErrorBoundary as SolidErrorBoundary } from "solid-js";
import { Panel } from "../shared/ui/Panel";
import { Button } from "../shared/ui/Button";
import { redactSensitiveText } from "../shared/security/redaction";

export function AppErrorBoundary(props: { children: JSX.Element }) {
  return (
    <SolidErrorBoundary
      fallback={(error, reset) => (
        <Panel title="页面渲染异常" tone="danger">
          <p class="tq-muted">页面渲染时遇到异常，请重试或保留当前证据。</p>
          <p class="tq-muted">{redactSensitiveText(error)}</p>
          <Button onClick={reset}>重试</Button>
        </Panel>
      )}
    >
      {props.children}
    </SolidErrorBoundary>
  );
}

export function RouteErrorBoundary(props: { children: JSX.Element; routeLabel?: string }) {
  return (
    <SolidErrorBoundary
      fallback={(error, reset) => (
        <section class="tq-page" data-testid="route-error-boundary">
          <Panel title={`${props.routeLabel ?? "当前页面"}渲染异常`} tone="danger">
            <p class="tq-muted">当前页面渲染失败，工作台导航和账户菜单仍可使用。</p>
            <p class="tq-muted">{redactSensitiveText(error)}</p>
            <div class="tq-tag-row">
              <Button onClick={reset}>重试当前页</Button>
              <Button href="/next/monitor" variant="subtle">返回实时行动</Button>
            </div>
          </Panel>
        </section>
      )}
    >
      {props.children}
    </SolidErrorBoundary>
  );
}
