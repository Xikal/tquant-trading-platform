import type { StockCardView } from "../workspace-shared/workspaceTypes";

interface StableCardListMapperOptions<TItem> {
  keyOf: (item: TItem) => string;
  signatureOf: (item: TItem) => string;
  mapItem: (item: TItem) => StockCardView;
}

interface CachedCard {
  signature: string;
  card: StockCardView;
}

export function createStableCardListMapper<TItem>({
  keyOf,
  signatureOf,
  mapItem,
}: StableCardListMapperOptions<TItem>): (items: readonly TItem[]) => StockCardView[] {
  let cache = new Map<string, CachedCard>();

  return (items: readonly TItem[]) => {
    const nextCache = new Map<string, CachedCard>();
    const cards = items.map((item) => {
      const key = keyOf(item);
      const signature = signatureOf(item);
      const cached = cache.get(key);
      if (cached?.signature === signature) {
        nextCache.set(key, cached);
        return cached.card;
      }
      const next = { signature, card: mapItem(item) };
      nextCache.set(key, next);
      return next.card;
    });
    cache = nextCache;
    return cards;
  };
}

export function countChangedMonitorCardRenders(
  previous: readonly StockCardView[],
  next: readonly StockCardView[],
): number {
  const previousBySymbol = new Map(previous.map((card) => [card.symbol, card]));
  return next.reduce((count, card) => (
    previousBySymbol.get(card.symbol) === card ? count : count + 1
  ), 0);
}
