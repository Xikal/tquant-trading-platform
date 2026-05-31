import { memo, type CSSProperties } from "react";
import { useSignals } from "@preact/signals-react/runtime";
import { liveQuoteSignalsFor, type LiveQuoteField } from "../../state/realtime/liveQuoteSignals";
import { formatPct, formatPrice } from "../../features/workspace-shared/workspaceFormatters";

interface LiveCellProps {
  symbol: string;
  field: LiveQuoteField;
  fallback?: string;
  style?: CSSProperties;
}

export const LiveCell = memo(function LiveCell({
  symbol,
  field,
  fallback = "--",
  style,
}: LiveCellProps) {
  useSignals();
  const signals = liveQuoteSignalsFor(symbol);
  const value = signals[field].value;
  return <span style={style}>{formatLiveValue(field, value, fallback)}</span>;
});

function formatLiveValue(field: LiveQuoteField, value: number | string | null, fallback: string): string {
  if (field === "price") {
    return typeof value === "number" ? formatPrice(value) : fallback;
  }
  if (field === "changePct") {
    return typeof value === "number" ? formatPct(value) : fallback;
  }
  return typeof value === "string" && value ? value : fallback;
}
