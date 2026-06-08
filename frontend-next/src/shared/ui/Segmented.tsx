import { For } from "solid-js";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  disabled?: boolean;
}

export interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label?: string;
  size?: "sm" | "md";
  class?: string;
}

export function Segmented<T extends string>(props: SegmentedProps<T>) {
  return (
    <div
      class={`tq-segmented legacy-ant-segmented${props.size === "sm" ? " tq-segmented--sm" : ""}${props.class ? ` ${props.class}` : ""}`}
      role="radiogroup"
      aria-label={props.label}
    >
      <For each={props.options}>
        {(option) => (
          <button
            type="button"
            role="radio"
            aria-checked={option.value === props.value}
            disabled={option.disabled}
            class={`tq-segmented__item legacy-ant-segmented-item${option.value === props.value ? " tq-segmented__item--active legacy-ant-segmented-item-selected" : ""}`}
            onClick={() => props.onChange(option.value)}
          >
            {option.label}
          </button>
        )}
      </For>
    </div>
  );
}
