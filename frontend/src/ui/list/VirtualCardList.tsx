import type { CSSProperties, ReactNode } from "react";
import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

interface VirtualCardListProps<T> {
  className?: string;
  empty?: ReactNode;
  estimateSize?: number;
  getItemKey: (item: T, index: number) => string | number;
  height?: number;
  itemGap?: number;
  items: T[];
  maxHeight?: number;
  overscan?: number;
  renderItem: (item: T, index: number) => ReactNode;
  style?: CSSProperties;
}

const VIRTUAL_CARD_LIST_STYLE: CSSProperties = {
  display: "block",
  position: "relative",
  width: "100%",
  overflow: "auto",
};

const VIRTUAL_CARD_LIST_INNER_STYLE: CSSProperties = {
  position: "relative",
  width: "100%",
};

const VIRTUAL_CARD_LIST_ROW_STYLE: CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  width: "100%",
};

export function VirtualCardList<T>({
  className,
  empty,
  estimateSize = 112,
  getItemKey,
  height,
  itemGap = 6,
  items,
  maxHeight = 520,
  overscan = 6,
  renderItem,
  style,
}: VirtualCardListProps<T>) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: items.length,
    estimateSize: () => estimateSize,
    getItemKey: (index) => getItemKey(items[index], index),
    getScrollElement: () => parentRef.current,
    overscan,
  });

  if (!items.length) {
    return <>{empty ?? null}</>;
  }

  if (typeof window === "undefined") {
    return (
      <div className={className} style={style}>
        {items.map((item, index) => (
          <div key={getItemKey(item, index)} style={{ paddingBottom: itemGap }}>
            {renderItem(item, index)}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div
      className={className}
      ref={parentRef}
      style={{
        ...VIRTUAL_CARD_LIST_STYLE,
        height: height ?? Math.min(maxHeight, Math.max(estimateSize, items.length * estimateSize)),
        ...style,
      }}
    >
      <div style={{ ...VIRTUAL_CARD_LIST_INNER_STYLE, height: rowVirtualizer.getTotalSize() }}>
        {rowVirtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            ref={rowVirtualizer.measureElement}
            data-index={virtualItem.index}
            style={{
              ...VIRTUAL_CARD_LIST_ROW_STYLE,
              boxSizing: "border-box",
              paddingBottom: itemGap,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            {renderItem(items[virtualItem.index], virtualItem.index)}
          </div>
        ))}
      </div>
    </div>
  );
}
