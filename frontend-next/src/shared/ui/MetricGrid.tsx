import { For } from "solid-js";

export interface MetricItem {
  label: string;
  value: string | number;
  tone?: "neutral" | "up" | "down" | "warn";
}

export function MetricGrid(props: { items: MetricItem[]; class?: string }) {
  return (
    <div class={`tq-grid tq-grid--metrics tq-metric-grid${props.class ? ` ${props.class}` : ""}`}>
      <For each={props.items}>
        {(item) => (
          <div class={`tq-metric tq-stat-tile${item.tone ? ` tq-stat-tile--${item.tone}` : ""}`}>
            <div class="tq-metric__label tq-stat-tile__label">{item.label}</div>
            <div class={`tq-metric__value tq-stat-tile__value tnum${item.tone === "up" ? " price-up" : item.tone === "down" ? " price-down" : ""}`}>{item.value}</div>
          </div>
        )}
      </For>
    </div>
  );
}
