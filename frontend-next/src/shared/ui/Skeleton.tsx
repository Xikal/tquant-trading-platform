import { For, type JSX } from "solid-js";

export interface SkeletonProps {
  rows?: number;
  label?: string;
  ariaLabel?: string;
  variant?: "line" | "card" | "table";
  class?: string;
}

export function Skeleton(props: SkeletonProps) {
  const rows = () => Math.max(1, props.rows ?? 3);
  return (
    <div
      class={props.class}
      role="status"
      aria-label={props.ariaLabel ?? props.label ?? "内容加载中"}
      aria-live="polite"
      style={{
        display: "grid",
        gap: "var(--sp-2)",
      }}
    >
      <For each={Array.from({ length: rows() })}>
        {(_, index) => <span aria-hidden="true" style={skeletonStyle(props.variant ?? "line", index())} />}
      </For>
      <span style={visuallyHiddenStyle}>{props.label ?? "内容加载中"}</span>
    </div>
  );
}

function skeletonStyle(variant: SkeletonProps["variant"], index: number): JSX.CSSProperties {
  const width = variant === "table" ? `${96 - (index % 3) * 12}%` : index % 2 === 0 ? "100%" : "78%";
  return {
    display: "block",
    width,
    height: variant === "card" ? "72px" : "14px",
    "border-radius": variant === "card" ? "var(--radius-sm)" : "var(--radius-pill)",
    border: variant === "card" ? "1px solid var(--line)" : undefined,
    background: "linear-gradient(90deg, var(--bg-subtle), color-mix(in srgb, var(--bg-subtle) 70%, #ffffff), var(--bg-subtle))",
    "background-size": "200% 100%",
    animation: "none",
  };
}

const visuallyHiddenStyle: JSX.CSSProperties = {
  position: "absolute",
  width: "1px",
  height: "1px",
  padding: 0,
  margin: "-1px",
  overflow: "hidden",
  clip: "rect(0, 0, 0, 0)",
  "white-space": "nowrap",
  border: 0,
};
