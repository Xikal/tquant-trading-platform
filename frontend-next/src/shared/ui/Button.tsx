import { Show, type JSX } from "solid-js";

export type ButtonVariant = "default" | "primary" | "subtle" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "compact";

export interface ButtonProps {
  children?: JSX.Element;
  onClick?: (event: MouseEvent) => unknown;
  href?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  icon?: JSX.Element;
  iconOnly?: boolean;
  ariaLabel?: string;
  "aria-label"?: string;
  title?: string;
  class?: string;
  id?: string;
  form?: string;
  name?: string;
  value?: string;
  "data-testid"?: string;
}

export function Button(props: ButtonProps) {
  const variant = () => props.variant ?? "default";
  const accessibleLabel = () => props.ariaLabel ?? props["aria-label"] ?? props.title;
  const tooltip = () => props.title ?? (props.iconOnly ? accessibleLabel() : undefined);
  const className = () =>
    [
      "tq-button",
      "legacy-ant-btn",
      variant() === "primary" ? "tq-button--primary legacy-ant-btn-primary" : "",
      variant() === "danger" ? "tq-button--danger legacy-ant-btn-dangerous" : "",
      variant() === "ghost" ? "tq-button--ghost legacy-ant-btn-text" : "",
      variant() === "subtle" ? "tq-button--subtle" : "",
      props.size ? `tq-button--${props.size}` : "",
      props.iconOnly ? "tq-button--icon-only" : "",
      props.class ?? "",
    ]
      .filter(Boolean)
      .join(" ");
  const style = (): JSX.CSSProperties => ({
    ...variantStyle(variant()),
    ...sizeStyle(props.size ?? "md"),
    "gap": props.children && props.icon ? "6px" : undefined,
    "width": props.iconOnly ? "30px" : undefined,
    "padding": props.iconOnly ? "0" : sizeStyle(props.size ?? "md").padding,
  });

  if (props.href) {
    return (
      <a
        id={props.id}
        class={className()}
        href={props.disabled ? undefined : props.href}
        aria-disabled={props.disabled ? "true" : undefined}
        aria-label={accessibleLabel()}
        title={tooltip()}
        data-testid={props["data-testid"]}
        style={style()}
        onClick={(event) => {
          if (props.disabled) {
            event.preventDefault();
            return;
          }
          void props.onClick?.(event);
        }}
      >
        <Show when={props.icon}>{props.icon}</Show>
        <Show when={!props.iconOnly || !props.icon}>{props.children}</Show>
      </a>
    );
  }

  return (
    <button
      id={props.id}
      class={className()}
      type={props.type ?? "button"}
      disabled={props.disabled}
      aria-label={accessibleLabel()}
      title={tooltip()}
      form={props.form}
      name={props.name}
      value={props.value}
      data-testid={props["data-testid"]}
      style={style()}
      onClick={(event) => void props.onClick?.(event)}
    >
      <Show when={props.icon}>{props.icon}</Show>
      <Show when={!props.iconOnly || !props.icon}>{props.children}</Show>
    </button>
  );
}

function variantStyle(variant: ButtonVariant): JSX.CSSProperties {
  if (variant === "danger") {
    return {
      "border-color": "color-mix(in srgb, var(--error) 38%, var(--line))",
      "background": "var(--card)",
      "color": "var(--error)",
    };
  }
  if (variant === "subtle") {
    return {
      "background": "var(--muted-bg)",
    };
  }
  if (variant === "ghost") {
    return {
      "border-color": "transparent",
      "background": "transparent",
    };
  }
  return {};
}

function sizeStyle(size: ButtonSize): JSX.CSSProperties {
  if (size === "compact") {
    return {
      "min-height": "24px",
      "padding": "0 7px",
      "font-size": "var(--font-micro)",
    };
  }
  if (size === "sm") {
    return {
      "min-height": "28px",
      "padding": "0 8px",
    };
  }
  return {
    "min-height": "30px",
    "padding": "0 10px",
  };
}
