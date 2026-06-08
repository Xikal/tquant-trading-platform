import { createEffect, createMemo, createSignal, For, onCleanup, onMount, Show } from "solid-js";
import type { JSX } from "solid-js";
import { Button } from "./Button";
import { createDialogFocus } from "./dialogFocus";

export interface CommandPaletteOption {
  key: string;
  label: string;
  hint: string;
}

export interface CommandPaletteProps {
  open: boolean;
  getOptions: (query: string) => readonly CommandPaletteOption[];
  onClose: () => void;
  onExecute: (option: CommandPaletteOption) => void;
  placeholder?: string;
  emptyText?: string;
  footer?: JSX.Element;
}

export function CommandPalette(props: CommandPaletteProps) {
  const [query, setQuery] = createSignal("");
  let dialogRef: HTMLElement | undefined;
  let wasOpen = false;

  const options = createMemo(() => props.getOptions(query()));
  const focus = createDialogFocus({
    getContainer: () => dialogRef,
    isOpen: () => props.open,
    onClose: props.onClose,
  });

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

  onMount(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!props.open) return;
      if (event.key !== "Enter") return;
      const firstOption = options()[0];
      if (!firstOption) return;
      event.preventDefault();
      props.onExecute(firstOption);
    };
    window.addEventListener("keydown", onKeyDown);
    onCleanup(() => window.removeEventListener("keydown", onKeyDown));
  });

  return (
    <Show when={props.open}>
      <div class="tq-command-backdrop" role="presentation" onMouseDown={props.onClose}>
        <section
          ref={(element) => {
            dialogRef = element;
          }}
          class="tq-command"
          role="dialog"
          aria-modal="true"
          aria-label="全局搜索"
          tabIndex={-1}
          onMouseDown={(event) => event.stopPropagation()}
        >
          <input
            class="tq-command__input"
            value={query()}
            onInput={(event) => setQuery(event.currentTarget.value)}
            placeholder={props.placeholder ?? "搜索页面、策略或输入 6 位股票代码"}
          />
          <div class="tq-command__list">
            <For each={options()}>
              {(item) => (
                <button class="tq-command__item" type="button" onClick={() => props.onExecute(item)}>
                  <strong>{item.label}</strong>
                  <span>{item.hint}</span>
                </button>
              )}
            </For>
            <Show when={!options().length}>
              <div class="tq-command__empty">{props.emptyText ?? "没有匹配结果。输入股票代码可直接进入量化分析。"}</div>
            </Show>
          </div>
          <footer class="tq-command__footer">
            {props.footer ?? (
              <>
                <span>Enter 执行</span>
                <span>Esc 关闭</span>
                <span>Cmd/Ctrl+1~8 切换页面</span>
                <Button onClick={props.onClose}>关闭</Button>
              </>
            )}
          </footer>
        </section>
      </div>
    </Show>
  );
}
