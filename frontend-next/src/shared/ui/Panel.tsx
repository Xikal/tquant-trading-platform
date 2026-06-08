import type { JSX } from "solid-js";
import { PagePanel } from "./PagePanel";

export function Panel(props: {
  title?: JSX.Element;
  subtitle?: JSX.Element;
  actions?: JSX.Element;
  children: JSX.Element;
  class?: string;
  tone?: "default" | "danger";
  padding?: "none" | "sm" | "md";
}) {
  const padding = () => props.padding ?? "md";
  return (
    <PagePanel
      class={`panel tq-panel${props.tone === "danger" ? " tq-panel--danger" : ""}${props.class ? ` ${props.class}` : ""}`}
      headerClass="tq-panel__header tq-panel__head"
      titleClass="tq-panel__title"
      subtitleClass="tq-panel__subtitle"
      metaClass="tq-tag-row"
      bodyClass={`tq-panel__body tq-panel__body--${padding()}`}
      title={props.title}
      subtitle={props.subtitle}
      actions={props.actions}
    >
      {props.children}
    </PagePanel>
  );
}
