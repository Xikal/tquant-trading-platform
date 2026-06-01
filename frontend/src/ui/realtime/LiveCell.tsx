import { memo } from "react";
import { useSignals } from "@preact/signals-react/runtime";
import { liveQuoteSignalsFor, type LiveQuoteField } from "../../state/realtime/liveQuoteSignals";
import { formatPct, formatPrice } from "../../features/workspace-shared/workspaceFormatters";
import { resolvePriceTone } from "../data/PriceText";

interface LiveCellProps {
  symbol: string;
  field: LiveQuoteField;
  fallback?: string;
}

export const LiveCell = memo(function LiveCell({
  symbol,
  field,
  fallback = "--",
}: LiveCellProps) {
  useSignals();
  const signals = liveQuoteSignalsFor(symbol);
  const value = signals[field].value;
  const toneClass = field === "changePct" && typeof value === "number" ? ` tq-price--${resolvePriceTone(value)}` : "";
  return <span className={`tq-live-cell${toneClass}`}>{formatLiveValue(field, value, fallback)}</span>;
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
