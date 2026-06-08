import {
  createSolidTable,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
} from "@tanstack/solid-table";
import { createSignal, For, Show, type JSX } from "solid-js";
import { EmptyState } from "./EmptyState";
import { Skeleton } from "./Skeleton";

export interface DataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  emptyText?: string;
  caption?: string;
  ariaLabel?: string;
  loading?: boolean;
  compact?: boolean;
  stickyHeader?: boolean;
  minWidth?: number | string;
  rowKey?: (row: T, index: number) => string | number;
  rowTone?: (row: T, index: number) => "neutral" | "up" | "down" | "warn" | "danger" | undefined;
  onRowClick?: (row: T, index: number) => void;
  class?: string;
  "data-testid"?: string;
}

export function DataTable<T>(props: DataTableProps<T>) {
  const [sorting, setSorting] = createSignal<SortingState>([]);
  const table = createSolidTable<T>({
    get data() {
      return props.data;
    },
    get columns() {
      return props.columns;
    },
    state: {
      get sorting() {
        return sorting();
      },
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <Show when={!props.loading} fallback={<Skeleton rows={4} ariaLabel={props.ariaLabel ?? "表格加载中"} />}>
      <Show when={props.data.length > 0} fallback={<EmptyState text={props.emptyText} />}>
        <div
          class={`tq-table-wrap legacy-ant-table-wrapper${props.class ? ` ${props.class}` : ""}`}
          role="region"
          aria-label={props.ariaLabel ?? props.caption}
          data-testid={props["data-testid"]}
        >
          <table class="tq-table legacy-ant-table" style={{ "min-width": cssSize(props.minWidth) }}>
            <Show when={props.caption}>
              <caption style={visuallyHiddenStyle}>{props.caption}</caption>
            </Show>
            <thead>
              <For each={table.getHeaderGroups()}>
                {(headerGroup) => (
                  <tr>
                    <For each={headerGroup.headers}>
                      {(header) => {
                        const sortState = () => header.column.getIsSorted();
                        const canSort = () => header.column.getCanSort();
                        return (
                          <th
                            scope="col"
                            aria-sort={sortState() === "asc" ? "ascending" : sortState() === "desc" ? "descending" : undefined}
                            class={props.stickyHeader === false ? "tq-table__cell--unstuck" : undefined}
                            style={{ "padding": props.compact ? "5px 7px" : undefined }}
                          >
                            <Show
                              when={canSort()}
                              fallback={header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                            >
                              <button
                                type="button"
                                class="tq-table__sort"
                                aria-label={`按${headerLabel(header.column.columnDef.header)}排序`}
                                onClick={header.column.getToggleSortingHandler()}
                              >
                                <span>{header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}</span>
                                <span aria-hidden="true">{sortState() === "asc" ? "▲" : sortState() === "desc" ? "▼" : "↕"}</span>
                              </button>
                            </Show>
                          </th>
                        );
                      }}
                    </For>
                  </tr>
                )}
              </For>
            </thead>
            <tbody>
              <For each={table.getRowModel().rows}>
                {(row) => {
                  const rowIndex = () => row.index;
                  const original = () => row.original;
                  const clickable = () => Boolean(props.onRowClick);
                  return (
                    <tr
                      data-row-key={props.rowKey?.(original(), rowIndex())}
                      data-tone={props.rowTone?.(original(), rowIndex())}
                      tabIndex={clickable() ? 0 : undefined}
                      role={clickable() ? "button" : undefined}
                      onClick={() => props.onRowClick?.(original(), rowIndex())}
                      onKeyDown={(event) => {
                        if (!clickable()) return;
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          props.onRowClick?.(original(), rowIndex());
                        }
                      }}
                    >
                      <For each={row.getVisibleCells()}>
                        {(cell) => <td style={{ "padding": props.compact ? "5px 7px" : undefined }}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>}
                      </For>
                    </tr>
                  );
                }}
              </For>
            </tbody>
          </table>
        </div>
      </Show>
    </Show>
  );
}

function cssSize(value: number | string | undefined): string | undefined {
  if (typeof value === "number") return `${value}px`;
  return value;
}

function headerLabel<T>(header: ColumnDef<T>["header"]): string {
  if (typeof header === "string") return header;
  return "该列";
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
