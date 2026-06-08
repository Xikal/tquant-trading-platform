import type { JSX } from "solid-js";

export function Tag(props: { children: JSX.Element; tone?: "neutral" | "up" | "down" | "warn"; title?: string; "aria-label"?: string }) {
  return (
    <span class={`tq-tag${props.tone && props.tone !== "neutral" ? ` tq-tag--${props.tone}` : ""}`} title={props.title} aria-label={props["aria-label"]}>
      {props.children}
    </span>
  );
}
