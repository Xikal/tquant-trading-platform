import { useNavigate } from "@tanstack/solid-router";
import { createSignal, onCleanup, onMount, Show } from "solid-js";
import type { AuthModel } from "../auth/authModel";
import { Button } from "../../shared/ui/Button";
import { AUTH_LOGIN_ROUTE } from "../../app/authRoutes";

export function UserMenu(props: { auth: AuthModel }) {
  const navigate = useNavigate();
  const [open, setOpen] = createSignal(false);
  let rootRef: HTMLDivElement | undefined;

  const userName = () => props.auth.user()?.display_name || props.auth.user()?.username || "账户";

  onMount(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!open()) return;
      if (rootRef?.contains(event.target as Node)) return;
      setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    onCleanup(() => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    });
  });

  async function openSettings() {
    setOpen(false);
    await navigate({ to: "/next/settings" });
  }

  async function logout() {
    setOpen(false);
    await props.auth.logout();
    await navigate({ to: AUTH_LOGIN_ROUTE });
  }

  return (
    <Show when={props.auth.status() === "authenticated"}>
      <div class="tq-user-menu" ref={rootRef}>
        <Button
          class="tq-user-menu__trigger"
          ariaLabel="账户菜单"
          aria-expanded={open() ? "true" : "false"}
          aria-haspopup="menu"
          onClick={() => setOpen((current) => !current)}
        >
          {userName()}
        </Button>
        <Show when={open()}>
          <div class="tq-user-menu__panel" role="menu" aria-label="账户菜单">
            <button type="button" role="menuitem" onClick={() => void openSettings()}>
              系统设置
            </button>
            <button type="button" role="menuitem" class="tq-user-menu__danger" onClick={() => void logout()}>
              退出登录
            </button>
          </div>
        </Show>
      </div>
    </Show>
  );
}
