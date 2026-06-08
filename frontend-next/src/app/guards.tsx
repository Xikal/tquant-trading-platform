import { Show, type JSX } from "solid-js";
import { Navigate, useLocation } from "@tanstack/solid-router";
import { Panel } from "../shared/ui/Panel";
import { Button } from "../shared/ui/Button";
import { useAuth } from "../features/auth/authModel";

export function AuthGuard(props: { children: JSX.Element }) {
  const auth = useAuth();
  const location = useLocation();
  return (
    <Show when={auth.status() !== "restoring"} fallback={<GuardPanel title="正在恢复会话" message="正在校验本地登录状态。" />}>
      <Show when={auth.status() === "authenticated"} fallback={<Navigate to="/login" search={{ redirect: location().href }} />}>
        {props.children}
      </Show>
    </Show>
  );
}

export function PaperGuard(props: { children: JSX.Element }) {
  const auth = useAuth();
  return (
    <Show when={auth.canPaperTrade()} fallback={<GuardPanel title="模拟盘权限不足" message="当前账号未开通 can_paper_trade，委托表单保持不可用。" />}>
      {props.children}
    </Show>
  );
}

export function AdminGuard(props: { children: JSX.Element }) {
  const auth = useAuth();
  return (
    <Show when={auth.isAdmin()} fallback={<GuardPanel title="管理员权限不足" message="数据中心和管理设置需要 admin 权限；当前仅开放只读替代路径。" />}>
      {props.children}
    </Show>
  );
}

export function GuardPanel(props: { title: string; message: string }) {
  return (
    <section class="tq-page">
      <Panel title={props.title} tone="danger">
        <p class="tq-muted">{props.message}</p>
        <Button href="/next/monitor">返回实时行动</Button>
      </Panel>
    </section>
  );
}
