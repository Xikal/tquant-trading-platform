export type BoardFilter = "include_all" | "main_only";

export function filterMainBoardItems<T extends { symbol: string }>(items: T[], boardFilter: BoardFilter): T[] {
  if (boardFilter !== "main_only") return items;
  return items.filter((item) => isMainBoardSymbol(item.symbol));
}

export function nextBoardFilter(boardFilter: BoardFilter): BoardFilter {
  return boardFilter === "main_only" ? "include_all" : "main_only";
}

function isMainBoardSymbol(symbol: string): boolean {
  const normalized = symbol.trim();
  return normalized.startsWith("60") || normalized.startsWith("00");
}
