import { createEffect, Show, type JSX } from "solid-js";
import { Portal } from "solid-js/web";
import { Button } from "./Button";
import { createDialogFocus } from "./dialogFocus";

export interface ModalProps {
  open: boolean;
  title: JSX.Element;
  children: JSX.Element;
  onClose: () => void;
  footer?: JSX.Element;
  closeLabel?: string;
  width?: number | string;
  dismissible?: boolean;
  class?: string;
}

export function Modal(props: ModalProps) {
  let dialogElement: HTMLDivElement | undefined;
  const focus = createDialogFocus({
    getContainer: () => dialogElement,
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
          style={backdropStyle}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && props.dismissible !== false) props.onClose();
          }}
        >
          <div
            ref={(element) => {
              dialogElement = element;
            }}
            class={props.class}
            role="dialog"
            aria-modal="true"
            aria-labelledby="tq-modal-title"
            tabIndex={-1}
            style={{ ...surfaceStyle, width: cssSize(props.width ?? 560) }}
          >
            <header style={headerStyle}>
              <h2 id="tq-modal-title" class="tq-panel__title" style={{ margin: 0 }}>
                {props.title}
              </h2>
              <Button iconOnly ariaLabel={props.closeLabel ?? "关闭弹窗"} title={props.closeLabel ?? "关闭"} variant="ghost" onClick={props.onClose}>
                ×
              </Button>
            </header>
            <div style={bodyStyle}>{props.children}</div>
            <Show when={props.footer}>
              <footer style={footerStyle}>{props.footer}</footer>
            </Show>
          </div>
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
  display: "grid",
  "place-items": "center",
  padding: "var(--sp-4)",
  background: "rgba(15, 23, 42, 0.38)",
};

const surfaceStyle: JSX.CSSProperties = {
  "max-width": "min(100%, 720px)",
  "max-height": "min(86vh, 760px)",
  overflow: "auto",
  border: "1px solid var(--line)",
  "border-radius": "var(--radius-md)",
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
