import { createEffect, Show, type JSX } from "solid-js";
import { Portal } from "solid-js/web";
import { Button } from "./Button";
import { createDialogFocus } from "./dialogFocus";

export interface DrawerProps {
  open: boolean;
  title: JSX.Element;
  children: JSX.Element;
  onClose: () => void;
  footer?: JSX.Element;
  side?: "left" | "right";
  width?: number | string;
  closeLabel?: string;
  dismissible?: boolean;
  class?: string;
}

export function Drawer(props: DrawerProps) {
  let drawerElement: HTMLElement | undefined;
  const focus = createDialogFocus({
    getContainer: () => drawerElement,
    isOpen: () => props.open,
    onClose: () => {
      if (props.dismissible !== false) props.onClose();
    },
  });
  let wasOpen = false;

  createEffect(() => {
    if (props.open && !wasOpen) {
      focus.captureTrigger();
      focus.activate();
      wasOpen = true;
      return;
    }
    if (!props.open && wasOpen) {
      focus.deactivate();
      wasOpen = false;
    }
  });

  return (
    <Show when={props.open}>
      <Portal>
        <div
          role="presentation"
          style={{ ...backdropStyle, "justify-content": props.side === "left" ? "flex-start" : "flex-end" }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && props.dismissible !== false) props.onClose();
          }}
        >
          <aside
            ref={(element) => {
              drawerElement = element;
            }}
            class={props.class}
            role="dialog"
            aria-modal="true"
            aria-labelledby="tq-drawer-title"
            tabIndex={-1}
            style={{ ...surfaceStyle, width: cssSize(props.width ?? 420) }}
          >
            <header style={headerStyle}>
              <h2 id="tq-drawer-title" class="tq-panel__title" style={{ margin: 0 }}>
                {props.title}
              </h2>
              <Button iconOnly ariaLabel={props.closeLabel ?? "关闭抽屉"} title={props.closeLabel ?? "关闭"} variant="ghost" onClick={props.onClose}>
                ×
              </Button>
            </header>
            <div style={bodyStyle}>{props.children}</div>
            <Show when={props.footer}>
              <footer style={footerStyle}>{props.footer}</footer>
            </Show>
          </aside>
        </div>
      </Portal>
    </Show>
  );
}

function cssSize(value: number | string): string {
  return typeof value === "number" ? `${value}px` : value;
}

const backdropStyle: JSX.CSSProperties = {
  position: "fixed",
  inset: 0,
  "z-index": 1000,
  display: "flex",
  padding: 0,
  background: "rgba(15, 23, 42, 0.34)",
};

const surfaceStyle: JSX.CSSProperties = {
  height: "100%",
  "max-width": "min(100%, 520px)",
  overflow: "auto",
  border: "1px solid var(--line)",
  background: "var(--card)",
  color: "var(--text)",
  "box-shadow": "0 18px 48px rgba(15, 23, 42, 0.22)",
};

const headerStyle: JSX.CSSProperties = {
  display: "flex",
  "align-items": "center",
  "justify-content": "space-between",
  gap: "var(--sp-2)",
  padding: "var(--sp-3)",
  "border-bottom": "1px solid var(--line)",
};

const bodyStyle: JSX.CSSProperties = {
  padding: "var(--sp-3)",
};

const footerStyle: JSX.CSSProperties = {
  display: "flex",
  "align-items": "center",
  "justify-content": "flex-end",
  gap: "var(--sp-2)",
  padding: "var(--sp-3)",
  "border-top": "1px solid var(--line)",
};
