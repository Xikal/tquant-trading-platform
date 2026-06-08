import { createSignal, For, onCleanup, Show } from "solid-js";
import { Button } from "./Button";

export type ToastTone = "info" | "success" | "warning" | "error";

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  tone?: ToastTone;
  durationMs?: number;
}

export interface ToastViewportProps {
  messages?: ToastMessage[];
  onDismiss?: (id: string) => void;
  position?: "top-right" | "bottom-right";
}

export function createToastStore() {
  const [messages, setMessages] = createSignal<ToastMessage[]>([]);
  const timers = new Map<string, number>();

  function clearTimer(id: string) {
    const timer = timers.get(id);
    if (timer) window.clearTimeout(timer);
    timers.delete(id);
  }

  function dismiss(id: string) {
    clearTimer(id);
    setMessages((current) => current.filter((message) => message.id !== id));
  }

  function show(message: Omit<ToastMessage, "id"> & { id?: string }) {
    const id = message.id ?? `toast-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const nextMessage = { ...message, id };
    clearTimer(id);
    setMessages((current) => [...current.filter((item) => item.id !== id), nextMessage]);
    const durationMs = message.durationMs ?? 4200;
    if (durationMs > 0) {
      timers.set(id, window.setTimeout(() => dismiss(id), durationMs));
    }
    return id;
  }

  onCleanup(() => {
    for (const timer of timers.values()) window.clearTimeout(timer);
    timers.clear();
  });

  return {
    messages,
    show,
    dismiss,
  };
}

export function ToastViewport(props: ToastViewportProps) {
  const messages = () => props.messages ?? [];
  return (
    <Show when={messages().length > 0}>
      <div
        role="region"
        aria-label="通知"
        style={{
          position: "fixed",
          right: "var(--sp-4)",
          top: props.position === "bottom-right" ? undefined : "var(--sp-4)",
          bottom: props.position === "bottom-right" ? "var(--sp-4)" : undefined,
          "z-index": 1100,
          display: "grid",
          gap: "var(--sp-2)",
          width: "min(360px, calc(100vw - 32px))",
        }}
      >
        <For each={messages()}>
          {(message) => (
            <div
              role="status"
              style={{
                display: "grid",
                gap: "4px",
                border: `1px solid ${toneBorder(message.tone ?? "info")}`,
                "border-radius": "var(--radius-sm)",
                background: "var(--card)",
                color: "var(--text)",
                padding: "var(--sp-3)",
                "box-shadow": "var(--shadow-2)",
              }}
            >
              <div style={{ display: "flex", "align-items": "flex-start", "justify-content": "space-between", gap: "var(--sp-2)" }}>
                <strong style={{ color: toneColor(message.tone ?? "info"), "font-size": "var(--font-section)" }}>{message.title}</strong>
                <Button iconOnly variant="ghost" ariaLabel="关闭通知" title="关闭" onClick={() => props.onDismiss?.(message.id)}>
                  ×
                </Button>
              </div>
              <Show when={message.description}>
                <div class="tq-muted">{message.description}</div>
              </Show>
            </div>
          )}
        </For>
      </div>
    </Show>
  );
}

function toneColor(tone: ToastTone): string {
  if (tone === "success") return "var(--success)";
  if (tone === "warning") return "var(--warning)";
  if (tone === "error") return "var(--error)";
  return "var(--info)";
}

function toneBorder(tone: ToastTone): string {
  return `color-mix(in srgb, ${toneColor(tone)} 34%, var(--line))`;
}
