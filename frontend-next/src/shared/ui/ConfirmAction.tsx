import { createSignal, Show, type JSX } from "solid-js";
import { Button, type ButtonVariant } from "./Button";
import { Modal } from "./Modal";

export interface ConfirmActionProps {
  label: JSX.Element;
  title: JSX.Element;
  description?: JSX.Element;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: ButtonVariant;
  confirmVariant?: ButtonVariant;
  disabled?: boolean;
  requireText?: string;
  onConfirm: () => void | Promise<void>;
  children?: JSX.Element;
}

export function ConfirmAction(props: ConfirmActionProps) {
  const [open, setOpen] = createSignal(false);
  const [input, setInput] = createSignal("");
  const [pending, setPending] = createSignal(false);
  const canConfirm = () => !props.requireText || input() === props.requireText;

  async function handleConfirm() {
    if (!canConfirm()) return;
    setPending(true);
    try {
      await props.onConfirm();
      setOpen(false);
      setInput("");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <Button
        variant={props.variant}
        disabled={props.disabled}
        onClick={() => {
          setOpen(true);
        }}
      >
        {props.label}
      </Button>
      <Modal
        open={open()}
        title={props.title}
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button
              onClick={() => {
                setOpen(false);
              }}
              disabled={pending()}
            >
              {props.cancelLabel ?? "取消"}
            </Button>
            <Button variant={props.confirmVariant ?? "danger"} onClick={handleConfirm} disabled={pending() || !canConfirm()}>
              {pending() ? "处理中" : props.confirmLabel ?? "确认"}
            </Button>
          </>
        }
      >
        <div style={{ display: "grid", gap: "var(--sp-3)" }}>
          <Show when={props.description}>
            <p class="tq-muted" style={{ margin: 0 }}>
              {props.description}
            </p>
          </Show>
          {props.children}
          <Show when={props.requireText}>
            {(requiredText) => (
              <label class="tq-field">
                <span>输入 {requiredText()} 确认</span>
                <input class="tq-input" value={input()} onInput={(event) => setInput(event.currentTarget.value)} />
              </label>
            )}
          </Show>
        </div>
      </Modal>
    </>
  );
}
