import { createVirtualizer } from "@tanstack/solid-virtual";
import { createMemo, createSignal, For, Show, type JSX } from "solid-js";
import { EmptyState } from "./EmptyState";
import { Skeleton } from "./Skeleton";

export interface VirtualListProps<T> {
  items: T[];
  estimateSize?: number;
  maxHeight?: number;
  overscan?: number;
  gap?: number;
  ariaLabel?: string;
  loading?: boolean;
  class?: string;
  initialItemLimit?: number;
  getItemKey?: (item: T, index: number) => string | number;
  renderItem: (item: T, index: number) => JSX.Element;
  emptyText?: string;
}

export function VirtualList<T>(props: VirtualListProps<T>) {
  let scrollElement: HTMLDivElement | undefined;
  const [scrollReady, setScrollReady] = createSignal(false);
  const virtualizer = createVirtualizer<HTMLDivElement, HTMLDivElement>({
    get count() {
      return props.items.length;
    },
    getScrollElement: () => scrollElement ?? null,
    estimateSize: () => props.estimateSize ?? 112,
    getItemKey: (index) => props.getItemKey?.(props.items[index], index) ?? index,
    overscan: props.overscan ?? 6,
  });
  const rowGap = () => props.gap ?? 8;
  const estimateSize = () => props.estimateSize ?? 112;
  const initialItemLimit = () => {
    const viewportRows = Math.ceil((props.maxHeight ?? 520) / estimateSize());
    const withOverscan = viewportRows + (props.overscan ?? 6) * 2;
    const limit = props.initialItemLimit ?? Math.min(20, Math.max(1, withOverscan));
    return Math.max(1, Math.min(props.items.length, limit));
  };
  const virtualItems = createMemo(() => {
    const measuredItems = scrollReady() ? virtualizer.getVirtualItems() : [];
    if (measuredItems.length > 0) return measuredItems;
    return props.items.slice(0, initialItemLimit()).map((_, index) => ({ index, start: index * estimateSize(), key: props.getItemKey?.(props.items[index], index) ?? index }));
  });

  return (
    <Show when={!props.loading} fallback={<Skeleton rows={4} variant="card" ariaLabel={props.ariaLabel ?? "列表加载中"} />}>
      <Show when={props.items.length > 0} fallback={<EmptyState text={props.emptyText} />}>
      <div
        class={props.class}
        ref={(el) => {
          scrollElement = el;
          setScrollReady(true);
        }}
        role="list"
        aria-label={props.ariaLabel}
        style={{ "max-height": `${props.maxHeight ?? 520}px`, overflow: "auto", "min-width": 0 }}
      >
        <div style={{ height: `${scrollReady() ? virtualizer.getTotalSize() : props.items.length * estimateSize()}px`, position: "relative" }}>
          <For each={virtualItems()}>
            {(virtualItem) => (
              <div
                {...{ "data-index": virtualItem.index }}
                role="listitem"
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualItem.start}px)`,
                  padding: `0 0 ${rowGap()}px`,
                }}
              >
                {props.renderItem(props.items[virtualItem.index], virtualItem.index)}
              </div>
            )}
          </For>
        </div>
      </div>
      </Show>
    </Show>
  );
}

export function VirtualCardList<T>(props: VirtualListProps<T>) {
  return <VirtualList {...props} />;
}
