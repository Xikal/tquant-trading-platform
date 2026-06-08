export type PaperOrderSide = "buy" | "sell";
export type PaperOrderType = "market" | "limit";

export interface PaperOrderDraft {
  side: PaperOrderSide;
  order_type: PaperOrderType;
  symbol: string;
  name: string;
  quantity: string;
  price: string;
  strategy_key: string;
  reason: string;
}

export const defaultPaperOrderDraft: PaperOrderDraft = {
  side: "buy",
  order_type: "limit",
  symbol: "",
  name: "",
  quantity: "100",
  price: "",
  strategy_key: "",
  reason: "frontend-next paper review order",
};

export function mergePaperOrderDraft(input?: Partial<PaperOrderDraft> | null): PaperOrderDraft {
  const merged = { ...defaultPaperOrderDraft, ...definedValues(input) };
  return {
    side: merged.side === "sell" ? "sell" : "buy",
    order_type: merged.order_type === "market" ? "market" : "limit",
    symbol: normalizePaperSymbol(merged.symbol),
    name: textValue(merged.name),
    quantity: positiveText(merged.quantity, defaultPaperOrderDraft.quantity),
    price: positiveText(merged.price, defaultPaperOrderDraft.price),
    strategy_key: textValue(merged.strategy_key),
    reason: textValue(merged.reason, defaultPaperOrderDraft.reason),
  };
}

export function paperOrderDraftFromSearch(search: unknown): Partial<PaperOrderDraft> | null {
  if (readSearchValue(search, "source") !== "analysis") return null;
  const symbol = normalizePaperSymbol(readSearchValue(search, "symbol"));
  if (!symbol) return null;
  return {
    side: readSearchValue(search, "side") === "sell" ? "sell" : "buy",
    order_type: readSearchValue(search, "order_type") === "market" ? "market" : "limit",
    symbol,
    name: textValue(readSearchValue(search, "name")),
    quantity: positiveText(readSearchValue(search, "quantity"), defaultPaperOrderDraft.quantity),
    price: positiveText(readSearchValue(search, "price"), defaultPaperOrderDraft.price),
    strategy_key: textValue(readSearchValue(search, "strategy_key")),
    reason: textValue(readSearchValue(search, "reason"), "分析结果导入模拟委托"),
  };
}

export function paperOrderDraftKey(draft: Partial<PaperOrderDraft> | null): string {
  if (!draft?.symbol) return "";
  return [draft.symbol, draft.side ?? "buy", draft.quantity ?? "", draft.price ?? "", draft.strategy_key ?? "", draft.reason ?? ""].join("|");
}

export function normalizePaperSymbol(value: unknown): string {
  return textValue(value).trim().replace(/\D/g, "").slice(0, 6);
}

function definedValues(input?: Partial<PaperOrderDraft> | null): Partial<PaperOrderDraft> {
  if (!input) return {};
  return Object.fromEntries(Object.entries(input).filter(([, value]) => value !== undefined && value !== null && value !== "")) as Partial<PaperOrderDraft>;
}

function positiveText(value: unknown, fallback: string): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? String(value) : fallback;
}

function readSearchValue(search: unknown, key: string): unknown {
  return search && typeof search === "object" ? (search as Record<string, unknown>)[key] : undefined;
}

function textValue(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}
