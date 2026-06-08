import type { JSX } from "solid-js";
import { Show } from "solid-js";
import { Icon } from "./Icon";

export function PagePanel(props: {
  title?: JSX.Element;
  subtitle?: JSX.Element;
  icon?: string;
  badge?: JSX.Element;
  actions?: JSX.Element;
  children: JSX.Element;
  class?: string;
  headerClass?: string;
  titleClass?: string;
  subtitleClass?: string;
  bodyClass?: string;
  iconClass?: string;
  metaClass?: string;
}) {
  return (
    <section class={props.class}>
      <Show when={props.title || props.subtitle || props.badge || props.actions}>
        <header class={props.headerClass}>
          <div>
            <Show when={props.icon}>
              {(name) => <Icon name={name()} class={props.iconClass} />}
            </Show>
            <Show when={props.title}>
              <h2 class={props.titleClass}>{props.title}</h2>
            </Show>
            <Show when={props.subtitle}>
              <div class={props.subtitleClass}>{props.subtitle}</div>
            </Show>
          </div>
          <Show when={props.badge || props.actions}>
            <div class={props.metaClass}>
              {props.badge}
              {props.actions}
            </div>
          </Show>
        </header>
      </Show>
      <div class={props.bodyClass}>{props.children}</div>
    </section>
  );
}
