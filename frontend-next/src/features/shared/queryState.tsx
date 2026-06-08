import type { CreateQueryResult } from "@tanstack/solid-query";
import { Match, Switch, type JSX } from "solid-js";
import { errorMessage } from "../../shared/api/errors";
import { EmptyState } from "../../shared/ui/EmptyState";
import { Panel } from "../../shared/ui/Panel";

export function QueryState<T>(props: {
  query: CreateQueryResult<T, Error>;
  children: (data: T) => JSX.Element;
  empty?: (data: T) => boolean;
  emptyText?: string;
}) {
  return (
    <Switch>
      <Match when={props.query.isPending}>
        <Panel title="数据加载中">
          <p class="tq-muted">正在加载</p>
        </Panel>
      </Match>
      <Match when={props.query.isError}>
        <Panel title="接口暂不可用" tone="danger">
          <p class="tq-muted">{errorMessage(props.query.error)}</p>
        </Panel>
      </Match>
      <Match when={props.query.data && props.empty?.(props.query.data)}>
        <EmptyState text={props.emptyText} />
      </Match>
      <Match when={props.query.data}>{(data) => props.children(data())}</Match>
    </Switch>
  );
}
