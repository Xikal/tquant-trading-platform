import { createSignal } from "solid-js";

export interface LiveQuote {
  symbol: string;
  price?: number | null;
  change_pct?: number | null;
  updated_at?: string | null;
}

const [quotes, setQuotes] = createSignal<Record<string, LiveQuote>>({});
const [connectionState, setConnectionState] = createSignal<"idle" | "connecting" | "open" | "closed" | "error">("idle");

export const liveQuoteSignals = {
  quotes,
  connectionState,
  upsert(nextQuotes: LiveQuote[]) {
    setQuotes((current) => {
      const merged = { ...current };
      nextQuotes.forEach((quote) => {
        merged[quote.symbol] = { ...merged[quote.symbol], ...quote };
      });
      return merged;
    });
  },
  setConnectionState,
  reset() {
    setQuotes({});
    setConnectionState("idle");
  },
};
