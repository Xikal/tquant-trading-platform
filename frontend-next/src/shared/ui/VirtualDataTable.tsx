import {
  createSolidTable,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
} from "@tanstack/solid-table";
import { createMemo, createSignal, For, Show, type JSX } from "solid-js";
import { EmptyState } from "./EmptyState";
import { Skeleton } from "./Skeleton";
import { VirtualList } from "./VirtualList";

export interface VirtualDataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  emptyText?: string;
  caption?: string;
  ariaLabel?: string;
  loading?: boolean;
  compact?: boolean;
  maxHeight?: number;
  estimateSize?: number;
  overscan?: number;
  minWidth?: number | string;
  rowKey?: (row: T, index: number) => string | number;
  rowTone?: (row: T, index: number) => "neutral" | "up" | "down" | "warn" | "danger" | undefined;
  onRowClick?: (row: T, index: number) => void;
  class?: string;
  "data-testid"?: string;
}

export function VirtualDataTable<T>(props: VirtualDataTableProps<T>) {
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
  const rows = createMemo(() => table.getRowModel().rows);

  return (
    <Show when={!props.loading} fallback={<Skeleton rows={4} ariaLabel={props.ariaLabel ?? "表格加载中"} />}>
      <Show when={props.data.length > 0} fallback={<EmptyState text={props.emptyText} />}>
        <div
          class={`tq-table-wrap tq-virtual-table-wrap legacy-ant-table-wrapper${props.class ? ` ${props.class}` : ""}`}
          role="region"
          aria-label={props.ariaLabel ?? props.caption}
          data-testid={props["data-testid"]}
        >
          <Show when={props.caption}>
            <span style={visuallyHiddenStyle}>{props.caption}</span>
          </Show>
          <div class="tq-table tq-virtual-table legacy-ant-table" style={{ "min-width": cssSize(props.minWidth) }}>
            <div class="tq-virtual-table__head" role="rowgroup">
              <For each={table.getHeaderGroups()}>
                {(headerGroup) => (
                  <div class="tq-virtual-table__row tq-virtual-table__row--head" role="row" style={{ "grid-template-columns": columnTemplate(headerGroup.headers.length) }}>
                    <For each={headerGroup.headers}>
                      {(header) => {
                        const sortState = () => header.column.getIsSorted();
                        const canSort = () => header.column.getCanSort();
                        return (
                          <div role="columnheader" class="tq-virtual-table__cell tq-virtual-table__cell--head" style={{ "padding": props.compact ? "5px 7px" : undefined }}>
                            <Show when={canSort()} fallback={header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}>
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
                          </div>
                        );
                      }}
                    </For>
                  </div>
                )}
              </For>
            </div>
            <VirtualList
              items={rows()}
              ariaLabel={props.ariaLabel ?? props.caption}
              maxHeight={props.maxHeight ?? 240}
              estimateSize={props.estimateSize ?? (props.compact ? 34 : 42)}
              overscan={props.overscan ?? 4}
              gap={0}
              class="tq-virtual-table__body"
              getItemKey={(row) => props.rowKey?.(row.original, row.index) ?? row.id}
              renderItem={(row) => {
                const original = () => row.original;
                const rowIndex = () => row.index;
                const clickable = () => Boolean(props.onRowClick);
                return (
                  <div
                    class="tq-virtual-table__row tq-virtual-table__row--body"
                    role={clickable() ? "button" : "row"}
                    data-row-key={props.rowKey?.(original(), rowIndex())}
                    data-tone={props.rowTone?.(original(), rowIndex())}
                    tabIndex={clickable() ? 0 : undefined}
                    style={{ "grid-template-columns": columnTemplate(row.getVisibleCells().length) }}
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
                      {(cell) => (
                        <div class="tq-virtual-table__cell" role="cell" style={{ "padding": props.compact ? "5px 7px" : undefined }}>
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </div>
                      )}
                    </For>
                  </div>
                );
              }}
            />
          </div>
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

function columnTemplate(count: number): string {
  return `repeat(${Math.max(1, count)}, minmax(92px, 1fr))`;
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
