import { Panel } from "../shared/ui/Panel";
import { Button } from "../shared/ui/Button";

export function RouteLoadingFallback(props: { routeLabel?: string }) {
  const label = () => props.routeLabel ?? "当前页面";
  return (
    <section class="tq-page" data-testid="route-loading-fallback">
      <Panel
        title={`${label()}加载中`}
        subtitle="页面资源或首屏数据正在对齐，导航和账户菜单仍可使用。"
        actions={<Button href="/next/monitor" variant="subtle">返回实时行动</Button>}
      >
        <div class="next-route-loading" role="status" aria-live="polite">
          <span class="next-route-loading__bar" />
          <p class="tq-muted">正在加载 {label()}，请稍候。</p>
        </div>
      </Panel>
    </section>
  );
}
