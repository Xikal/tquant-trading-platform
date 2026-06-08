import type { JSX } from "solid-js";

export function StatusBadge(props: { children: JSX.Element; class?: string; tone?: string }) {
  return <span class={props.class ?? `tq-status-badge${props.tone ? ` tq-status-badge--${props.tone}` : ""}`}>{props.children}</span>;
}
