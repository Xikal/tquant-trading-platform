import { Show, createSignal, onCleanup, onMount } from "solid-js";
import { useNavigate } from "@tanstack/solid-router";
import type { AuthModel } from "../features/auth/authModel";
import type { NextRoute } from "../shared/config/routes";
import { Button } from "../shared/ui/Button";
import { Segmented } from "../shared/ui/Segmented";
import { UserMenu } from "../features/trading-workspace/UserMenu";
import { formatMarketClock } from "../shared/realtime/marketSession";
import { liveQuoteSignals } from "../shared/realtime/liveQuoteSignals";
import { legacyPageTitle } from "./legacyNavConfig";

export function LegacyTopbar(props: {
  currentRoute: NextRoute;
  auth: AuthModel;
  online: boolean;
  onOpenNav: () => void;
  onOpenCommand: () => void;
}) {
  const navigate = useNavigate();
  const [pulse, setPulse] = createSignal(formatMarketClock());
  const showMonitorSwitch = () => props.currentRoute.page === "monitor" || props.currentRoute.page === "monitor-market";

  onMount(() => {
    const timer = window.setInterval(() => setPulse(formatMarketClock()), 1000);
    onCleanup(() => window.clearInterval(timer));
  });

  return (
    <header class="legacy-topbar">
      <div class="legacy-topbar__left">
        <button class="legacy-topbar__menu tq-mobile-only" type="button" aria-label="打开导航菜单" onClick={props.onOpenNav}>
          ☰
        </button>
        <h1 class="legacy-topbar__title">{legacyPageTitle[props.currentRoute.page]}</h1>
        <Show when={showMonitorSwitch()}>
          <Segmented
            size="sm"
            class="legacy-topbar__segmented"
            label="监控页面切换"
            value={props.currentRoute.page}
            options={[
              { value: "monitor", label: "实时行动台" },
              { value: "monitor-market", label: "市场环境" },
            ]}
            onChange={(page) => void navigate({ to: page === "monitor" ? "/next/monitor" : "/next/monitor/market" })}
          />
        </Show>
      </div>
      <div class="legacy-topbar__right">
        <Show when={props.currentRoute.page === "paper"}>
          <Button variant="primary" size="sm" onClick={() => window.dispatchEvent(new CustomEvent("frontend-next:paper-refresh"))}>
            刷新
          </Button>
        </Show>
        <span class="legacy-topbar__badge legacy-topbar__badge--opportunity">
          <span class="legacy-topbar__badge-label">机会</span>
          <span class="legacy-topbar__badge-count">0</span>
        </span>
        <span class="legacy-topbar__badge legacy-topbar__badge--risk">
          <span class="legacy-topbar__badge-label">风险</span>
          <span class="legacy-topbar__badge-count">0</span>
        </span>
        <span class="legacy-topbar__chip">脉冲 <strong>{pulse()}</strong></span>
        <Show when={!props.online}>
          <span class="legacy-topbar__chip legacy-topbar__chip--warn">网络离线</span>
        </Show>
        <span class="legacy-topbar__chip">实时流 {connectionStateText(liveQuoteSignals.connectionState())}</span>
        <UserMenu auth={props.auth} />
      </div>
    </header>
  );
}

function connectionStateText(state: ReturnType<typeof liveQuoteSignals.connectionState>): string {
  const labels: Record<ReturnType<typeof liveQuoteSignals.connectionState>, string> = {
    idle: "未连接",
    connecting: "连接中",
    open: "已连接",
    closed: "已关闭",
    error: "异常",
  };
  return labels[state];
}
