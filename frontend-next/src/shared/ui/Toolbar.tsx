import type { JSX } from "solid-js";

export interface ToolbarProps {
  children: JSX.Element;
  label?: string;
  align?: "start" | "between" | "end";
  wrap?: boolean;
  class?: string;
}

export function Toolbar(props: ToolbarProps) {
  return (
    <div
      class={props.class}
      role="toolbar"
      aria-label={props.label}
      style={{
        display: "flex",
        "align-items": "center",
        "justify-content": props.align === "end" ? "flex-end" : props.align === "between" ? "space-between" : "flex-start",
        gap: "var(--sp-2)",
        "flex-wrap": props.wrap === false ? "nowrap" : "wrap",
        "min-width": 0,
      }}
    >
      {props.children}
    </div>
  );
}
