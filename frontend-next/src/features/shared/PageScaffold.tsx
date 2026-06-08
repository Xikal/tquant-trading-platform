import type { JSX } from "solid-js";
import { Show } from "solid-js";
import { nextRouteByPage, type NextPage } from "../../shared/config/routes";

export function PageScaffold(props: {
  page: NextPage;
  description?: string;
  children: JSX.Element;
  actions?: JSX.Element;
  class?: string;
  intro?: boolean;
}) {
  const route = () => nextRouteByPage[props.page];
  return (
    <section class={`tq-page${props.class ? ` ${props.class}` : ""}`} data-page={props.page}>
      <Show when={props.intro === true && (props.description || props.actions)}>
        <div class="panel tq-panel tq-page__full">
          <div class="tq-panel__header tq-panel__head">
            <div>
              <h2 class="tq-panel__title" style={{ margin: 0 }}>{route().label}</h2>
              <Show when={props.description}>
                <div class="tq-panel__subtitle">{props.description}</div>
              </Show>
            </div>
            <div class="tq-tag-row">
              {props.actions}
            </div>
          </div>
        </div>
      </Show>
      {props.children}
    </section>
  );
}
