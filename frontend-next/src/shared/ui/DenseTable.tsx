import type { JSX } from "solid-js";
import { For, Show } from "solid-js";

export type DenseTableColumn<T> = {
  key: string;
  header: JSX.Element;
  class?: string;
  cell: (row: T, index: number) => JSX.Element;
};

export function DenseTable<T>(props: {
  rows: T[];
  columns: DenseTableColumn<T>[];
  class?: string;
  tableClass?: string;
  emptyText?: string;
}) {
  return (
    <div class={props.class}>
      <table class={props.tableClass}>
        <thead>
          <tr>
            <For each={props.columns}>{(column) => <th class={column.class}>{column.header}</th>}</For>
          </tr>
        </thead>
        <tbody>
          <Show when={props.rows.length} fallback={<tr><td colspan={props.columns.length}>{props.emptyText ?? "暂无数据"}</td></tr>}>
            <For each={props.rows}>
              {(row, index) => (
                <tr>
                  <For each={props.columns}>{(column) => <td class={column.class}>{column.cell(row, index())}</td>}</For>
                </tr>
              )}
            </For>
          </Show>
        </tbody>
      </table>
    </div>
  );
}
