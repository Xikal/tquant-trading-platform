import { For } from "solid-js";
import { Segmented } from "./Segmented";

export interface TabItem<T extends string> {
  key: T;
  label: string;
  disabled?: boolean;
}

export function Tabs<T extends string>(props: { items: TabItem<T>[]; value: T; onChange: (value: T) => void; label?: string; variant?: "tabs" | "segmented" }) {
  if (props.variant === "segmented") {
    return <Segmented options={props.items.map((item) => ({ value: item.key, label: item.label, disabled: item.disabled }))} value={props.value} onChange={props.onChange} label={props.label} />;
  }
  return (
    <div class="tq-tabs legacy-ant-tabs" role="tablist" aria-label={props.label}>
      <For each={props.items}>
        {(item) => (
          <button
            class={`tq-tabs__tab legacy-ant-tabs-tab${item.key === props.value ? " tq-tabs__tab--active legacy-ant-tabs-tab-active" : ""}`}
            type="button"
            role="tab"
            aria-selected={item.key === props.value}
            disabled={item.disabled}
            onClick={() => props.onChange(item.key)}
          >
            {item.label}
          </button>
        )}
      </For>
    </div>
  );
}
